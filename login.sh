#!/usr/bin/env bash
set -euo pipefail
here="$(cd -- "$(dirname -- "$0")" && pwd)"
profile="$here/browser-profile"
mkdir -p "$profile"
exec /usr/bin/chromium \
  --user-data-dir="$profile" \
  --profile-directory='Profile 1' \
  --disable-blink-features=AutomationControlled \
  'https://ai.duoke.com/#/'
