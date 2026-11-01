#!/usr/bin/env python3
"""Sudhaar (सुधार, "fix"): find Sarvam API calls that will break, prove it against the live API, fix them.

    python3 sudhaar.py <path>                 # scan and report (path, or github:owner/repo, or a GitHub URL)
    python3 sudhaar.py <path> --verify        # also prove each error live (needs SARVAM_API_KEY)
    python3 sudhaar.py <path> --fix           # rewrite the files and show the diff
    python3 sudhaar.py <path> --explain hi-IN # Sarvam-105B explains the report, Bulbul reads it aloud
    python3 sudhaar.py --learn                # Sarvam-105B reads Sarvam's changelog, live API confirms new rules
    python3 sudhaar.py --refresh-rules        # regenerate rules.json from the installed sarvamai SDK

Stdlib only. Exit code 1 when any error is found, so it can gate CI.
"""
import argparse
import base64
import difflib
import io
import json
import os
import re
import tarfile
import sys
import tempfile
import typing
import urllib.error
import urllib.request
import uuid
import wave
from pathlib import Path

HERE = Path(__file__).parent
RULES_FILE = HERE / "rules.json"
LEARNED_FILE = HERE / "rules_learned.json"
CHANGELOG = "https://docs.sarvam.ai/changelog/llms.txt"
API = "https://api.sarvam.ai"

# Checked against the live API on 2026-11-01 (errors = the API returns 400 today).
# Everything enumerable (model ids, speakers, language codes) comes from rules.json instead.
DEPRECATED = {
    # model: (replacement, severity, why)
    "sarvam-m": ("sarvam-105b", "error", "deprecated, the Chat API rejects it"),
    "sarvam-30b": ("sarvam-105b", "error", "deprecated, the Chat API rejects it"),
    "sarvam-30b-16k": ("sarvam-105b", "error", "retired fixed-context variant"),
    "sarvam-105b-32k": ("sarvam-105b", "error", "retired fixed-context variant"),
    "saarika:v1": ("saaras:v3", "error", "deprecated, speech-to-text rejects it"),
    "saarika:v2": ("saaras:v3", "error", "deprecated, speech-to-text rejects it"),
    "saarika:flash": ("saaras:v3", "error", "deprecated, speech-to-text rejects it"),
    "saarika:v2.5": ("saaras:v3", "warning", "dropped from the SDK, the API still accepts it for now"),
    "saaras:v1": ("saaras:v3", "error", "old Saaras version, speech-to-text rejects it"),
    "saaras:v2": ("saaras:v3", "error", "old Saaras version, speech-to-text rejects it"),
    "saaras:v2.5": ("saaras:v3", "warning", "being removed, use saaras:v3 with mode='translate'"),
    "saaras:v4-realtime": ("saaras:v4", "error", "not a real id, streaming takes saaras:v4 or saaras:v3-realtime"),
    "bulbul:v1": ("bulbul:v3", "error", "removed, text-to-speech rejects it"),
    "bulbul:v2": ("bulbul:v3", "error", "deprecated, text-to-speech rejects it"),
}
EXTRA_STT_MODELS = {"saaras:v3-realtime", "saaras:v2.5", "saarika:v2.5"}  # accepted by the live API, not in the SDK enum
EXTRA_TTS_MODELS = {"bulbul:v3-beta"}  # accepted by the live API, not in the SDK enum
DEFAULT_TTS = "bulbul:v3"  # what the API uses when `model` is omitted
PACE = {"bulbul:v2": (0.3, 3.0), "bulbul:v3": (0.5, 2.0), "bulbul:v4-flash": (0.5, 2.0)}
V2_ONLY = {"pitch", "loudness"}
V2_SPEAKERS = {"anushka", "abhilash", "manisha", "vidya", "arya", "karun", "hitesh"}
V3_SPEAKERS = set(
    "shubh aditya ritu priya neha rahul pooja rohan simran kavya amit dev ishita shreya ratan varun manan "
    "sumit roopa kabir aayan ashutosh advait anand tanya tarun sunny mani gokul vijay shruti suhani mohit "
    "kavitha rehan soham rupali".split()
)
V4_DEFAULT_SPEAKER = "shubh_enhi_ads"
# Bulbul v1 voices: every current model rejects them (all 12 returned 400 live on 2026-11-01).
# AI assistants still write `meera` from stale memory, so these are flagged even without a model nearby.
RETIRED_VOICES = {"meera", "arvind", "amol", "maitreyi", "pavithra", "amartya", "diya", "neel", "misha", "vian", "arjun", "maya"}
TTS_FIELD_RENAMES = {"voice": "speaker", "voice_id": "speaker", "language": "target_language_code", "lang": "target_language_code", "sample_rate": "speech_sample_rate"}
TTS_CONTEXT = re.compile(r"bulbul|text.to.speech|tts", re.I)
API_USE = re.compile(r"api\.sarvam\.ai|sarvamai|SarvamAI")
SAMPLE_RATES = {8000, 16000, 22050, 24000, 32000, 44100, 48000}

KEYS = (
    r"[A-Za-z_]*(?:MODEL|[Mm]odel)(?:_?(?:NAME|ID|[Nn]ame|[Ii]d))?|"  # model, TTS_MODEL, ttsModel, model_name
    "speaker|voice_id|voice|pace|pitch|loudness|speech_sample_rate|sample_rate|output_audio_codec|language|lang|"
    "target_language_code|source_language_code|language_code"
)
MODEL_KEY = re.compile(r"[a-z_]*model(_?(name|id))?", re.I)
# `key = v`, `key: v`, and typed Python defaults `key: str = v`
PAIR = re.compile(r"""["']?\b(%s)\b["']?\s*(?::\s*[A-Za-z_][\w\[\], .|]*?\s*=|[:=])\s*(?:["']([^"'\n]+)["']|(-?\d+(?:\.\d+)?))""" % KEYS)
MARKER = re.compile(r"sarvam|bulbul|saaras|saarika|mayura", re.I)
EXTS = {".py", ".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx", ".json", ".ipynb"}
SKIP_DIRS = {"node_modules", ".git", "venv", ".venv", "__pycache__", "dist", "build"}
WINDOW = 12  # ponytail: params bind to the nearest model literal within 12 lines; an AST pass if this misfires
TTS_KEYS = {"speaker", "pace", "pitch", "loudness", "speech_sample_rate", "output_audio_codec"}
DELETE = "__delete_line__"
VOICE_ID = re.compile(r"[A-Z]?[a-z]+(_[a-z]+)*")  # shubh, Anushka, simran_hi_news; not "IVR" or "Dr. Sharma"


def load_rules():
    return json.loads(RULES_FILE.read_text())


def family(model):
    if model.startswith("bulbul"):
        return "tts"
    if model.startswith(("saaras", "saarika")):
        return "stt-stream" if "realtime" in model else "stt"
    if model.startswith(("mayura", "sarvam-translate")):
        return "translate"
    if model.startswith("sarvam-"):  # includes ids AI assistants invent, like sarvam-tts or sarvam-stt
        if re.search(r"tts|text-to-speech|speech-synth", model):
            return "tts"
        if re.search(r"stt|speech-to-text|asr|transcri", model):
            return "stt"
        if "translat" in model:
            return "translate"
        return "chat"
    return None


# ---------- scan ----------

def iter_files(root):
    root = Path(root)
    if root.is_file():
        yield root
        return
    for p in sorted(root.rglob("*")):
        if p.suffix in EXTS and p.is_file() and not SKIP_DIRS & set(p.parts) and p.name != RULES_FILE.name:
            yield p


def hits_in(text):
    for ln, line in enumerate(text.splitlines(), 1):
        for m in PAIR.finditer(line):
            is_str = m.group(2) is not None
            g = 2 if is_str else 3
            key = "model" if MODEL_KEY.fullmatch(m.group(1)) else m.group(1)
            yield {"line": ln, "start": m.start(g), "end": m.end(g), "kstart": m.start(1), "kend": m.end(1), "quoted": m.group(0)[0] in "\"'", "key": key,
                   "value": m.group(g), "num": not is_str}


def read_code(path):
    """Notebooks are scanned as their code cells joined together (line numbers then count within that code)."""
    text = path.read_text(errors="ignore")
    if path.suffix != ".ipynb":
        return text
    try:
        cells = json.loads(text).get("cells", [])
    except ValueError:
        return ""
    return "\n".join("".join(c.get("source", [])) for c in cells if c.get("cell_type") == "code")


def nearest(hits, line, pred):
    best = None
    for h in hits:
        if pred(h) and abs(h["line"] - line) <= WINDOW and (best is None or abs(h["line"] - line) < abs(best["line"] - line)):
            best = h
    return best


def remap_speaker(name, model, lang):
    base = name.split("_")[0].lower()
    if model == "bulbul:v4-flash":
        tag = (lang or "hi-IN")[:2]
        opts = [s for s in RULES["v4_speakers"] if s.startswith(base + "_")]
        return next((s for s in opts if f"_{tag}_" in s), opts[0] if opts else V4_DEFAULT_SPEAKER)
    if model == "bulbul:v3":
        return base if base in V3_SPEAKERS else "shubh"
    return "shubh"  # v2 itself is rejected now, so suggest the v3 default


def check_file(path):
    text = read_code(path)
    if not MARKER.search(text):
        return []
    tts_context, api_use = bool(TTS_CONTEXT.search(text)), bool(API_USE.search(text))
    hits = list(hits_in(text))
    models = [h for h in hits if h["key"] == "model" and not h["num"] and family(h["value"])]
    issues = []

    def add(h, sev, msg, fix, model=None, fam=None, lang=None):
        issues.append({**h, "file": str(path), "severity": sev, "msg": msg, "fix": fix,
                       "model": model, "family": fam, "lang": lang})

    for h in hits:
        k, v = h["key"], h["value"]
        near_tts = nearest(models, h["line"], lambda m: family(m["value"]) == "tts")
        near_any = nearest(models, h["line"], lambda m: True)
        tts = near_tts["value"] if near_tts else DEFAULT_TTS
        fam = family(near_any["value"]) if near_any else None
        lang_hit = nearest(hits, h["line"], lambda x: x["key"].endswith("language_code") and not x["num"])
        lang = lang_hit["value"] if lang_hit else None
        if k in TTS_FIELD_RENAMES:
            if near_tts and api_use and h["quoted"]:  # only request-body keys like "voice": …, never a variable named voice
                right = TTS_FIELD_RENAMES[k]
                add(h, "error", f"text-to-speech has no `{k}` field, it's `{right}` (the value is ignored or rejected)", right, tts, "tts", lang)
                issues[-1]["span"] = "key"
                if right == "speaker" and v.lower() in RETIRED_VOICES:
                    live = tts if tts in ("bulbul:v3", "bulbul:v4-flash") else DEFAULT_TTS
                    add(h, "error", f"voice `{v}` was retired, every current Bulbul model rejects it", remap_speaker(v, live, lang), tts, "tts", lang)
            continue
        if k == "speaker" and not h["num"] and v.lower() in RETIRED_VOICES and tts_context:
            live = tts if tts in ("bulbul:v3", "bulbul:v4-flash") else DEFAULT_TTS
            add(h, "error", f"voice `{v}` was retired, every current Bulbul model rejects it", remap_speaker(v, live, lang), tts, "tts", lang)
            continue
        # Voice params only count next to a literal Bulbul model: elsewhere the model may live in a variable,
        # and `speaker` is often a UI label ("IVR", "Dr. Sharma"). False positives kill trust, so stay quiet.
        if k in TTS_KEYS and (not near_tts or (k == "speaker" and not VOICE_ID.fullmatch(v))):
            continue

        if k == "model" and not h["num"]:
            f = family(v)
            if v in DEPRECATED:
                new, sev, why = DEPRECATED[v]
                add(h, sev, f"`{v}`: {why}", new, v, f)
            elif f == "tts" and v not in RULES["tts_models"] and v not in EXTRA_TTS_MODELS:
                add(h, "error", f"`{v}` is not a TTS model the API accepts", "bulbul:v3", v, f)
            elif f in ("stt", "stt-stream") and v not in RULES["stt_models"] and v not in EXTRA_STT_MODELS:
                add(h, "error", f"`{v}` is not a speech-to-text model the API accepts", "saaras:v3", v, f)
            elif f == "chat" and v not in RULES["chat_models"]:
                if api_use:  # the file talks to Sarvam's API, so an unknown id is a guaranteed 400
                    add(h, "error", f"`{v}` is not a chat model the API accepts", "sarvam-105b", v, f)
                else:
                    add(h, "warning", f"`{v}` is not on Sarvam's chat API (fine if you run the open model locally)", "sarvam-105b", v, f)
            elif v == "bulbul:v3" and not any(i["severity"] == "info" for i in issues):
                add(h, "info", "bulbul:v3 reaches end of life on Sarvam Voice Agents on 10 Nov 2026 (REST TTS keeps it), plan a move to bulbul:v4-flash", None, v, f)

        elif k == "speaker" and not h["num"]:
            ok = {"bulbul:v4-flash": set(RULES["v4_speakers"]), "bulbul:v3": V3_SPEAKERS, "bulbul:v2": V2_SPEAKERS}.get(tts)
            if ok is not None and v.lower() not in ok:
                new = remap_speaker(v, tts, lang)
                add(h, "error", f"speaker `{v}` is not valid on {tts}", new, tts, "tts", lang)

        elif k == "pace" and h["num"]:
            lo, hi = PACE.get(tts, (0.5, 2.0))
            if not lo <= float(v) <= hi:
                add(h, "error", f"pace {v} is outside {lo}-{hi} for {tts}", str(min(max(float(v), lo), hi)), tts, "tts", lang)

        elif k in V2_ONLY and h["num"] and tts != "bulbul:v2":
            add(h, "warning", f"`{k}` is a bulbul:v2-only setting, the docs say it has no effect on {tts}", DELETE, tts, "tts", lang)

        elif k == "speech_sample_rate" and h["num"] and int(float(v)) not in SAMPLE_RATES:
            add(h, "error", f"sample rate {v} is not accepted", "22050", tts, "tts", lang)

        elif k == "output_audio_codec" and v == "opus":
            add(h, "warning", "`opus` fails unless speech_sample_rate is 8000/12000/16000/24000/48000 (default 22050 → 400)", "mp3", tts, "tts", lang)

        elif k.endswith("language_code") and not h["num"]:
            if v == "or-IN" and fam in ("tts", "stt", "translate"):
                add(h, "error", f"Odia is `od-IN` on {fam}, `or-IN` is rejected", "od-IN", near_any["value"], fam, v)
            elif v == "od-IN" and fam == "stt-stream":
                add(h, "error", "streaming STT spells Odia `or-IN`", "or-IN", near_any["value"], fam, v)
            elif fam == "tts" and k == "target_language_code" and v not in RULES["tts_languages"]:
                add(h, "error", f"`{v}` is not a TTS language code", None, tts, "tts", v)
    return issues


def scan(root):
    return [i for p in iter_files(root) for i in check_file(p)]


# ---------- live verification ----------

def http(path, payload=None, files=None, timeout=60):
    key = os.environ.get("SARVAM_API_KEY")
    headers = {"api-subscription-key": key}
    if files:
        boundary = uuid.uuid4().hex
        body = b""
        for name, val in payload.items():
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{val}\r\n'.encode()
        for name, (fname, data) in files.items():
            body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{fname}"\r\n'
                     f"Content-Type: audio/wav\r\n\r\n").encode() + data + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    else:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="ignore")
        try:
            err = json.loads(raw).get("error", raw)
            raw = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        except ValueError:
            pass
        return e.code, raw[:160]
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, str(getattr(e, "reason", e))


def silence_wav(seconds=1.0, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


def probe(issue, value):
    """Send the smallest request that exercises `issue` with `value` (DELETE drops the param)."""
    k, fam, model = issue["key"], issue["family"], issue["model"]
    if k == "model":
        model = value
    if fam == "chat":
        return http("/v1/chat/completions", {"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5})
    if fam == "stt":
        return http("/speech-to-text", {"model": model, "language_code": issue["lang"] or "unknown"},
                    files={"file": ("probe.wav", silence_wav())})
    if fam == "translate":
        return http("/translate", {"input": "hello", "source_language_code": "en-IN",
                                   "target_language_code": value if k.endswith("language_code") else "hi-IN", "model": model})
    if fam == "tts":
        body = {"text": "नमस्ते", "target_language_code": issue["lang"] or "hi-IN", "model": model}
        if k != "model" and value != DELETE:
            body[k] = float(value) if issue["num"] else value
        if k.endswith("language_code"):
            body["target_language_code"] = value
        return http("/text-to-speech", body)
    return None


def prove_calls(path):
    """Live-test every Sarvam call in a file as written (model + its nearby voice, pace and language)."""
    hits = list(hits_in(read_code(path)))
    out, seen = [], set()
    for m in [h for h in hits if h["key"] == "model" and not h["num"] and family(h["value"])]:
        fam = family(m["value"])
        if fam == "stt-stream":
            continue  # streaming is WebSocket only, nothing to probe over REST
        near = lambda key: nearest(hits, m["line"], lambda x: x["key"] == key)
        if fam == "tts":
            lang = near("target_language_code") or near("language_code")
            body = {"text": "नमस्ते", "target_language_code": lang["value"] if lang else "hi-IN", "model": m["value"]}
            for key in ("speaker", "pace"):
                n = near(key)
                if n:
                    body[key] = float(n["value"]) if n["num"] else n["value"]
            call = m["value"] + (f" + {body['speaker']}" if "speaker" in body else "")
            if call in seen:
                continue
            seen.add(call)
            status, res = http("/text-to-speech", body)
        else:
            call = m["value"]
            if call in seen:
                continue
            seen.add(call)
            status, res = probe({"key": "model", "family": fam, "model": call, "lang": None, "num": False}, call)
        out.append({"line": m["line"], "call": call, "status": status, "msg": "" if status == 200 else str(res)[:140]})
    return out


def verify(issues):
    for i in issues:
        if i["severity"] != "error" or i["fix"] is None or i["family"] == "stt-stream":
            continue
        before = probe(i, i["value"])
        after = probe(i, i["fix"])
        if before:
            i["live"] = {"before": before[0], "before_msg": before[1] if before[0] != 200 else "",
                         "after": after[0] if after else None}


# ---------- fix ----------

def apply_fixes(issues):
    by_file = {}
    for i in issues:
        if i["fix"] is not None and i["severity"] != "info" and not i["file"].endswith(".ipynb"):  # notebook lines are cell-joined, so report only
            by_file.setdefault(i["file"], []).append(i)
    for path, items in by_file.items():
        p = Path(path)
        old = p.read_text()
        lines = old.splitlines(keepends=True)
        for i in sorted(items, key=lambda i: (i["line"], i["kstart"] if i.get("span") == "key" else i["start"]), reverse=True):
            idx = i["line"] - 1
            if i["fix"] == DELETE:
                lines[idx] = ""
            elif i.get("span") == "key":
                ln = lines[idx]
                lines[idx] = ln[:i["kstart"]] + i["fix"] + ln[i["kend"]:]
            else:
                ln = lines[idx]
                lines[idx] = ln[:i["start"]] + i["fix"] + ln[i["end"]:]
        new = "".join(lines)
        p.write_text(new)
        sys.stdout.writelines(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{p.name}", f"b/{p.name}"))


# ---------- Sarvam-105B helpers ----------

def ask_105b(prompt, max_tokens=4000, effort="none"):
    """One chat call; returns the text with any <think> block removed. Retries once on empty output.
    /v2 accepts reasoning_effort "none": on /v1 the model spent 2000 reasoning tokens on "say namaste"."""
    for _ in range(2):
        status, res = http("/v2/chat/completions", {"model": "sarvam-105b", "max_tokens": max_tokens, "reasoning_effort": effort,
                                                    "messages": [{"role": "user", "content": prompt}]}, timeout=180)
        if status != 200:
            sys.exit(f"Sarvam-105B call failed ({status}): {res}")
        text = re.sub(r"<think>.*?</think>", "", res["choices"][0]["message"].get("content") or "", flags=re.S).strip()
        if text:  # reasoning can eat the whole token budget, so retry once
            return text
    sys.exit("Sarvam-105B returned no text twice, try again")


# ---------- learn (Sarvam-105B reads the changelog, live API confirms) ----------

BREAKING = re.compile(r"deprecat|no longer|removed|retire|end of life|sunset|replaced by|migrate|renamed|not accepted|rejects", re.I)


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "sudhaar"}), timeout=30) as r:
        return r.read().decode(errors="ignore")


def changelog_text(limit=80):
    """Breaking-change paragraphs from the newest `limit` changelog pages, each tagged with its date."""
    urls = re.findall(r"https://docs\.sarvam\.ai/changelog/\d{4}/\d+/\d+\.md", fetch(CHANGELOG))[:limit]
    out = []
    for u in urls:
        date = "-".join(u.rsplit("/changelog/", 1)[1][:-3].split("/"))
        body = "\n".join(l for l in fetch(u).splitlines() if not l.startswith(">"))
        out += [f"[{date}] {p.strip()}" for p in body.split("\n\n") if BREAKING.search(p)]
    return "\n\n".join(out)


def learn():
    text = changelog_text()
    if not text:
        sys.exit("No breaking-change entries found in the changelog")
    prompt = ("Below are entries from Sarvam AI's API changelog. Extract every change where an API model id stops "
              "working or is replaced. Reply with ONLY a JSON array, no prose, each item: "
              '{"old": "<old model id>", "new": "<replacement model id>", "evidence": "<short quote>", "date": "<date>"}. '
              "Use exact model ids as written (like bulbul:v2, saaras:v2.5, sarvam-m). Empty array if none.\n\n" + text[:30000])
    raw = ask_105b(prompt, 4000)
    try:
        candidates = json.loads(raw[raw.index("["): raw.rindex("]") + 1])
    except ValueError:
        sys.exit(f"Sarvam-105B did not return JSON:\n{raw[:500]}")

    learned = json.loads(LEARNED_FILE.read_text()) if LEARNED_FILE.exists() else {}
    unique = list({(str(c.get("old", "")), str(c.get("new", ""))): c for c in candidates}.items())
    probeable = [(k, c) for k, c in unique if family(k[0]) not in (None, "stt-stream") and family(k[1]) == family(k[0])]
    print(f"Sarvam-105B proposed {len(unique)} rules from the changelog; {len(probeable)} are model swaps we can test.\n"
          "Confirming each against the live API (the model proposes, the API decides):\n")
    done = set()
    for (old, new), c in probeable:
        if old in done:
            continue
        done.add(old)
        fam = family(old)
        probe_issue = {"key": "model", "family": fam, "model": old, "lang": None, "num": False}
        before, after = probe(probe_issue, old), probe(probe_issue, new)
        if before[0] != 200 and after[0] != 200:
            # The model guessed a dead replacement; the API's own 400 usually names the right one.
            named = [m for m in re.findall(r"[a-z]+[-:][\w.:-]*\w", str(before[1])) if family(m) == fam and m not in (old, new)]
            if named:
                print(f"  ↻ {old} → {new} failed too; the API's error names {named[0]}, trying that")
                new, after = named[0], probe(probe_issue, named[0])
        if before[0] != 200 and after[0] == 200:
            learned[old] = [new, "error", f"rejected by the live API (learned from changelog {c.get('date', '')})"]
            print(f"  ✓ {old} → {new}   live: {before[0]} → 200   \"{str(c.get('evidence', ''))[:80]}\"")
        elif before[0] == 200 and after[0] == 200:
            learned.setdefault(old, [new, "warning", f"deprecated in changelog {c.get('date', '')}, still accepted today"])
            print(f"  ! {old} → {new}   still accepted (200), kept as a warning")
        elif before[0] == 200:
            print(f"  ✗ {old} → {new}   {old} still works and {new} is rejected ({after[0]}), not learned")
        else:
            print(f"  ✗ {old} → {new}   replacement also failed ({after[0]}), not learned")
    LEARNED_FILE.write_text(json.dumps(learned, indent=1) + "\n")
    print(f"\n{len(learned)} learned rules saved to {LEARNED_FILE.name}; the scanner uses them from now on.")


# ---------- explain (Sarvam-105B + Bulbul) ----------

LANG_NAMES = {"hi-IN": "Hindi", "mr-IN": "Marathi", "bn-IN": "Bengali", "ta-IN": "Tamil", "te-IN": "Telugu",
              "kn-IN": "Kannada", "ml-IN": "Malayalam", "gu-IN": "Gujarati", "pa-IN": "Punjabi", "od-IN": "Odia", "en-IN": "English"}


def explain(issues, lang, out):
    errors = [i for i in issues if i["severity"] == "error"]
    summary = "\n".join(f"- {i['msg']}" for i in errors)
    name = LANG_NAMES.get(lang, lang)  # a bare code like hi-IN got a Marathi answer in testing
    prompt = (f"Reply ONLY in {name}, written in its own script. You are reviewing a developer's code that calls "
              f"Sarvam AI's APIs. In under 45 words of plain spoken {name}, no markdown, no lists, no code formatting, "
              f"tell them there are {len(errors)} calls that will fail and which to fix first.\n{summary}")
    text = ask_105b(prompt, 2000).replace("`", "")  # backticks would be read aloud by Bulbul
    print(f"\n🗣  {text}\n")
    status, res = http("/text-to-speech", {"text": text[:2500], "target_language_code": lang, "model": "bulbul:v3", "speaker": "shubh"})
    if status != 200:
        sys.exit(f"Bulbul call failed ({status}): {res}")
    Path(out).write_bytes(base64.b64decode(res["audios"][0]))
    print(f"🔊 saved {out}")
    return text


# ---------- report ----------

COLOR = {"error": "\033[31m", "warning": "\033[33m", "info": "\033[36m"}
ICON = {"error": "✗", "warning": "!", "info": "i"}


def report(issues, root, gh=None):
    if not issues:
        print("✓ No Sarvam compatibility problems found.")
        return
    tty = sys.stdout.isatty()
    for i in issues:
        c, r = (COLOR[i["severity"]], "\033[0m") if tty else ("", "")
        rel = os.path.relpath(i["file"], root if Path(root).is_dir() else Path(root).parent)
        fix = "" if i["fix"] is None else (" → remove it" if i["fix"] == DELETE else f" → `{i['fix']}`")
        print(f"{c}{ICON[i['severity']]} {rel}:{i['line']}  {i['msg']}{fix}{r}")
        if gh:
            print(f"    https://github.com/{gh}/blob/HEAD/{rel}#L{i['line']}")
        if "live" in i:
            lv = i["live"]
            after = {None: "", 200: "  |  with fix: 200 OK ✓"}.get(lv["after"], f"  |  with fix: {lv['after']}")
            print(f"    live API: {lv['before']} {lv['before_msg']}{after}")
    n = {s: sum(i["severity"] == s for i in issues) for s in ICON}
    print(f"\n{n['error']} errors, {n['warning']} warnings, {n['info']} notes")


# ---------- rules refresh ----------

def refresh_rules():
    import sarvamai
    from sarvamai import types as t

    def lits(tp):
        out = []
        for a in typing.get_args(tp):
            out += [a] if isinstance(a, str) else lits(a)
        return sorted(set(out))

    rules = {
        "sdk_version": sarvamai.__version__ if hasattr(sarvamai, "__version__") else "unknown",
        "tts_models": lits(t.TextToSpeechModel),
        "stt_models": lits(t.SpeechToTextModel),
        "chat_models": sorted(set(lits(t.SarvamModelIds)) | set(lits(t.V2ModelIds))),
        "translate_models": lits(t.TranslateModel),
        "v4_speakers": [s for s in lits(t.TextToSpeechSpeaker) if "_" in s],
        "tts_languages": lits(t.TextToSpeechLanguage),
        "stt_languages": lits(t.SpeechToTextLanguage),
        "translate_languages": lits(t.TranslateTargetLanguage),
    }
    RULES_FILE.write_text(json.dumps(rules, indent=1) + "\n")
    print(f"rules.json refreshed from sarvamai {rules['sdk_version']}: "
          f"{len(rules['v4_speakers'])} v4 speakers, {len(rules['chat_models'])} chat models")


GH = re.compile(r"^(?:github:|https?://github\.com/)([\w.-]+/[\w.-]+?)(?:\.git)?/?$")


MAX_REPO_BYTES = 60_000_000


def resolve(target):
    """Local path stays as is; github:owner/repo or a GitHub URL is downloaded as a tarball (read only, never executed).
    A tarball needs no `git`, so this also works on serverless hosts."""
    m = GH.match(target)
    if not m:
        return target, None
    repo = m.group(1)
    dest = Path(tempfile.mkdtemp(prefix="sudhaar-"))
    try:
        with urllib.request.urlopen(urllib.request.Request(f"https://codeload.github.com/{repo}/tar.gz/HEAD",
                                                           headers={"User-Agent": "sudhaar"}), timeout=60) as r:
            data = r.read(MAX_REPO_BYTES + 1)
    except urllib.error.HTTPError as e:
        sys.exit(f"Could not download {repo}: {'not found, or private' if e.code == 404 else e.code}")
    except (urllib.error.URLError, TimeoutError) as e:
        sys.exit(f"Could not download {repo}: {getattr(e, 'reason', e)}")
    if len(data) > MAX_REPO_BYTES:
        sys.exit(f"{repo} is too large to scan here (over 60 MB); run the CLI on a local clone instead")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        tar.extractall(dest, filter="data")  # "data" filter blocks absolute paths, links and other tricks
    inner = [p for p in dest.iterdir() if p.is_dir()]
    return str(inner[0] if len(inner) == 1 else dest), repo


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="*", default=["."], help="files/folders (several, e.g. from pre-commit) or one GitHub repo")
    ap.add_argument("--verify", action="store_true", help="prove each error against the live API")
    ap.add_argument("--fix", action="store_true", help="rewrite files in place and print the diff")
    ap.add_argument("--explain", metavar="LANG", help="spoken explanation via Sarvam-105B + Bulbul, e.g. hi-IN")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--learn", action="store_true", help="learn new rules from Sarvam's changelog with Sarvam-105B")
    ap.add_argument("--refresh-rules", action="store_true")
    a = ap.parse_args()

    if a.refresh_rules:
        return refresh_rules()
    if (a.verify or a.explain or a.learn) and not os.environ.get("SARVAM_API_KEY"):
        sys.exit("Set SARVAM_API_KEY for --verify / --explain / --learn")
    if a.learn:
        return learn()

    issues = []
    for target in a.path:
        root, gh = resolve(target)
        if gh and a.fix:
            print(f"(--fix edits the temporary clone of {gh}, not the real repo)")
        found = scan(root)
        if a.verify:
            verify(found)
        if not a.json:
            report(found, root, gh) if found or len(a.path) == 1 else None
        issues += found
    if a.json:
        print(json.dumps(issues, indent=1, ensure_ascii=False))
    if a.explain and issues:
        explain(issues, a.explain, "sudhaar_report.wav")
    if a.fix:
        print()
        apply_fixes(issues)
    sys.exit(1 if any(i["severity"] == "error" for i in issues) else 0)


RULES = load_rules() if RULES_FILE.exists() else {}
if LEARNED_FILE.exists():  # rules Sarvam-105B learned from the changelog and the live API confirmed
    DEPRECATED.update({k: tuple(v) for k, v in json.loads(LEARNED_FILE.read_text()).items()})

if __name__ == "__main__":
    main()
