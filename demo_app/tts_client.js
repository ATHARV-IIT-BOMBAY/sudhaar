// Upgraded to Bulbul v4 Flash, but kept the v3 habits. Bugs from real issues, see ../PROOF.md
const API = "https://api.sarvam.ai";

export async function announce(text) {
  // Docs: "The v3 default shubh is not valid on this model"
  const res = await fetch(`${API}/text-to-speech`, {
    method: "POST",
    headers: { "api-subscription-key": process.env.SARVAM_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      target_language_code: "hi-IN",
      model: "bulbul:v4-flash",
      speaker: "shubh",
      output_audio_codec: "opus",
    }),
  });
  return (await res.json()).audios[0];
}

export async function announceLegacy(text) {
  // Old tutorials still use bulbul:v2, now 400 "has been deprecated"
  const res = await fetch(`${API}/text-to-speech`, {
    method: "POST",
    headers: { "api-subscription-key": process.env.SARVAM_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ text, target_language_code: "hi-IN", model: "bulbul:v2" }),
  });
  return (await res.json()).audios[0];
}

// GrindleWall PR #12: saaras:v4-realtime is not a real model id
export const STREAMING_STT = { model: "saaras:v4-realtime", language_code: "hi-IN" };
