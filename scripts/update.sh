#!/usr/bin/env bash
# =============================================================================
#  Agility Shell -- Updater
#  Updates an existing installation in place.
# =============================================================================

set -euo pipefail

REPO_URL="https://github.com/AbsolOrg/agility-shell.git"
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

# -- Interactive prompt helper (handles pipe / curl execution) -----------------
prompt_user() {
    local prompt_msg="$1"
    local var_name="$2"
    local default_val="${3:-}"

    if [ -t 0 ]; then
        read -rp "$prompt_msg" "$var_name"
    elif [ -r /dev/tty ]; then
        read -rp "$prompt_msg" "$var_name" < /dev/tty
    else
        eval "$var_name=\"$default_val\""
    fi
}

# -- Sanity checks -------------------------------------------------------------
check_not_root() {
    if [[ "$EUID" -eq 0 ]]; then
        die "Please run this script as a regular user, not root."
    fi
}

check_installation() {
    if [[ ! -d "$INSTALL_DIR" ]]; then
        die "No Agility Shell installation found at $INSTALL_DIR -- run install.sh first."
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

inject_niri_include() {
    local niri_config_dir="$HOME/.config/niri"
    local niri_config="$niri_config_dir/config.kdl"
    local include_line='include "~/.config/agility-shell/config/niri.kdl"'

    mkdir -p "$niri_config_dir"

    if [[ ! -f "$niri_config" ]]; then
        info "No Niri config found at $niri_config -- creating one with default configuration template..."
        local candidate_defaults=(
            "/usr/share/doc/niri/default-config.kdl"
            "/etc/xdg/niri/config.kdl"
            "/etc/niri/config.kdl"
        )
        local copied=false
        for cand in "${candidate_defaults[@]}"; do
            if [[ -f "$cand" ]]; then
                cp "$cand" "$niri_config"
                copied=true
                info "Copied default Niri template from $cand"
                break
            fi
        done

        if [[ "$copied" == "false" ]]; then
            info "Creating clean base Niri config..."
            cat << 'BASE_NIRI_EOF' > "$niri_config"
// Niri Base Configuration
prefer-no-csd

input {
    keyboard {
        xkb {
        }
        numlock
    }
    touchpad {
        tap
        natural-scroll
    }
}

binds {
    Mod+T { spawn "alacritty"; }
    Mod+Q { close-window; }
    Mod+Shift+E { quit; }
}
BASE_NIRI_EOF
        fi

        echo "" >> "$niri_config"
        echo "$include_line" >> "$niri_config"
        success "Niri config initialized with default settings and Agility Shell include."
        return
    fi

    # Clean old caffyne includes if any
    if grep -qF 'caffyne-shell' "$niri_config"; then
        info "Removing old caffyne-shell include from niri config..."
        sed -i '/caffyne-shell/d' "$niri_config"
    fi

    if grep -qF "$include_line" "$niri_config"; then
        info "Agility Shell include already present in $niri_config."
        return
    fi

    info "Appending Agility Shell include to existing Niri config..."
    echo "" >> "$niri_config"
    echo "$include_line" >> "$niri_config"
    success "Niri config updated with Agility Shell include."
}

setup_matugen() {
    info "Configuring Matugen templates..."

    local matugen_config_dir="$HOME/.config/matugen"
    local matugen_conf="$matugen_config_dir/config.toml"

    mkdir -p "$matugen_config_dir"

    if [[ ! -f "$matugen_conf" ]]; then
        info "Creating Matugen config.toml..."
        touch "$matugen_conf"
    fi

    if ! grep -q "^\[config\]$" "$matugen_conf"; then
        info "Adding [config] section..."
        printf "[config]\n" >> "$matugen_conf"
    fi

    # Remove old caffyne entries if present
    if grep -q '\[templates.caffyne\]' "$matugen_conf"; then
        info "Removing old caffyne matugen config entries..."
        sed -i '/\[templates.caffyne\]/,/^$/d' "$matugen_conf"
        sed -i '/# Caffyne Shell Colors/d' "$matugen_conf"
    fi

    if grep -q "\[templates.agility\]" "$matugen_conf"; then
        info "Matugen config entry already exists -- skipping append."
    else
        info "Appending Agility Shell template config to matugen/config.toml..."
        cat <<MATUGEN_EOF >> "$matugen_conf"

# Agility Shell Colors
[templates.agility]
input_path = '~/.config/agility-shell/style/agility-shell-colors.css'
output_path = '~/.config/agility-shell/style/colors.css'
MATUGEN_EOF
    fi
    success "Matugen configured."
}

# -- Remote & Local update routines -------------------------------------------
update_from_github_release() {
    info "Updating Agility Shell to latest release tag from GitHub ($REPO_URL)..."
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        git -C "$INSTALL_DIR" fetch --tags origin
        local latest_tag
        latest_tag=$(git -C "$INSTALL_DIR" describe --tags "$(git -C "$INSTALL_DIR" rev-list --tags --max-count=1 2>/dev/null)" 2>/dev/null || echo "")
        if [[ -n "$latest_tag" ]]; then
            info "Checking out latest release tag: $latest_tag"
            git -C "$INSTALL_DIR" checkout "$latest_tag"
        else
            warn "No release tags found -- falling back to main branch."
            git -C "$INSTALL_DIR" fetch origin
            git -C "$INSTALL_DIR" reset --hard origin/main
        fi
    else
        info "Installation directory is not a git repository -- cloning latest release..."
        local tmp_clone
        tmp_clone=$(mktemp -d)
        git clone "$REPO_URL" "$tmp_clone/repo"
        local latest_tag
        latest_tag=$(git -C "$tmp_clone/repo" describe --tags "$(git -C "$tmp_clone/repo" rev-list --tags --max-count=1 2>/dev/null)" 2>/dev/null || echo "")
        if [[ -n "$latest_tag" ]]; then
            info "Checking out latest release tag: $latest_tag"
            git -C "$tmp_clone/repo" checkout "$latest_tag"
        fi
        if command -v rsync &>/dev/null; then
            rsync -a --delete --exclude='venv' --exclude='__pycache__' "$tmp_clone/repo/" "$INSTALL_DIR/"
        else
            cp -r "$tmp_clone/repo"/.git "$INSTALL_DIR/"
            cp -r "$tmp_clone/repo"/* "$INSTALL_DIR/"
        fi
        rm -rf "$tmp_clone"
    fi
    success "Release files synchronized."
}

update_from_github_main() {
    info "Updating Agility Shell to latest main branch ($REPO_URL)..."
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        git -C "$INSTALL_DIR" fetch origin
        git -C "$INSTALL_DIR" checkout -B main origin/main 2>/dev/null || git -C "$INSTALL_DIR" reset --hard origin/main
    else
        info "Installation directory is not a git repository -- cloning latest main branch..."
        local tmp_clone
        tmp_clone=$(mktemp -d)
        git clone --branch main "$REPO_URL" "$tmp_clone/repo"
        if command -v rsync &>/dev/null; then
            rsync -a --delete --exclude='venv' --exclude='__pycache__' "$tmp_clone/repo/" "$INSTALL_DIR/"
        else
            cp -r "$tmp_clone/repo"/.git "$INSTALL_DIR/"
            cp -r "$tmp_clone/repo"/* "$INSTALL_DIR/"
        fi
        rm -rf "$tmp_clone"
    fi
    success "Main branch synchronized with latest commits."
}

update_from_github() {
    update_from_github_main
}

update_from_local() {
    local src_dir="${1:-}"

    # Auto-detect local source directory if not provided
    if [[ -z "$src_dir" ]]; then
        local cwd
        cwd="$(pwd)"
        local script_src="${BASH_SOURCE[0]:-}"
        local script_dir=""
        local repo_root=""
        if [[ -n "$script_src" && "$script_src" != "bash" && "$script_src" != "sh" && "$script_src" != "/dev/stdin" && -f "$script_src" ]]; then
            script_dir="$(cd "$(dirname "$script_src")" 2>/dev/null && pwd || echo "")"
            repo_root="$(cd "$script_dir/.." 2>/dev/null && pwd || echo "")"
        fi

        if [[ -f "$cwd/main.py" && -f "$cwd/bar.py" && -d "$cwd/bar_widgets" && "$(realpath "$cwd" 2>/dev/null)" != "$(realpath "$INSTALL_DIR" 2>/dev/null)" ]]; then
            src_dir="$cwd"
        elif [[ -n "$repo_root" && -f "$repo_root/main.py" && -f "$repo_root/bar.py" && -d "$repo_root/bar_widgets" && "$(realpath "$repo_root" 2>/dev/null)" != "$(realpath "$INSTALL_DIR" 2>/dev/null)" ]]; then
            src_dir="$repo_root"
        elif [[ -n "$script_dir" && -f "$script_dir/main.py" && -f "$script_dir/bar.py" && -d "$script_dir/bar_widgets" && "$(realpath "$script_dir" 2>/dev/null)" != "$(realpath "$INSTALL_DIR" 2>/dev/null)" ]]; then
            src_dir="$script_dir"
        fi
    fi

    # If still not determined, prompt the user
    if [[ -z "$src_dir" || ! -f "$src_dir/main.py" ]]; then
        echo
        prompt_user "  Enter path to local Agility Shell repository/directory: " user_path ""
        src_dir="$user_path"
    fi

    src_dir="$(realpath "$src_dir" 2>/dev/null || echo "$src_dir")"

    if [[ ! -d "$src_dir" || ! -f "$src_dir/main.py" || ! -f "$src_dir/bar.py" ]]; then
        die "Invalid Agility Shell source directory: '$src_dir'"
    fi

    if [[ "$src_dir" == "$(realpath "$INSTALL_DIR" 2>/dev/null || true)" ]]; then
        die "Source directory cannot be the same as installation directory ($INSTALL_DIR)."
    fi

    info "Deploying Agility Shell from local source ($src_dir) to $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
    if command -v rsync &>/dev/null; then
        rsync -a --delete --exclude='.git' --exclude='venv' --exclude='__pycache__' "$src_dir/" "$INSTALL_DIR/"
    else
        cp -r "$src_dir"/* "$INSTALL_DIR/"
    fi
    success "Local files synchronized."
}

install_cli() {
    info "Setting up agl CLI..."
    local bin_dir="$HOME/.local/bin"
    mkdir -p "$bin_dir"

    if [[ -f "$INSTALL_DIR/bin/agl" ]]; then
        ln -sf "$INSTALL_DIR/bin/agl" "$bin_dir/agl"
        chmod +x "$INSTALL_DIR/bin/agl" "$bin_dir/agl"
        success "agl CLI installed to $bin_dir/agl"
    fi

    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        warn "$HOME/.local/bin is not in your PATH. Add it to ~/.bashrc or ~/.zshrc:"
        warn "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
}

# -- Update --------------------------------------------------------------------
do_update() {
    local source_mode="$1"
    local local_path="${2:-}"

    info "Updating Agility Shell..."

    local tmp_backup
    tmp_backup=$(mktemp -d)

    backup_preserved_dirs "$tmp_backup"
    backup_preserved_files "$tmp_backup"

    if [[ "$source_mode" == "release" || "$source_mode" == "github_release" ]]; then
        update_from_github_release
    elif [[ "$source_mode" == "main" || "$source_mode" == "github_main" || "$source_mode" == "github" ]]; then
        update_from_github_main
    elif [[ "$source_mode" == "local" ]]; then
        update_from_local "$local_path"
    else
        die "Unknown update source mode: $source_mode"
    fi

    restore_preserved_files "$tmp_backup"
    restore_preserved_dirs "$tmp_backup"
    rm -rf "$tmp_backup"

    info "Refreshing Python dependencies..."
    if [[ ! -d "$INSTALL_DIR/venv" ]]; then
        info "Setting up Python virtual environment..."
        python -m venv "$INSTALL_DIR/venv"
    fi
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip -q
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q
    success "Python dependencies updated."

    compile_snippets
    inject_niri_include
    setup_matugen
    install_cli

    chmod +x "$INSTALL_DIR"/*.sh "$INSTALL_DIR/scripts"/*.sh "$INSTALL_DIR/bin/agl" "$INSTALL_DIR/agility-shell" 2>/dev/null || true

    success "Agility Shell updated successfully!"
    echo
    post_update_action
}

post_update_action() {
    prompt_user "  Would you like to restart Agility Shell now? [Y/n]: " restart_choice "y"
    case "$restart_choice" in
        [nN]|[nN][oO])
            echo
            info "Restart skipped. You can manually restart using: agl restart"
            echo
            prompt_user "  Would you like to reboot the system now? [y/N]: " reboot_choice "n"
            case "$reboot_choice" in
                [yY]|[yY][eE][sS])
                    info "Rebooting system..."
                    systemctl reboot || sudo reboot
                    ;;
                *)
                    info "Reboot skipped."
                    ;;
            esac
            ;;
        *)
            info "Restarting Agility Shell..."
            if [[ -f "$INSTALL_DIR/scripts/restart.sh" ]]; then
                exec "$INSTALL_DIR/scripts/restart.sh"
            elif [[ -f "$INSTALL_DIR/restart.sh" ]]; then
                exec "$INSTALL_DIR/restart.sh"
            elif command -v agl &>/dev/null; then
                exec agl restart
            else
                warn "Restart script not found at $INSTALL_DIR/scripts/restart.sh"
            fi
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

    local mode=""
    local custom_path=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --release|-r)
                mode="release"
                shift
                ;;
            --main|-m)
                mode="main"
                shift
                ;;
            --github|--remote|-g)
                mode="main"
                shift
                ;;
            --local|-l)
                mode="local"
                if [[ $# -gt 1 && ! "$2" =~ ^-- ]]; then
                    custom_path="$2"
                    shift 2
                else
                    shift
                fi
                ;;
            -h|--help)
                echo "Usage: agl update [OPTIONS] or ./update.sh [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --release, -r      Update to latest release tag"
                echo "  --main, -m         Update to latest main branch"
                echo "  --local, -l [PATH] Update from local directory"
                echo "  -h, --help         Show this help message"
                exit 0
                ;;
            *)
                shift
                ;;
        esac
    done

    if [[ -z "$mode" ]]; then
        echo -e "  Select update source:"
        echo -e "  ${BOLD}1)${RESET} Latest release tag (stable release)"
        echo -e "  ${BOLD}2)${RESET} Main branch (latest GitHub commits)"
        echo -e "  ${BOLD}3)${RESET} Local directory (local files / repository)"
        echo -e "  ${BOLD}q)${RESET} Quit"
        echo
        prompt_user "  Choice [1/2/3/q]: " choice "1"
        case "$choice" in
            1) mode="release" ;;
            2) mode="main" ;;
            3) mode="local" ;;
            q|Q) info "Update aborted."; exit 0 ;;
            *) die "Invalid choice." ;;
        esac
    fi

    do_update "$mode" "$custom_path"
}

main "$@"

