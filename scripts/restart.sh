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
REPO_ROOT="$(cd "$SCRIPT_DIR/.." 2>/dev/null && pwd || echo "")"
USER_CONFIG="$HOME/.config/agility-shell"
LOG_DIR="$HOME/.cache/agility-shell"
LOG_FILE="$LOG_DIR/shell.log"

mkdir -p "$LOG_DIR"

info "Restarting Agility Shell..."

# -- 1. Terminate existing shell processes safely -----------------------------
info "Stopping running Agility Shell & Quickshell instances..."

find_shell_pids() {
    local found_pids=()
    local raw_pids
    raw_pids=$(pgrep -x "agility-shell" 2>/dev/null || true)
    raw_pids+=" $(pgrep -f "python.*agility-shell/main\.py" 2>/dev/null || true)"
    raw_pids+=" $(pgrep -f "python.*[m]ain\.py" 2>/dev/null || true)"
    raw_pids+=" $(pgrep -f "[q]uickshell.*(agility|Awe)|[q]s.*(agility|Awe)" 2>/dev/null || true)"

    for pid in $raw_pids; do
        [[ -z "$pid" ]] && continue
        # Do not kill self or parent
        if [[ "$pid" -eq "$$" || "$pid" -eq "$PPID" ]]; then
            continue
        fi
        # Never match restart, update, install, or agl scripts
        local cmdline
        cmdline=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
        if [[ "$cmdline" =~ restart\.sh|update\.sh|install\.sh|/bin/agl ]]; then
            continue
        fi
        found_pids+=("$pid")
    done
    echo "${found_pids[@]:-}"
}

ALL_PIDS=$(find_shell_pids)

if [[ -n "${ALL_PIDS// /}" ]]; then
    # Send SIGTERM first for clean shutdown
    kill -15 $ALL_PIDS 2>/dev/null || true
    
    # Wait up to 2 seconds for graceful exit
    for i in {1..20}; do
        REMAINING=$(find_shell_pids)
        if [[ -z "${REMAINING// /}" ]]; then
            break
        fi
        sleep 0.1
    done

    # Force kill if still lingering
    REMAINING=$(find_shell_pids)
    if [[ -n "${REMAINING// /}" ]]; then
        warn "Force terminating lingering processes..."
        kill -9 $REMAINING 2>/dev/null || true
        sleep 0.2
    fi
fi

success "All previous shell processes stopped."
sleep 0.3

# -- 2. Determine launcher target (prefer updated ~/.config/agility-shell) -----
TARGET_DIR=""
PYTHON_BIN="python3"

if [[ -d "$USER_CONFIG" && -f "$USER_CONFIG/main.py" ]]; then
    TARGET_DIR="$USER_CONFIG"
    if [[ -x "$USER_CONFIG/venv/bin/python3" ]]; then
        PYTHON_BIN="$USER_CONFIG/venv/bin/python3"
    fi
elif [[ -f "$SCRIPT_DIR/main.py" && -f "$SCRIPT_DIR/bar.py" ]]; then
    TARGET_DIR="$SCRIPT_DIR"
    if [[ -x "$SCRIPT_DIR/venv/bin/python3" ]]; then
        PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"
    elif [[ -x "$USER_CONFIG/venv/bin/python3" ]]; then
        PYTHON_BIN="$USER_CONFIG/venv/bin/python3"
    fi
elif [[ -n "$REPO_ROOT" && -f "$REPO_ROOT/main.py" && -f "$REPO_ROOT/bar.py" ]]; then
    TARGET_DIR="$REPO_ROOT"
    if [[ -x "$REPO_ROOT/venv/bin/python3" ]]; then
        PYTHON_BIN="$REPO_ROOT/venv/bin/python3"
    elif [[ -x "$USER_CONFIG/venv/bin/python3" ]]; then
        PYTHON_BIN="$USER_CONFIG/venv/bin/python3"
    fi
else
    error "Could not find Agility Shell main.py in $USER_CONFIG or $SCRIPT_DIR"
    exit 1
fi

info "Launching updated shell from: $TARGET_DIR"
info "Using Python:                 $PYTHON_BIN"

# -- 3. Start Shell -----------------------------------------------------------
FOREGROUND=false
PASS_ARGS=()
for arg in "$@"; do
    if [[ "$arg" == "--foreground" || "$arg" == "-f" ]]; then
        FOREGROUND=true
    else
        PASS_ARGS+=("$arg")
    fi
done

cd "$TARGET_DIR"

if [[ "$FOREGROUND" == true ]]; then
    info "Running in foreground mode..."
    exec "$PYTHON_BIN" main.py ${PASS_ARGS[@]+"${PASS_ARGS[@]}"}
else
    # Disown and background safely with a new session
    if command -v setsid >/dev/null 2>&1; then
        setsid "$PYTHON_BIN" main.py ${PASS_ARGS[@]+"${PASS_ARGS[@]}"} </dev/null >> "$LOG_FILE" 2>&1 &
    else
        nohup "$PYTHON_BIN" main.py ${PASS_ARGS[@]+"${PASS_ARGS[@]}"} </dev/null >> "$LOG_FILE" 2>&1 &
    fi
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
