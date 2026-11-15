#!/bin/bash
set -e

# Start Xvfb (virtual X server) for Draw.io to run headless
Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &
XVFB_PID=$!

# Set DISPLAY environment variable
export DISPLAY=:99

# Cleanup on exit
trap 'kill "$XVFB_PID" 2>/dev/null || true' SIGTERM SIGINT EXIT

# Give Xvfb time to start
sleep 2

# Hot-reload of the backend on file changes.
watchfiles "python backend/main.py" backend
