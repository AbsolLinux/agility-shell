#!/usr/bin/env bash
# =============================================================================
#  Agility Shell -- Root Update Wrapper (Forwarder)
#  Guarantees 100% backward compatibility for direct execution and updater scripts.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"

if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/scripts/update.sh" ]]; then
    exec "$SCRIPT_DIR/scripts/update.sh" "$@"
fi

# Fallback when running piped via curl/stdin without a git clone
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
curl -fsSL https://raw.githubusercontent.com/AbsolOrg/agility-shell/main/scripts/update.sh -o "$TMP_DIR/update.sh"
chmod +x "$TMP_DIR/update.sh"
exec "$TMP_DIR/update.sh" "$@"
