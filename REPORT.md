# Sudhaar (सुधार): everything we built, explained

This report covers what Sudhaar is, why it exists, how every part works technically,
what we found, and the questions judges are likely to ask, with answers.
Read it once from top to bottom before the showcase.

---

## 1. The one-minute version

**Problem.** Sarvam releases new models quickly (Saarika → Saaras v3 → v4, Bulbul v1 → v2 → v3 → v4 Flash,
Sarvam-M → 30B → 105B) and retires old ones. Code written against older docs then fails with
`400 Bad Request`. We scanned public GitHub and found **42% of checkable projects built on Sarvam (191 of 457)
make at least one call that Sarvam's API rejects today.**

**Solution.** Sudhaar is a tool and a web portal that:
1. **Scans** a project (local folder or any GitHub repo) for Sarvam API calls
2. **Proves** each failure by sending a tiny real request to Sarvam's API (400 before, 200 after the fix)
3. **Fixes** the code automatically and shows the diff
4. **Learns** new rules itself: Sarvam-105B reads Sarvam's changelog, the live API confirms each rule
5. **Explains** the report aloud in Indian languages (Sarvam-105B writes it, Bulbul speaks it)
6. **Answers questions** about the scan in a chat (Sarvam-105B with the scan as context)

**Why it matters to Sarvam.** Every broken repo is a developer who hit an error and may conclude
"Sarvam doesn't work". Sudhaar keeps the developer ecosystem working while Sarvam ships fast.

---

## 2. The problem, with evidence

### 2a. Public bug reports (all real, links in `PROOF.md`)
| Where | What broke |
|---|---|
| livekit/agents #6774 | Rejected 9 valid Bulbul voices, wrong pace range → 400s on v3 |
| mastra-ai/mastra #27090 | Silently sent `saarika:v2.5` whatever model you picked |
| run-llama/llama_index #19931 | Typos in model name and base URL |
| sarvamai/sarvam-mcp #79, #64, #62 | Sarvam's **own** MCP server: TTS failures, vision and batch STT never returning output |
| sarvamai/sarvam-ai-sdk #11, #20 | Sarvam's **own** SDK: OpenAI-compatibility gaps |
| sarvamai/sarvam-ai-cookbook #180 | Odia is `od-IN` on REST but `or-IN` on streaming |
| Sarvam repos | 20+ open `[docs-sync]` issues just to keep SDK, MCP, skills and n8n node current |

### 2b. Is it already solved? No.
- Sarvam's docs-sync bot and the cookbook's model allowlist check only cover **Sarvam's own repos**.
- GitHub search for a Sarvam linter, migrator, doctor or validator found nothing.
- Third-party code (LiveKit, Mastra, LlamaIndex, Pipecat, n8n, student projects) is on its own.

### 2c. Our measurement: 42%
- GitHub code search for `api.sarvam.ai` and `sarvamai` in Python, JavaScript and TypeScript → **911 repos**
  (forks and Sarvam's own org excluded).
- We downloaded the Sarvam-calling files and ran Sudhaar's scanner.
- **457** repos have model names written directly in code, so they can be checked.
- **191 (42%)** contain at least one call the live API rejects. Full list: `ecosystem/broken_repos.md`.

| What breaks | Live API response (1 Nov 2026) | Repos |
|---|---|---|
| `bulbul:v2` | 400 “has been deprecated. Please use ‘bulbul:v3’” | 44 |
| `sarvam-m` | 400 “has been deprecated” | 39 |
| `bulbul:v1` | 400 “Input should be ‘bulbul:v3’ or ‘bulbul:v4-flash’” | 37 |
| `sarvam-30b` | 400 “has been deprecated” | 20 |
| `saarika:v2` / `v1` | 400 “Please use ‘saaras:v3’ instead” | 15 |
| `saaras:v1` / `v2` | 400 validation error | 11 |

**Honest caveats** (say these if asked):
- The sample comes from GitHub code search, not a random sample of all Sarvam users.
- The scan is static: it reads code, it doesn't run it. A repo may never execute the broken line.
- Many repos are old hackathon projects nobody maintains. "Broken" means "would fail if run today".
- Every *rule type* was confirmed live, but we did not run 191 repos end to end.

---

## 3. Architecture

```
                        ┌──────────────────────── BROWSER ────────────────────────┐
                        │  portal.html: chat UI, history saved in localStorage    │
                        └───────────────┬─────────────────────────────────────────┘
                                        │ HTTP (localhost:8000), JSON
                        ┌───────────────▼─────────────────────────────────────────┐
                        │  portal.py: tiny web server (Python standard library)   │
                        │  /api/scan  /api/verify  /api/fix  /api/explain /api/ask│
                        │  API key lives here only, never sent to the browser     │
                        └───────────────┬─────────────────────────────────────────┘
                                        │ calls the same functions as the CLI
┌─────────────── sudhaar.py (the engine, also a command-line tool) ───────────────┐
│                                                                                  │
│  resolve()  ── github:owner/repo → git clone --depth 1 (read only, never run)    │
│  scan()     ── find Sarvam calls in .py/.js/.ts/.json files (regex)              │
│  check_file()── compare each call with the RULES                                 │
│  verify()   ── probe(): tiny live request with the bad value, then the fix       │
│  apply_fixes() rewrite the exact characters, print a unified diff                │
│  learn()    ── changelog → Sarvam-105B → candidate rules → live probe → save     │
│  explain()  ── Sarvam-105B summary in a chosen language → Bulbul audio (.wav)    │
│                                                                                  │
│  RULES = rules.json (from Sarvam's SDK) + DEPRECATED/PACE (live-checked)         │
│          + rules_learned.json (written by learn())                               │
└──────────────────────────────────────────────────────────────────────────────────┘
                                        │
                              api.sarvam.ai (live)
       /v2/chat/completions (Sarvam-105B) · /text-to-speech (Bulbul) ·
       /speech-to-text (Saaras) · /translate (Mayura)
```

**Design choices**
- **Python standard library only.** Nothing to install, nothing to break on stage.
- **One engine, two front ends.** The CLI and the portal call the same functions, so they always agree.
- **The API is the source of truth.** Docs were wrong in five places; we trust the live response.

---

## 4. How each part works

### 4a. Scanner (`scan`, `hits_in`, `check_file`)
1. Walk the folder, keeping `.py .js .mjs .cjs .ts .jsx .tsx .json` files and skipping `node_modules`, `.git`, `venv`.
2. Skip files that never mention `sarvam`, `bulbul`, `saaras`, `saarika` or `mayura`, which makes it fast.
3. One regular expression finds `key = "value"` and `key: value` pairs for the keys that matter:
   `model, speaker, pace, pitch, loudness, speech_sample_rate, output_audio_codec, *language_code`.
   It works for Python keyword arguments, Python dicts, JavaScript objects and JSON alike.
4. **Context:** a `speaker` or `pace` only makes sense next to a TTS model. Each parameter is linked to the
   **nearest model name within 12 lines**. Simple and good enough. The known limit is noted in the code
   (`ponytail:` comment): an AST parser would be the upgrade if it ever misfires.
5. **False-positive guards** (added after testing real repos):
   - Voice parameters are only checked when a literal Bulbul model is nearby. If the model sits in a variable,
     we stay quiet rather than guess.
   - `speaker` must look like a voice id (`shubh`, `simran_hi_news`). Labels like `"IVR"` or `"Dr. Sharma"` in
     chat-UI code are ignored.
   - Open-model ids like `sarvam-2b` are warnings, not errors, because people run them locally.

**Severity levels:** `error` = the live API returns 400 today. `warning` = works today but deprecated or has no
effect. `info` = something to plan for (e.g. Bulbul v3 end of life on Voice Agents on 10 Nov 2026).

### 4b. Rules: where they come from
| Source | What it gives | How it stays current |
|---|---|---|
| `rules.json` | Accepted model ids, all 222 Bulbul v4 voices, language codes per endpoint | Generated from Sarvam's own Python SDK type definitions with `--refresh-rules` |
| `DEPRECATED`, `PACE` in `sudhaar.py` | Dead models and replacements, pace ranges, v2-only parameters | Every entry checked against the live API on 1 Nov 2026 |
| `rules_learned.json` | Rules Sarvam-105B found in the changelog | Written by `--learn`, only after the live API confirms |

The count of 222 v4 voices matched Sarvam's docs exactly, which shows the SDK extraction is accurate.

### 4c. Live verification (`verify`, `probe`)
For each error Sudhaar builds the **smallest possible request** that uses the bad value:
- TTS: `{"text": "नमस्ते", "target_language_code": "hi-IN", "model": ..., <the bad parameter>}`
- Chat: one message, `max_tokens: 5`
- STT: one second of generated silence as a WAV file (built in memory with Python's `wave` module)
- Translate: the word "hello"

It sends the request **twice**: once with the bad value (expect 400) and once with the fix (expect 200).
Each probe costs a few paise. The output shows Sarvam's real error message, so nothing is a guess.

### 4d. Auto-fix (`apply_fixes`)
The scanner records the exact line and character positions of each bad value. The fixer replaces those
characters (or deletes the line, e.g. for `pitch` on bulbul:v3), working bottom-up so positions stay valid,
then prints a standard unified diff. The portal always fixes a **copy**; the original repo is never touched.

### 4e. The learning agent (`--learn`)
```
docs.sarvam.ai/changelog (61 pages)
   → keep only paragraphs mentioning "deprecated / removed / migrate / no longer…"
   → Sarvam-105B: "return ONLY a JSON array of {old, new, evidence, date}"
   → for each candidate: probe old model (expect 400) and new model (expect 200)
        ✓ both as expected → save the rule
        ↻ replacement also fails → read the API's own 400 message, which usually names the
          right model ("Please use 'sarvam-105b'"), probe that instead
        ✗ otherwise → discard
   → rules_learned.json, used by the scanner from then on
```
**Key idea: "the model proposes, the API decides."** In testing Sarvam-105B suggested `sarvam-m → sarvam-30b`,
but `sarvam-30b` is also dead. The API's error message named `sarvam-105b`, Sudhaar retried with that,
and saved the correct rule. A wrong LLM guess can never become a rule.

### 4f. Explain aloud (`explain`)
Sarvam-105B gets the list of errors and writes a short spoken summary in the chosen language;
Bulbul v3 turns it into audio. Two lessons from testing:
- With only the code `hi-IN`, Sarvam-105B answered in **Marathi**. Naming the language ("Reply ONLY in Hindi") fixed it.
- Backticks were read aloud, so they are stripped before speech.

### 4g. Portal (`portal.py` + `portal.html`)
| Endpoint | Does |
|---|---|
| `GET /` | The chat page |
| `GET /dashboard` | The ecosystem health page |
| `GET /api/status` | Is the API key set? |
| `POST /api/scan` | Clone (GitHub only) + scan; returns findings and a session id |
| `POST /api/verify` | Live proof for that session |
| `POST /api/fix` | Fix a copy, return the diff and before/after counts |
| `POST /api/explain` | Sarvam-105B text + Bulbul audio (sent as base64) |
| `POST /api/ask` | Sarvam-105B answers a question using verified facts + the session's findings |

- **Chat logic:** if what you type looks like a repo, it scans; anything else is a question for Sarvam-105B.
- **History** is saved in the browser's `localStorage` (no accounts): the last 20 checks with their reports.
  Reopening is instant. If a saved check has no server session any more, live actions re-scan first.
- **Security choices:** the API key stays on the server; everything from a scanned repo is inserted as plain
  text, never as HTML (a repo can't inject code into the page); only GitHub repos and the bundled sample app
  can be scanned from the portal; cloned code is read, never executed; the server listens on localhost only.

### 4h. Sarvam-105B gotcha we found
On `/v1/chat/completions` Sarvam-105B spent **1,999 of 2,000 tokens reasoning** about "say namaste" and returned
nothing. `/v1` only accepts `reasoning_effort` low/medium/high. **`/v2/chat/completions` with
`reasoning_effort: "none"` answers in 0.2 s.** All of Sudhaar's AI calls use that.

---

## 5. What the live API taught us (1 Nov 2026)
Our first rules came from the docs. The live API corrected five of them:

| Claim | Live result | Now |
|---|---|---|
| `saarika:v2.5` is rejected | 200, still accepted | warning |
| `pitch`/`loudness` break bulbul:v3 | 200, accepted | warning (no effect) |
| `bulbul:v2` is just old | **400, rejected** | error (44 repos!) |
| `bulbul:v3-beta` is invalid | 200 | rule removed |
| Malayalam/Odia fail on v4-flash | 200 | rule removed |

Lesson worth saying on stage: **"We didn't trust the docs. Every rule was confirmed against your live API."**

---

## 6. Files and commands

```
sudhaar/
├── sudhaar.py            engine + CLI
├── portal.py             web server
├── portal.html           chat UI
├── rules.json            from Sarvam's SDK
├── rules_learned.json    from --learn
├── demo_app/             deliberately broken sample (bugs copied from real issues)
├── test_sudhaar.py       self-check
├── ecosystem/            911-repo scan, dashboard, broken_repos.md
├── PROOF.md              public bug reports
├── IDEA.md               plan, demo script, Q&A
└── REPORT.md             this file
```

```bash
cd "/Users/atharv/sarvam ai hackathon/sudhaar"
export SARVAM_API_KEY=...                                  # from the event
python3 portal.py                                          # portal at http://localhost:8000
python3 sudhaar.py github:anyaaa1924/VittBot-GBH --verify  # live proof from the terminal
python3 sudhaar.py demo_app --explain hi-IN                # Hindi audio report
python3 sudhaar.py --learn                                 # learn rules from the changelog
python3 test_sudhaar.py                                    # should print "ok"
pkill -f portal.py                                         # stop the portal
```

---

## 7. The 2-minute demo
1. **(0:00–0:20)** Ecosystem health page: “We scanned 911 public projects built on Sarvam. 42% fail on your API today.”
2. **(0:20–0:40)** Proof slide: LiveKit, Mastra, Sarvam’s own MCP server. “You ship fast; everyone else falls behind.”
3. **(0:40–1:30)** Portal: paste VittBot → findings → **Prove it live** (real 400s, 200 after fix) → **Show the fix**.
4. **(1:30–1:50)** “The rules aren’t hard-coded. Sarvam-105B reads your changelog; your API confirms each rule.”
   Then **Explain aloud in Hindi**, or ask a question in Hinglish.
5. **(1:50–2:00)** “Ship fast. Don’t break developers.”

Backups if Wi-Fi fails: the scan, the fix and the ecosystem page work offline; the live proof needs internet.

---

## 8. Questions judges may ask, with answers

**Product**

1. **Why not just add validation to the Sarvam SDK?**
   That helps new code written with the latest SDK. It doesn't fix the 191 public repos already out there,
   people calling the REST API directly, or wrappers like LiveKit and Mastra with their own stale checks.
   Sudhaar works on any code in any framework.

2. **Who would use this?**
   Developers building on Sarvam (run it before a demo or in CI), framework maintainers (LiveKit, Pipecat),
   and Sarvam itself: run it on release day to see what a change will break, or open fix PRs for affected repos.

3. **Isn't this just a linter?**
   A linter guesses from rules. Sudhaar proves each finding against the live API, learns new rules from the
   changelog with Sarvam-105B, and fixes the code. The proof step is what makes it trustworthy.

4. **What's next?**
   A GitHub Action for CI, a bot that opens tested fix PRs on broken public repos, and a release-day
   "what will this break" report for Sarvam.

**The number**

5. **Is 42% real?**
   It's 191 of 457 checkable public repos, from a code-search sample. Every rule type behind it returned a real
   400 from your API today. Caveats: the sample isn't random, the scan is static, and many repos are old
   hackathon projects. So read it as "a large share of public Sarvam code is stale", not an exact census.

6. **Why only 457 of 911?**
   In the other repos the model name is in a variable or config, so a static scan can't read it. We chose not
   to guess, to avoid false positives.

**Technical**

7. **How does it find the calls?**
   One regular expression for key/value pairs (model, speaker, pace, language codes…) across Python, JS, TS and
   JSON, plus a context rule linking each parameter to the nearest model name within 12 lines.

8. **What about false positives?**
   We tested on real repos and found three kinds (UI labels named "speaker", models in variables, open models
   run locally) and added guards for each. Anything uncertain is skipped or shown as a warning, not an error.

9. **How does the learning agent avoid hallucinated rules?**
   Sarvam-105B only proposes. A rule is saved only if the old model returns 400 and the new one returns 200 on
   the live API. When the model guesses a wrong replacement, Sudhaar reads the API's own error message, which
   names the right model, and tests that.

10. **How do the rules stay current?**
    Model ids, voices and language codes are generated from Sarvam's SDK. Deprecations are learned from the
    changelog and confirmed live.

11. **Why Python standard library only?**
    Zero install, nothing to break during a live demo, easy to drop into any CI.

12. **Is it safe to scan someone's repo?**
    Yes. It's a shallow read-only clone; the code is never executed. Fixes are applied to a copy.

13. **Where is the API key?**
    Only on the server, in an environment variable. It's never written to a file or sent to the browser.

14. **What did you learn about Sarvam's own API?**
    Three things worth reporting: Sarvam-105B on `/v1` can spend its whole token budget on reasoning and return
    nothing (`/v2` with `reasoning_effort: "none"` fixes it); with only `hi-IN` it sometimes answers in Marathi;
    and `saarika:v2.5` is gone from the SDK but still accepted by the API.

15. **How did you use Sarvam's models?**
    Sarvam-105B (learning rules from the changelog, chat answers, spoken summaries), Bulbul (audio),
    and the live STT, TTS, chat and translate endpoints for proof.

**Tough ones**

16. **Couldn't Sarvam build this in a day?**
    The code is small on purpose. The value is the insight (42% broken, with the list) and the approach:
    prove it live, learn from the changelog. Happy to hand it over.

17. **Aren't you criticising Sarvam?**
    No. Shipping fast is good. This keeps the developer ecosystem working while you do it.

18. **What if a repo builds the model name dynamically?**
    Static analysis can't see it, so we skip it rather than guess. A runtime check (wrapping the SDK) would be
    the next step.

19. **Does it handle streaming and WebSockets?**
    It flags wrong streaming model ids (e.g. `saaras:v4-realtime`) and the `or-IN` vs `od-IN` difference, but
    live proof covers REST endpoints only today.

20. **What took the longest?**
    Making the claims honest: testing against the live API, which corrected five doc-based rules and brought
    the number from guesses to confirmed failures.

---

## 9. Limitations (be upfront)
- Static analysis: models in variables or config files are skipped.
- The 12-line context window can link a parameter to the wrong call in very dense code.
- Live proof covers REST endpoints (chat, TTS, STT, translate), not streaming.
- The portal keeps scan sessions in memory; restarting the server forgets them (history in the browser survives).
- The learning agent relies on Sarvam-105B returning valid JSON; it retries once and fails safely.

---

## 10. Glossary
| Term | Meaning |
|---|---|
| **400 / 200** | HTTP status codes. 400 = the server rejected the request (bad input). 200 = success. |
| **Deprecated** | Retired by the provider; may still work for a while, or may already be rejected. |
| **STT / TTS** | Speech-to-text (Saaras) / text-to-speech (Bulbul). |
| **REST endpoint** | A URL you send a request to, e.g. `api.sarvam.ai/text-to-speech`. |
| **Static analysis** | Reading code to find problems without running it. |
| **Regex** | Regular expression, a pattern for finding text. |
| **Unified diff** | Standard "red/green" format showing removed and added lines. |
| **Shallow clone** | Downloading only the latest version of a repo (`git clone --depth 1`). |
| **localStorage** | Browser storage for a site; survives reloads, private to that browser. |
| **CI** | Continuous integration: checks that run automatically on every code change. |
| **Changelog** | Sarvam's dated list of product and API changes (docs.sarvam.ai/changelog). |
| **reasoning_effort** | How much a reasoning model "thinks" before answering; `none` = answer directly. |
