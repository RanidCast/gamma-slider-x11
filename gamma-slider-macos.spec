# -*- mode: python ; coding: utf-8 -*-
import os

icon = "gamma-slider.icns" if os.path.exists("gamma-slider.icns") else None

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["backend_macos", "gamma_color", "platform_support"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["backend_linux", "backend_win32", "PyQt6"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="gamma-slider",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="gamma-slider",
)

app = BUNDLE(
    coll,
    name="Gamma Slider.app",
    icon=icon,
    bundle_identifier="com.ranidcast.gammaslider",
    info_plist={
        "CFBundleName": "Gamma Slider",
        "CFBundleDisplayName": "Gamma Slider",
        "CFBundleShortVersionString": "1.2.0",
        "CFBundleVersion": "1.2.0",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.utilities",
    },
)
