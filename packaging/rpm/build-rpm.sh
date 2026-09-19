#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
VERSION="${VERSION:-1.1.0}"
PKG_NAME="gamma-slider-x11"
TOPDIR="$SCRIPT_DIR/rpmbuild"
SOURCE_DIR="$TOPDIR/source"
SOURCE_ZIP="$TOPDIR/SOURCES/$PKG_NAME-$VERSION.zip"

rm -rf "$TOPDIR"
mkdir -p "$TOPDIR/BUILD" "$TOPDIR/RPMS" "$TOPDIR/SOURCES" "$TOPDIR/SPECS" "$TOPDIR/SRPMS" "$SOURCE_DIR"

cp "$SCRIPT_DIR/gamma-slider-x11.spec" "$TOPDIR/SPECS/"
for file in app.py install.sh gamma_slider_icon.svg; do
    cp "$PROJECT_ROOT/$file" "$SOURCE_DIR/$file"
done
(cd "$SOURCE_DIR" && zip -q "$SOURCE_ZIP" app.py install.sh gamma_slider_icon.svg)

rpmbuild --define "_topdir $TOPDIR" --define "version $VERSION" -ba "$TOPDIR/SPECS/$PKG_NAME.spec"
printf 'Built packages in %s/RPMS and %s/SRPMS\n' "$TOPDIR" "$TOPDIR"
