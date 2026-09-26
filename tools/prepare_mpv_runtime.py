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
import sys
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile


MPV_REVISION = "v0.41.0"
WINDOWS_BUILDER_REVISION = "630cfb0e6cafce97122f67122a53ef63f47e64c1"
WINDOWS_ARCHIVE_URL = (
    "https://github.com/Paxton-PKJ/libmpv/releases/download/release/"
    "libmpv-lgpl-windows-x86_64.zip"
)
WINDOWS_ARCHIVE_SHA256 = (
    "30fecef3c97d9634190bc5ac0a023694b414d3fd9e0938dbadd802ba34bf8794"
)
WINDOWS_RUNTIME_SHA256 = {
    "avcodec-60.dll": "5ee4181e9a8c887b5739e8621ba21073cd57f9fa6931be863be82605febcb39d",
    "avdevice-60.dll": "b0ab711150175a0b6f15e82baf695aa393624ecb91e4762d3a64debeb7f12247",
    "avfilter-9.dll": "c254183bdba9bab53f2de38dda221461abfa9885342f95e88d0b998a89c52157",
    "avformat-60.dll": "5102ed286a0104c461d8ca6f1668163b8248b1ea7d155e74a82061d062e8369c",
    "avutil-58.dll": "2358bc9aebbd848801bd5454904869556913bae45f02b84e0727b9136ad6af36",
    "libass-9.dll": "59e725382149883c9e82d56bb7a679ac411d635bc08f83ee3057ede808889fe3",
    "libbrotlicommon.dll": "e7b5cc38cb34ce01ea73649180a9c793ca8f7e335de9de79022715ab015de2a5",
    "libbrotlidec.dll": "3eb14ff61cd5e6feaccae6864354e4ba15fd792fc77df6d5b1e013854a426ce7",
    "libbz2-1.dll": "6862dec7a41e7f81c01557896eabc5a81142915141b50aaadd8588d0cb90cc3f",
    "libfreetype-6.dll": "3376ec5e6fd97cb76be18aeb95a9986c3908a5650d8587a0b532d75470e8a551",
    "libfribidi-0.dll": "34b29fa49891faeab9c63fdc33885821f459049034390c2dc50c68ec73d0c956",
    "libgcc_s_seh-1.dll": "f39b60f9c01647a413c91a11a51867451a3be148f724cfb9cbd993a357c0f910",
    "libglib-2.0-0.dll": "2bb430faf052d63201e27444b504f0bee5cb3e76469e57d87023600365ed2412",
    "libgraphite2.dll": "b5de193322bd737c63bb9845a6fee35c6ed19ead3e38bea74cd4e16aaeda5ff0",
    "libharfbuzz-0.dll": "fc0822c2a058fc25faba942a64fd16dfcbf8b5d9e625bc470748d5060fadc8f3",
    "libiconv-2.dll": "bdec7b9d1f63eafda352e2abaab7ce63f26ece8b0eb08563887dd364eaefaf92",
    "libintl-8.dll": "053619b17a082a055eb0d36e9c0d657c073a1dafaa5fddf686d149fe3cbd49d6",
    "liblzma-5.dll": "baff57ef3f67e2e3e47c28aaaab537bf9e80a4f86e13fad0dc9e651f586c2297",
    "libmpv-2.dll": "d3f3337a28fc26ecee34e5b74e0d13ac1d0a819d205b46b10865cd6bfb10a2e3",
    "libpcre2-8-0.dll": "fdc4501f0d397ddc5afbe2fd6ff2c3d92fd4cbf3bef73f8467c60546f15901f0",
    "libplacebo-338.dll": "80bbeab5a6ee3f658e04083cd6e519c0e4b4fc78b963b3ecb123cda47a569b41",
    "libpng16-16.dll": "9ee9e7cabaaa80733c675c3e26cdb8eaf119eae8ddbdeab073f41b1d69e6e371",
    "libshaderc_shared.dll": "41245aead01a92d758cdd23c2ced1e5a608d9bf25de9af3c0c4c2e823a5679c9",
    "libstdc++-6.dll": "7035c8b53db5a2dbec9236dccb76811235a5459c0f842fbdde898d6d9b06080a",
    "libwinpthread-1.dll": "87052c9fc40ce8d5216247fa920c2f74fa114692e4453e9c95cbb5ff46723767",
    "swresample-4.dll": "e246ae4380b74bb707401f9e7113d9ff41d031a5cfda50952c7e94e9f861a9bf",
    "swscale-7.dll": "5fc3fcfe65fd97164b5b9866e41922896f9882ab98e126d96297a84e4d8890d2",
    "zlib1.dll": "02e041c4b7c4cafba56851e04315ac3925ac82f89d20ef701e533515a18433e1",
}
_DOWNLOAD_CHUNK_BYTES = 1024 * 1024
_DOWNLOAD_TIMEOUT_SECONDS = 60


def main(argv: list[str] | None = None) -> int:
    """Stage the exact native runtime selected for the current release host."""

    arguments = _parse_arguments(argv)
    _require_windows_x64()
    output_root = arguments.output_root.expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="sugarsubstitute-mpv-") as workspace_name:
        workspace = Path(workspace_name)
        archive = _obtain_archive(arguments.archive, workspace=workspace)
        _require_sha256(archive, WINDOWS_ARCHIVE_SHA256, label="libmpv archive")
        extracted = workspace / "extracted"
        extracted.mkdir()
        _extract_archive(archive=archive, destination=extracted)
        source = extracted / "bin"
        _require_runtime_files(source)
        _require_embeddable_runtime(source / "libmpv-2.dll")
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
    destination = workspace / "libmpv.zip"
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


def _extract_archive(*, archive: Path, destination: Path) -> None:
    """Extract the pinned ZIP after rejecting paths outside the workspace."""

    resolved_destination = destination.resolve()
    with ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (resolved_destination / member.filename).resolve()
            if not target.is_relative_to(resolved_destination):
                raise RuntimeError("Pinned libmpv archive contains an unsafe path.")
        bundle.extractall(resolved_destination)


def _stage_runtime(*, source: Path, output_root: Path) -> Path:
    """Atomically replace every file in the owned Windows runtime bundle."""

    _require_runtime_files(source)
    destination_dir = output_root / "windows-x64"
    destination_dir.mkdir(parents=True, exist_ok=True)
    for name in WINDOWS_RUNTIME_SHA256:
        destination = destination_dir / name
        partial = destination.with_suffix(destination.suffix + ".partial")
        shutil.copy2(source / name, partial)
        partial.replace(destination)
    return destination_dir / "libmpv-2.dll"


def _require_runtime_files(source: Path) -> None:
    """Verify every binary in the pinned dynamically linked runtime bundle."""

    for name, expected in WINDOWS_RUNTIME_SHA256.items():
        _require_sha256(source / name, expected, label=f"libmpv runtime file {name}")


def _require_embeddable_runtime(library: Path) -> None:
    """Reject Windows libmpv builds that embed unsafe scripting runtimes."""

    content = library.read_bytes()
    required = (b"-Dlua=disabled", b"-Djavascript=disabled")
    forbidden = (b"LuaJIT ", b"-Dlua=enabled", b"-Dlua=luajit")
    if any(token not in content for token in required) or any(
        token in content for token in forbidden
    ):
        raise RuntimeError(
            "Pinned libmpv runtime is unsafe for Windows render-API embedding."
        )


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
