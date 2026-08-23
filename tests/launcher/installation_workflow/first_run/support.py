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

"""Provide deterministic local release artifacts for first-run contracts."""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections.abc import Callable, Sequence
from pathlib import Path


def record_command(
    started_commands: list[list[str]],
) -> Callable[[Sequence[str]], None]:
    """Return a process starter that records commands without launching."""

    def starter(command: Sequence[str]) -> None:
        """Record one subprocess command."""

        started_commands.append(list(command))

    return starter


def write_manifest(
    path: Path, *, app_zip: Path, launcher_zip: Path | None = None
) -> None:
    """Write a minimal local release manifest for tests."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest_payload(app_zip=app_zip, launcher_zip=launcher_zip)),
        encoding="utf-8",
    )


def manifest_payload(
    *, app_zip: Path, launcher_zip: Path | None = None
) -> dict[str, object]:
    """Return a local release manifest payload fixture."""

    payload: dict[str, object] = {
        "schema_version": 1,
        "channel": "stable",
        "version": "0.4.0",
        "minimum_launcher_version": "0.1.0",
        "app": {
            "filename": app_zip.name,
            "url": app_zip.as_uri(),
            "sha256": sha256(app_zip),
            "size_bytes": app_zip.stat().st_size,
        },
        "launchers": {},
        "installers": {},
    }
    if launcher_zip is not None:
        payload["launchers"] = {
            "windows_x64": {
                "filename": launcher_zip.name,
                "url": launcher_zip.as_uri(),
                "sha256": sha256(launcher_zip),
                "size_bytes": launcher_zip.stat().st_size,
            },
        }
    return payload


def write_valid_payload_zip(path: Path) -> Path:
    """Write a minimal valid app payload zip."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("main.py", "print('app')\n")
        archive.writestr("requirements.txt", "PySide6\n")
        archive.writestr("sitecustomize.py", "# site customization\n")
        archive.writestr("substitute/__init__.py", '"""App package."""\n')
        archive.writestr("third_party/manifest.toml", "[[component]]\n")
    return path


def write_valid_launcher_bundle_zip(path: Path) -> Path:
    """Write a minimal valid PyInstaller onedir launcher bundle zip."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("SugarSubstitute.exe", b"launcher")
        archive.writestr("launcher-bin/python312.dll", b"dll")
    return path


def write_file(path: Path, content: str) -> None:
    """Write one text fixture file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def sha256(path: Path) -> str:
    """Return the SHA256 hex digest for one file."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(payload: bytes) -> str:
    """Return the SHA256 hex digest for in-memory test bytes."""

    return hashlib.sha256(payload).hexdigest()
