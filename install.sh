#!/usr/bin/env bash
# =============================================================================
#  Agility Shell -- Root Install Wrapper (Forwarder)
#  Guarantees 100% backward compatibility for curl piping and direct execution.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"

if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/scripts/install.sh" ]]; then
    exec "$SCRIPT_DIR/scripts/install.sh" "$@"
fi

# Fallback when running piped via curl/stdin without a git clone
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
curl -fsSL https://raw.githubusercontent.com/AbsolOrg/agility-shell/main/scripts/install.sh -o "$TMP_DIR/install.sh"
chmod +x "$TMP_DIR/install.sh"
exec "$TMP_DIR/install.sh" "$@"
