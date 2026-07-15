#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Build Linux x64 AppImage and Debian installers from the setup launcher."""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile


class LinuxInstallerBuildError(RuntimeError):
    """Report invalid Linux packaging inputs or external tool failures."""


LINUX_QT_RUNTIME_DEPENDENCIES = (
    "libegl1",
    "libfontconfig1",
    "libgl1",
    "libxcb-cursor0",
    "libxcb-icccm4",
    "libxcb-image0",
    "libxcb-keysyms1",
    "libxcb-render-util0",
    "libxcb-shape0",
    "libxcb-util1",
    "libxcb-xkb1",
    "libxkbcommon-x11-0",
    "libxkbcommon0",
)


def prepare_linux_package_roots(
    *,
    setup_bundle: Path,
    icon_path: Path,
    version: str,
    appdir: Path,
    debian_root: Path,
) -> None:
    """Create deterministic AppDir and Debian filesystem roots."""

    executable = setup_bundle / "SugarSubstitute Setup"
    support_dir = setup_bundle / "launcher-bin"
    if not executable.is_file() or not support_dir.is_dir():
        raise LinuxInstallerBuildError(
            f"Linux setup bundle is incomplete: {setup_bundle}"
        )
    if not icon_path.is_file():
        raise LinuxInstallerBuildError(f"Linux installer icon is missing: {icon_path}")

    _recreate_directory(appdir)
    appimage_install_dir = appdir / "usr" / "lib" / "sugarsubstitute-setup"
    shutil.copytree(setup_bundle, appimage_install_dir)
    _write_executable_script(
        appdir / "AppRun",
        '#!/bin/sh\nHERE="$(dirname "$(readlink -f "$0")")"\nexec "$HERE/usr/lib/sugarsubstitute-setup/SugarSubstitute Setup" "$@"\n',
    )
    appimage_desktop_content = _desktop_entry(
        executable="AppRun",
        version=version,
    )
    (appdir / "sugarsubstitute-setup.desktop").write_text(
        appimage_desktop_content,
        encoding="utf-8",
    )
    shutil.copy2(icon_path, appdir / "sugarsubstitute-setup.png")
    _make_bundle_executable(appimage_install_dir)

    _recreate_directory(debian_root)
    debian_install_dir = debian_root / "opt" / "sugarsubstitute-setup"
    shutil.copytree(setup_bundle, debian_install_dir)
    _make_bundle_executable(debian_install_dir)
    _write_executable_script(
        debian_root / "usr" / "bin" / "sugarsubstitute-setup",
        '#!/bin/sh\nexec "/opt/sugarsubstitute-setup/SugarSubstitute Setup" "$@"\n',
    )
    desktop_path = (
        debian_root / "usr" / "share" / "applications" / "sugarsubstitute-setup.desktop"
    )
    desktop_path.parent.mkdir(parents=True, exist_ok=True)
    desktop_path.write_text(
        _desktop_entry(executable="sugarsubstitute-setup", version=version),
        encoding="utf-8",
    )
    installed_icon = (
        debian_root
        / "usr"
        / "share"
        / "icons"
        / "hicolor"
        / "256x256"
        / "apps"
        / "sugarsubstitute-setup.png"
    )
    installed_icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(icon_path, installed_icon)
    control_path = debian_root / "DEBIAN" / "control"
    control_path.parent.mkdir(parents=True, exist_ok=True)
    control_path.write_text(
        "\n".join(
            (
                "Package: sugarsubstitute",
                f"Version: {version}",
                "Section: graphics",
                "Priority: optional",
                "Architecture: amd64",
                "Maintainer: Artificial Sweetener",
                "Depends: " + ", ".join(LINUX_QT_RUNTIME_DEPENDENCIES),
                "Description: Native Qt frontend and installer for ComfyUI",
                "",
            )
        ),
        encoding="utf-8",
    )


def build_linux_installers(
    *,
    setup_bundle: Path,
    icon_path: Path,
    appimagetool: Path,
    version: str,
    appimage_output: Path,
    deb_output: Path,
) -> tuple[Path, Path]:
    """Build AppImage and Debian artifacts on a Linux x64 host."""

    if platform.system() != "Linux" or platform.machine().lower() not in {
        "amd64",
        "x86_64",
    }:
        raise LinuxInstallerBuildError("Linux installers must be built on Linux x64.")
    if not appimagetool.is_file():
        raise LinuxInstallerBuildError(f"appimagetool is missing: {appimagetool}")

    appimage_output.parent.mkdir(parents=True, exist_ok=True)
    deb_output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sugarsubstitute-linux-package-") as temp:
        staging_root = Path(temp)
        appdir = staging_root / "SugarSubstitute.AppDir"
        debian_root = staging_root / "debian"
        prepare_linux_package_roots(
            setup_bundle=setup_bundle,
            icon_path=icon_path,
            version=version,
            appdir=appdir,
            debian_root=debian_root,
        )
        _run_packager(
            [str(appimagetool), str(appdir), str(appimage_output)],
            env={"ARCH": "x86_64", "APPIMAGE_EXTRACT_AND_RUN": "1"},
        )
        _run_packager(
            [
                "dpkg-deb",
                "--build",
                "--root-owner-group",
                str(debian_root),
                str(deb_output),
            ],
        )
    return appimage_output, deb_output


def _desktop_entry(*, executable: str, version: str) -> str:
    """Return the freedesktop launcher entry for the setup application."""

    return "\n".join(
        (
            "[Desktop Entry]",
            "Type=Application",
            "Name=SugarSubstitute Setup",
            f"Comment=Install SugarSubstitute {version}",
            f"Exec={executable}",
            "Icon=sugarsubstitute-setup",
            "Categories=Graphics;Utility;",
            "Terminal=false",
            "",
        )
    )


def _make_bundle_executable(bundle_dir: Path) -> None:
    """Restore execute permission on the PyInstaller launcher and bundled uv."""

    for path in (
        bundle_dir / "SugarSubstitute Setup",
        bundle_dir / "launcher-bin" / "launcher_assets" / "uv",
    ):
        if path.is_file():
            path.chmod(0o755)


def _write_executable_script(path: Path, content: str) -> None:
    """Write one UTF-8 shell entrypoint with executable permissions."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(0o755)


def _recreate_directory(path: Path) -> None:
    """Replace one builder-owned staging directory."""

    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _run_packager(command: list[str], *, env: dict[str, str] | None = None) -> None:
    """Run one Linux packaging tool with bounded execution time."""

    import os

    process_env = os.environ.copy()
    if env is not None:
        process_env.update(env)
    try:
        subprocess.run(command, check=True, timeout=600, env=process_env)
    except (OSError, subprocess.SubprocessError) as error:
        raise LinuxInstallerBuildError(
            f"Linux packaging command failed: {' '.join(command)}: {error}"
        ) from error


def main() -> int:
    """Run the Linux installer builder command-line interface."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup-bundle", type=Path, required=True)
    parser.add_argument("--icon", type=Path, required=True)
    parser.add_argument("--appimagetool", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--appimage-output", type=Path, required=True)
    parser.add_argument("--deb-output", type=Path, required=True)
    args = parser.parse_args()
    appimage, deb = build_linux_installers(
        setup_bundle=args.setup_bundle,
        icon_path=args.icon,
        appimagetool=args.appimagetool,
        version=args.version,
        appimage_output=args.appimage_output,
        deb_output=args.deb_output,
    )
    print(f"appimage={appimage}")
    print(f"deb={deb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
