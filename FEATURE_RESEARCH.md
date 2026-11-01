# What developers building on Sarvam struggle with, and what Sudhaar should do about it

*Research done 1 Nov 2026, ~16:00, during the event. Sources: GitHub issues (100 most recent mentioning Sarvam),
Sarvam's own Agent Skills (the gotchas Sarvam itself says developers hit), Sarvam's docs, Hacker News, the web.
Reddit blocks automated access, so it isn't covered. "Live" = tested against api.sarvam.ai today.*

---

## The short version

Sudhaar today solves **model and parameter drift** (dead models, wrong voices, wrong fields). Developers hit
six more kinds of pain that the same engine, and especially the **proxy**, can solve:

| # | Pain | Evidence | Sudhaar feature | Effort |
|---|---|---|---|---|
| 1 | **OpenAI-compatible tools break** (array message content, auth header) | sarvam-ai-sdk #11; oh-my-pi “user content always sent as array, rejected by Sarvam (400)”; Vercel AI SDK reasoning_effort issue. **Live: array content → 400** | Proxy **compat mode**: flattens array content, maps `Authorization: Bearer` to `api-subscription-key`, so OpenAI SDK / Vercel AI SDK / LangChain work unchanged | ~15 min |
| 2 | **Size limits fail at runtime** (TTS 2,500 chars, REST STT 30 s, Doc AI 10 pages, legacy `inputs` 500 chars) | Sarvam skills + docs; translator projects asking for “safe chunking”. **Live: 2,600 chars → 400** | Proxy **auto-chunks long TTS text** and stitches the audio; scanner warns on long literals; clear message + Batch API pointer for long audio | ~25 min |
| 3 | **Flaky production calls** (429 / 503 / 502, no retries, 402 confused with 429) | RiverVoice “add retry-with-backoff to all outbound clients”; Sarvam’s docs disagree on 402 vs 429 for empty credits | Proxy **retries 429/500/502/503 with backoff**, never retries 400/402, and turns 402 into “credits exhausted, retrying won’t help”; scanner flags Sarvam calls with no retry | ~15 min |
| 4 | **No cost or usage visibility** (prices in ₹ only, credits burn silently) | “Sarvam API Credit Monitor” issue; voice-prices: “rate card in INR only, not priceable”; OpenLIT: “TTS span records no cost” | Proxy **usage meter**: ₹ cost, latency and status per call → a “Usage” page (spend today, by model, slowest calls) | ~25 min |
| 5 | **SDK version traps** (renames that raise `TypeError` before any request) | Sarvam skills: TTS `language_code` vs `target_language_code` is SDK-version-gated (Python 0.1.29, JS 1.1.8); dubbing JS field names; Doc AI `digitise` → `parse`; OpenLIT broke on the same rename | Scanner reads `requirements.txt` / `package.json`, knows the installed `sarvamai` version, flags code written for the other side of a rename | ~25 min |
| 6 | **Silent failures** (200 OK, wrong result) | Sarvam skills: `content=None` when reasoning eats `max_tokens` (we saw 1,999 of 2,000 tokens spent); Doc AI ignores `language_code`; dubbing export list silently truncated at 5; streaming idle timeout after 60 s | New **“silent failure” rules**: low `max_tokens` with no `reasoning_effort` and no `None` check, Doc AI `language_code`, `get_export_status` without `limit`, streaming without keep-alive or with MP3 | ~20 min |
| 7 | **Confusing errors** | Same docs inconsistency; issues full of pasted 400/422 JSON | **Error explainer**: paste any Sarvam error → plain-language cause and the exact fix (error-code table + Sarvam-105B) | ~10 min |
| 8 | **Voice-agent latency** (3.8 s → 1 s goals) | yuviz “Reduce voice agent latency (~3.8 s → ~1 s)”; vendor guides: Hinglish + latency budget 500–800 ms | Usage page shows **latency per stage** (STT / LLM / TTS) through the proxy; tips: `bulbul:v4-flash`, `reasoning_effort: none`, streaming | with #4 |
| 9 | **Streaming fragility** | Pipecat: “SarvamSTTService never reconnects after its websocket drops”; skills: 60 s idle close, PCM-only codecs | Scanner rules for streaming code (no reconnect, no keep-alive, wrong codec); proxy is REST-only today | ~15 min (rules) |

---

## Details and sources

### 1 · OpenAI compatibility gaps
- Sarvam's chat API rejects OpenAI's array-style message content: **live test returned
  `400 body.messages.0.user.content : Input should be a valid string`**.
- Tools that always send arrays break: `can1357/oh-my-pi` ("rejected by providers that require string content
  (Sarvam AI 400)"), Sarvam's own SDK issue `sarvamai/sarvam-ai-sdk#11`.
- Sarvam's REST uses `api-subscription-key`; OpenAI-style clients send `Authorization: Bearer`.
- **Feature:** the proxy already rewrites requests; add a compat pass so any OpenAI-compatible client works by
  only changing `base_url`. One line in a pitch: *"Point the OpenAI SDK at Sudhaar and Sarvam just works."*

### 2 · Size limits
| Limit | Source | Live |
|---|---|---|
| TTS `text` ≤ 2,500 chars | Bulbul docs, skills | ✅ 2,600 chars → 400 "at most 2500 characters" |
| Legacy TTS `inputs` items ≤ 500 chars | skills | not tested |
| REST STT ≤ 30 s audio | STT FAQ: "Maximum duration: 30 seconds per request"; Batch up to 2 h | not tested |
| Doc AI ≤ 10 pages per job | skills, errors page | not tested |
- **Feature:** proxy splits long TTS text at sentence boundaries (`।`, `.`, `?`), calls Bulbul per chunk, and joins
  the WAVs into one response, with an `X-Sudhaar-Fixed: chunked 6200 chars into 3 calls` header.

### 3 · Errors, retries, credits
From Sarvam's errors page: `402 insufficient_quota_error` (credits empty, "retrying will not help"),
`429 rate_limit_exceeded_error / model_rate_limit_exceeded_error / audio_duration_busy_error`,
`500/502/503` (retry with backoff). The pricing page and the rate-limits page disagree on whether empty credits
are 402 or 429. Developers file issues asking for retry-with-backoff (`Rivervoice-org/RiverVoice`).
- **Feature:** retries with exponential backoff and jitter in the proxy (429/500/502/503 only, respecting
  `Retry-After`), a human message for 402, and a scanner warning for Sarvam calls with no retry/timeout.

### 4 · Cost and usage
- Prices are published in ₹ only (`mahimailabs/voice-prices`: "not priceable today"). Examples from Sarvam's
  pricing page: Sarvam-105B ₹15 / ₹5 cached / ₹60 per 1M tokens (in/cached/out); STT ₹0.41–0.49 per minute;
  Bulbul v4 Flash ₹0.85–1.00 per 1,000 characters (by plan).
- Projects build their own credit monitors (`shivaram19/voter-sentiment-analysis-platform`: "Sarvam API Credit
  Monitor"); OpenLIT's Sarvam integration records no cost.
- **Feature:** the proxy already sees every call; record `usage` (tokens, characters, seconds), price it in ₹, and
  show a Usage page: spend today, by model, slowest calls, error rate.

### 5 · SDK version traps (Sarvam documents these itself)
- TTS: Python `sarvamai>=0.1.29` / JS `>=1.1.8` take `language_code`; older take `target_language_code`.
  "Hard rename, no alias", so the wrong one raises `TypeError` before any request. (The REST API accepts both: live.)
  WebSocket `configure()` was *not* renamed in Python.
- Dubbing JS: `src_lang`/`target_langs`, not `source_language_code`/`target_language_codes`.
- Document AI: `digitise()` → `parse()` in `>=0.1.40`; `output_format="markdown"` → 400 (use `"md"`).
- OpenLIT shipped a bug from the same rename ("TTS span records an empty language for sarvamai >= 0.1.29").
- **Feature:** read the pinned `sarvamai` version from `requirements.txt`, `pyproject.toml` or `package.json` and
  check SDK calls against it. No other tool knows these renames.

### 6 · Silent failures (200 OK, wrong behaviour)
- Chat: `content` is `None` when reasoning consumes `max_tokens` (Sarvam skills; we measured 1,999/2,000).
- Document AI: `language_code` silently ignored (the field is `language`).
- Dubbing: `get_export_status` returns 5 items by default, silently truncating.
- STT streaming: socket closes after 60 s idle; MP3/AAC not accepted for streaming.
- **Feature:** static rules for each. These are exactly what live 400-checks can't catch.

### 7–9 · Error explainer, latency, streaming
- Paste-an-error in the portal: match `error.code` against Sarvam's table, then Sarvam-105B explains it in the
  user's language with the fix.
- Latency: `yuviz-ai/yuviz` targets 3.8 s → 1 s for a voice agent; the proxy can time each stage.
- Streaming: `pipecat-ai/pipecat` "SarvamSTTService never reconnects after its websocket drops".

---

## Recommendation for the time left

Build the **proxy upgrades first** (they reuse what exists and demo well):
1. **Compat mode + retries + 402 message** (#1, #3): ~20 min. Demo: the OpenAI SDK pointed at Sudhaar talks to Sarvam.
2. **TTS auto-chunking** (#2): ~25 min. Demo: a 6,000-character story → 400 direct, one audio file through Sudhaar.
3. **Error explainer** (#7): ~10 min, in the portal.

Then the stage line becomes: *"Sudhaar fixes your code before it ships, and protects it while it runs:
dead models, wrong voices, size limits, retries, OpenAI compatibility."*

Keep for the roadmap slide: usage/cost meter (#4), SDK-version rules (#5), silent-failure rules (#6), streaming (#9).

## Sources
- GitHub: [sarvamai/sarvam-ai-sdk#11](https://github.com/sarvamai/sarvam-ai-sdk/issues/11) ·
  [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat/issues?q=sarvam) ·
  [openlit/openlit](https://github.com/openlit/openlit/issues?q=sarvam) ·
  [vercel/ai](https://github.com/vercel/ai/issues?q=reasoning_effort) ·
  [livekit/agents](https://github.com/livekit/agents/issues?q=sarvam) ·
  search: `gh search issues "sarvam"`
- Sarvam: [Errors & troubleshooting](https://docs.sarvam.ai/api/getting-started/errors-troubleshooting) ·
  [Pricing, credits & rate limits](https://docs.sarvam.ai/api/getting-started/pricing) ·
  [STT FAQ](https://docs.sarvam.ai/api/speech-to-text/faq) · [Agent Skills](https://github.com/sarvamai/skills)
- Web: [Caller Digital: LLM benchmark for Indian voice agents](https://caller.digital/blog/llm-benchmark-indian-voice-agents-function-calling-latency-2026) ·
  [Product Leaders Day: voicebot latency](https://productleadersdayindia.org/blogs/building-for-bharat-tech-stack/voicebot-latency-optimization-slms.html)
