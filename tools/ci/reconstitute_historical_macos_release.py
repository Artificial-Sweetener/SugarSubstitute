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

"""Reconstitute an installable macOS history from exact released bytes."""

from __future__ import annotations

import argparse
from copy import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
from collections.abc import Sequence
import zipfile

from launcher.sugarsubstitute_launcher.platforms import MACOS_ARM64
from tools.ci.local_release_server import LOCAL_RELEASE_BASE_URL_PLACEHOLDER
from tools.release_assets.launcher_archive import (
    validate_installed_launcher_archive,
)

_APP_ROOT = "SugarSubstitute.app"
_PYINSTALLER_SIBLING_ROOT = "SugarSubstitute"
_APP_EXECUTABLE = PurePosixPath("SugarSubstitute.app/Contents/MacOS/SugarSubstitute")
_APP_FRAMEWORKS_ROOT = PurePosixPath("SugarSubstitute.app/Contents/Frameworks")


def reconstitute_historical_macos_release(
    *,
    source_root: Path,
    output_root: Path,
) -> Path:
    """Rebuild the symlink-stripped app from its exact released sibling runtime."""

    manifest = _read_object(source_root / "manifest.json")
    version = _required_string(manifest, "version")
    app_asset = _required_object(manifest, "app")
    launchers = _required_object(manifest, "launchers")
    launcher_asset = _required_object(launchers, "macos_arm64")
    app_source = source_root / _required_string(app_asset, "filename")
    launcher_source = source_root / _required_string(launcher_asset, "filename")
    _verify_released_asset(app_source, app_asset)
    _verify_released_asset(launcher_source, launcher_asset)

    output_root.mkdir(parents=True, exist_ok=True)
    app_output = output_root / app_source.name
    launcher_output = output_root / launcher_source.name
    shutil.copy2(app_source, app_output)
    removed_roots = _write_reconstituted_launcher(
        source=launcher_source,
        destination=launcher_output,
    )
    validate_installed_launcher_archive(launcher_output, target=MACOS_ARM64)

    original_launcher_sha256 = _sha256(launcher_source)
    app_asset["url"] = f"{LOCAL_RELEASE_BASE_URL_PLACEHOLDER}/{app_output.name}"
    launcher_asset.update(
        {
            "url": f"{LOCAL_RELEASE_BASE_URL_PLACEHOLDER}/{launcher_output.name}",
            "sha256": _sha256(launcher_output),
            "size_bytes": launcher_output.stat().st_size,
        }
    )
    manifest_path = output_root / "manifest.json"
    _write_json(manifest_path, manifest)
    _write_json(
        output_root / "historical-reconstitution.json",
        {
            "schema_version": 1,
            "version": version,
            "source_launcher_sha256": original_launcher_sha256,
            "reconstituted_launcher_sha256": _sha256(launcher_output),
            "retained_root": _APP_ROOT,
            "runtime_source_root": _PYINSTALLER_SIBLING_ROOT,
            "runtime_support_root": _APP_FRAMEWORKS_ROOT.as_posix(),
            "removed_roots": list(removed_roots),
        },
    )
    return manifest_path


def _write_reconstituted_launcher(
    *, source: Path, destination: Path
) -> tuple[str, ...]:
    """Place exact one-folder bytes in the app bootloader's support topology."""

    encountered_roots: set[str] = set()
    retained_members = 0
    with (
        zipfile.ZipFile(source) as source_archive,
        zipfile.ZipFile(
            destination,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as destination_archive,
    ):
        seen_names: set[str] = set()
        written_names: set[str] = set()
        runtime_executable_found = False
        runtime_library_found = False
        for member in source_archive.infolist():
            normalized = _validated_member_name(member.filename)
            if member.filename in seen_names:
                raise ValueError(
                    f"Historical launcher archive repeats {member.filename!r}."
                )
            seen_names.add(member.filename)
            encountered_roots.add(normalized.parts[0])
            if normalized == _APP_EXECUTABLE or _is_original_framework(normalized):
                continue
            destination_name = normalized
            if normalized.parts[0] == _PYINSTALLER_SIBLING_ROOT:
                destination_name = _remap_onedir_member(normalized)
                runtime_executable_found |= destination_name == _APP_EXECUTABLE
                runtime_library_found |= (
                    len(destination_name.parts) >= 2
                    and destination_name.parent.name == "lib-dynload"
                    and destination_name.name.startswith("_struct.")
                )
            if destination_name.as_posix() in written_names:
                raise ValueError(
                    "Historical macOS launcher remaps duplicate member: "
                    f"{destination_name}."
                )
            rewritten_member = copy(member)
            rewritten_member.filename = destination_name.as_posix()
            destination_archive.writestr(
                rewritten_member,
                source_archive.read(member),
            )
            written_names.add(destination_name.as_posix())
            retained_members += 1
    expected_roots = {_APP_ROOT, _PYINSTALLER_SIBLING_ROOT}
    if encountered_roots != expected_roots:
        raise ValueError(
            "Historical macOS launcher roots differ from the reviewed defect: "
            f"{sorted(encountered_roots)}."
        )
    if retained_members == 0:
        raise ValueError("Historical macOS launcher contains no signed app members.")
    if not runtime_executable_found or not runtime_library_found:
        raise ValueError(
            "Historical macOS launcher lacks its runnable one-folder runtime."
        )
    return (_PYINSTALLER_SIBLING_ROOT,)


def _remap_onedir_member(member: PurePosixPath) -> PurePosixPath:
    """Place one released one-folder member where the app bootloader resolves it."""

    relative = PurePosixPath(*member.parts[1:])
    if relative == PurePosixPath("SugarSubstitute"):
        return _APP_EXECUTABLE
    if relative.parts and relative.parts[0] == "_internal":
        return _APP_FRAMEWORKS_ROOT / PurePosixPath(*relative.parts[1:])
    raise ValueError(f"Unexpected historical one-folder member: {member}.")


def _is_original_framework(member: PurePosixPath) -> bool:
    """Return whether a member belongs to the app's symlink-stripped runtime."""

    return member.is_relative_to(_APP_FRAMEWORKS_ROOT)


def _validated_member_name(name: str) -> PurePosixPath:
    """Reject unsafe or platform-ambiguous historical archive member names."""

    if not name or name.startswith("/") or "\\" in name:
        raise ValueError(f"Unsafe historical launcher member: {name!r}.")
    normalized = PurePosixPath(name)
    if any(part in {"", ".", ".."} for part in normalized.parts):
        raise ValueError(f"Unsafe historical launcher member: {name!r}.")
    return normalized


def _verify_released_asset(path: Path, metadata: dict[str, object]) -> None:
    """Require downloaded history to match its immutable release manifest."""

    if not path.is_file():
        raise FileNotFoundError(f"Historical release asset is missing: {path}")
    if _sha256(path) != _required_string(metadata, "sha256"):
        raise ValueError(f"Historical release asset checksum differs: {path.name}.")
    size = metadata.get("size_bytes")
    if not isinstance(size, int) or size != path.stat().st_size:
        raise ValueError(f"Historical release asset size differs: {path.name}.")


def _sha256(path: Path) -> str:
    """Return the streaming SHA256 digest for one release asset."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, object]:
    """Read one required JSON object."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Historical release JSON is not an object: {path}.")
    return payload


def _required_object(
    payload: dict[str, object],
    key: str,
) -> dict[str, object]:
    """Return one required nested JSON object."""

    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Historical release field {key!r} is not an object.")
    return value


def _required_string(payload: dict[str, object], key: str) -> str:
    """Return one required non-empty JSON string."""

    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Historical release field {key!r} is not a string.")
    return value


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """Write deterministic qualification evidence."""

    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse historical channel preparation arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Prepare one reviewed historical macOS channel for installer qualification."""

    arguments = _parse_args(argv)
    manifest_path = reconstitute_historical_macos_release(
        source_root=arguments.source_root.resolve(),
        output_root=arguments.output_root.resolve(),
    )
    print(f"HISTORICAL_MACOS_CHANNEL_READY manifest={manifest_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
