"""A typical Sarvam voice agent, written against last year's docs.
Every bug here is copied from a real public issue (see ../PROOF.md)."""
import os

import requests

API = "https://api.sarvam.ai"
HEADERS = {"api-subscription-key": os.environ["SARVAM_API_KEY"]}


def transcribe(wav_path):
    # Seen in 12 public repos: saarika:v2 now returns 400 "has been deprecated"
    with open(wav_path, "rb") as f:
        r = requests.post(f"{API}/speech-to-text", headers=HEADERS, files={"file": f},
                          data={"model": "saarika:v2", "language_code": "hi-IN"})
    return r.json()["transcript"]


def think(user_text):
    # sarvam-m was the flagship last year, the API now rejects it
    r = requests.post(f"{API}/v1/chat/completions", headers=HEADERS, json={
        "model": "sarvam-m",
        "messages": [{"role": "user", "content": user_text}],
    })
    return r.json()["choices"][0]["message"]["content"]


def speak_hindi(text):
    # LiveKit #6774: v2-era speaker and v2 pace range sent to bulbul:v3 (400); pitch/loudness are v2-only no-ops
    r = requests.post(f"{API}/text-to-speech", headers=HEADERS, json={
        "text": text,
        "target_language_code": "hi-IN",
        "model": "bulbul:v3",
        "speaker": "anushka",
        "pace": 2.5,
        "pitch": 0.2,
        "loudness": 1.5,
    })
    return r.json()["audios"][0]


def speak_odia(text):
    # sarvam-ai-cookbook #180: Odia is od-IN on REST TTS, or-IN only on streaming
    r = requests.post(f"{API}/text-to-speech", headers=HEADERS, json={
        "text": text,
        "target_language_code": "or-IN",
        "model": "bulbul:v3",
        "speaker": "shubh",
    })
    return r.json()["audios"][0]
