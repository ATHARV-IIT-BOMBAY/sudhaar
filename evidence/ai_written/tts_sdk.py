from sarvam import SarvamClient

client = SarvamClient()

response = client.text_to_speech(
    text="வணக்கம், நான் உங்களுக்கு உதவ தயாராக இருக்கிறேன்.",
    language="ta",
    voice="female",
    model="sarvam-text-to-speech",
    speaker="meera"
)

print(response.audio)
