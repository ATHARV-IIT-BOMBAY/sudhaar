# Sudhaar (सुधार)

**Live:** https://sudhaar-nu.vercel.app · **Code:** https://github.com/ATHARV-IIT-BOMBAY/sudhaar

Finds Sarvam API calls that will break, proves it against the live API, and fixes them.
Python 3 stdlib only, works on Python and JS/TS projects. Use it from the terminal or the web portal. Why it's needed: [PROOF.md](PROOF.md).

**Portal:** `python3 portal.py` → http://localhost:8000 (chat-style: paste a GitHub repo to scan, then prove live / show the fix / explain aloud, or ask follow-up questions that Sarvam-105B answers using the scan; plus the ecosystem page).
The API key stays on the server, never sent to the browser.

**Terminal:**
```bash
python3 sudhaar.py demo_app                    # report
export SARVAM_API_KEY=...
python3 sudhaar.py demo_app --verify           # each error: live API status before / after the fix
python3 sudhaar.py demo_app --explain hi-IN    # Sarvam-105B explains it in Hindi, Bulbul speaks it
python3 sudhaar.py demo_app --fix              # rewrite files, print the diff
python3 sudhaar.py github:anyaaa1924/VittBot-GBH  # scan any public GitHub repo (read-only clone)
python3 sudhaar.py --learn                     # Sarvam-105B reads Sarvam's changelog, live API confirms new rules
python3 ecosystem/dashboard.py                 # rebuild ecosystem/dashboard.html (42% of public Sarvam code broken)
python3 test_sudhaar.py                        # self-check
```

Rules: enumerable values (models, 222 v4 voices, language codes) are generated from Sarvam's own SDK
(`--refresh-rules`, needs `pip install sarvamai`). Behaviour rules (deprecations, pace ranges, v2-only params)
come from docs.sarvam.ai and live in `DEPRECATED` / `PACE` at the top of `sudhaar.py`.
Exits 1 on errors, so it can gate CI.

## Everywhere you code
| Where | How |
|---|---|
| **Portal** | `python3 portal.py` → paste a repo or code, "Write Sarvam code" (generated, fixed, verified live), Docs health, Ecosystem health |
| **CLI** | `python3 sudhaar.py <files or folders or github:owner/repo> [--verify] [--fix] [--explain hi-IN]` |
| **CI** | `action.yml` (GitHub Action, see `examples/github-workflow.yml`) and `.pre-commit-hooks.yaml`; exits 1 on errors |
| **AI coding agents** | Agent Skill in `skills/sudhaar/SKILL.md`; MCP server `mcp_server.py` (`sudhaar_check`, `sudhaar_verify`, `sudhaar_fix`) |
| **Production** | Self-healing proxy: set your Sarvam base URL to `http://localhost:8000/proxy`; dead models, wrong voices, pace and field names are fixed in flight and reported in the `X-Sudhaar-Fixed` header. Uses your own API key. |
| **Share it** | `./go_public.sh` opens a temporary public link (costly calls are rate-limited) |
| **Sarvam's docs** | `SARVAM_API_KEY=… python3 ecosystem/docs_health.py` checks every docs code sample live |
