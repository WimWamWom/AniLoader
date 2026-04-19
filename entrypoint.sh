#!/bin/bash
set -e

# Start a virtual framebuffer so patchright/Chromium can run with headless=False
# (required for CAPTCHA solving via playwright_get_page_url).
# Screen resolution 1280x720 is enough; colour depth 24 is standard.
Xvfb :99 -screen 0 1280x720x24 -nolisten tcp -ac &
XVFB_PID=$!

# Export the display so every child process (including aniworld → patchright → Chromium)
# picks it up automatically.
export DISPLAY=:99

# Wait until Xvfb is ready before starting the app.
XVFB_READY=0
for i in $(seq 1 20); do
    if xdpyinfo -display :99 >/dev/null 2>&1; then
        XVFB_READY=1
        break
    fi
    sleep 0.5
done

if [ "$XVFB_READY" -eq 0 ]; then
    echo "ERROR: Xvfb failed to start within 10s – aborting." >&2
    exit 1
fi

echo "Xvfb started (PID $XVFB_PID, DISPLAY=:99)"

# Watchdog: restart Xvfb automatically if it crashes.
# Runs in the background for the lifetime of the container.
(
    while true; do
        if ! kill -0 "$XVFB_PID" 2>/dev/null; then
            echo "WARN: Xvfb crashed – restarting …" >&2
            Xvfb :99 -screen 0 1280x720x24 -nolisten tcp -ac &
            XVFB_PID=$!
            # Wait until the new instance is ready before continuing
            for i in $(seq 1 20); do
                if xdpyinfo -display :99 >/dev/null 2>&1; then
                    echo "Xvfb restarted (PID $XVFB_PID)" >&2
                    break
                fi
                sleep 0.5
            done
        fi
        sleep 5
    done
) &

exec "$@"
