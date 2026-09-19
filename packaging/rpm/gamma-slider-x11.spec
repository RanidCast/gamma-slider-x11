Name:           gamma-slider-x11
Version:        %{?version}%{!?version:1.1.0}
Release:        1%{?dist}
Summary:        Simple X11 tray app for changing screen color temperature

License:        GPL-3.0-or-later
URL:            https://github.com/RanidCast/gamma-slider-x11
Source0:        %{name}-%{version}.zip

BuildArch:      noarch
Requires:       python3
Requires:       libX11
Requires:       libxcb

%description
Gamma Slider X11 is a lightweight tray utility for changing screen color
temperature on Linux/X11. It includes a small bundled X11/RandR gamma engine.

%prep
%setup -q -c

%install
mkdir -p %{buildroot}/opt/%{name}
mkdir -p %{buildroot}/usr/bin
mkdir -p %{buildroot}/usr/share/applications
mkdir -p %{buildroot}/usr/share/icons/hicolor/scalable/apps

install -m 755 app.py %{buildroot}/opt/%{name}/app.py
install -m 755 install.sh %{buildroot}/opt/%{name}/install.sh
install -m 644 gamma_slider_icon.svg %{buildroot}/usr/share/icons/hicolor/scalable/apps/gamma-slider-x11.svg

cat > %{buildroot}/usr/bin/gamma-slider-x11 <<'EOF'
#!/usr/bin/env bash
exec python3 /opt/gamma-slider-x11/app.py "$@"
EOF
chmod 755 %{buildroot}/usr/bin/gamma-slider-x11

cat > %{buildroot}/usr/share/applications/gamma-slider-x11.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Gamma Slider X11
Comment=Change screen color temperature on X11
Exec=gamma-slider-x11
Icon=gamma-slider-x11
Terminal=false
Categories=Utility;Settings;
EOF
chmod 644 %{buildroot}/usr/share/applications/gamma-slider-x11.desktop

%files
/opt/%{name}/app.py
/opt/%{name}/install.sh
/usr/bin/gamma-slider-x11
/usr/share/applications/gamma-slider-x11.desktop
/usr/share/icons/hicolor/scalable/apps/gamma-slider-x11.svg

%changelog
* Sat Sep 19 2026 RanidCast - 1.1.0-1
- Add Windows support, color modes, and updated documentation
