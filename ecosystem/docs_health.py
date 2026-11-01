"""SARVAM_API_KEY=... python3 ecosystem/docs_health.py → ecosystem/docs_health.html (+ .json)

Checks every code sample in Sarvam's docs against the live API. A block's voices are only paired with its model
when the block names exactly one Bulbul model, so mixed v3/v4 examples are never mis-paired.
"""
import html
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import sudhaar as sd

DOCS = "https://docs.sarvam.ai"
SKIP = ("/changelog/", "/models/sarvam-m", "/models/sarvam-30b")  # history and pages labelled deprecated on purpose


def fetch(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "sudhaar"}), timeout=20) as r:
            return r.read().decode(errors="ignore")
    except Exception:
        return ""


def calls_in(block):
    hits = list(sd.hits_in(block))
    models = sorted({h["value"] for h in hits if h["key"] == "model" and not h["num"] and sd.family(h["value"])})
    bulbul = [m for m in models if sd.family(m) == "tts"]
    out = set()
    if len(bulbul) == 1:
        lang = next((h["value"] for h in hits if h["key"] == "target_language_code"), "hi-IN")
        for s in {h["value"] for h in hits if h["key"] == "speaker" and not h["num"]} or {None}:
            out.add(("tts", bulbul[0], s, lang))
    for m in models:
        if m in sd.DEPRECATED and sd.DEPRECATED[m][1] == "error" and sd.family(m) != "tts":
            out.add((sd.family(m), m, None, None))
    return out


def test(call):
    fam, model, speaker, lang = call
    if fam == "tts":
        body = {"text": "नमस्ते", "target_language_code": lang if lang in sd.RULES["tts_languages"] else "hi-IN", "model": model}
        if speaker:
            body["speaker"] = speaker
        return sd.http("/text-to-speech", body)
    return sd.probe({"key": "model", "family": fam, "model": model, "lang": None, "num": False}, model)


def fix_for(call):
    fam, model, speaker, lang = call
    if model in sd.DEPRECATED:
        new = sd.DEPRECATED[model][0]
        if speaker and new == "bulbul:v3" and speaker.lower() not in sd.V3_SPEAKERS:
            return f"model → {new}, speaker → {sd.remap_speaker(speaker, new, lang)}"
        return f"model → {new}"
    if speaker:
        live = model if model in ("bulbul:v3", "bulbul:v4-flash") else sd.DEFAULT_TTS
        return f"speaker → {sd.remap_speaker(speaker, live, lang)}"
    return ""


def main():
    index = fetch(DOCS + "/llms.txt") + fetch(DOCS + "/api/llms.txt")
    urls = sorted({u for u in re.findall(r"https://docs\.sarvam\.ai/[\w/.-]+\.md", index) if not any(s in u for s in SKIP)})
    with ThreadPoolExecutor(12) as ex:
        pages = dict(zip(urls, ex.map(fetch, urls)))
    page_calls = {u: set().union(*[calls_in(b) for b in re.findall(r"```[\w-]*\n(.*?)```", t, re.S)] or [set()])
                  for u, t in pages.items()}
    unique = sorted({c for cs in page_calls.values() for c in cs}, key=str)
    with ThreadPoolExecutor(6) as ex:
        results = dict(zip(unique, ex.map(test, unique)))
    failing = []
    for u, cs in page_calls.items():
        bad = [c for c in cs if results[c][0] != 200]
        if bad:
            title = (re.search(r"^# (.+)$", pages[u], re.M) or [None, u])[1]
            failing.append({"url": u.replace(".md", ""), "title": title, "calls": [
                {"call": c[1] + (f" + {c[2]}" if c[2] else ""), "status": results[c][0],
                 "error": str(results[c][1])[:120], "fix": fix_for(c)} for c in sorted(bad, key=str)]})
    with_code = sum(1 for t in pages.values() if "```" in t)
    data = {"checked_at": time.strftime("%d %b %Y, %H:%M"), "pages": len(urls), "pages_with_code": with_code,
            "calls_tested": len(unique), "failing_pages": sorted(failing, key=lambda p: p["url"])}
    (HERE / "docs_health.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
    render(data)
    print(f"{len(failing)} of {with_code} docs pages with code have samples the live API rejects ({len(unique)} calls tested)")


def render(d):
    e = html.escape
    rows = "\n".join(
        f"""<li><div class="lbl"><a href="{e(p['url'])}">{e(p['title'])}</a></div><div class="path">{e(p['url'].replace(DOCS, ''))}</div>"""
        + "".join(f"""<div class="call"><code>{e(c['call'])}</code> → <b>{c['status']}</b> <span>{e(c['error'])}</span>"""
                  f"""{f' <em>Fix: {e(c["fix"])}</em>' if c['fix'] else ''}</div>""" for c in p["calls"]) + "</li>"
        for p in d["failing_pages"])
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Sarvam Docs Health</title>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,500&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#ffffff;--fg:#1a1a1a;--muted:#6b6b6b;--faint:#9a9a9a;--line:#e8e8e5;--soft:#f3f3f1;--accent:#C2410C;--err:#b42318;--ok:#067647}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#1b1b1a;--fg:#ededeb;--muted:#a3a3a0;--faint:#77776f;--line:#2c2c2a;--soft:#242423;--accent:#FF8A50;--err:#fda29b;--ok:#75e0a7}}}}
:root[data-theme=dark]{{--bg:#1b1b1a;--fg:#ededeb;--muted:#a3a3a0;--faint:#77776f;--line:#2c2c2a;--soft:#242423;--accent:#FF8A50;--err:#fda29b;--ok:#75e0a7}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 Inter,system-ui,sans-serif}}
main{{max-width:760px;margin:0 auto;padding:44px 20px 56px}}
.kicker{{color:var(--muted);font-size:13px}}
.big{{font-family:"Source Serif 4",Georgia,serif;font-size:clamp(72px,14vw,128px);color:var(--accent);line-height:1;margin:14px 0 6px;letter-spacing:-.03em}}
h1{{font-family:"Source Serif 4",Georgia,serif;font-weight:400;font-size:clamp(24px,3.6vw,34px);line-height:1.25;margin:0 0 12px}}
.sub{{color:var(--muted);margin:0 0 26px}}
ul{{list-style:none;padding:0;margin:0;border:1px solid var(--line);border-radius:16px;overflow:hidden}}
li{{padding:14px 18px;border-top:1px solid var(--line)}}li:first-child{{border-top:0}}
.lbl a{{color:var(--fg);font-weight:500;text-decoration-color:var(--line)}}.path{{font-size:12px;color:var(--faint);margin-bottom:6px}}
.call{{font-size:13px;margin:4px 0;overflow-wrap:anywhere}}.call code{{font-family:ui-monospace,Menlo,monospace;background:var(--soft);padding:1px 6px;border-radius:5px}}
.call b{{color:var(--err)}}.call span{{color:var(--muted)}}.call em{{display:block;font-style:normal;color:var(--ok);margin-top:2px}}
footer{{margin-top:22px;color:var(--faint);font-size:13px}}
</style></head><body><main>
<div class="kicker">Sarvam docs health · checked live {e(d['checked_at'])}</div>
<div class="big">{len(d['failing_pages'])}</div>
<h1>docs pages have code samples that Sarvam’s API rejects today</h1>
<p class="sub">Sudhaar tested every code sample in {d['pages_with_code']} docs pages ({d['calls_tested']} distinct calls) against the live API.
Each failing call below shows the real response and a one-line fix.</p>
<ul>{rows}</ul>
<footer>Method: docs.sarvam.ai/llms.txt index; code blocks only; a block’s voices are paired with its model only when it names exactly one Bulbul model.
The changelog and pages labelled deprecated are skipped. Re-run: SARVAM_API_KEY=… python3 ecosystem/docs_health.py</footer>
</main></body></html>"""
    (HERE / "docs_health.html").write_text(page)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--render":
        render(json.loads((HERE / "docs_health.json").read_text()))
    else:
        main()
