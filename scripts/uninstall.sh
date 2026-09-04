#!/usr/bin/env bash
# =============================================================================
#  Agility Shell -- Uninstaller
#  Cleanly terminates running processes and uninstalls Agility Shell.
# =============================================================================

set -euo pipefail

INSTALL_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/agility-shell"
BIN_FILE="$HOME/.local/bin/agl"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/agility-shell"
NIRI_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/niri/config.kdl"
HYPR_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/hypr/hyprland.conf"

# -- Colors --------------------------------------------------------------------
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

PURGE=false
KEEP_DATA=false
FORCE=false

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --purge)
            PURGE=true
            ;;
        --keep-data|--keep-config)
            KEEP_DATA=true
            ;;
        -y|--yes)
            FORCE=true
            ;;
        -h|--help)
            echo "Usage: uninstall.sh [options]"
            echo ""
            echo "Options:"
            echo "  --purge        Completely remove all files including configs and wallpapers"
            echo "  --keep-data    Keep ~/.config/agility-shell/config and wallpapers"
            echo "  -y, --yes      Do not ask for confirmation"
            echo "  -h, --help     Show this help message"
            exit 0
            ;;
    esac
done

echo ""
echo -e "${BOLD}${RED}Agility Shell Uninstaller${RESET}"
echo -e "This will remove Agility Shell from your system."
echo ""

# Confirm uninstall if not forced
if [[ "$FORCE" == false ]]; then
    read -r -p "Are you sure you want to uninstall Agility Shell? [y/N]: " confirm_uninstall
    case "$confirm_uninstall" in
        [yY]|[yY][eE][sS])
            ;;
        *)
            info "Uninstall aborted by user."
            exit 0
            ;;
    esac
fi

# -- 1. Stop running processes -------------------------------------------------
info "Stopping running Agility Shell processes..."
PIDS=$(pgrep -f "agility-shell|caffyne-shell|python3.*main\.py" 2>/dev/null || true)
QS_PIDS=$(pgrep -f "quickshell.*Awe|qs.*Awe" 2>/dev/null || true)
SWAY_PIDS=$(pgrep -f "swayidle.*agility-shell" 2>/dev/null || true)

ALL_PIDS="${PIDS} ${QS_PIDS} ${SWAY_PIDS}"
if [[ -n "${ALL_PIDS// /}" ]]; then
    kill -15 $ALL_PIDS 2>/dev/null || true
    sleep 0.5
    REMAINING=$(pgrep -f "agility-shell|caffyne-shell|python3.*main\.py" 2>/dev/null || true)
    if [[ -n "${REMAINING// /}" ]]; then
        kill -9 $REMAINING 2>/dev/null || true
    fi
    success "Shell processes stopped."
fi

# -- 2. Determine data preservation --------------------------------------------
if [[ "$PURGE" == false && "$KEEP_DATA" == false ]]; then
    echo ""
    read -r -p "Would you like to keep your custom configurations and wallpapers? [Y/n]: " keep_choice
    case "$keep_choice" in
        [nN]|[nN][oO])
            PURGE=true
            ;;
        *)
            KEEP_DATA=true
            ;;
    esac
fi

# -- 3. Remove agl CLI binary --------------------------------------------------
if [[ -f "$BIN_FILE" || -L "$BIN_FILE" ]]; then
    info "Removing CLI binary ($BIN_FILE)..."
    rm -f "$BIN_FILE"
    success "Removed agl CLI binary."
fi

# -- 4. Remove cache -----------------------------------------------------------
if [[ -d "$CACHE_DIR" ]]; then
    info "Removing cache ($CACHE_DIR)..."
    rm -rf "$CACHE_DIR"
    success "Removed cache."
fi

# -- 5. Clean installation directory -------------------------------------------
if [[ -d "$INSTALL_DIR" ]]; then
    if [[ "$PURGE" == true ]]; then
        info "Purging all Agility Shell files ($INSTALL_DIR)..."
        rm -rf "$INSTALL_DIR"
        success "Purged installation directory."
    else
        info "Removing application files while preserving configs and wallpapers..."
        TMP_DATA="$(mktemp -d)"
        
        # Save config and wallpapers if they exist
        if [[ -d "$INSTALL_DIR/config" ]]; then
            cp -r "$INSTALL_DIR/config" "$TMP_DATA/config"
        fi
        if [[ -d "$INSTALL_DIR/wallpapers" ]]; then
            cp -r "$INSTALL_DIR/wallpapers" "$TMP_DATA/wallpapers"
        fi

        rm -rf "$INSTALL_DIR"
        mkdir -p "$INSTALL_DIR"

        if [[ -d "$TMP_DATA/config" ]]; then
            cp -r "$TMP_DATA/config" "$INSTALL_DIR/config"
        fi
        if [[ -d "$TMP_DATA/wallpapers" ]]; then
            cp -r "$TMP_DATA/wallpapers" "$INSTALL_DIR/wallpapers"
        fi

        rm -rf "$TMP_DATA"
        success "Preserved user configs in $INSTALL_DIR"
    fi
fi

# -- 6. Clean compositor configs -----------------------------------------------
if [[ -f "$NIRI_CONFIG" ]] && grep -qF 'include "~/.config/agility-shell/config/niri.kdl"' "$NIRI_CONFIG"; then
    info "Removing Agility Shell include from Niri config ($NIRI_CONFIG)..."
    sed -i '/include "~\/\.config\/agility-shell\/config\/niri\.kdl"/d' "$NIRI_CONFIG"
    success "Cleaned Niri config."
fi

if [[ -f "$HYPR_CONFIG" ]] && grep -qF '~/.config/agility-shell/start.sh' "$HYPR_CONFIG"; then
    warn "Found agility-shell autostart in $HYPR_CONFIG. You may remove the line manually if desired."
fi

echo ""
success "Agility Shell has been uninstalled successfully."
echo ""
