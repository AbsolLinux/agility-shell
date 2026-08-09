Name:           caffyne-shell
Version:        1.0.0
Release:        3%{?dist}
Summary:        A modern, GTK-based desktop shell built on top of Fabric

License:        GPL-3.0-only
URL:            https://github.com/caffyne-org/caffyne-shell
Source0:        https://github.com/caffyne-org/caffyne-shell/archive/refs/heads/main.tar.gz#/caffyne-shell-1.0.0.tar.gz
Source1:        https://github.com/Fabric-Development/fabric/archive/refs/heads/main.tar.gz#/fabric-main.tar.gz
Source2:        https://github.com/Fabric-Development/fabric-cli/archive/refs/heads/main.tar.gz#/fabric-cli-main.tar.gz
Source3:        https://codeberg.org/LGFae/awww/archive/main.tar.gz#/awww-main.tar.gz
Patch0:         fabric-pygobject.patch


BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-wheel
BuildRequires:  python3-setuptools
BuildRequires:  make
BuildRequires:  gcc
BuildRequires:  wayland-devel
BuildRequires:  gtk3-devel
BuildRequires:  golang
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  rust
BuildRequires:  cargo
BuildRequires:  lz4-devel
BuildRequires:  wayland-protocols-devel

Provides:       python3-fabric = 0.0.2
Provides:       fabric-cli = 0.0.2

%global __requires_exclude ^python3.*dist.*$

# FHS workaround for python modules, I really hate non FHS stuff on nixos
%global __os_install_post %{nil}

# Python dependencies
Requires:       python3-cffi
Requires:       python3-click
Requires:       python3-loguru
Requires:       python3-pam
Requires:       python3-pillow
Requires:       python3-psutil
Requires:       python3-cairo
Requires:       python3-pycparser
Requires:       python3-gobject
Requires:       python3-rapidfuzz
Requires:       python3-setproctitle
Requires:       python3-six

# System packages
Requires:       gtk-layer-shell
Requires:       libdbusmenu-gtk3
Requires:       cinnamon-desktop
Requires:       gnome-bluetooth
Requires:       matugen
Requires:       playerctl
Requires:       brightnessctl
Requires:       wf-recorder
Requires:       upower
Requires:       NetworkManager
Requires:       bluez
Requires:       swayidle
Requires:       gtk-session-lock
%description
caffyne shell is a modern, GTK-based desktop shell built on top of Fabric, Python, and GTK.
It features a highly customizable drag-and-drop panel, fluid animations, and deeply integrated system applets designed specifically for modern Wayland compositors.

%prep
%setup -q -n caffyne-shell-main
%setup -q -T -D -a 1 -n caffyne-shell-main
%setup -q -T -D -a 2 -n caffyne-shell-main
%setup -q -T -D -a 3 -n caffyne-shell-main

%patch -P0 -p1 -d fabric-main



%build
# Compile native snippets
pushd snippets/blur/lib
make %{?_smp_mflags}
popd

pushd snippets/hacktk/lib
make %{?_smp_mflags}
popd

# Build Fabric CLI
pushd fabric-cli-main
%meson
%meson_build
popd

# Build Fabric Python package and bundle missing PyPI dependencies
pushd fabric-main
pip3 wheel --no-deps --wheel-dir dist . thefuzz==0.22.1
popd

# Build awww
pushd awww
cargo build --release
popd

%install
# Create directories
mkdir -p %{buildroot}/usr/share/caffyne-shell
mkdir -p %{buildroot}%{_bindir}

cp -r assets bar_widgets config desktop_applets greetd icons lightdm matugen services snippets sounds style svgs themes utils wallpapers windows bar.py lockscreen.py main.py plugin_loader.py user_options.py %{buildroot}/usr/share/caffyne-shell/

cp packaging/fedora/caffyne-shell %{buildroot}%{_bindir}/caffyne-shell
chmod +x %{buildroot}%{_bindir}/caffyne-shell

# Fix permissions on shared libraries
chmod +x %{buildroot}/usr/share/caffyne-shell/snippets/blur/lib/libblur.so
chmod +x %{buildroot}/usr/share/caffyne-shell/snippets/hacktk/lib/libhacktk.so

# Install Fabric CLI
pushd fabric-cli-main
%meson_install
popd

# Install Fabric package
pushd fabric-main
pip3 install --no-index --no-deps --root %{buildroot} --prefix /usr dist/*.whl
popd

# Install awww
install -m 755 awww/target/release/awww %{buildroot}%{_bindir}/awww
install -m 755 awww/target/release/awww-daemon %{buildroot}%{_bindir}/awww-daemon

%files
/usr/share/caffyne-shell/
%{_bindir}/caffyne-shell
%{_bindir}/fabric-cli
%{_bindir}/awww
%{_bindir}/awww-daemon
/usr/share/bash-completion/completions/fabric-cli
/usr/share/fish/completions/fabric-cli.fish
/usr/share/zsh/site-functions/_fabric-cli
/usr/lib*/python3.*/site-packages/fabric/
/usr/lib*/python3.*/site-packages/fabric-*.dist-info/
/usr/lib*/python3.*/site-packages/thefuzz/
/usr/lib*/python3.*/site-packages/thefuzz-*.dist-info/

%changelog
* Fri Jul 03 2026 Maintainer <amritanshukumar13012008@gmail.com> - 1.0.0-1
- First packaging for Fedora COPR.
- Bundled fabric and fabric-cli into the monolithic package.
* Sun Aug 09 2026 Maintainer <caffyne@proton.me> - 1.0.0-3
