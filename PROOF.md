# The problem is real: public evidence

Sarvam ships models fast (Saarika → Saaras v3 → v4, Bulbul v2 → v3 → v4 Flash, Sarvam-M → 30B → 105B).
Every integration breaks quietly, including Sarvam's own.

| # | Where | What broke | sudhaar rule |
|---|---|---|---|
| 1 | [livekit/agents #6774](https://github.com/livekit/agents/issues/6774) | Rejects 9 valid Bulbul speakers, accepts 2 the API rejects; one pace range for all models → 400s on v3 | speaker × model, pace range |
| 2 | [mastra-ai/mastra #27090](https://github.com/mastra-ai/mastra/issues/27090) | `listen()` ignores your model, always sends `saarika:v2.5` | deprecated STT model |
| 3 | [run-llama/llama_index #19931](https://github.com/run-llama/llama_index/issues/19931) | Typos in class name, model name and base URL | unknown model ids |
| 4 | [sarvamai/sarvam-mcp #79](https://github.com/sarvamai/sarvam-mcp/issues/79) | **Sarvam's own MCP**: TTS always fails on bulbul:v3, pitch/loudness sent unconditionally | v2-only params |
| 5 | [sarvamai/sarvam-mcp #64](https://github.com/sarvamai/sarvam-mcp/issues/64), [#62](https://github.com/sarvamai/sarvam-mcp/issues/62) | Vision jobs and batch STT never return output: response fields drifted | (contract drift) |
| 6 | [sarvamai/sarvam-ai-cookbook #180](https://github.com/sarvamai/sarvam-ai-cookbook/issues/180) | Odia is `od-IN` on REST TTS/STT but `or-IN` on streaming/dubbing | Odia code per endpoint |
| 7 | [manasnilarout/GrindleWall #12](https://github.com/manasnilarout/GrindleWall/pull/12) | `saaras:v4-realtime` and `bulbul:v3-beta` used, neither exists | non-existent ids |
| 8 | [arhamgarg/Chhaaya #35](https://github.com/arhamgarg/Chhaaya/issues/35) | v3 speaker names invalid on v4 | speaker remap |
| 9 | [sarvamai/sarvam-ai-sdk #11](https://github.com/sarvamai/sarvam-ai-sdk/issues/11), [#20](https://github.com/sarvamai/sarvam-ai-sdk/issues/20) | **Official SDK**: OpenAI-compat gaps, streaming usage never reported | (contract drift) |
| 10 | Sarvam repos (sdk, mcp, skills, n8n node) | **20+ open `[docs-sync]` issues**: model ids, limits, prices lag the docs | rules.json auto-refresh |

Sarvam's own docs confirm the rules: Sarvam-M and 30B deprecated, `shubh` is "not valid" on v4 Flash,
pace 0.5–2.0 on v3/v4, pitch/loudness v2-only, no Malayalam/Odia on v4 Flash, `opus` errors on REST,
Bulbul v3 end of life on Voice Agents (10 Nov 2026). Sources: [Models](https://docs.sarvam.ai/api/getting-started/models),
[Bulbul](https://docs.sarvam.ai/api/api-guides-tutorials/models/bulbul).

Existing fixes cover only Sarvam's own repos (docs-sync bot, cookbook model allowlist CI).
No public tool checks *third-party* code; GitHub search for sarvam lint/migrate/doctor/validator found none.
