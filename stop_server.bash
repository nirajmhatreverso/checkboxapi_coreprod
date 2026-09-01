#!/bin/bash

# Script: stop-django.sh
# Purpose: Gracefully stop Django server using PID from api.pid file

PID_FILE="/home/checkboxadmin/scripts/coredev/api.pid"

# ------------------------------------------------
# 1. Check if PID file exists
# ------------------------------------------------
if [ ! -f "$PID_FILE" ]; then
    echo "Error: PID file not found ? $PID_FILE"
    echo "Is the server actually running?"
    exit 1
fi

# ------------------------------------------------
# 2. Read PID and remove surrounding whitespace
# ------------------------------------------------
PID=$(cat "$PID_FILE" | tr -d '[:space:]')

# ------------------------------------------------
# 3. Basic validation that it looks like a number
# ------------------------------------------------
if ! [[ "$PID" =~ ^[0-9]+$ ]]; then
    echo "Error: Content of $PID_FILE is not a valid PID: '$PID'"
    exit 1
fi

# ------------------------------------------------
# 4. Check if process really exists
# ------------------------------------------------
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "Warning: PID $PID from $PID_FILE does not exist (already stopped?)"
    # Optional: rm -f "$PID_FILE"   # uncomment if you want to clean up stale PID file
    exit 0
fi

# ------------------------------------------------
# 5. Try graceful shutdown first (SIGTERM)
# ------------------------------------------------
echo "Sending SIGTERM to Django process (PID $PID)..."
kill -TERM "$PID"

# Wait a reasonable time for graceful shutdown
sleep 4

# ------------------------------------------------
# 6. Check if still running ? force kill if needed
# ------------------------------------------------
if ps -p "$PID" > /dev/null 2>&1; then
    echo "Process did not terminate after 4 seconds ? sending SIGKILL"
    kill -9 "$PID"
    sleep 1
fi

# ------------------------------------------------
# 7. Final status check & cleanup
# ------------------------------------------------
if ps -p "$PID" > /dev/null 2>&1; then
    echo "ERROR: Could not kill process $PID even with SIGKILL"
    exit 1
else
    echo "Django process (PID $PID) stopped successfully"
    # Clean up PID file (common practice)
    rm -f "$PID_FILE"
    echo "Removed PID file: $PID_FILE"
fi

exit 0