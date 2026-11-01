"""python3 ecosystem/dashboard.py → ecosystem/dashboard.html (static, works offline on a projector)."""
import collections
import html
import json
from pathlib import Path

HERE = Path(__file__).parent
s = json.loads((HERE / "summary.json").read_text())


def group(name):
    if name.startswith("bad pitch") or name.startswith("bad loudness"):
        return "pitch / loudness sent to a model that rejects them"
    if name.startswith("dead model saarika"):
        return "saarika (no longer accepted by speech-to-text)"
    if name.startswith("dead model saaras:v1") or name.startswith("dead model saaras:v2"):
        return "old saaras v1 / v2"
    if name.startswith("dead model "):
        return name.replace("dead model ", "") + " (removed / deprecated)"
    return name


rows, examples = collections.Counter(), collections.defaultdict(list)
for name, n in s["rules"]:
    g = group(name)
    rows[g] = max(rows[g], n) if g.startswith("pitch") else rows[g] + n  # pitch+loudness hit the same repos
    for e in s["examples"].get(name, []):
        if e not in examples[g] and len(examples[g]) < 3:
            examples[g].append(e)

pct = round(100 * s["broken"] / s["checked"])
top = rows.most_common(8)
peak = top[0][1]
bars = "\n".join(
    f"""<li><div class="lbl"><span>{html.escape(g)}</span><b>{n}</b></div>
<div class="bar"><i style="width:{100 * n / peak:.0f}%"></i></div>
<div class="ex">{' · '.join(f'<a href="https://github.com/{html.escape(e)}">{html.escape(e)}</a>' for e in examples[g])}</div></li>"""
    for g, n in top)

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sarvam Ecosystem Health</title>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,500&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#ffffff;--fg:#1a1a1a;--muted:#6b6b6b;--faint:#9a9a9a;--line:#e8e8e5;--soft:#f3f3f1;--accent:#C2410C;--bar:#F26A2E}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#1b1b1a;--fg:#ededeb;--muted:#a3a3a0;--faint:#77776f;--line:#2c2c2a;--soft:#242423;--accent:#FF8A50;--bar:#F26A2E}}}}
:root[data-theme=dark]{{--bg:#1b1b1a;--fg:#ededeb;--muted:#a3a3a0;--faint:#77776f;--line:#2c2c2a;--soft:#242423;--accent:#FF8A50;--bar:#F26A2E}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 Inter,system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:760px;margin:0 auto;padding:44px 20px 56px}}
.kicker{{color:var(--muted);font-size:13px}}
.big{{font-family:"Source Serif 4",Georgia,serif;font-size:clamp(84px,16vw,148px);font-weight:400;color:var(--accent);line-height:1;letter-spacing:-.03em;margin:14px 0 6px;font-variant-numeric:tabular-nums}}
h1{{font-family:"Source Serif 4",Georgia,serif;font-weight:400;font-size:clamp(26px,4vw,38px);line-height:1.2;margin:0 0 12px;letter-spacing:-.01em}}
.sub{{color:var(--muted);max-width:640px;margin:0}}
.stats{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:28px 0 36px}}
.stat{{border:1px solid var(--line);border-radius:16px;padding:16px 18px}}
.stat b{{display:block;font-size:26px;font-weight:500;font-variant-numeric:tabular-nums}}.stat span{{color:var(--muted);font-size:14px}}
h2{{font-size:16px;font-weight:600;margin:0 0 12px}}ul{{list-style:none;padding:0;margin:0;border:1px solid var(--line);border-radius:16px;overflow:hidden}}
li{{padding:14px 18px;border-top:1px solid var(--line)}}li:first-child{{border-top:0}}
.lbl{{display:flex;justify-content:space-between;gap:12px;font-weight:500}}.lbl b{{font-weight:500;font-variant-numeric:tabular-nums}}
.bar{{height:6px;background:var(--soft);border-radius:4px;margin:10px 0 8px;overflow:hidden}}.bar i{{display:block;height:100%;background:var(--bar);border-radius:4px}}
.ex{{font-size:13px;color:var(--muted);overflow-wrap:anywhere}}.ex a{{color:inherit;text-decoration-color:var(--line)}}
footer{{margin-top:24px;color:var(--faint);font-size:13px}}
@media (max-width:560px){{.stats{{grid-template-columns:1fr}}}}
</style></head><body><main>
<div class="kicker">Ecosystem health · measured 1 Nov 2026</div>
<div class="big">{pct}%</div>
<h1>of public projects built on Sarvam break on today's API</h1>
<p class="sub">We scanned {s['sampled']} public GitHub repos that call Sarvam. In {s['checked']} of them the model ids are written in code,
so we can check them. {s['broken']} contain at least one call the live API rejects.</p>
<div class="stats">
<div class="stat"><b>{s['sampled']}</b><span>repos sampled</span></div>
<div class="stat"><b>{s['checked']}</b><span>checkable</span></div>
<div class="stat"><b>{s['broken']}</b><span>broken today</span></div>
</div>
<h2>What breaks (repos affected)</h2>
<ul>{bars}</ul>
<footer>Method: GitHub code search for api.sarvam.ai / sarvamai (forks and sarvamai org excluded), static scan with Sudhaar's rules
(Sarvam SDK 0.1.41 types + docs.sarvam.ai). Open-model ids such as sarvam-2b are not counted as broken. Reproduce: ecosystem/eco_fetch.py, eco_scan.py.</footer>
</main></body></html>"""
(HERE / "dashboard.html").write_text(page)
print(f"wrote dashboard.html: {pct}% ({s['broken']}/{s['checked']})")
