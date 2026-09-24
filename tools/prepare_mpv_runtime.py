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

"""Fetch, verify, and stage the pinned Windows libmpv release runtime."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen


MPV_REVISION = "062f4bf"
WINDOWS_ARCHIVE_URL = (
    "https://downloads.sourceforge.net/project/mpv-player-windows/libmpv/"
    "mpv-dev-x86_64-20260412-git-062f4bf.7z"
)
WINDOWS_ARCHIVE_SHA256 = (
    "f66f04075da0cbccd106513eab67b78b72ac00780423a9fe3c6e34ae93317806"
)
WINDOWS_LIBRARY_SHA256 = (
    "9936e45ba4c5c8a93ce4e978634de369af0a1d61595447699b17393ba2dec417"
)
_DOWNLOAD_CHUNK_BYTES = 1024 * 1024
_DOWNLOAD_TIMEOUT_SECONDS = 60


def main(argv: list[str] | None = None) -> int:
    """Stage the exact native runtime selected for the current release host."""

    arguments = _parse_arguments(argv)
    _require_windows_x64()
    repository_root = Path(__file__).resolve().parents[1]
    seven_zip = (
        arguments.seven_zip.expanduser().resolve()
        if arguments.seven_zip is not None
        else repository_root
        / "third_party"
        / "bin"
        / "7zip"
        / "windows-x64"
        / "7za.exe"
    )
    if not seven_zip.is_file():
        raise FileNotFoundError(f"Bundled 7-Zip executable is unavailable: {seven_zip}")

    output_root = arguments.output_root.expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="sugarsubstitute-mpv-") as workspace_name:
        workspace = Path(workspace_name)
        archive = _obtain_archive(arguments.archive, workspace=workspace)
        _require_sha256(archive, WINDOWS_ARCHIVE_SHA256, label="libmpv archive")
        extracted = workspace / "extracted"
        extracted.mkdir()
        _extract_archive(seven_zip=seven_zip, archive=archive, destination=extracted)
        source = extracted / "libmpv-2.dll"
        _require_sha256(source, WINDOWS_LIBRARY_SHA256, label="libmpv runtime")
        staged = _stage_runtime(source=source, output_root=output_root)
    print(f"{staged} sha256={_sha256(staged)}")
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    """Parse deterministic source, extractor, and destination options."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("third_party") / "bin" / "mpv",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        help="Use an already-downloaded archive after applying the same checksum.",
    )
    parser.add_argument("--seven-zip", type=Path)
    return parser.parse_args(argv)


def _require_windows_x64(
    *, platform_name: str | None = None, machine: str | None = None
) -> None:
    """Reject hosts that do not match the audited prebuilt archive."""

    resolved_platform = platform_name or sys.platform
    resolved_machine = (machine or platform.machine()).strip().lower()
    if resolved_platform != "win32" or resolved_machine not in {"amd64", "x86_64"}:
        raise RuntimeError(
            "The pinned prebuilt libmpv runtime supports Windows x64 only."
        )


def _obtain_archive(requested: Path | None, *, workspace: Path) -> Path:
    """Return a caller archive or download the immutable pinned source."""

    if requested is not None:
        archive = requested.expanduser().resolve()
        if not archive.is_file():
            raise FileNotFoundError(archive)
        return archive
    destination = workspace / "libmpv.7z"
    with (
        urlopen(  # noqa: S310 - immutable URL is project-owned configuration
            WINDOWS_ARCHIVE_URL,
            timeout=_DOWNLOAD_TIMEOUT_SECONDS,
        ) as response,
        destination.open("wb") as output,
    ):
        while chunk := response.read(_DOWNLOAD_CHUNK_BYTES):
            output.write(chunk)
    return destination


def _extract_archive(*, seven_zip: Path, archive: Path, destination: Path) -> None:
    """Extract the pinned archive with the repository-owned 7-Zip binary."""

    subprocess.run(  # noqa: S603
        [str(seven_zip), "x", "-y", f"-o{destination}", str(archive)],
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _stage_runtime(*, source: Path, output_root: Path) -> Path:
    """Atomically replace only the owned Windows runtime library."""

    if not source.is_file():
        raise FileNotFoundError(source)
    destination_dir = output_root / "windows-x64"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / "libmpv-2.dll"
    partial = destination.with_suffix(".dll.partial")
    shutil.copy2(source, partial)
    partial.replace(destination)
    return destination


def _require_sha256(path: Path, expected: str, *, label: str) -> None:
    """Reject a source or staged runtime whose digest does not match."""

    if not path.is_file() or _sha256(path) != expected.casefold():
        raise RuntimeError(f"Pinned {label} failed SHA-256 verification.")


def _sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest for one file."""

    digest = hashlib.sha256()
    with path.open("rb") as binary:
        for chunk in iter(lambda: binary.read(_DOWNLOAD_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
