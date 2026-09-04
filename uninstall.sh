#!/usr/bin/env bash
# =============================================================================
#  Agility Shell -- Root Uninstall Wrapper (Forwarder)
#  Guarantees 100% backward compatibility for direct execution.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"

if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/scripts/uninstall.sh" ]]; then
    exec "$SCRIPT_DIR/scripts/uninstall.sh" "$@"
elif [[ -f "$HOME/.config/agility-shell/scripts/uninstall.sh" ]]; then
    exec "$HOME/.config/agility-shell/scripts/uninstall.sh" "$@"
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
curl -fsSL https://raw.githubusercontent.com/Naitik-Vadher-4661/agility-shell/main/scripts/uninstall.sh -o "$TMP_DIR/uninstall.sh"
chmod +x "$TMP_DIR/uninstall.sh"
exec "$TMP_DIR/uninstall.sh" "$@"
