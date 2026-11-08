# Development and Release Guide

## One source of truth

Work only in this folder on CachyOS:

```text
/home/ilya/Applications/gamma-slider-x11
```

It is a normal clone of the GitHub repository. The folders on the Windows drive are old copies or build outputs and must not be used for routine editing.

The installed tray application is also registered from this folder. After changing installation-related files, refresh the user installation:

```bash
cd /home/ilya/Applications/gamma-slider-x11
./install.sh --install
./install.sh --check
```

The application stores its config and runtime files outside the repository:

```text
~/.config/gamma-slider/
~/.local/share/gamma-slider/
~/.config/autostart/gamma-slider-x11.desktop
```

## Everyday changes on CachyOS

```bash
cd /home/ilya/Applications/gamma-slider-x11
git pull --ff-only
# edit the source
python3 -m py_compile app.py backend_linux.py backend_win32.py backend_macos.py gamma_color.py platform_support.py
python3 -m pytest -q
./install.sh --check
git status
git add <changed-files>
git commit -m "Describe the change"
git push origin main
```

If `pytest` is unavailable, install the project test dependency in the active Python environment or report that tests could not run. Do not hide a failed or skipped validation.

## Windows development

For a local Windows build, use a Windows checkout of the same GitHub repository. Do not maintain a manually synchronized second source tree.

```powershell
git clone https://github.com/RanidCast/gamma-slider-x11.git
git checkout main
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install PyQt5 pyinstaller
.\.venv\Scripts\pyinstaller.exe --noconfirm gamma-slider.spec
Compress-Archive -Path dist\gamma-slider -DestinationPath gamma-slider-windows-local.zip
```

The resulting archive must contain `gamma-slider.exe` and the complete `_internal` folder. Test the archive on Windows before release. The repository workflow in `.github/workflows/windows-release.yml` performs this build automatically for version tags.

## macOS development

macOS binaries cannot be built on CachyOS. Use a Mac or the GitHub Actions workflow in `.github/workflows/macos-release.yml`.

```bash
python3 -m pip install PyQt5 pyinstaller
python3 packaging/macos/make_icns.py
./packaging/macos/build-dmg.sh local
```

The result is `gamma-slider-macos-<tag>.dmg` with `Gamma Slider.app` and a shortcut to Applications. The workflow targets Apple Silicon (`macos-latest`). Trigger it with `workflow_dispatch` or a `v*` tag.

Ad-hoc signing is used. Notarization requires an Apple Developer ID and is not part of the default pipeline.

## Version history

- `v1.0` is the original release.
- `v1.1.0` adds Windows support, the Windows GDI backend, three color calculation modes, Windows per-user autostart, and updated screenshots/documentation.
- `v1.2.0` adds macOS (CoreGraphics, LaunchAgent, DMG), KDE Plasma Wayland (KWin Night Color), global hotkeys, CLI IPC, presets, and schedule settings.
- Future releases should use semantic version tags such as `v1.3.0`.

Git history is already present in this clone. Inspect it with:

```bash
git log --oneline --decorate --graph --all
git tag --list
```

## Release checklist

1. Pull the latest `main` and inspect `git status`.
2. Make the source and documentation changes.
3. Run Python syntax checks and tests.
4. Test the Linux installation on an X11 session: verify hotkeys while another application has focus, hold a key to verify repeat, and confirm conflicting desktop shortcuts are reported as unavailable.
5. Build or obtain the Windows onedir ZIP and test it on Windows: hold PgUp/PgDown with Ctrl+Alt to verify repeat behavior, test the hotkeys while another application has focus, including when the active window is on a second monitor, and confirm conflicting chords fail cleanly.
6. Build or obtain the macOS DMG from the macOS workflow and test it on an Apple Silicon Mac: verify the hotkey works without app focus, repeats while held, and releases when the key is released; also check conflicting chords.
7. Build Debian, RPM, and Arch packages from the same source revision. Verify their embedded versions.
8. Create and push an annotated tag, for example `v1.2.0`.
9. Confirm the GitHub Actions Windows and macOS jobs complete.
10. Attach the Windows ZIP, macOS DMG, Linux packages, source archive, and a checksum file to the GitHub Release.
11. Write release notes with changes, downloads, requirements, and known limitations.
12. Download the public assets and verify their checksums and archive integrity.

Never publish a file from an old backup simply because its filename has the new version. Rebuild it or verify that its bytes came from the tagged source revision.

## Current packaging note

Debian and RPM build scripts are maintained in `packaging/`. Their package payload must include the Python modules imported by `app.py`, not only the entry-point script. The Arch PKGBUILD tracks a published source ZIP and its exact SHA256; update both only after the matching release source archive has been generated.

## Backup and cleanup

The old migration backup is:

```text
/home/ilya/Applications/gamma-slider-x11-old-20260919
```

Keep it until the new clone has been used successfully and any needed local packaging files have been migrated. Once it is no longer needed, remove it only with an explicit, deliberate command. Do not delete the canonical clone.
