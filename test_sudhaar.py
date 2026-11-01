"""python3 test_sudhaar.py: scans the demo app, fixes a copy, rescans clean."""
import shutil
import tempfile
from pathlib import Path

import sudhaar as sd

DEMO = Path(__file__).parent / "demo_app"


def test():
    found = {(Path(i["file"]).name, i["line"]) for i in sd.scan(DEMO) if i["severity"] == "error"}
    expected = {("voice_agent.py", n) for n in (15, 22, 34, 35, 46)} | {("tts_client.js", n) for n in (13, 25, 31)}
    assert found == expected, found ^ expected

    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "demo"
        shutil.copytree(DEMO, copy)
        sd.apply_fixes(sd.scan(copy))
        left = [i for i in sd.scan(copy) if i["severity"] in ("error", "warning")]
        assert left == [], left
        assert '"pitch":' not in (copy / "voice_agent.py").read_text()

    # The 5 samples Sarvam-105B wrote on 1 Nov: every invented id and retired voice must be caught (9 failures).
    ai = [(Path(i["file"]).name, i["value"]) for i in sd.scan(Path(__file__).parent / "evidence" / "ai_written") if i["severity"] == "error"]
    assert sorted(ai) == sorted([("chat.js", "sarvam-1"), ("stt.py", "saarika"),
                                 ("tts_requests.py", "sarvam-text-to-speech"), ("tts_requests.py", "meera"),
                                 ("tts_sdk.py", "sarvam-text-to-speech"), ("tts_sdk.py", "meera"),
                                 ("voice_agent.py", "sarvam-stt"), ("voice_agent.py", "sarvam-chat"),
                                 ("voice_agent.py", "sarvam-tts")]), ai

    # Wrong TTS field names are renamed in request bodies only, never in variables.
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "a.py"
        p.write_text('import requests\ndef tts(text, voice="priya"):\n'
                     '    payload = {"text": text, "voice": "meera", "language": "hi-IN", "model": "bulbul:v3"}\n'
                     '    return requests.post("https://api.sarvam.ai/text-to-speech", json=payload)\n')
        sd.apply_fixes(sd.scan(Path(tmp)))
        fixed = p.read_text()
        assert '"speaker": "shubh"' in fixed and '"target_language_code": "hi-IN"' in fixed, fixed
        assert 'voice="priya"' in fixed, fixed
        assert not [i for i in sd.scan(Path(tmp)) if i["severity"] == "error"]
    print("ok")


if __name__ == "__main__":
    test()
