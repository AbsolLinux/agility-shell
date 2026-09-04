#!/usr/bin/env bash
# =============================================================================
#  Agility Shell -- Root Start Wrapper (Forwarder)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"

if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/scripts/start.sh" ]]; then
    exec "$SCRIPT_DIR/scripts/start.sh" "$@"
elif [[ -f "$HOME/.config/agility-shell/scripts/start.sh" ]]; then
    exec "$HOME/.config/agility-shell/scripts/start.sh" "$@"
else
    source ~/.config/agility-shell/venv/bin/activate 2>/dev/null || true
    exec python3 ~/.config/agility-shell/main.py "$@"
fi
