#!/usr/bin/env bash
# =============================================================================
#  Agility Shell -- Updater
#  Updates an existing installation in place.
# =============================================================================

set -euo pipefail

INSTALL_DIR="$HOME/.config/agility-shell"

# Directories to preserve during updates (relative to INSTALL_DIR)
PRESERVE_DIRS=("wallpapers" "config")

# Individual files to preserve during updates (relative to INSTALL_DIR)
PRESERVE_FILES=(
    "style/colors.css"
    "style/borders.css"
    "style/fonts.css"
)

# -- Colours -------------------------------------------------------------------
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
die()     { error "$*"; exit 1; }

# -- Sanity checks -------------------------------------------------------------
check_not_root() {
    if [[ "$EUID" -eq 0 ]]; then
        die "Please run this script as a regular user, not root."
    fi
}

check_installation() {
    if [[ ! -d "$INSTALL_DIR/.git" ]]; then
        die "No Agility Shell installation found at $INSTALL_DIR -- run install.sh first."
    fi

    if [[ ! -x "$INSTALL_DIR/venv/bin/pip" ]]; then
        die "Python venv not found at $INSTALL_DIR/venv -- run install.sh first."
    fi
}

# -- Compile native snippets ---------------------------------------------------
compile_snippets() {
    info "Compiling native libraries..."

    local blur_dir="$INSTALL_DIR/snippets/blur/lib"
    local hacktk_dir="$INSTALL_DIR/snippets/hacktk/lib"

    if [[ -d "$blur_dir" ]]; then
        make -C "$blur_dir"
        success "blur library compiled."
    else
        warn "blur lib directory not found -- skipping."
    fi

    if [[ -d "$hacktk_dir" ]]; then
        make -C "$hacktk_dir"
        success "hacktk library compiled."
    else
        warn "hacktk directory not found -- skipping."
    fi
}

# -- Preserve / restore ---------------------------------------------------------
backup_preserved_dirs() {
    local tmp_backup="$1"
    for dir in "${PRESERVE_DIRS[@]}"; do
        local src="$INSTALL_DIR/$dir"
        if [[ -d "$src" ]]; then
            info "Preserving $dir/..."
            cp -r "$src" "$tmp_backup/$dir"
        fi
    done
}

restore_preserved_dirs() {
    local tmp_backup="$1"
    for dir in "${PRESERVE_DIRS[@]}"; do
        local backed_up="$tmp_backup/$dir"
        if [[ -d "$backed_up" ]]; then
            info "Restoring $dir/..."
            rm -rf "$INSTALL_DIR/$dir"
            cp -r "$backed_up" "$INSTALL_DIR/$dir"
        fi
    done
}

backup_preserved_files() {
    local tmp_backup="$1"
    for file in "${PRESERVE_FILES[@]}"; do
        local src="$INSTALL_DIR/$file"
        if [[ -f "$src" ]]; then
            mkdir -p "$tmp_backup/$(dirname "$file")"
            cp "$src" "$tmp_backup/$file"
            info "Preserving $file..."
        fi
    done
}

restore_preserved_files() {
    local tmp_backup="$1"
    for file in "${PRESERVE_FILES[@]}"; do
        local backed_up="$tmp_backup/$file"
        if [[ -f "$backed_up" ]]; then
            mkdir -p "$INSTALL_DIR/$(dirname "$file")"
            cp "$backed_up" "$INSTALL_DIR/$file"
            info "Restoring $file..."
        fi
    done
}

# -- Update --------------------------------------------------------------------
do_update() {
    info "Updating Agility Shell..."

    local tmp_backup
    tmp_backup=$(mktemp -d)

    backup_preserved_dirs "$tmp_backup"
    backup_preserved_files "$tmp_backup"

    git -C "$INSTALL_DIR" fetch origin
    git -C "$INSTALL_DIR" reset --hard origin/main

    restore_preserved_files "$tmp_backup"
    restore_preserved_dirs "$tmp_backup"
    rm -rf "$tmp_backup"

    info "Refreshing Python dependencies..."
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip -q
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q
    success "Python dependencies updated."

    compile_snippets
    chmod +x "$INSTALL_DIR/start.sh" "$INSTALL_DIR/update.sh" "$INSTALL_DIR/install.sh" "$INSTALL_DIR/agility-shell" 2>/dev/null || true

    success "Agility Shell updated successfully!"
    echo
    info "Restart the shell or reboot to apply changes."
    echo -e "  Manual start: ${CYAN}$INSTALL_DIR/start.sh${RESET}"

    prompt_reboot
}

prompt_reboot() {
    echo
    warn "A system reboot is recommended to ensure all services, environment variables, and compositor configs take effect."
    echo
    read -rp "  Would you like to reboot now? [y/N]: " reboot_choice
    case "$reboot_choice" in
        [yY]|[yY][eE][sS])
            info "Rebooting system..."
            systemctl reboot || sudo reboot
            ;;
        *)
            info "Reboot skipped. You can manually restart the shell using: $INSTALL_DIR/start.sh"
            ;;
    esac
}

main() {
    echo
    echo -e "${BOLD}${CYAN}+==================================+${RESET}"
    echo -e "${BOLD}${CYAN}|       Agility Shell Update       |${RESET}"
    echo -e "${BOLD}${CYAN}+==================================+${RESET}"
    echo

    check_not_root
    check_installation
    do_update
}

main "$@"

