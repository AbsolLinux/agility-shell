#!/usr/bin/env bash
# =============================================================================
#  Agility Shell -- Installer
#  Arch Linux only
# =============================================================================

set -euo pipefail

REPO_URL="https://github.com/AbsolOrg/agility-shell.git"
INSTALL_DIR="$HOME/.config/agility-shell"
CONFIG_DIR="$INSTALL_DIR/config"

SCRIPT_SRC="${BASH_SOURCE[0]:-}"
if [[ -n "$SCRIPT_SRC" && "$SCRIPT_SRC" != "bash" && "$SCRIPT_SRC" != "sh" && "$SCRIPT_SRC" != "/dev/stdin" && -f "$SCRIPT_SRC" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SRC")" 2>/dev/null && pwd || echo "")"
    REPO_ROOT="$(cd "$SCRIPT_DIR/.." 2>/dev/null && pwd || echo "")"
else
    SCRIPT_DIR=""
    REPO_ROOT=""
fi

IS_LOCAL_REPO=false
LOCAL_SRC_DIR=""
if [[ -n "$REPO_ROOT" && -f "$REPO_ROOT/main.py" && -f "$REPO_ROOT/bar.py" && -d "$REPO_ROOT/bar_widgets" ]]; then
    IS_LOCAL_REPO=true
    LOCAL_SRC_DIR="$REPO_ROOT"
elif [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/main.py" && -f "$SCRIPT_DIR/bar.py" && -d "$SCRIPT_DIR/bar_widgets" ]]; then
    IS_LOCAL_REPO=true
    LOCAL_SRC_DIR="$SCRIPT_DIR"
fi

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

cat << "EOF"

                       m                
                     wq                 
                   qqX                  
                  dqd                   
                wwwp      1             
              .ppqm     Jr              
             <wqqp     pp               
            !dpqw    ~ww                
            pppd_   [pq;                
           CpqqL    pwU   `c            
          (pqqq    Qpp    ww!           
         YmqqqZ   ?qqw   |ppp           
        ]pqwww    qww    Zqqwml         
        qpqw:     d.      Owppq"        
       )pw       C          .mwL        
       wp                     wp[       
      _b                       qq,      
      m                          Z   
      
EOF

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
check_arch() {
    if ! command -v pacman &>/dev/null; then
        die "This installer is for Arch Linux only."
    fi
}

check_not_root() {
    if [[ "$EUID" -eq 0 ]]; then
        die "Please run this script as a regular user, not root."
    fi
}

# -- Dependencies definitions --------------------------------------------------
PACMAN_DEPS=(
    gtk3
    cairo
    libgirepository
    gobject-introspection
    gtk-layer-shell
    libdbusmenu-gtk3
    cinnamon-desktop
    gnome-bluetooth-3.0
    gtk-session-lock
    matugen
    playerctl
    brightnessctl
    wf-recorder
    upower
    swayidle
    networkmanager
    bluez
    python
    python-pip
    awww
    base-devel
    git
    niri
)

AUR_DEPS=(
    fabric-cli-git
)

# -- yay bootstrap -------------------------------------------------------------
ensure_yay() {
    if command -v yay &>/dev/null; then
        success "yay is already installed."
        return
    elif command -v paru &>/dev/null; then
        success "paru is already installed."
        return
    fi

    info "AUR helper not found -- installing yay from AUR..."
    sudo pacman -S --needed --noconfirm git base-devel

    local tmp
    tmp=$(mktemp -d)
    git clone https://aur.archlinux.org/yay.git "$tmp/yay"
    (cd "$tmp/yay" && makepkg -si --noconfirm)
    rm -rf "$tmp"
    success "yay installed."
}

# -- Pre-flight dependency check & prompt ---------------------------------------
check_and_install_deps() {
    info "Checking system dependencies..."
    local missing_pacman=()
    local missing_aur=()

    for pkg in "${PACMAN_DEPS[@]}"; do
        if ! pacman -Qi "$pkg" &>/dev/null; then
            missing_pacman+=("$pkg")
        fi
    done

    for pkg in "${AUR_DEPS[@]}"; do
        if ! pacman -Qi "$pkg" &>/dev/null; then
            missing_aur+=("$pkg")
        fi
    done

    local need_yay=false
    if [[ ${#missing_aur[@]} -gt 0 ]] && ! command -v yay &>/dev/null && ! command -v paru &>/dev/null; then
        need_yay=true
    fi

    if [[ ${#missing_pacman[@]} -eq 0 && ${#missing_aur[@]} -eq 0 && "$need_yay" == "false" ]]; then
        success "All required dependencies are already installed."
        return 0
    fi

    echo
    warn "The following dependencies are missing and required:"
    if [[ ${#missing_pacman[@]} -gt 0 ]]; then
        echo -e "  ${BOLD}Pacman packages:${RESET} ${CYAN}${missing_pacman[*]}${RESET}"
    fi
    if [[ ${#missing_aur[@]} -gt 0 ]]; then
        echo -e "  ${BOLD}AUR packages:${RESET}    ${CYAN}${missing_aur[*]}${RESET}"
    fi
    if [[ "$need_yay" == "true" ]]; then
        echo -e "  ${BOLD}AUR Helper:${RESET}      ${CYAN}yay (will be bootstrapped)${RESET}"
    fi
    echo

    prompt_user "  Would you like to install the missing dependencies now? [Y/n]: " dep_choice "y"
    case "$dep_choice" in
        [nN]|[nN][oO])
            warn "Dependency installation skipped by user."
            ;;
        *)
            if [[ ${#missing_pacman[@]} -gt 0 ]]; then
                info "Installing missing pacman packages..."
                sudo pacman -S --needed --noconfirm "${missing_pacman[@]}"
                success "Pacman dependencies installed."
            fi

            if [[ "$need_yay" == "true" ]]; then
                ensure_yay
            fi

            if [[ ${#missing_aur[@]} -gt 0 ]]; then
                local aur_helper="yay"
                if command -v paru &>/dev/null; then
                    aur_helper="paru"
                fi
                info "Installing missing AUR packages using $aur_helper..."
                "$aur_helper" -S --needed --noconfirm "${missing_aur[@]}"
                success "AUR dependencies installed."
            fi
            ;;
    esac
}

# -- Deploy files to INSTALL_DIR ------------------------------------------------
deploy_source() {
    if [[ "$IS_LOCAL_REPO" == "true" ]]; then
        if [[ "$(realpath "$LOCAL_SRC_DIR")" == "$(realpath "$INSTALL_DIR" 2>/dev/null || true)" ]]; then
            info "Already located in $INSTALL_DIR."
            return
        fi

        info "Deploying Agility Shell from local source ($LOCAL_SRC_DIR) to $INSTALL_DIR..."
        mkdir -p "$INSTALL_DIR"
        if command -v rsync &>/dev/null; then
            rsync -a --delete --exclude='.git' --exclude='venv' --exclude='__pycache__' "$LOCAL_SRC_DIR/" "$INSTALL_DIR/"
        else
            cp -r "$LOCAL_SRC_DIR"/* "$INSTALL_DIR/"
        fi
        success "Local files deployed."
    else
        if [[ -d "$INSTALL_DIR" ]]; then
            rm -rf "$INSTALL_DIR"
        fi
        info "Cloning Agility Shell from $REPO_URL to $INSTALL_DIR..."
        git clone "$REPO_URL" "$INSTALL_DIR"
        success "Repository cloned."
    fi
}

# -- Python venv ---------------------------------------------------------------
setup_venv() {
    info "Setting up Python virtual environment..."
    python -m venv "$INSTALL_DIR/venv"
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip -q
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q
    success "Python dependencies installed."
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

# -- Niri Config Integration ---------------------------------------------------
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

# -- Matugen Setup -------------------------------------------------------------
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

# -- Install CLI ---------------------------------------------------------------
install_cli() {
    info "Setting up agl CLI tool..."
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

# -- Prompt Reboot -------------------------------------------------------------
prompt_reboot() {
    echo
    warn "A system reboot is recommended to ensure all services, environment variables, and compositor configs take effect."
    echo
    prompt_user "  Would you like to reboot now? [y/N]: " reboot_choice "n"
    case "$reboot_choice" in
        [yY]|[yY][eE][sS])
            info "Rebooting system..."
            systemctl reboot || sudo reboot
            ;;
        *)
            info "Reboot skipped. You can manually start the shell using: agl start"
            ;;
    esac
}

# -- Fresh Install -------------------------------------------------------------
do_install() {
    info "Starting installation of Agility Shell..."

    check_and_install_deps
    deploy_source
    setup_venv
    compile_snippets
    inject_niri_include
    setup_matugen
    install_cli

    chmod +x "$INSTALL_DIR"/*.sh "$INSTALL_DIR/scripts"/*.sh "$INSTALL_DIR/bin/agl" "$INSTALL_DIR/agility-shell" 2>/dev/null || true

    echo
    success "Agility Shell installed successfully!"
    echo
    echo -e "  ${BOLD}Start shell:${RESET}"
    echo -e "    ${CYAN}agl start${RESET}  ${DIM}(or ~/.config/agility-shell/start.sh)${RESET}"
    echo
    echo -e "  ${BOLD}CLI Commands:${RESET}"
    echo -e "    ${CYAN}agl restart${RESET}   - Restart running shell"
    echo -e "    ${CYAN}agl update${RESET}    - Update to latest version"
    echo -e "    ${CYAN}agl uninstall${RESET} - Uninstall cleanly"
    echo
    echo -e "  ${BOLD}Compositor configs:${RESET}"
    echo -e "    ${CYAN}~/.config/agility-shell/config/${RESET}"
    echo
    echo -e "  ${BOLD}Niri integration:${RESET}"
    echo -e "    Auto-start and keybindings included in: ${CYAN}~/.config/niri/config.kdl${RESET}"
    echo

    prompt_reboot
}

# Directories and files to preserve during updates (relative to INSTALL_DIR)
PRESERVE_DIRS=("wallpapers" "config")
PRESERVE_FILES=(
    "style/colors.css"
    "style/borders.css"
    "style/fonts.css"
)

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
        info "Cloning latest release from GitHub..."
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
        info "Cloning latest main branch from GitHub..."
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

do_update() {
    local target_mode="$1"
    info "Updating existing Agility Shell installation..."

    check_and_install_deps

    local tmp_backup
    tmp_backup=$(mktemp -d)

    backup_preserved_dirs "$tmp_backup"
    backup_preserved_files "$tmp_backup"

    if [[ "$target_mode" == "release" ]]; then
        update_from_github_release
    else
        update_from_github_main
    fi

    restore_preserved_files "$tmp_backup"
    restore_preserved_dirs "$tmp_backup"
    rm -rf "$tmp_backup"

    setup_venv
    compile_snippets
    inject_niri_include
    setup_matugen
    install_cli

    chmod +x "$INSTALL_DIR"/*.sh "$INSTALL_DIR/scripts"/*.sh "$INSTALL_DIR/bin/agl" "$INSTALL_DIR/agility-shell" 2>/dev/null || true

    echo
    success "Agility Shell updated successfully!"
    echo
    prompt_user "  Would you like to restart Agility Shell now? [Y/n]: " restart_choice "y"
    case "$restart_choice" in
        [nN]|[nN][oO])
            info "Restart skipped. You can manually restart using: agl restart"
            prompt_reboot
            ;;
        *)
            info "Restarting Agility Shell..."
            if [[ -f "$INSTALL_DIR/scripts/restart.sh" ]]; then
                exec "$INSTALL_DIR/scripts/restart.sh"
            elif command -v agl &>/dev/null; then
                exec agl restart
            else
                prompt_reboot
            fi
            ;;
    esac
}

# -- Entry point ---------------------------------------------------------------
main() {
    echo
    echo -e "${BOLD}${CYAN}+==================================+${RESET}"
    echo -e "${BOLD}${CYAN}|       Agility Shell Setup        |${RESET}"
    echo -e "${BOLD}${CYAN}+==================================+${RESET}"
    echo

    check_arch
    check_not_root

    if [[ -d "$INSTALL_DIR" ]]; then
        warn "Existing installation found at $INSTALL_DIR"
        echo
        echo -e "  Please choose an option:"
        echo -e "  ${BOLD}1)${RESET} ${RED}Reinstall from scratch${RESET} (Clean wipe & fresh install)"
        echo -e "  ${BOLD}2)${RESET} ${CYAN}Update with latest release tag${RESET} (Preserves configs & wallpapers)"
        echo -e "  ${BOLD}3)${RESET} ${GREEN}Update with main branch${RESET} (Latest commits, preserves configs & wallpapers)"
        echo -e "  ${BOLD}4)${RESET} Cancel"
        echo
        prompt_user "  Choice [1/2/3/4]: " choice "2"
        case "$choice" in
            1)
                warn "Wiping existing installation..."
                rm -rf "$INSTALL_DIR"
                do_install
                ;;
            2)
                do_update "release"
                ;;
            3)
                do_update "main"
                ;;
            4|[qQ]|[eE][xX][iI][tT])
                info "Installation cancelled."
                exit 0
                ;;
            *)
                die "Invalid choice: '$choice'"
                ;;
        esac
    else
        do_install
    fi
}

main "$@"

