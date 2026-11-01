import requests

def transcribe_hindi_wav(wav_path, api_key, base_url="https://api.sarvam.ai/speech-to-text"):
    url = f"{base_url}/v1/transcribe"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "multipart/form-data"
    }
    with open(wav_path, "rb") as f:
        files = {"file": (wav_path, f, "audio/wav")}
    data = {
        "model": "saarika",
        "language_code": "hi-IN",
        "enable_preprocessing": "true"
    }
    response = requests.post(url, headers=headers, files=files, data=data)
    response.raise_for_status()
    return response.json()
