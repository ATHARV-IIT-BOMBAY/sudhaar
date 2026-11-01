const chatSarvam = async (apiKey, messages) => {
  const response = await fetch('https://api.sarvam.ai/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    },
    body: JSON.stringify({
      model: 'sarvam-1',
      messages
    })
  });
  return response.json();
};
