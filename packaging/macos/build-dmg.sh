#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

TAG="${1:-dev}"
APP="dist/Gamma Slider.app"
STAGE="$(mktemp -d)"
DMG="gamma-slider-macos-${TAG}.dmg"

python3 packaging/macos/make_icns.py
pyinstaller --noconfirm gamma-slider-macos.spec

if [ ! -d "$APP" ]; then
  echo "missing $APP" >&2
  exit 1
fi

codesign --force --deep --sign - "$APP" || true

cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

rm -f "$DMG"
hdiutil create -volname "Gamma Slider" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
echo "Created $DMG"
