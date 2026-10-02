#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SVG = os.path.join(ROOT, "gamma_slider_icon.svg")
ICONSET = os.path.join(ROOT, "packaging", "macos", "GammaSlider.iconset")
ICNS = os.path.join(ROOT, "gamma-slider.icns")

FILES = (
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
)


def main():
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QImage, QPainter
    from PyQt5.QtSvg import QSvgRenderer
    from PyQt5.QtWidgets import QApplication

    if not os.path.isfile(SVG):
        raise SystemExit("missing %s" % SVG)

    QApplication(sys.argv)
    renderer = QSvgRenderer(SVG)
    if os.path.isdir(ICONSET):
        shutil.rmtree(ICONSET)
    os.makedirs(ICONSET, exist_ok=True)

    for size, name in FILES:
        image = QImage(size, size, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        renderer.render(painter)
        painter.end()
        if not image.save(os.path.join(ICONSET, name)):
            raise SystemExit("failed to write %s" % name)

    subprocess.check_call(["iconutil", "-c", "icns", "-o", ICNS, ICONSET])
    print(ICNS)


if __name__ == "__main__":
    main()
