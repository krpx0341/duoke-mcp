#!/usr/bin/env bash
set -euo pipefail
here="$(cd -- "$(dirname -- "$0")" && pwd)"
profile="$here/browser-profile"
browser="${DUOKE_CHROMIUM:-}"
if [[ -z "$browser" ]]; then
  for candidate in chromium chromium-browser google-chrome google-chrome-stable; do
    if browser="$(command -v "$candidate" 2>/dev/null)"; then break; fi
  done
fi
if [[ -z "$browser" ]]; then
  echo "Chromium not found. Install it or set DUOKE_CHROMIUM." >&2
  exit 1
fi
mkdir -p "$profile"
exec "$browser" \
  --user-data-dir="$profile" \
  --profile-directory='Profile 1' \
  --disable-blink-features=AutomationControlled \
  'https://ai.duoke.com/#/'
