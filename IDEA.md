# Sudhaar (सुधार): the full plan

**Event:** Sarvam Campus '26 x IIT Bombay, 1 Nov 2026, 2:00–5:00 PM, Hostel 4. Individual, offline.
**Format:** 60 min build-along (~3:15–4:15 PM) → 15 min showcase (~4:15) → top 3 present on stage.
**Theme:** "Build with Sarvam AI": solve a real problem with Sarvam's models and APIs.

---

## 1. The pitch, in one line

> **"42% of public projects built on Sarvam are broken right now, and nobody knew.
> Sudhaar finds them, proves it against your live API, fixes them, and learns new rules from your changelog by itself."**

---

## 2. The problem (with proof)

Sarvam ships fast: Saarika → Saaras v3 → v4, Bulbul v1 → v2 → v3 → v4 Flash, Sarvam-M → 30B → 105B.
Every release quietly breaks code that was written against the older docs.

### 2a. Our own measurement (done 1 Nov 2026, 11:30 AM)
We pulled **911 public GitHub repos** that call Sarvam (GitHub code search, forks excluded, Sarvam's own org excluded)
and ran Sudhaar's scanner on them.

- **457** repos have Sarvam model ids written directly in code (the ones we can check statically)
- **191 of them (42%)** contain calls that would fail against today's API
- **Every rule type behind this number was confirmed live on 1 Nov** (real 400 from api.sarvam.ai, 200 after the fix).

| What's broken (live API response) | Repos |
|---|---|
| `bulbul:v2`: 400 "has been deprecated. Please use 'bulbul:v3'" | 44 |
| `sarvam-m`: 400 "has been deprecated" | 39 |
| `bulbul:v1`: 400 "Input should be 'bulbul:v3' or 'bulbul:v4-flash'" | 37 |
| `sarvam-30b`: 400 "has been deprecated" | 20 |
| `saarika:v2` / `v1` / `flash`: 400 "has been deprecated. Please use 'saaras:v3'" | 15 |
| `saaras:v1` / `saaras:v2`: 400 validation error | 11 |
| Invalid speaker for the Bulbul model in use: 400 | 4 |

### 2a-bis. What the live API corrected (1 Nov, with the event key)
Our docs-based rules were wrong in places. The live API is the source of truth now:
- `saarika:v2.5` is **still accepted** (200) → warning, not error.
- `pitch` / `loudness` on bulbul:v3/v4 are **accepted** (200) → warning (docs say no effect), not error.
- `bulbul:v2` is **rejected** (400) → upgraded to error. `bulbul:v3-beta` is accepted (200) → rule removed.
- Malayalam / Odia on bulbul:v4-flash work (200) → rule removed. `opus` fails only at the default 22050 Hz.
- Sarvam-105B on `/v1` spent **1999 of 2000 tokens reasoning on "say namaste"** and returned nothing.
  Fix: `/v2/chat/completions` with `reasoning_effort: "none"` (0.2 s). A finding worth telling Sarvam.
- Asked for `hi-IN`, Sarvam-105B answered in **Marathi** until the prompt named "Hindi" (language confusion, cookbook #67).

Many are **student hackathon projects** (SIH 2K26, Hack4Bengal, IIT assignments), the same people in this room.
Raw data: `ecosystem/summary.json`; reproduce with `ecosystem/eco_fetch.py` + `ecosystem/eco_scan.py`.

**Caveats (say them if asked):** the sample comes from code search, not a random sample. Detection is static.
A few hits (`sarvam-1`, `sarvam-2b`) may be locally run open models, not API calls. Treat it as "roughly 40%+,
confirmed live with `--verify`."

### 2b. Public bug reports (full list with links: `PROOF.md`)
- **LiveKit agents #6774:** rejects 9 valid Bulbul speakers, wrong pace range → 400s on v3
- **Mastra #27090:** silently sends `saarika:v2.5` whatever model you pick
- **LlamaIndex #19931:** typos in model name / base URL
- **Sarvam's own MCP server #79, #64, #62:** TTS always fails on v3; vision and batch STT never return output
- **Sarvam's own SDK #11, #20:** OpenAI-compatibility gaps, streaming usage never reported
- **Cookbook #180:** Odia is `od-IN` on REST but `or-IN` on streaming
- **20+ open `[docs-sync]` issues** across Sarvam's SDK, MCP server, skills and n8n node

### 2c. Is it already solved? No.
- Sarvam's docs-sync bot and the cookbook's model-allowlist CI only cover **Sarvam's own repos**.
- GitHub search for sarvam lint / migrate / doctor / validator found nothing. The one repo named
  "sarvam_doctor" is an unrelated doctor–patient translator.
- Third-party code (LiveKit, Mastra, LlamaIndex, Pipecat, n8n, every student project) is on its own.

### 2d. Why it matters to Sarvam
Every broken repo is a developer who hits a 400 and decides "Sarvam doesn't work."
That hurts Sarvam's developer funnel, the startup program, and campus events like this one.

---

## 3. Why this wins (what the judges care about)

| What makes Sarvam judges say "must win" | How Sudhaar delivers it |
|---|---|
| Tells them something they didn't know about their own product | "42% of public Sarvam code is broken", a number they don't have |
| Uses their models for real work, not as a gimmick | Sarvam-105B reads their changelog and learns new rules; rewrites code; explains in Hindi via Bulbul |
| Unique in the room | Everyone else builds a voice bot or form helper. We fix their ecosystem. |
| A live "wow" moment | "Give me any GitHub repo" → scanned, proven, fixed in about 30 s |
| They'd use it after the event | Run it in CI and on every release; point it at the cookbook and SDK repos |

**Tone on stage:** we're *helping* Sarvam ship fast without breaking developers. We're not criticising them.

---

## 4. What it is

```
                 ┌──────────────── Sarvam changelog / docs (llms.txt) ───────────────┐
                 │                                                                    │
                 ▼                                                                    │
  ┌──────────────────────────┐   candidate rules   ┌──────────────────────────┐       │
  │ RULE LEARNER (agent)     │ ──────────────────▶ │ LIVE PROBE               │       │
  │ Sarvam-105B reads the    │                     │ tiny real API call:      │       │
  │ changelog → JSON rules   │ ◀─── confirmed ──── │ old value 400? new 200?  │       │
  └──────────────────────────┘                     └──────────────────────────┘       │
                 │ rules_learned.json   + rules.json (from Sarvam's SDK types)          │
                 ▼                                                                    │
  ┌──────────────────────────┐   issues   ┌──────────────┐   patch   ┌────────────┐   │
  │ SCANNER (Py / JS / TS)   │ ─────────▶ │ VERIFY live  │ ────────▶ │ FIX + diff │   │
  │ local dir or GitHub repo │            │ before/after │           │ re-scan ✓  │   │
  └──────────────────────────┘            └──────────────┘           └────────────┘   │
                 │                                                                    │
                 ├──▶ EXPLAIN: Sarvam-105B summary in Hindi → Bulbul reads it aloud    │
                 └──▶ ECOSYSTEM DASHBOARD: % broken across 911 public repos ◀──────────┘
```

### Components and status

| # | Component | Status | Command |
|---|---|---|---|
| 1 | **Scanner:** Python/JS/TS, 10+ rule types | ✅ built, tested on demo app | `python3 sudhaar.py demo_app` |
| 2 | **Rules from Sarvam's SDK:** models, 222 v4 voices, language codes | ✅ built | `--refresh-rules` |
| 3 | **Auto-fix + diff** (9/10 demo errors) | ✅ built, tested | `--fix` |
| 4 | **Live verify:** 400 before, 200 after | ✅ tested live on demo app + VittBot | `--verify` |
| 5 | **Explain in Hindi:** Sarvam-105B + Bulbul | ✅ tested live (22 s Hindi audio) | `--explain hi-IN` |
| 6 | **Scan a GitHub repo by URL** | ✅ built, tested on 5 real repos | `github:owner/repo` |
| 7 | **Ecosystem dashboard** (HTML from `summary.json`) | ✅ built | `python3 ecosystem/dashboard.py` → `ecosystem/dashboard.html` |
| 8 | **Rule learner agent:** Sarvam-105B reads changelog → rules → live-confirmed | ✅ tested live: 5 rules confirmed (~60 s); API error text corrects bad LLM guesses | `--learn` |
| 9 | Slides (7, speaker notes = pitch script) | ✅ built | https://claude.ai/artifact/8hyEGBVTcL4qfd32URFx6v |
| 10 | Self-check test | ✅ passes | `python3 test_sudhaar.py` |
| 11 | **Web portal (chat-style, light, Cowork-like):** paste a repo → scan, prove live, fix diff, explain aloud, follow-up questions answered by Sarvam-105B with the scan as context, ecosystem page | ✅ built, every button tested live in the browser | `python3 portal.py` → http://localhost:8000 |

### Sarvam APIs used (for the "built with Sarvam" requirement)
- **Sarvam-105B** (`/v1/chat/completions`): rule learning from the changelog, the explanation, code rewrite fallback
- **Bulbul** (`/text-to-speech`): spoken Hindi report, plus live probes
- **Saaras** (`/speech-to-text`): live probes for STT rules
- **Mayura** (`/translate`): live probes for translate rules
- **Sarvam's own SDK types + docs `llms.txt`**: rules stay in sync with Sarvam automatically

---

## 5. Design details (for building at medium effort)

### 5a. Scan a GitHub repo by URL (component 6)
- Accept `github:owner/repo` or `https://github.com/owner/repo` as the path.
- `git clone --depth 1` into a temp dir, then run the normal `scan()`. Never execute anything from the clone.
- Print relative paths and link each issue to `https://github.com/owner/repo/blob/HEAD/<path>#L<line>`.
- ✅ Built: `python3 sudhaar.py github:owner/repo` (or a GitHub URL). Issues print with a GitHub line link.

**Demo repos, checked by hand on 1 Nov (real public projects):**
1. `github:anyaaa1924/VittBot-GBH` (Python, 2 errors + 2 warnings, **live-verified 400 → 200**): STT `saarika:v2`, TTS `bulbul:v1`. Best for stage.
2. `github:alwinjosegeorge/KisanQueue` (TypeScript, 6 errors): a farmer IVR app; `bulbul:v1` + pitch/loudness in 2 functions.
3. `github:DevAgarwal2/sarvamai-skills` (Python, 6 errors + 2 warnings): a "skills" repo that **teaches AI coding agents** dead ids
   (`sarvam-m`, `saarika:v2.5`, v1 speakers `meera`/`arvind`). Good line: "even the docs agents learn from are stale."
- Avoid `ravitejabolla756-sys/Bavio-Ai-v1` on stage: `bulbul-v3`/`saaras-v3` may be internal router keys.
- False-positive guard added: voice params only count next to a literal Bulbul model, and `speaker` must look like a voice id.
- Possible extra rule (not built): legacy TTS field `"inputs": [text]` (now `"text"`), seen in VittBot.

### 5b. Ecosystem dashboard (component 7)
- One static HTML file generated from `summary.json`: the headline "191 of 457 (42%)", a bar list by rule, and 2–3 example repos per rule.
- Works offline on the projector. Light and dark mode. Also the first slide.

### 5c. Rule learner (component 8, the "AI" part)
1. Fetch `https://docs.sarvam.ai/changelog/llms.txt` → list of dated entries → fetch the last ~30 `.md` pages.
2. Ask Sarvam-105B for **JSON only**, one object per breaking change:
   `{"kind": "deprecated_model" | "param_range" | "param_removed" | "speaker_set", "endpoint", "old", "new", "evidence": "<quote>", "date"}`
3. Validate each candidate with the existing `probe()`: the old value must fail and the new value must return 200. Keep only confirmed rules.
4. Write `rules_learned.json`; the scanner merges it into `DEPRECATED` / `PACE` at load time.
5. Demo line: "This rule wasn't written by me. Sarvam-105B learned it from your changelog, and your API confirmed it."
- Known risk: Sarvam-105B can spend its token budget on reasoning and return empty content. Use a high `max_tokens`,
  strip `<think>`, retry once, and fall back to "no new rules" without crashing.

### 5d. Live verify (component 4)
- Each error → the smallest request with the bad value, then with the fixed value. Costs a few paise.
- If the live API **accepts** something the docs call invalid, downgrade that rule to a warning. That's also a finding worth reporting to Sarvam.

---

## 6. Timeline

### Now → 1:45 PM (prep, no key needed)
1. Repo-by-URL scan (5a)
2. Ecosystem dashboard (5b)
3. Rule learner code (5c), untested
4. Pick 3 real demo repos and check their findings by hand
5. Slides + pitch script
6. Laptop charged; `cd sudhaar`; terminal font large

### 2:00–3:15 PM (intro, Q&A, demos)
- Collect Sarvam credits / API key as soon as they're handed out: `export SARVAM_API_KEY=...`
- In the Q&A, ask one sharp question: *"How do you keep third-party integrations in sync when you deprecate models?"*
  Their answer becomes a line in your pitch.

### 3:15–4:15 PM (build-along, 60 min)
| Minutes | Task |
|---|---|
| 0–10 | `--verify` on `demo_app`. Fix any rule the live API disagrees with. |
| 10–20 | `--explain hi-IN`, check the audio plays |
| 20–40 | Rule learner end to end: `--learn`, confirm at least 1 rule learned + live-confirmed. If possible, build part of it with **Sarvam Code** and say so on stage. |
| 40–50 | Dry-run the demo on the 3 chosen real repos |
| 50–60 | Rehearse the 2-minute pitch twice, out loud |

### 4:15 PM showcase → see section 7

---

## 7. The 2-minute demo script

1. **(0:00–0:20) Hook:** dashboard on screen.
   "We scanned 911 public GitHub projects built on Sarvam. 42% of the ones we could check will fail on your API today.
   Many are student hackathon projects, people like everyone in this room."
2. **(0:20–0:40) Proof:** 3 issue screenshots: LiveKit, Mastra, Sarvam's own MCP server.
   "It even happens in your own repos. This isn't anyone's fault. You ship fast, and everyone else falls behind."
3. **(0:40–1:30) Live (portal at localhost:8000; terminal as backup):**
   - `python3 sudhaar.py github:<real-repo> --verify` → red lines, **live 400s from your API**
   - `--fix` → diff → re-run → **200 OK ✓**
   - "Give me any repo." (If a judge gives one, scan it. If not, use backup repo #2.)
4. **(1:30–1:50) The AI part:**
   "These rules aren't hard-coded. Sarvam-105B reads your changelog, writes the rule, and your own API confirms it."
   Then `--explain hi-IN` → Bulbul speaks the report in Hindi.
5. **(1:50–2:00) Close:**
   "Ship fast. Don't break developers. Run Sudhaar on every release."

---

## 8. Slides (5)
1. **"42% of public Sarvam code is broken today"**: dashboard number + bar chart
2. **Proof:** 4 real issue screenshots (LiveKit, Mastra, Sarvam MCP, docs-sync count)
3. **How it works:** the diagram from section 4
4. **Live demo** (switch to terminal)
5. **Impact + what's next:** CI action, a GitHub bot that opens fix PRs, a release-day ecosystem report for Sarvam

---

## 9. Judge Q&A prep

| Likely question | Answer |
|---|---|
| "Couldn't we just add validation in our SDK?" | That helps new code. It doesn't fix the 191 repos already out there, or LiveKit/Mastra wrappers with their own stale checks. This works on any code, in any framework. |
| "How do you know these really fail?" | `--verify` calls your live API: old value → 400, fix → 200. Nothing is guessed. |
| "Your rules will go stale too." | Enumerable rules come from your SDK types (`--refresh-rules`). Behavioural rules are learned from your changelog by Sarvam-105B and live-confirmed. |
| "Is 42% real?" | Static scan of a code-search sample, 457 checkable repos. Detection is conservative. A few may be local model usage. Exact method is in `ecosystem/`. |
| "What's next?" | A GitHub Action, a bot that opens fix PRs, and a release-day "what breaks" report before every Sarvam launch. |
| "Why not build an end-user app?" | Every app built on Sarvam depends on its integration working. Fixing the base helps every app at once. |

---

## 10. Risks and fallbacks

| Risk | Fallback |
|---|---|
| No API key / credits late | Demo the static scan + fix + dashboard. Say "live verify runs once the key is in" and show the dry-run requests. |
| Live API accepts something we flag | Downgrade it to a warning on the spot. Mention it as an honest finding. |
| Sarvam-105B returns empty or bad JSON in `--learn` | Retry once, then show rules from the SDK and docs. The pitch still holds. |
| Wi-Fi fails | Pre-cloned demo repos + `demo_app` work offline (scan + fix). The dashboard is a static file. |
| Organisers announce a fixed problem statement | Reuse the Sarvam API wiring (`http()` helper) and switch to their problem. |

---

## 11. Command cheat sheet

```bash
cd "/Users/atharv/sarvam ai hackathon/sudhaar"
export SARVAM_API_KEY=...                        # from the event
python3 sudhaar.py demo_app                # static report
python3 sudhaar.py demo_app --verify       # live 400 → 200 proof
python3 sudhaar.py demo_app --fix          # rewrite + diff (use a copy!)
python3 sudhaar.py demo_app --explain hi-IN
python3 test_sudhaar.py                    # self-check
```

Before the demo: `git stash` / copy `demo_app` so `--fix` can be shown more than once.

---

## 12. Rules of engagement
- Never open PRs or post anything on other people's repos without asking the user first, for each repo.
- Never run code from cloned repos. We only read them.
- Keep the API key in the environment only. Never write it to a file.
