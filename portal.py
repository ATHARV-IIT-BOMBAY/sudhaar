#!/usr/bin/env python3
"""Sudhaar portal: the same engine as the CLI, in a browser.

    export SARVAM_API_KEY=...      # stays on this machine, never sent to the browser
    python3 portal.py              # then open http://localhost:8000
"""
import base64
import contextlib
import io
import json
import os
import random
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import wave
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import sudhaar as sd

HERE = Path(__file__).parent
IST = timezone(timedelta(hours=5, minutes=30))
PORT = int(os.environ.get("PORT", 8000))
SESSIONS = {}  # ponytail: in-memory, one laptop; a store if this ever serves more than one person


def public(issue, root):
    keep = ("line", "key", "value", "severity", "msg", "fix", "live")
    out = {k: issue.get(k) for k in keep if k in issue}
    out["file"] = os.path.relpath(issue["file"], root)
    out["fix"] = "remove it" if issue["fix"] == sd.DELETE else issue["fix"]
    return out


def counts(issues):
    return {s: sum(i["severity"] == s for i in issues) for s in ("error", "warning", "info")}


def api_scan(body):
    target = body.get("target", "").strip()
    if not target:
        raise ValueError("Paste a GitHub URL, github:owner/repo, or a local folder")
    # GitHub repos, or folders inside this project (the sample app); the CLI is for scanning anything else locally
    local = (HERE / target).resolve()
    if not sd.GH.match(target) and not (local.is_dir() and local.is_relative_to(HERE)):
        raise ValueError("Paste a GitHub URL or github:owner/repo")
    try:
        root, gh = sd.resolve(target if sd.GH.match(target) else str(local))
    except SystemExit as e:  # resolve() exits on a failed clone
        raise ValueError(str(e))
    issues = sd.scan(root)
    sid = uuid.uuid4().hex[:12]
    SESSIONS[sid] = {"root": root, "gh": gh, "issues": issues}
    return {"id": sid, "gh": gh, "counts": counts(issues), "issues": [public(i, root) for i in issues]}


def session(body):
    s = SESSIONS.get(body.get("id"))
    if not s:
        raise ValueError("Scan expired, scan again")
    return s


def need_key():
    if not os.environ.get("SARVAM_API_KEY"):
        raise ValueError("Start the portal with SARVAM_API_KEY set to use live features")


def api_verify(body):
    need_key()
    s = session(body)
    sd.verify(s["issues"])
    return {"issues": [public(i, s["root"]) for i in s["issues"]]}


def api_fix(body):
    s = session(body)
    copy = Path(tempfile.mkdtemp(prefix="sudhaar-fix-")) / "repo"
    shutil.copytree(s["root"], copy, ignore=shutil.ignore_patterns(".git"))  # never touch the original
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sd.apply_fixes(sd.scan(copy))
    return {"diff": buf.getvalue(), "before": counts(s["issues"]), "after": counts(sd.scan(copy))}


def api_explain(body):
    need_key()
    s = session(body)
    lang = body.get("lang", "hi-IN")
    out = Path(tempfile.mkdtemp(prefix="sudhaar-audio-")) / "report.wav"
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            text = sd.explain(s["issues"], lang, out)
    except SystemExit as e:  # ask_105b / Bulbul exit with a message on failure
        raise ValueError(str(e))
    return {"text": text, "audio": "data:audio/wav;base64," + base64.b64encode(out.read_bytes()).decode()}


FACTS = """Facts Sudhaar verified against Sarvam's live API on 1 Nov 2026 (that is the test date, NOT the date Sarvam deprecated anything; don't state deprecation dates):
- Rejected (400): sarvam-m, sarvam-30b (use sarvam-105b); saarika:v1, saarika:v2, saarika:flash, saaras:v1, saaras:v2 (use saaras:v3);
  bulbul:v1, bulbul:v2 (use bulbul:v3 or bulbul:v4-flash); speakers from another Bulbul version; pace outside 0.5-2.0 on v3/v4;
  Odia code or-IN on REST TTS/STT (use od-IN).
- Still accepted: saarika:v2.5 (dropped from the SDK), bulbul:v3-beta; pitch/loudness on v3/v4 are accepted but have no effect.
- bulbul:v4-flash uses persona voices like shubh_hi_ads; v3 short names like shubh are rejected on it.
- bulbul:v3 reaches end of life on Sarvam Voice Agents on 10 Nov 2026; REST text-to-speech keeps it."""


def api_ask(body):
    need_key()
    q = body.get("question", "").strip()[:1000]
    if not q:
        raise ValueError("Ask a question")
    s = SESSIONS.get(body.get("id"))
    scan = ""
    if s:
        lines = [f"- {os.path.relpath(i['file'], s['root'])}:{i['line']} [{i['severity']}] {i['msg']}" for i in s["issues"][:40]]
        scan = f"\nThe user's latest scan ({s['gh'] or 'local project'}) found:\n" + ("\n".join(lines) or "- nothing")
    prompt = ("You are Sudhaar, an assistant that helps developers keep their code working with Sarvam AI's APIs. "
              "Answer the question in the same language the user wrote it in, in plain text (no markdown), under 90 words. "
              "Be concrete: name the file, line and the exact replacement when relevant. If the facts below don't cover it, say so.\n\n"
              f"{FACTS}{scan}\n\nQuestion: {q}")
    try:
        return {"answer": sd.ask_105b(prompt, 1500)}
    except SystemExit as e:
        raise ValueError(str(e))


def code_file(code, lang_hint=""):
    """Save pasted or generated code to a temp project so the normal scanner can read it."""
    js = lang_hint.lower() in ("js", "javascript", "node", "ts", "typescript", "jsx", "tsx") or \
        (not lang_hint and re.search(r"\b(const|let|function|=>|await fetch|require\()", code) and "def " not in code)
    root = Path(tempfile.mkdtemp(prefix="sudhaar-code-"))
    path = root / ("snippet.js" if js else "snippet.py")
    path.write_text(code)
    return root, path


def api_scan_code(body):
    code = body.get("code", "")
    if not code.strip():
        raise ValueError("Paste some code")
    if len(code) > 200_000:
        raise ValueError("That's a lot of code: scan the repo or folder instead")
    root, path = code_file(code)
    issues = sd.scan(root)
    sid = uuid.uuid4().hex[:12]
    SESSIONS[sid] = {"root": str(root), "gh": None, "issues": issues}
    return {"id": sid, "gh": None, "counts": counts(issues), "issues": [public(i, str(root)) for i in issues]}


def api_write(body):
    """Write it right: Sarvam-105B writes the code, Sudhaar fixes it and live-tests every Sarvam call in it."""
    need_key()
    request = body.get("request", "").strip()[:600]
    if not request:
        raise ValueError("Say what code you need")
    # Grounding: the model writes from stale memory (5 of 5 samples failed in our test), so give it the verified shapes.
    prompt = ("Write minimal working code for this request using Sarvam AI's REST API with the requests library "
              "(or fetch in JavaScript if asked). Set every model name and voice explicitly. Reply with one code block only.\n\n"
              "Verified request and response shapes (base URL https://api.sarvam.ai, header api-subscription-key):\n"
              "- Text-to-speech: POST /text-to-speech, JSON {text, target_language_code, speaker, model: \"bulbul:v3\"}; "
              "voices for bulbul:v3 include shubh, priya, ritu, aditya, kavya, rahul. Response JSON {\"audios\": [base64 WAV]}.\n"
              "- Speech-to-text: POST /speech-to-text, multipart file=<audio> plus form fields model=\"saaras:v3\", language_code; "
              "response JSON {\"transcript\"}.\n"
              "- Chat: POST /v2/chat/completions, OpenAI-style JSON {model: \"sarvam-105b\", messages, reasoning_effort: \"none\"}; "
              "answer at choices[0].message.content.\n"
              "- Translate: POST /translate, JSON {input, source_language_code, target_language_code, model: \"mayura:v1\"}; "
              "response JSON {\"translated_text\"}.\n"
              f"{FACTS}\n\nRequest: {request}")
    try:
        raw = sd.ask_105b(prompt, 2500)
    except SystemExit as e:
        raise ValueError(str(e))
    block = re.search(r"```([\w+-]*)\n(.*?)```", raw, re.S)
    lang, original = (block.group(1), block.group(2)) if block else ("", raw)
    root, path = code_file(original, lang)
    before = sd.scan(root)
    with contextlib.redirect_stdout(io.StringIO()):
        sd.apply_fixes(before)
    fixed = path.read_text()
    after = sd.scan(root)
    return {
        "language": "javascript" if path.suffix == ".js" else "python",
        "original": original, "code": fixed,
        "corrections": [{"line": i["line"], "msg": i["msg"], "fix": "remove it" if i["fix"] == sd.DELETE else i["fix"]}
                        for i in before if i["severity"] in ("error", "warning")],
        "remaining": counts(after),
        "checks": sd.prove_calls(path),
        "at": datetime.now(IST).strftime("%H:%M IST"),  # servers (Vercel) run on UTC
    }


ROUTES = {"/api/scan": api_scan, "/api/verify": api_verify, "/api/fix": api_fix, "/api/explain": api_explain,
          "/api/ask": api_ask, "/api/scan_code": api_scan_code, "/api/write": api_write}
STATIC = {"/": ("portal.html", "text/html"), "/dashboard": ("ecosystem/dashboard.html", "text/html"),
          "/docs-health": ("ecosystem/docs_health.html", "text/html"), "/tour": ("tour.html", "text/html")}


# ---------- self-healing proxy: point base_url at <portal>/proxy and calls stop breaking ----------

def heal_json(path, body):
    """Rewrite only what the live API is confirmed to reject. Returns (body, list of changes)."""
    changes = []

    def swap(key, new, why):
        changes.append(f"{key}: {body.get(key)!r}->{new!r} ({why})")
        body[key] = new

    model = body.get("model")
    if isinstance(model, str) and model in sd.DEPRECATED and sd.DEPRECATED[model][1] == "error":
        swap("model", sd.DEPRECATED[model][0], "deprecated")
    if "chat/completions" in path:
        # OpenAI-style clients send content as [{"type": "text", ...}]; Sarvam's chat API only takes a string (live: 400)
        for i, msg in enumerate(body.get("messages") or []):
            parts = msg.get("content") if isinstance(msg, dict) else None
            if isinstance(parts, list) and parts and all(isinstance(x, dict) and x.get("type") == "text" for x in parts):
                msg["content"] = "\n".join(x.get("text", "") for x in parts)
                changes.append(f"messages[{i}].content array->string")
    if path.startswith("/text-to-speech"):
        for wrong, right in sd.TTS_FIELD_RENAMES.items():
            if wrong in body and right not in body:
                changes.append(f"field {wrong}->{right}")
                body[right] = body.pop(wrong)
        tts = body.get("model") or sd.DEFAULT_TTS
        ok = {"bulbul:v4-flash": set(sd.RULES["v4_speakers"]), "bulbul:v3": sd.V3_SPEAKERS}.get(tts)
        spk = body.get("speaker")
        if ok and isinstance(spk, str) and spk.lower() not in ok:
            swap("speaker", sd.remap_speaker(spk, tts, body.get("target_language_code")), f"not a {tts} voice")
        lo, hi = sd.PACE.get(tts, (0.5, 2.0))
        if isinstance(body.get("pace"), (int, float)) and not lo <= body["pace"] <= hi:
            swap("pace", min(max(body["pace"], lo), hi), f"{tts} range {lo}-{hi}")
    for key in ("target_language_code", "source_language_code", "language_code"):
        if body.get(key) == "or-IN":
            swap(key, "od-IN", "REST spells Odia od-IN")
    return body, changes


def heal_multipart(raw):
    """Speech-to-text uploads are multipart: only the `model` form field is rewritten."""
    changes = []

    def fix(m):
        old = m.group(2).decode()
        if old in sd.DEPRECATED and sd.DEPRECATED[old][1] == "error":
            changes.append(f"model: {old!r}->{sd.DEPRECATED[old][0]!r} (deprecated)")
            return m.group(1) + sd.DEPRECATED[old][0].encode() + m.group(3)
        return m.group(0)
    raw = re.sub(rb'(name="model"\r\n\r\n)([^\r]*)(\r\n)', fix, raw)
    return raw, changes


RETRY = {429, 500, 502, 503}
NO_RETRY_429 = (b"insufficient_quota", b"seat_budget")  # budget errors don't get better by waiting
TTS_LIMIT = 2500


def forward(path, raw, headers, attempts=4):
    """POST to Sarvam, retrying 429/500/502/503 with exponential backoff (honours Retry-After). Never retries 4xx input errors."""
    for n in range(attempts):
        req = urllib.request.Request(sd.API + path, data=raw, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, r.read(), r.headers.get("Content-Type", "application/json"), n
        except urllib.error.HTTPError as e:
            code, data, rtype, after = e.code, e.read(), e.headers.get("Content-Type", "application/json"), e.headers.get("Retry-After")
        except (urllib.error.URLError, TimeoutError) as e:
            code, data, rtype, after = 502, json.dumps({"error": f"Sarvam unreachable: {getattr(e, 'reason', e)}"}).encode(), "application/json", None
        if code not in RETRY or n == attempts - 1 or any(x in data for x in NO_RETRY_429):
            return code, data, rtype, n
        wait = float(after) if after and after.replace(".", "", 1).isdigit() else 0.5 * 2 ** n
        time.sleep(min(wait, 8) + random.uniform(0, 0.25))
    return code, data, rtype, n


def split_text(text, limit=TTS_LIMIT - 100):
    """Split at sentence ends (।, ., !, ?, newline) into pieces under the TTS limit."""
    pieces, cur = [], ""
    for s in re.split(r"(?<=[।.!?\n])\s+", text):
        while len(s) > limit:
            if cur:
                pieces.append(cur)
                cur = ""
            pieces.append(s[:limit])
            s = s[limit:]
        if cur and len(cur) + 1 + len(s) > limit:
            pieces.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    return pieces + ([cur] if cur else [])


def join_wavs(b64s):
    frames, params = [], None
    for b in b64s:
        with wave.open(io.BytesIO(base64.b64decode(b))) as w:
            params = params or w.getparams()
            frames.append(w.readframes(w.getnframes()))
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setparams(params)
        w.writeframes(b"".join(frames))
    return base64.b64encode(out.getvalue()).decode()


def chunked_tts(body, headers):
    """Text over Bulbul's 2,500-character limit (live: 400) is spoken in pieces and returned as one audio."""
    parts, audios, first, retries = split_text(body["text"]), [], None, 0
    for part in parts:
        code, data, rtype, n = forward("/text-to-speech", json.dumps({**body, "text": part}).encode(), headers)
        retries += n
        if code != 200:
            return code, data, rtype, retries, len(parts)
        res = json.loads(data)
        first = first or res
        audios += res.get("audios", [])
    wav = body.get("output_audio_codec", "wav") in ("wav", None)
    out = {**first, "audios": [join_wavs(audios)] if wav else audios}
    return 200, json.dumps(out).encode(), "application/json", retries, len(parts)


def proxy(path, headers, raw):
    ctype = headers.get("content-type", "")
    changes, retries = [], 0
    fwd = {k: v for k, v in headers.items() if k in ("content-type", "api-subscription-key", "authorization")}
    auth = fwd.get("authorization", "")
    if "api-subscription-key" not in fwd and auth.lower().startswith("bearer "):  # OpenAI-style clients
        fwd["api-subscription-key"] = auth[7:].strip()
        changes.append("auth: Bearer->api-subscription-key")
    body = None
    if "application/json" in ctype and raw:
        body, fixed = heal_json(path, json.loads(raw))
        changes += fixed
        raw = json.dumps(body).encode()
    elif "multipart/form-data" in ctype:
        raw, fixed = heal_multipart(raw)
        changes += fixed
    if body is not None and path.startswith("/text-to-speech") and len(str(body.get("text", ""))) > TTS_LIMIT:
        code, data, rtype, retries, n = chunked_tts(body, fwd)
        changes.append(f"text: {len(body['text'])} chars split into {n} calls and joined")
    else:
        code, data, rtype, retries = forward(path, raw, fwd)
    out = [("Content-Type", rtype)]
    if changes:
        out.append(("X-Sudhaar-Fixed", "; ".join(changes)[:1000]))
        print(f"  proxy {path}: healed " + "; ".join(changes))
    if retries:
        out.append(("X-Sudhaar-Retries", str(retries)))
    if code == 402:
        out.append(("X-Sudhaar-Hint", "Sarvam credits are exhausted: add credits in the dashboard, retrying will not help"))
    return code, out, data


# ---------- paste an error: what it means and how to fix it ----------

ERROR_CODES = {  # from docs.sarvam.ai -> Errors & troubleshooting
    "insufficient_quota_error": "402: your Sarvam credit balance is empty. Add credits; retrying will not help.",
    "rate_limit_exceeded_error": "429: too many requests on your account. Retry with exponential backoff.",
    "model_rate_limit_exceeded_error": "429: the model is at capacity (not your quota). Retry with backoff.",
    "seat_budget_exhausted_error": "429: your seat spend budget is used up.",
    "audio_duration_busy_error": "429: the gateway is busy reading audio duration. Retry shortly.",
    "invalid_request_error": "400/413/422: bad parameters, payload or file. Fix the request; don't retry blindly.",
    "unprocessable_entity_error": "422: the schema is valid but a business rule failed (often a wrong field name).",
    "internal_server_error": "500: server-side failure. Retry with backoff.",
    "model_call_failed": "502: model backend unreachable. Retry.",
    "model_overloaded": "503: model overloaded. Retry with backoff.",
}


def error_facts(text):
    facts = [f"`{c}`: {why}" for c, why in ERROR_CODES.items() if c in text]
    for model in set(re.findall(r"[a-z]+[-:][\w.:-]*\w", text)):
        if model in sd.DEPRECATED:
            facts.append(f"`{model}` is {sd.DEPRECATED[model][2]}; use `{sd.DEPRECATED[model][0]}`")
    m = re.search(r"Speaker '([\w-]+)' is not (?:compatible with model|recognized)[^\n.]*?(bulbul:[\w-]+)?", text)
    if m:
        model = m.group(2) or sd.DEFAULT_TTS
        facts.append(f"voice `{m.group(1)}` isn't valid on {model}; try `{sd.remap_speaker(m.group(1), model, None)}`")
    if "at most 2500 characters" in text:
        facts.append("Bulbul takes at most 2,500 characters per request: split the text, or send it through Sudhaar's proxy, which splits and joins for you")
    if re.search(r"content\s*(?:is|=|:)\s*None|'NoneType'", text):
        facts.append("chat `content` is None when reasoning uses up max_tokens: raise max_tokens (500+) or set reasoning_effort to none")
    if "should be a valid string" in text and "content" in text:
        facts.append("Sarvam's chat API wants message content as a plain string, not the OpenAI array format (Sudhaar's proxy converts it)")
    if "TypeError" in text and "language_code" in text:
        facts.append("sarvamai >= 0.1.29 (JS >= 1.1.8) renamed the TTS parameter: use `language_code` on new SDKs, `target_language_code` on old ones")
    return facts


def api_explain_error(body):
    text = body.get("error", "").strip()[:4000]
    if not text:
        raise ValueError("Paste an error")
    facts = error_facts(text)
    lang = sd.LANG_NAMES.get(body.get("lang", "en-IN"), "English")
    if not os.environ.get("SARVAM_API_KEY"):
        return {"answer": "\n".join(facts) or "I don't recognise this error yet.", "facts": facts}
    # In testing the model once contradicted a verified fact, so the facts are shown as the answer and the model only explains.
    prompt = (f"A developer using Sarvam AI's API got this error. In plain {lang}, under 70 words, no markdown, explain why it "
              "happened. The fixes below were verified against the live API: recommend exactly them, never contradict or "
              "replace them, and don't name any other model or voice. If there are none, say what to check.\n\n"
              "Verified fixes:\n" + ("\n".join(f"- {f}" for f in facts) or "- none") + f"\n\nError:\n{text}")
    try:
        return {"answer": sd.ask_105b(prompt, 1500), "facts": facts}
    except SystemExit:
        return {"answer": "\n".join(facts) or "I couldn't explain this one right now.", "facts": facts}


ROUTES["/api/explain_error"] = api_explain_error


# Calls that spend the portal's Sarvam credits are rate-limited, so a public link can't drain the key.
# ponytail: in-memory per-process limits, fine for one laptop or warm serverless instances; a shared store at real scale
COSTLY = {"/api/verify", "/api/explain", "/api/write", "/api/ask", "/api/explain_error"}
PER_CLIENT, PER_CLIENT_WINDOW = 20, 600   # 20 costly calls per visitor per 10 minutes
GLOBAL, GLOBAL_WINDOW = 300, 3600         # and 300 per hour in total
_hits = {}


def allowed(client):
    now = time.time()
    for key, cap, window in ((client, PER_CLIENT, PER_CLIENT_WINDOW), ("*", GLOBAL, GLOBAL_WINDOW)):
        recent = [t for t in _hits.get(key, []) if now - t < window]
        if len(recent) >= cap:
            return False
        _hits[key] = recent
    for key in (client, "*"):
        _hits[key].append(now)
    return True


def as_json(code, body):
    return code, [("Content-Type", "application/json; charset=utf-8")], json.dumps(body, ensure_ascii=False).encode()


def dispatch(method, path, headers, raw, client):
    """One request in, (status, headers, bytes) out. Used by the local server and by the Vercel function."""
    path = path.split("?", 1)[0]
    if method == "GET":
        if path == "/api/status":
            return as_json(200, {"key": bool(os.environ.get("SARVAM_API_KEY"))})
        if path in STATIC:
            name, ctype = STATIC[path]
            return 200, [("Content-Type", f"{ctype}; charset=utf-8")], (HERE / name).read_bytes()
        return as_json(404, {"error": "not found"})
    if method != "POST":
        return as_json(405, {"error": "method not allowed"})
    if path.startswith("/proxy/"):
        return proxy(path[len("/proxy"):], headers, raw)
    fn = ROUTES.get(path)
    if not fn:
        return as_json(404, {"error": "not found"})
    if path in COSTLY and not allowed(client):
        return as_json(429, {"error": "Too many live checks from here, try again in a few minutes"})
    try:
        return as_json(200, fn(json.loads(raw or b"{}")))
    except ValueError as e:
        return as_json(400, {"error": str(e)})
    except Exception as e:  # keep the demo alive and show what broke
        return as_json(500, {"error": f"{type(e).__name__}: {e}"})


class Handler(BaseHTTPRequestHandler):
    def handle_any(self):
        headers = {k.lower(): v for k, v in self.headers.items()}
        raw = self.rfile.read(int(headers.get("content-length", 0) or 0))
        client = (headers.get("x-forwarded-for") or self.client_address[0]).split(",")[0].strip()
        code, out, data = dispatch(self.command, self.path, headers, raw, client)
        self.send_response(code)
        for k, v in out:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = handle_any

    def log_message(self, fmt, *args):
        print(f"  {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")


def app(environ, start_response):
    """WSGI entry point (Vercel and any WSGI host)."""
    headers = {k[5:].replace("_", "-").lower(): v for k, v in environ.items() if k.startswith("HTTP_")}
    if environ.get("CONTENT_TYPE"):
        headers["content-type"] = environ["CONTENT_TYPE"]
    raw = environ["wsgi.input"].read(int(environ.get("CONTENT_LENGTH") or 0) or 0)
    client = (headers.get("x-forwarded-for") or environ.get("REMOTE_ADDR", "?")).split(",")[0].strip()
    code, out, data = dispatch(environ["REQUEST_METHOD"], environ.get("PATH_INFO") or "/", headers, raw, client)
    start_response(f"{code} {HTTPStatus(code).phrase}", out + [("Content-Length", str(len(data)))])
    return [data]


if __name__ == "__main__":
    print(f"Sudhaar portal on http://localhost:{PORT}  (live features: {'on' if os.environ.get('SARVAM_API_KEY') else 'off, set SARVAM_API_KEY'})")
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        raise SystemExit(f"Port {PORT} is busy (another portal is running?). Open http://localhost:{PORT}, "
                         f"or stop it with: pkill -f portal.py, or use another port: PORT=8001 python3 portal.py")
    server.serve_forever()
