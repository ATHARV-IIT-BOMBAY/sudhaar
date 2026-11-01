---
name: sudhaar
description: Verify any code that calls Sarvam AI's APIs (Bulbul, Saaras, Saarika, Sarvam-105B, Mayura) before calling it done. Use after writing or editing code that sets a Sarvam model, voice (speaker), pace or language code, and whenever a Sarvam API call returns 400.
---

# Sudhaar: prove Sarvam API code works before you finish

Your training data about Sarvam's API is probably stale. In a test on 1 Nov 2026, 5 of 5 code samples
written from memory (by Sarvam-105B itself) failed on Sarvam's live API: invented model ids
(`sarvam-tts`, `sarvam-stt`, `sarvam-chat`), retired voices (`meera`), and wrong field names (`voice`, `language`).
Sarvam's own docs had 8 pages with samples the API rejects. Don't trust memory. Check.

## Every time you write or change Sarvam API code

1. Run the check on the files you touched (or the whole project):
   ```bash
   python3 /path/to/sudhaar/sudhaar.py <file-or-folder> --verify
   ```
   `--verify` sends a tiny real request per finding: the current value (expect 400) and the fix (expect 200).
   It needs `SARVAM_API_KEY` in the environment; without it, drop `--verify` for a static check.
2. If it reports errors, apply its fixes and show the user the diff:
   ```bash
   python3 /path/to/sudhaar/sudhaar.py <file-or-folder> --fix
   ```
3. Re-run step 1 until it prints `0 errors`. Exit code 1 means errors remain.
4. Tell the user what Sudhaar corrected and that the calls were verified live.

## Facts verified live (1 Nov 2026), use these instead of memory
- Text-to-speech: `POST /text-to-speech` with `{text, target_language_code, speaker, model}`, model `bulbul:v3` or
  `bulbul:v4-flash`. Response `{"audios": [base64 WAV]}`. `bulbul:v1` and `bulbul:v2` are rejected.
- v3 voices are short names (`shubh`, `priya`, `ritu`, `aditya` …); v4-flash voices are personas (`shubh_hi_ads`,
  `simran_en_customer` …). Mixing them returns 400. Pace must be 0.5–2.0 on v3/v4.
- Speech-to-text: `POST /speech-to-text`, multipart `file` + `model` = `saaras:v3` (or `saaras:v4`).
  `saarika:v1/v2/flash` and `saaras:v1/v2` are rejected.
- Chat: `sarvam-105b` or `sarvam-105b-conversations` only (`sarvam-m`, `sarvam-30b` are rejected).
  Use `/v2/chat/completions` with `reasoning_effort: "none"` for short answers; on `/v1` the model can spend
  its whole token budget reasoning and return empty content.
- Odia is `od-IN` on REST text-to-speech and speech-to-text, `or-IN` only on streaming.

## As an MCP tool
Add Sudhaar's MCP server to your client to get `sudhaar_check`, `sudhaar_verify` and `sudhaar_fix` tools:
```json
{"mcpServers": {"sudhaar": {"command": "python3", "args": ["/path/to/sudhaar/mcp_server.py"],
  "env": {"SARVAM_API_KEY": "<YOUR_KEY>"}}}}
```
