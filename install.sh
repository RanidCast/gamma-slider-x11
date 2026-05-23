#!/usr/bin/env bash
set -euo pipefail

# Absolute path to current directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_PATH="$DIR/app.py"
ICON_PATH="gamma-slider-x11"
MENU_FILE="$HOME/.local/share/applications/gamma-slider-x11.desktop"
AUTOSTART_FILE="$HOME/.config/autostart/gamma-slider-x11.desktop"
DATA_DIR="$HOME/.local/share/gamma-slider"
CONFIG_DIR="$HOME/.config/gamma-slider"
LOCK_FILE="/tmp/gamma_slider.lock"

usage() {
    echo "Usage: $0 [--install|--uninstall|--check]"
}

uninstall() {
    echo "Uninstalling Gamma Slider X11..."
    rm -f "$MENU_FILE" "$AUTOSTART_FILE" "$LOCK_FILE"
    rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/gamma-slider-x11.svg"
    rm -rf "$DATA_DIR" "$CONFIG_DIR"
    echo "Done. Repository files were not removed: $DIR"
}

check_install() {
    echo "Checking Gamma Slider X11 installation..."
    test -x "$APP_PATH" && echo "OK: app.py is executable" || echo "ERR: app.py is not executable"
    test -f "$MENU_FILE" && echo "OK: menu entry exists: $MENU_FILE" || echo "ERR: menu entry not found: $MENU_FILE"
    test -f "$AUTOSTART_FILE" && echo "OK: autostart entry exists: $AUTOSTART_FILE" || echo "ERR: autostart entry not found: $AUTOSTART_FILE"
    test -f "$DATA_DIR/gamma-engine" && echo "OK: gamma-engine is unpacked" || echo "INFO: gamma-engine will appear after first run"
    test -f "$HOME/.local/share/icons/hicolor/scalable/apps/gamma-slider-x11.svg" && echo "OK: icon installed" || echo "INFO: icon not installed (will use after next login or icon cache update)"

    if command -v desktop-file-validate >/dev/null 2>&1; then
        desktop-file-validate "$MENU_FILE" && echo "OK: .desktop is valid"
    else
        echo "INFO: desktop-file-validate not found, skipping .desktop validation"
    fi
}

case "${1:---install}" in
    --install) ;;
    --uninstall) uninstall; exit 0 ;;
    --check) check_install; exit 0 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 1 ;;
esac

echo "Installing Gamma Slider X11 from $DIR..."

# 1. Make the main script executable
chmod +x "$APP_PATH"

# 2. Create .desktop file
CAT_FILE="[Desktop Entry]
Type=Application
Name=Gamma Slider X11
Comment=Quick screen color temperature control (X11)
Exec=python3 \"$APP_PATH\"
Icon=$ICON_PATH
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true"

# 3. Install menu entry
mkdir -p "$(dirname "$MENU_FILE")"
echo "$CAT_FILE" > "$MENU_FILE"
chmod +x "$MENU_FILE"

# 4. Install autostart entry
mkdir -p "$(dirname "$AUTOSTART_FILE")"
echo "$CAT_FILE" > "$AUTOSTART_FILE"
chmod +x "$AUTOSTART_FILE"

# 5. Install application icon (scalable SVG)
ICON_SRC="$DIR/gamma_slider_icon.svg"
if [ -f "$ICON_SRC" ]; then
    ICON_DST_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
    mkdir -p "$ICON_DST_DIR"
    cp -f "$ICON_SRC" "$ICON_DST_DIR/gamma-slider-x11.svg"
    echo "Icon installed to $ICON_DST_DIR/gamma-slider-x11.svg"
    echo ""
    echo ">>> IMPORTANT: To make the new icon appear in the menu, run:"
    echo "    gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor/"
    echo "    # For KDE/Plasma also:"
    echo "    kbuildsycoca6 --noincremental   # or kbuildsycoca5 on older Plasma"
    echo "    # Then restart your panel or log out / log in."
    echo ""
fi

echo "Done! The app is now in the menu and will start on next login."
echo "You can run it now: python3 \"$APP_PATH\""
echo "Check installation: $0 --check"
