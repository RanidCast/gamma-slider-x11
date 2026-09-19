# Linux packaging

All package builds must start from the canonical Git checkout. Do not copy source files from another project folder.

## Debian-based distributions

Requirements: `dpkg-deb` and `fakeroot`.

```bash
cd packaging/debian
VERSION=1.1.0 ./build-deb.sh
```

The package is written to `packaging/debian/dist/` and its embedded version can be checked with:

```bash
dpkg-deb -f packaging/debian/dist/gamma-slider-x11_1.1.0_all.deb Version
```

## RPM-based distributions

Requirements: `rpmbuild` and `zip`.

```bash
cd packaging/rpm
VERSION=1.1.0 ./build-rpm.sh
```

The RPM and source RPM are written below `packaging/rpm/rpmbuild/`. The script creates its source archive from the current checkout; it does not depend on a stale `Release/` directory.

## Arch-based distributions

`packaging/aur/PKGBUILD` is intended for an AUR repository. For each release:

1. Update `pkgver`.
2. Point `source` to the source ZIP attached to the matching GitHub Release.
3. Run `updpkgsums` or replace `sha256sums` with the checksum of that exact asset.
4. Run `makepkg --verifysource` and `makepkg`.

The package should be built from the tagged source revision and its metadata checked with:

```bash
pacman -Qp --info gamma-slider-x11-*.pkg.tar.zst
```

## Release artifacts

Generated packages belong in a temporary build directory or GitHub Release assets, not in Git history. Before publishing, verify:

```bash
sha256sum <release-files>
unzip -t <zip-files>
```

The same source revision must be used for the source ZIP, Debian package, RPM package, and Arch package.
