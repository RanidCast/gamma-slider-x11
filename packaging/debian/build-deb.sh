#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
VERSION="${VERSION:-1.1.0}"
PKG_NAME="gamma-slider-x11"
ARCH="all"
ROOT="$SCRIPT_DIR/${PKG_NAME}_${VERSION}_${ARCH}"
OUTPUT_DIR="$SCRIPT_DIR/dist"

rm -rf "$ROOT"
mkdir -p "$ROOT/DEBIAN" "$ROOT/opt/$PKG_NAME" "$ROOT/usr/bin"
mkdir -p "$ROOT/usr/share/applications" "$ROOT/usr/share/icons/hicolor/scalable/apps" "$OUTPUT_DIR"

install -m 755 "$PROJECT_ROOT/app.py" "$ROOT/opt/$PKG_NAME/app.py"
install -m 755 "$PROJECT_ROOT/install.sh" "$ROOT/opt/$PKG_NAME/install.sh"
install -m 644 "$PROJECT_ROOT/gamma_slider_icon.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/gamma-slider-x11.svg"

cat > "$ROOT/usr/bin/gamma-slider-x11" <<'EOF'
#!/usr/bin/env bash
exec python3 /opt/gamma-slider-x11/app.py "$@"
EOF
chmod 755 "$ROOT/usr/bin/gamma-slider-x11"

cat > "$ROOT/usr/share/applications/gamma-slider-x11.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Gamma Slider X11
Comment=Change screen color temperature on X11
Exec=gamma-slider-x11
Icon=gamma-slider-x11
Terminal=false
Categories=Utility;Settings;
EOF
chmod 644 "$ROOT/usr/share/applications/gamma-slider-x11.desktop"

cat > "$ROOT/DEBIAN/control" <<EOF
Package: $PKG_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Depends: python3, python3-pyqt5 | python3-pyqt6, libx11-6, libxcb1, libxcb-randr0
Maintainer: RanidCast
Description: Simple X11 tray app for changing screen color temperature
 Gamma Slider X11 is a lightweight tray utility for changing screen color
 temperature on Linux/X11. It includes a small bundled X11/RandR gamma engine.
EOF

fakeroot dpkg-deb --build "$ROOT" "$OUTPUT_DIR/${PKG_NAME}_${VERSION}_${ARCH}.deb"
rm -rf "$ROOT"
printf 'Built %s\n' "$OUTPUT_DIR/${PKG_NAME}_${VERSION}_${ARCH}.deb"
