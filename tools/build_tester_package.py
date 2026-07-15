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

"""Build an offline tester package from local release-channel artifacts."""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from launcher.sugarsubstitute_launcher.manifest import ReleaseManifest  # noqa: E402
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64  # noqa: E402

DEFAULT_DIST_DIR = REPO_ROOT / "dist"
DEFAULT_RELEASE_CHANNEL_DIR = REPO_ROOT / ".local-release-channel"
SETUP_EXE_NAME = "SugarSubstitute-Installer-Windows-x64.exe"
TESTER_PACKAGE_PREFIX = "SugarSubstitute-tester-v"
ZIP_TIMESTAMP = (2024, 1, 1, 0, 0, 0)


@dataclass(frozen=True, slots=True)
class TesterPackageResult:
    """Describe a completed offline tester package."""

    version: str
    package_dir: Path
    zip_path: Path
    setup_exe_path: Path
    release_channel_dir: Path


def build_tester_package(
    *,
    release_channel_dir: Path = DEFAULT_RELEASE_CHANNEL_DIR,
    setup_exe_path: Path = DEFAULT_DIST_DIR / SETUP_EXE_NAME,
    output_dir: Path = DEFAULT_DIST_DIR,
    package_name: str | None = None,
) -> TesterPackageResult:
    """Create a zip whose extracted `dist` folder can run the setup exe offline."""

    resolved_release_channel = release_channel_dir.expanduser().resolve()
    resolved_setup_exe = setup_exe_path.expanduser().resolve()
    resolved_output_dir = output_dir.expanduser().resolve()
    manifest = _load_valid_manifest(resolved_release_channel)
    _validate_setup_exe(resolved_setup_exe)

    resolved_package_name = package_name or f"{TESTER_PACKAGE_PREFIX}{manifest.version}"
    package_dir = resolved_output_dir / resolved_package_name
    package_dist_dir = package_dir / "dist"
    package_release_channel_dir = package_dist_dir / ".local-release-channel"
    zip_path = resolved_output_dir / f"{resolved_package_name}.zip"

    _remove_existing_package_dir(package_dir, output_dir=resolved_output_dir)
    if zip_path.exists():
        zip_path.unlink()
    package_release_channel_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(resolved_setup_exe, package_dist_dir / SETUP_EXE_NAME)
    for source_path in _release_channel_files(
        release_channel_dir=resolved_release_channel,
        manifest=manifest,
    ):
        shutil.copy2(source_path, package_release_channel_dir / source_path.name)

    _write_directory_zip(source_dir=package_dir, zip_path=zip_path)
    return TesterPackageResult(
        version=manifest.version,
        package_dir=package_dir,
        zip_path=zip_path,
        setup_exe_path=package_dist_dir / SETUP_EXE_NAME,
        release_channel_dir=package_release_channel_dir,
    )


def _load_valid_manifest(release_channel_dir: Path) -> ReleaseManifest:
    """Load the manifest and require the assets needed for offline setup."""

    manifest_path = release_channel_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Release manifest is missing: {manifest_path}")
    manifest = ReleaseManifest.load(manifest_path)
    if manifest.launcher_for(WINDOWS_X64) is None:
        raise ValueError("Release manifest must include a Windows launcher bundle.")
    return manifest


def _validate_setup_exe(setup_exe_path: Path) -> None:
    """Require the downloaded setup executable that testers will run."""

    if not setup_exe_path.is_file():
        raise FileNotFoundError(f"Setup executable is missing: {setup_exe_path}")
    if setup_exe_path.name != SETUP_EXE_NAME:
        raise ValueError(f"Setup executable must be named {SETUP_EXE_NAME}.")


def _release_channel_files(
    *, release_channel_dir: Path, manifest: ReleaseManifest
) -> Iterable[Path]:
    """Yield the exact release-channel files required by the tester package."""

    filenames = [
        "manifest.json",
        "checksums.txt",
        manifest.app.filename,
    ]
    launcher_asset = manifest.launcher_for(WINDOWS_X64)
    installer_asset = manifest.installer_for(WINDOWS_X64)
    if launcher_asset is not None:
        filenames.append(launcher_asset.filename)
    if installer_asset is not None:
        filenames.append(installer_asset.filename)

    seen: set[str] = set()
    for filename in filenames:
        if filename in seen:
            continue
        seen.add(filename)
        path = release_channel_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Release-channel asset is missing: {path}")
        yield path


def _remove_existing_package_dir(package_dir: Path, *, output_dir: Path) -> None:
    """Remove only the owned staging directory under the selected output root."""

    resolved_package_dir = package_dir.resolve()
    resolved_output_dir = output_dir.resolve()
    if (
        resolved_package_dir == resolved_output_dir
        or not resolved_package_dir.is_relative_to(resolved_output_dir)
        or not resolved_package_dir.name.startswith(TESTER_PACKAGE_PREFIX)
    ):
        raise ValueError(f"Refusing to clean unsafe package directory: {package_dir}")
    if resolved_package_dir.exists():
        shutil.rmtree(resolved_package_dir)


def _write_directory_zip(*, source_dir: Path, zip_path: Path) -> None:
    """Write a portable zip containing the package root directory."""

    source_root = source_dir.resolve()
    with zipfile.ZipFile(
        zip_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(source_root.rglob("*"), key=lambda value: value.as_posix()):
            archive_name = PurePosixPath(
                source_root.name,
                path.relative_to(source_root).as_posix(),
            ).as_posix()
            if path.is_dir():
                _write_zip_directory(archive=archive, archive_name=archive_name)
                continue
            _write_zip_file(
                archive=archive,
                source_path=path,
                archive_name=archive_name,
            )


def _write_zip_directory(*, archive: zipfile.ZipFile, archive_name: str) -> None:
    """Add one directory entry with stable metadata."""

    directory_name = archive_name.rstrip("/") + "/"
    zip_info = zipfile.ZipInfo(directory_name, date_time=ZIP_TIMESTAMP)
    zip_info.external_attr = 0o755 << 16
    archive.writestr(zip_info, b"")


def _write_zip_file(
    *, archive: zipfile.ZipFile, source_path: Path, archive_name: str
) -> None:
    """Add one file entry with stable metadata."""

    zip_info = zipfile.ZipInfo(archive_name, date_time=ZIP_TIMESTAMP)
    zip_info.compress_type = zipfile.ZIP_DEFLATED
    zip_info.external_attr = 0o644 << 16
    archive.writestr(
        zip_info,
        source_path.read_bytes(),
        compress_type=zipfile.ZIP_DEFLATED,
    )


def main() -> int:
    """Run the tester-package builder command-line interface."""

    args = _parse_args()
    result = build_tester_package(
        release_channel_dir=args.release_channel_dir,
        setup_exe_path=args.setup_exe_path,
        output_dir=args.output_dir,
        package_name=args.package_name,
    )
    print(f"version={result.version}")
    print(f"package_dir={result.package_dir}")
    print(f"zip_path={result.zip_path}")
    print(f"setup_exe={result.setup_exe_path}")
    print(f"release_channel={result.release_channel_dir}")
    print(f"installed_launcher_name={WINDOWS_X64.executable_relative_path.name}")
    return 0


def _parse_args() -> argparse.Namespace:
    """Parse tester-package builder arguments."""

    parser = argparse.ArgumentParser(
        description="Build an offline SugarSubstitute tester zip.",
    )
    parser.add_argument(
        "--release-channel-dir",
        type=Path,
        default=DEFAULT_RELEASE_CHANNEL_DIR,
        help="Local release-channel folder containing manifest.json and assets.",
    )
    parser.add_argument(
        "--setup-exe-path",
        type=Path,
        default=DEFAULT_DIST_DIR / SETUP_EXE_NAME,
        help="Setup executable to place under the package dist folder.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_DIST_DIR,
        help="Directory that receives the package folder and zip.",
    )
    parser.add_argument(
        "--package-name",
        default=None,
        help="Optional top-level folder and zip basename.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
