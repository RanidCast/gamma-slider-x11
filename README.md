# Gamma Slider X11

### [English]([https://github.com/RanidCast/gamma-slider-x11/blob/main/README.md](https://github.com/RanidCast/gamma-slider-x11/tree/dev?tab=readme-ov-file#)) | [Русский](https://github.com/RanidCast/gamma-slider-x11/blob/main/README_RU.md)

A small multi-platform tray utility for changing screen color temperature on Linux/X11, KDE Plasma Wayland, Windows, and macOS.

It is a lightweight GUI wrapper around a tiny bundled X11/RandR gamma engine. The app was made for quick personal use from the system tray: click the tray icon, move the slider, and the screen temperature changes immediately.

> Linux uses RandR on X11. KDE Plasma Wayland uses KWin Night Color and supports temperatures from 1000K to 6500K; gamma visibility and color calculation modes are unavailable there. GNOME, Sway, Hyprland, and other Wayland desktops are not supported. Windows uses a separate GDI backend, and macOS uses CoreGraphics display transfer tables.

## Screenshot

![Tray popup](screenshots/English(1.1).png)


## Features

- Tray icon with a compact popup slider.
- Color temperature range from 1000K to 10000K.
- Optional value display directly in the tray icon.
- Enable/disable switch.
- Optional higher gamma/contrast mode for better visibility.
- Three color calculation modes: Classic, Aggressive, and Mathematical.
- Smooth automatic day/night mode.
- Autostart support.
- PyQt5/PyQt6 compatibility.
- Tiny bundled gamma engine, no full Redshift dependency required.

## Platforms and requirements

- Python 3.
- PyQt5 or PyQt6.

### Linux/X11

- Linux with an X11 session.
- X11 RandR support.

On many desktop distributions PyQt is already available. If not, install the package from your distribution repositories, for example `python-pyqt5`, `python3-pyqt5`, or `python3-pyqt6`.

### KDE Plasma Wayland

- KDE Plasma running a Wayland session with KWin Night Color.
- PyQt5 and `python-dbus` are required for KDE global shortcuts.

KWin applies temperature changes. The range is 1000K–6500K; gamma visibility and color calculation modes are not available in this session. GNOME, Sway, Hyprland, and other Wayland compositors have no backend in this version.

## Windows

Unpack the complete `gamma-slider-windows-<ver>.zip` from GitHub Releases and run `gamma-slider.exe`. Keep the `_internal` directory next to the executable. No installer is required.

Running from source needs Python 3 and PyQt5 (or PyQt6).

The Windows build supports per-user autostart through the application menu. It does not require administrator rights.

Turn off Windows Night Light. HDR and some NVIDIA drivers ignore `SetDeviceGammaRamp`, so the slider may have no effect.

The repository name still says `x11` for historical reasons. Windows uses a separate GDI gamma backend.

The three color modes are available on all supported platforms. They affect the generated color ramp; the platform-specific backend only applies that ramp to the display.

## macOS

Download `gamma-slider-macos-<ver>.dmg` from GitHub Releases (or the macOS workflow artifact). Open the disk image and drag **Gamma Slider** to Applications.

The GitHub build targets Apple Silicon (`arm64`). Intel Macs are not covered by that DMG.

The app is not notarized. On first launch use right-click → Open, or:

```bash
xattr -cr "/Applications/Gamma Slider.app"
```

Turn off Night Shift and True Tone. HDR displays may ignore gamma tables, so the slider can have no effect.

Per-user autostart is a LaunchAgent created from the application menu. Administrator rights are not required.

Running from source needs Python 3 and PyQt5 (or PyQt6).

## Install

```bash
git clone https://github.com/RanidCast/gamma-slider-x11.git
cd gamma-slider-x11
./install.sh --install
```

Check the installation:

```bash
./install.sh --check
```

Run it immediately:

```bash
python3 app.py
```

After installation, Gamma Slider appears in the application menu and is added to autostart.

## Uninstall

```bash
./install.sh --uninstall
```

This removes the menu entry, autostart entry, config, logs, and the unpacked gamma engine from the user profile. It does not remove the cloned project directory.

## Packaging

See [DEVELOPMENT.md](DEVELOPMENT.md) for the development, build, and release workflow.

Prebuilt release files are attached in GitHub Releases:

- `gamma-slider-x11-v1.1.0-source.zip` for the plain source bundle
- `gamma-slider-x11_1.1.0_all.deb` for Debian/Ubuntu/Mint
- `gamma-slider-x11-1.1.0-1.noarch.rpm` for Fedora/RPM-based distros
- `gamma-slider-x11-1.1.0-1-x86_64.pkg.tar.zst` for Arch
- `gamma-slider-macos-<ver>.dmg` for macOS (Apple Silicon)

Install the packages directly:

```bash
sudo apt install ./gamma-slider-x11_1.1.0_all.deb
sudo dnf install ./gamma-slider-x11-1.1.0-1.noarch.rpm
sudo pacman -U ./gamma-slider-x11-1.1.0-1-x86_64.pkg.tar.zst
```

## Hotkeys and CLI

Default chords are `Ctrl+Alt+PgUp` (warmer, +100 K) and `Ctrl+Alt+PgDown` (cooler, −100 K). They change temperature only while the effect is enabled and Auto is off.

On Windows, macOS, Linux/X11, and KDE Plasma Wayland, configured hotkeys work while another app has focus. KDE Plasma Wayland registers them with KGlobalAccel and requires PyQt5 plus `python-dbus`. Holding a hotkey repeats the temperature change. Hotkeys are active only while the effect is enabled and Auto is off. A chord already used by the system or another app may fail to register; choose an available chord in Settings.

A second instance sends one command to the running app:

```bash
python3 app.py --warmer
python3 app.py --cooler
python3 app.py --toggle
python3 app.py --temp 4000
```

On Linux/X11, the application passively grabs configured chords. Global hotkeys are unavailable on Wayland, so bind the CLI commands in the system keyboard settings instead. The Settings page shows the exact argv for this install, not a desktop-file name. Middle-click toggles the effect only when Qt receives `MiddleClick`; on GNOME AppIndicator that event often never arrives, so middle-click stays the menu workaround below.

Tray-icon wheel and per-monitor temperature are not in this version. Five preset buttons (1000 / 2000 / 3000 / 4000 / 6500) turn Auto off and apply that temperature; their values can be changed in Settings. Schedule times are edited there as well.

## GNOME Desktop Known Issues

If you are running the GNOME desktop environment, please note that GNOME has native restrictions regarding the system tray:

1. **Missing Tray Icon:** GNOME does not support app indicators natively. You must manually install and enable an extension like **AppIndicator and KStatusNotifierItem Support** to make the tray icon visible.
2. **Click Behavior Bug:** Due to the way GNOME's AppIndicator extension translates mouse events to PyQt applications, single-clicking (both Left and Right click) on the tray icon might immediately trigger the context menu and execute the "Exit/Quit" action.
   - **Workaround:** Double-click the tray icon to open the program window properly, or use the **Middle Mouse Button (Scroll Click)** to trigger a clean Right-click menu without instantly closing the app.

On Wayland, only KDE Plasma is supported (KWin Night Color). GNOME, Sway, Hyprland, and other Wayland desktops cannot change temperature with this app; use an X11 session there. The GNOME tray notes above apply to GNOME on X11 only.

## Licensing

This project is intended to be released under the GNU GPL v3.0 or later.

The bundled gamma engine uses X11/RandR gamma ramp logic and blackbody color data adapted from Redshift-style implementations. Because that work is GPL-compatible/GPL-derived, the safest license for this project is GPL-3.0-or-later.

If you redistribute modified versions, keep the same license terms and preserve attribution to the original Redshift project where applicable.

## Notes

The bundled engine is extracted on first launch to:

```text
~/.local/share/gamma-slider/gamma-engine
```

Configuration is stored in:

```text
~/.config/gamma-slider/gamma_slider.conf
```

Logs are stored in:

```text
~/.local/share/gamma-slider/gamma_slider.log
```

On macOS, config is `~/Library/Application Support/gamma-slider/gamma_slider.conf` and logs are `~/Library/Logs/gamma-slider/gamma_slider.log`.

The app has been tested on KDE/Plasma, Cinnamon, and Xfce under X11.
