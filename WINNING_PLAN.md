# Sudhaar: project audit, new evidence and the features that make it essential

*Written 1 Nov 2026, 15:05, during the event. Everything marked "live" was tested against api.sarvam.ai today.*

Sarvam's own slide today: **Idea** (start with a real problem) → **Builder** (experiment, prototype, learn, *ship*)
→ **Product** (*put value in people's hands: useful, reliable, shipped*).
We nailed box 1. This document is about boxes 2 and 3.

---

## Status at 15:25: everything in Tier 1 and Tier 2 is built and tested
- **F1 Write it right**: grounded Sarvam-105B → fix → every model/voice called live → verified stamp.
- **F2 Paste code** + scanner upgrades: all 5 AI-written samples caught (9 failures); self-check covers them.
- **F3 Docs health**: 8 of 159 docs pages fail live, each with a one-line fix.
- **F4 Agent Skill + MCP server**: `skills/sudhaar/SKILL.md`, `mcp_server.py` (tested over stdio).
- **F5 CI gate**: `action.yml`, `.pre-commit-hooks.yaml`, `examples/github-workflow.yml`; CLI takes many files, exits 1.
- **F6 Self-healing proxy**: same broken request, direct → 400, through Sudhaar → 200 with 5 fixes reported.
- **F7 Public link**: rate limiting built and tested; `go_public.sh` ready, **not started** (needs your OK).
- Ecosystem re-measured with the new rules: **191 of 457 checkable repos (42%)**; slides, dashboard and list updated.
- Tier 3 (PR bot, alerts, badge, impact simulator, voice input) stays on the roadmap slide.

## 0. TL;DR

**Three new findings from today (all live-verified):**
1. **Sarvam-105B writes broken Sarvam code.** We asked it 5 times to write code for Sarvam's APIs.
   **All 5 samples fail on Sarvam's own API**: it invented model names (`sarvam-tts`, `sarvam-text-to-speech`,
   `sarvam-stt`, `sarvam-chat`), used `saarika` and `sarvam-1`, and the retired voice `meera`. Every one returned 400.
2. **Sarvam's own docs contain code samples that fail.** Of 159 docs pages with code, **8 have samples the live API
   rejects**, including **Getting started → "Building for India"**, two **cookbook voice agents** (one uses a voice that
   doesn't exist), and three TTS how-to pages that teach the deprecated `bulbul:v2`.
3. **Sarvam already knows the root cause.** Their docs ship "Agent Skills" because *"an assistant's training data goes
   stale"*. But skills only *teach*. Nothing *verifies* the result.

**New positioning:** *"Skills teach. Sudhaar verifies."* In 2026 most code is written by AI assistants, and they
write Sarvam code from stale memory. Sudhaar is the check that makes AI-written Sarvam code actually run.
That turns a nice-to-have linter into an essential step.

**Build in the 60-minute build-along (ranked):**
1. **"Write it right"**: ask Sudhaar for code; Sarvam-105B writes it, Sudhaar scans, fixes and *proves it live*
   before you see it. (~25 min, biggest wow, uses Sarvam-105B for real)
2. **Paste any code** (not just repos) + catch the misses this research exposed. (~15 min)
3. **Docs health tab**: Sarvam's own docs samples, checked live. (~10 min, the script already exists)

---

## 1. Honest audit of the project so far

### What's strong
| | Why it works |
|---|---|
| Real, measured problem | 191 of 457 checkable public repos (42%) fail today; every rule confirmed live |
| Proof, not guesses | `--verify` shows Sarvam's real 400 and the 200 after the fix |
| Learning agent | Sarvam-105B reads the changelog; the live API decides; the API's own error corrects bad guesses |
| Portal | Clean chat UI, history in the browser, Hindi voice, follow-up Q&A |
| Credibility | We corrected our own rules when the API disagreed (5 corrections) |

### What's weak (and what fixes it)
| Weakness | Why it matters to judges | Fix |
|---|---|---|
| Feels like a "linter", a one-off tool | "Useful" but not "essential" | Position on AI-written code (findings 1 & 3); add the generate→verify loop |
| Not *in use* by anyone | The slide's box 3: "In use. Shipped." | Let the room use it (QR + public link), or show fixes already prepared for real repos |
| Static gaps this research exposed | Misses real failures | See §4, F2: constants like `TTS_MODEL = "sarvam-tts"`, retired voices like `meera` without a model nearby, `.ipynb` notebooks skipped |
| Only runs on the laptop | Judges can't try it themselves | Public link (F7), or at least a phone-sized layout |
| 533 of 911 repos uncheckable (model in variables/config) | The 42% can be questioned | Runtime proxy (F6) covers dynamic names; scanning constants and `.env` raises coverage |
| Data files flagged as bugs | False positives on Sarvam's own allowlist/test files | Skip files that *list* ids (rules, tests) or downgrade them to info |

### Demo risks today
- Wi-Fi: live proof, cloning and Sarvam-105B need internet. The ecosystem page and the sample app work offline.
- First clone of a repo takes 5–10 s; use the pre-tested ones (VittBot, sample app).
- Sarvam-105B occasionally returns empty text; Sudhaar retries once and shows an error instead of hanging.

---

## 2. New evidence in detail

### 2a. Sarvam-105B's Sarvam code (5 prompts, `/v2/chat/completions`, every id probed live)
Prompts explicitly asked for "the model and speaker parameters explicitly". Files saved in `evidence/ai_written/`.

| Prompt | What Sarvam-105B wrote | Live API |
|---|---|---|
| Hindi TTS with requests | `model="sarvam-text-to-speech"`, `speaker="meera"`, old `inputs` field | 400 "should be 'bulbul:v3' or 'bulbul:v4-flash'"; 400 "Speaker 'meera' is not recognized" |
| Hindi STT with requests | `model="saarika"` | 400 "Input should be 'saarika:v2.5', 'saaras:v3', …" |
| Node.js chat | `model="sarvam-1"` | 400 "should be one of sarvam-105b, sarvam-105b-conversations" |
| Tamil TTS with the SDK | `model="sarvam-text-to-speech"`, `speaker="meera"` | 400 (both) |
| Voice assistant (STT→chat→TTS) | `sarvam-stt`, `sarvam-chat`, `sarvam-tts` | 400 (all three) |

**5 of 5 fail.** Small sample, so say "in our test", but the pattern is clear: models write Sarvam code from memory,
and the memory is wrong. Sudhaar's scanner caught 3 of the 5 today; F2 below closes the gap for the other 2
(ids stored in `*_MODEL` constants and retired voices without a model nearby).

### 2b. Sarvam's docs (204 pages indexed, 161 with code; each pair probed live, snippets read by hand)
| Docs page | Code sample says | Live API |
|---|---|---|
| Getting started → Building for India | `model="bulbul:v4-flash"`, `speaker="shubh"` | 400 "Speaker 'shubh' is not compatible with model bulbul:v4-flash" |
| Cookbook → Loan advisory voice agent (6 snippets) | `bulbul:v4-flash` with `aditya`, `anand`, `priya` | 400 (v3 voice names on v4) |
| Cookbook → Tutor voice agent (6 snippets) | `bulbul:v4-flash` with `ishita_en_edtech` | 400 "Speaker 'ishita_en_edtech' is not recognized" (no such voice) |
| STT use case → EdTech | `bulbul:v4-flash` with `ishita` | 400 |
| TTS how-to → Adjust the loudness | `bulbul:v2` (page: "loudness is only supported for bulbul:v2") | 400 "Model 'bulbul:v2' has been deprecated" |
| TTS how-to → Adjust the tone | `bulbul:v2` | 400 |
| TTS how-to → Enable text preprocessing | `bulbul:v2` | 400 |
| TTS → REST API guide | `bulbul:v4-flash` with `priya`, `roopa` | 400 (confirmed with strict one-model-per-block pairing) |

Not counted: the deprecated model pages (`sarvam-m`, `sarvam-30b`), which are labelled deprecated on purpose, and
blocks that mix v3 and v4 examples (voices are only paired when a block names exactly one Bulbul model).
Re-run any time: `SARVAM_API_KEY=… python3 ecosystem/docs_health.py` (portal → Docs health).

**The pattern is exactly our thesis:** the docs moved examples to `bulbul:v4-flash` but kept v3 voice names.
A migration where the examples got left behind, inside Sarvam's own docs.

### 2c. Sarvam's own GitHub repos (cookbook, MCP, skills, SDK, n8n node, eval tools)
**Clean.** Every flag was a false positive: allowlist files and tests that *list* deprecated ids on purpose.
Credit them: their CI works for their repos. The gap is everything outside their repos, and their docs website.

### 2d. Sarvam's own framing (docs → Developer tools → Agent Skills)
> "An assistant's training data goes stale, and Sarvam's SDK has a few patterns that don't match what a model expects."

They ship skills (Markdown that coding agents read) for Claude Code, Cursor and Windsurf. **Sarvam Code is
"coming soon"**, which means AI-written Sarvam code is about to become the main way people build on Sarvam.
Skills reduce mistakes; they can't prove the code works. That is Sudhaar's slot.

---

## 3. The new story (use this on stage)

> "Everyone in this room built with Sarvam today, and most of us used an AI assistant to write the code.
> We asked Sarvam-105B to write Sarvam API code five times. **All five fail on Sarvam's own API.**
> Sarvam's docs have the same problem: eight pages, including Getting Started, have samples that return 400 today.
> And 42% of public projects built on Sarvam are already broken.
> **Skills teach. Sudhaar verifies.** Paste any code or repo, and Sudhaar finds what will fail,
> proves it against the live API, and fixes it. Or ask it to write the code, and you only get code that's been proven to run."

---

## 4. Feature research: what makes Sudhaar essential

Scored on **impact** (judges, real users), **effort** (minutes), and **fit** with Sarvam's own direction.

### Tier 1: build in the build-along (highest impact per minute)

**F1. "Write it right" (generate → check → fix → prove), ~25 min, ★★★★★**
- User types: *"write Python code for Hindi text-to-speech"*.
- Sarvam-105B writes code (with Sudhaar's verified facts in the prompt) → Sudhaar scans it → auto-fixes →
  live-probes every Sarvam call → shows the code with a **"✓ Verified on Sarvam's API, 1 Nov, 15:42"** stamp,
  plus what it corrected ("the model wrote `meera`; that voice was retired, changed to `shubh`").
- Why essential: it turns Sudhaar from "find old bugs" into "**never ship a broken Sarvam call**".
  An agentic loop (fits the Indus "agentic platform" message) that uses Sarvam-105B for real work.
- Reuses: `ask_105b`, `check_file`, `apply_fixes`, `probe`. New: one `/api/write` endpoint + UI.

**F2. Paste any code + close the gaps found today, ~15 min, ★★★★☆**
- Portal: if the message contains code (multi-line, `model=` …), scan it as a snippet. Works for private repos
  and for AI-written code copied from any assistant.
- Scanner upgrades the research exposed:
  - constants: `TTS_MODEL = "sarvam-tts"`, `STT_MODEL = …`, `model_name = …`
  - retired voices anywhere near TTS code: `meera`, `arvind`, `amol`, `maitreyi`, `pavithra`, `amartya`, `diya`,
    `neel`, `misha`, `vian`, `arjun`, `maya` (all rejected live)
  - invented ids: anything starting `sarvam-`/`bulbul`/`saaras` that isn't a real model is already an error;
    route `sarvam-tts`/`sarvam-text-to-speech` to the TTS family instead of chat
  - `.ipynb` notebooks (very common in AI code; the research script already converts them)
- Demo: paste `evidence/ai_written/voice_agent.py`, which Sarvam-105B wrote: 3 failures, fixed, proven.

**F3. "Sarvam docs health" tab, ~10 min, ★★★★☆**
- A page next to "Ecosystem health": 161 docs pages checked, 7 with failing samples, each with the exact fix
  (`shubh` → `shubh_enhi_ads` on v4-flash, etc.).
- Why: it's the most *useful* thing we can hand Sarvam's team today, and it shows Sudhaar works on any text
  (docs, blogs, tutorials), not just repos. Frame it kindly: "here are 7 one-line fixes".

### Tier 2: what makes it a habit (essential, not one-off)

**F4. Agent Skill + MCP tool, ~10 min (skill) / ~40 min (MCP), ★★★★☆**
- A `sudhaar` skill in the same Agent Skills format Sarvam already uses: *"Before finishing any code that calls
  Sarvam, run `python3 sudhaar.py <path> --verify` and fix every error."* Works today in Claude Code, Cursor,
  Windsurf, and is ready for Sarvam Code when it launches.
- Later: an MCP server exposing `sudhaar_check`, `sudhaar_verify`, `sudhaar_fix`, next to Sarvam's own MCP server.
- Pitch line: "Sarvam's skills teach the agent; Sudhaar's skill makes the agent prove it."

**F5. CI gate: GitHub Action + pre-commit hook, ~15 min, ★★★☆☆**
- `uses: sudhaar/check@v1` runs on every pull request; fails the build on errors. The CLI already exits 1 on errors.
- Essential for teams: broken Sarvam calls never reach main.

**F6. Self-healing proxy, ~35 min, ★★★★☆ (strong idea, riskier to demo)**
- Change one line (`base_url` → Sudhaar). Sudhaar forwards to api.sarvam.ai but rewrites dead model ids and
  incompatible voices using live-confirmed rules, adds a header `X-Sudhaar-Fixed: bulbul:v2→bulbul:v3`, and logs it.
- Why: covers the 533 repos where the model is in a variable (static scans can't see those), and production apps
  keep running on the day Sarvam deprecates something.
- Risk: silent rewriting can surprise people; only confirmed rules, always reported.

**F7. Put it in people's hands today, ~10–20 min, ★★★★★ (needs your OK)**
- A public link + QR code on the last slide: *"Everyone here built a Sarvam app today. Scan this, paste your repo."*
  The audience uses it during the showcase: box 3 of Sarvam's slide, live.
- Fastest route: a temporary tunnel from the laptop (e.g. `ssh -R 80:localhost:8000 localhost.run`, no install).
  Needs: rate limiting (protect the API credits) and your explicit go-ahead, since it makes the portal public.

### Tier 3: roadmap slide (mention, don't build)
- **F8. Fix-PR bot**: open tested fix PRs on the 191 broken public repos (only with consent).
- **F9. Deprecation watch**: subscribe a repo; get notified when Sarvam's changelog affects your code.
  (Bulbul v3 voice agents end on 10 Nov, 9 days from now.)
- **F10. "Sarvam-ready ✓" README badge**: shows the repo passed Sudhaar today; a growth loop.
- **F11. Release-impact simulator for Sarvam**: "if we deprecate X, these public repos and docs pages break."
- **F12. Voice input**: speak to Sudhaar in Hindi (Saaras STT).

---

## 5. Recommended build-along plan (60 min)

| Min | Build | Done when |
|---|---|---|
| 0–15 | **F2** paste-code + constants + retired voices + TTS family for invented ids | Pasting `evidence/ai_written/voice_agent.py` shows 3 failures |
| 15–40 | **F1** "Write it right" endpoint + UI card | Asking for "Hindi TTS code" returns code with a live ✓ stamp and a "what we corrected" list |
| 40–50 | **F3** docs health tab (reuse the research script, save results as JSON, render like the ecosystem page) | Tab shows 7 pages with fixes |
| 50–60 | Rehearse the new 2-minute story twice | Under 2:10, both times |

If time is left, or instead of F3: **F7** (needs your OK) or the **F4** skill file.

---

## 6. New 2-minute demo
1. **(0:00–0:25) The hook:** "We asked Sarvam-105B to write Sarvam code five times. All five fail on Sarvam's own API.
   Your docs have eight pages like that. And 42% of public Sarvam projects are broken." (one slide, three numbers)
2. **(0:25–1:10) Write it right:** type *"Hindi text-to-speech in Python"* → Sudhaar shows what the model got wrong,
   fixes it, and stamps **✓ verified live**. Press play on the audio it generated.
3. **(1:10–1:35) Any code:** paste a repo (VittBot) → live 400s → fix.
4. **(1:35–1:50) Essential:** "Skills teach. Sudhaar verifies. As a skill, in CI, or as a proxy."
5. **(1:50–2:00) Close:** "Ship fast. Don't break builders."

---

## 7. New judge questions
| Question | Answer |
|---|---|
| Are you saying our docs are wrong? | Eight pages have samples that return 400 today, mostly v3 voice names left in v4 examples. Here are the one-line fixes. It's the same migration drift everyone faces, and it shows why automated checking matters. |
| Isn't Agent Skills enough? | Skills reduce mistakes; they can't prove code runs. In our test Sarvam-105B still wrote 5/5 failing samples. Sudhaar checks and proves. They work together. |
| Why does Sarvam-105B write wrong ids? | Like every model, it learned from older public code, and 42% of public Sarvam code is outdated. Sudhaar breaks that loop: verified rules go into the prompt, and the output is checked live. |
| Only 5 samples? | Yes, a quick test today, so we say "in our test". Every one failed, and the failures repeat the same stale ids we see in public repos. |
| How is "Write it right" different from just asking the model? | The model writes; Sudhaar refuses to hand it over until every Sarvam call returned 200 on the live API. |

---

## 8. Optional task for GPT
*"Here's a hackathon pitch for Sarvam AI judges: [paste section 3]. Act as a skeptical Sarvam engineer.
What's the weakest claim, and how would you attack it? Suggest one sharper opening line."*

---

## Appendix: raw evidence
- `evidence/ai_written/`: the 5 files Sarvam-105B wrote, unedited
- `evidence/research_results.json`: full output of the experiments
- `ecosystem/broken_repos.md`: the 191 public repos
- `PROOF.md`: public bug reports
