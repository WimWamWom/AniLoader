#!/bin/bash
set -e

# Start a virtual framebuffer so patchright/Chromium can run with headless=False
# (required for CAPTCHA solving via playwright_get_page_url).
# Screen resolution 1280x720 is enough; colour depth 24 is standard.
Xvfb :99 -screen 0 1280x720x24 -nolisten tcp -ac &

# Export the display so every child process (including aniworld → patchright → Chromium)
# picks it up automatically.
export DISPLAY=:99

# Wait until Xvfb is ready before starting the app.
for i in $(seq 1 10); do
    if xdpyinfo -display :99 >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

exec "$@"
