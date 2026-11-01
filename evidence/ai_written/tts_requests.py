import requests

def hindi_text_to_speech(text: str, model: str = "sarvam-text-to-speech", speaker: str = "meera", voice_id: str = "hi-IN-meera-f", language_code: str = "hi-IN", sample_rate: int = 8000):
    url = "https://api.sarvam.ai/text-to-speech"
    headers = {
        "Authorization": "Bearer YOUR_API_KEY",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": [text],
        "model": model,
        "speaker": speaker,
        "voice_id": voice_id,
        "language_code": language_code,
        "sample_rate": sample_rate
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()
