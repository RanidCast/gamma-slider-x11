# Gamma Slider X11: AI Instructions

## Canonical workspace

- The canonical working copy on CachyOS is `/home/ilya/Applications/gamma-slider-x11`.
- The repository is `https://github.com/RanidCast/gamma-slider-x11.git`.
- Do not use folders under `/run/media/ilya/Windows 10/` as source-of-truth copies.
- Do not copy files between project folders by hand. Use Git, commits, branches, and tags.
- Keep user changes. Inspect `git status` before editing and never reset or checkout away unrelated changes.

## Platform responsibilities

- Linux development and testing happen in the canonical CachyOS clone.
- Linux supports X11 only. Do not claim Wayland support.
- Windows builds are produced on Windows or by the GitHub Actions workflow in `.github/workflows/windows-release.yml`.
- The Windows build is an onedir PyInstaller build. Keep `gamma-slider.exe` together with its `_internal` directory.
- The Windows backend is `backend_win32.py`; the Linux backend is `backend_linux.py`.

## Before editing

1. Run `git status --short --branch`.
2. Read the nearby implementation and the current README files.
3. Identify the smallest test or check that can disprove the proposed change.
4. Do not edit release artifacts first. Change source and documentation, then rebuild artifacts.

## Validation

For Python source changes, run:

```bash
python3 -m py_compile app.py backend_linux.py backend_win32.py gamma_color.py platform_support.py
```

Run the project tests when the test runner is available:

```bash
python3 -m pytest -q
```

Check the local installation with:

```bash
./install.sh --check
```

For release files, verify package metadata, ZIP integrity, and SHA256 checksums before publishing.

## Git workflow

Normal work:

```bash
git pull --ff-only
# edit and validate
git add <files>
git commit -m "Short description of the change"
git push origin main
```

Release work:

1. Update source and both README files.
2. Validate Linux source and package metadata.
3. Create an annotated version tag such as `v1.2.0` only after the source is ready.
4. Push the branch and tag: `git push origin main v1.2.0`.
5. Let the Windows workflow build and attach the Windows ZIP.
6. Build and verify Linux packages, then attach the Debian, RPM, Arch, source, and checksum files to the same GitHub Release.
7. Add a release description listing changes, platform requirements, assets, and known limitations.

Never reuse an old `v1.0` artifact under a new filename. A release filename must match the version and the bytes must be checked with SHA256.

## Repository hygiene

- Do not commit `build/`, `dist/`, `__pycache__/`, PyInstaller output, unpacked Windows `_internal/`, or old release artifacts.
- Do not commit local caches, generated package trees, or files from the backup folder.
- Keep release artifacts out of source history unless they are intentionally attached to a GitHub Release.
- Prefer focused changes. Do not reformat unrelated files.
