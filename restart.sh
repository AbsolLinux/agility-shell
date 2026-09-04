#!/usr/bin/env bash
# =============================================================================
#  Agility Shell -- Restart Script
#  Gracefully stops running shell processes and relaunches Agility Shell.
# =============================================================================

set -euo pipefail

# -- Colors -------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}${BOLD}[agility]${RESET} $*"; }
success() { echo -e "${GREEN}${BOLD}[  ok  ]${RESET} $*"; }
warn()    { echo -e "${YELLOW}${BOLD}[ warn ]${RESET} $*"; }
error()   { echo -e "${RED}${BOLD}[ err  ]${RESET} $*" >&2; }

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_CONFIG="$HOME/.config/agility-shell"
LOG_DIR="$HOME/.cache/agility-shell"
LOG_FILE="$LOG_DIR/shell.log"

mkdir -p "$LOG_DIR"

info "Restarting Agility Shell..."

# -- 1. Terminate existing shell processes ------------------------------------
info "Stopping running Agility Shell & Quickshell instances..."

# Find PIDs of running agility-shell / main.py
PIDS=$(pgrep -f "agility-shell|caffyne-shell|python3.*main\.py" 2>/dev/null || true)
QS_PIDS=$(pgrep -f "quickshell.*(agility|Awe)|qs.*(agility|Awe)" 2>/dev/null || true)

ALL_PIDS="${PIDS} ${QS_PIDS}"

if [[ -n "${ALL_PIDS// /}" ]]; then
    # Send SIGTERM first for clean shutdown
    kill -15 $ALL_PIDS 2>/dev/null || true
    
    # Wait up to 2 seconds for graceful exit
    for i in {1..20}; do
        if ! pgrep -f "agility-shell|caffyne-shell|python3.*main\.py|quickshell.*(agility|Awe)|qs.*(agility|Awe)" >/dev/null 2>&1; then
            break
        fi
        sleep 0.1
    done

    # Force kill if still lingering
    REMAINING=$(pgrep -f "agility-shell|caffyne-shell|python3.*main\.py|quickshell.*(agility|Awe)|qs.*(agility|Awe)" 2>/dev/null || true)
    if [[ -n "${REMAINING// /}" ]]; then
        warn "Force terminating lingering processes..."
        kill -9 $REMAINING 2>/dev/null || true
        sleep 0.2
    fi
fi

success "All previous shell processes stopped."

# -- 2. Determine launcher target ---------------------------------------------
TARGET_DIR=""
PYTHON_BIN="python3"

if [[ -f "$SCRIPT_DIR/main.py" && -f "$SCRIPT_DIR/bar.py" ]]; then
    TARGET_DIR="$SCRIPT_DIR"
    if [[ -x "$SCRIPT_DIR/venv/bin/python3" ]]; then
        PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"
    elif [[ -x "$USER_CONFIG/venv/bin/python3" ]]; then
        PYTHON_BIN="$USER_CONFIG/venv/bin/python3"
    fi
elif [[ -d "$USER_CONFIG" && -f "$USER_CONFIG/main.py" ]]; then
    TARGET_DIR="$USER_CONFIG"
    if [[ -x "$USER_CONFIG/venv/bin/python3" ]]; then
        PYTHON_BIN="$USER_CONFIG/venv/bin/python3"
    fi
else
    error "Could not find Agility Shell main.py in $SCRIPT_DIR or $USER_CONFIG"
    exit 1
fi

info "Launching from: $TARGET_DIR"
info "Using Python:   $PYTHON_BIN"

# -- 3. Start Shell -----------------------------------------------------------
FOREGROUND=false
for arg in "$@"; do
    if [[ "$arg" == "--foreground" || "$arg" == "-f" ]]; then
        FOREGROUND=true
        break
    fi
done

cd "$TARGET_DIR"

if [[ "$FOREGROUND" == true ]]; then
    info "Running in foreground mode..."
    exec "$PYTHON_BIN" main.py "$@"
else
    # Disown and background safely
    nohup "$PYTHON_BIN" main.py "$@" </dev/null > "$LOG_FILE" 2>&1 &
    DISOWN_PID=$!
    disown "$DISOWN_PID" 2>/dev/null || true
    
    # Check if process launched successfully
    sleep 1.0
    if kill -0 "$DISOWN_PID" 2>/dev/null; then
        success "Agility Shell started with PID $DISOWN_PID"
        info "Log output: $LOG_FILE"
        
        if command -v notify-send >/dev/null 2>&1; then
            notify-send -a "Agility Shell" "Agility Shell" "Shell restarted successfully" 2>/dev/null || true
        fi
    else
        error "Failed to start Agility Shell! Check logs at $LOG_FILE"
        exit 1
    fi
fi
