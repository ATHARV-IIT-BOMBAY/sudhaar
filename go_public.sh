#!/usr/bin/env bash
# Share the portal for the showcase: a temporary public HTTPS link to http://localhost:8000.
# Uses localhost.run over plain ssh (nothing to install). The link stops working when you press Ctrl+C.
# Costly calls (live proof, explain, write, ask) are rate-limited in portal.py to protect your Sarvam credits.
set -euo pipefail
cd "$(dirname "$0")"

if ! curl -s --max-time 2 localhost:8000/api/status >/dev/null; then
  : "${SARVAM_API_KEY:?Set SARVAM_API_KEY first}"
  nohup python3 portal.py > /tmp/sudhaar_portal.log 2>&1 &
  sleep 2
fi

echo "Opening a public link to the Sudhaar portal (Ctrl+C to close it)…"
echo "Look for the https://….lhr.life line below and share that URL."
ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -R 80:localhost:8000 nokey@localhost.run
