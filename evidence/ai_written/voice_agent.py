import requests, json, base64, io, os, sys, time, threading
from pydub import AudioSegment
from pydub.playback import play

# Explicit model names
STT_MODEL = "sarvam-stt"
CHAT_MODEL = "sarvam-chat"
TTS_MODEL = "sarvam-tts"

# Endpoints
STT_URL = "https://api.sarvam.ai/speech-to-text"
CHAT_URL = "https://api.sarvam.ai/chat"
TTS_URL = "https://api.sarvam.ai/text-to-speech"

# Auth
API_KEY = os.environ.get("SARVAM_API_KEY", "")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

def record_audio(duration=5):
    print("Listening...")
    import sounddevice as sd

    samplerate = 16000
    duration_sec = duration
    print(f"Recording for {duration_sec}s...")
    samples = sd.rec(int(samplerate * duration_sec), samplerate=samplerate, channels=1, dtype="int16")
    sd.wait()
    print("Recording done.")
    return samples, samplerate

def audio_to_wav_bytes(samples, samplerate):
    wav = samples.tobytes()
    header = b"RIFF" + len(samples).to_bytes(4, "little") + b"WAVEfmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little") + (samplerate).to_bytes(4, "little") + (samplerate * 2).to_bytes(4, "little") + (4).to_bytes(2, "little") + (16).to_bytes(2, "little") + b"data" + len(samples).to_bytes(4, "little")
    return header + wav

def stt(audio_bytes):
    payload = {
        "model": STT_MODEL,
        "audio": base64.b64encode(audio_bytes).decode("utf-8"),
        "language": "en-IN",
    }
    r = requests.post(STT_URL, headers=HEADERS, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def chat(text):
    payload = {
        "model": CHAT_MODEL,
        "messages": [{"role": "user", "content": text}],
        "temperature": 0.7,
    }
    r = requests.post(CHAT_URL, headers=HEADERS, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def tts(text):
    payload = {
        "model": TTS_MODEL,
        "text": text,
        "language": "en-IN",
        "voice": "meera",
    }
    r = requests.post(TTS_URL, headers=HEADERS, json=payload, timeout=30)
    r.raise_for_status()
    return base64.b64decode(r.json()["audio"])

def speak(audio_bytes):
    play(AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav"))

def assistant_loop():
    print("Voice assistant ready. Say 'stop' to exit.")
    while True:
        samples, sr = record_audio()
        audio_bytes = audio_to_wav_bytes(samples, sr)
        result = stt(audio_bytes)
        transcript = result.get("text", "").strip()
        print(f"You: {transcript}")
        if transcript.lower() in {"stop", "exit", "quit"}:
            speak(tts("Goodbye."))
            print("Goodbye.")
            break

        chat_result = chat(transcript)
        reply = chat_result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        print(f"Assistant: {reply}")
        if reply:
            audio = tts(reply)
            speak(audio)

if __name__ == "__main__":
    assistant_loop()
