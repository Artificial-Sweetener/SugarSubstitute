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

"""Provide deterministic fixtures for launcher runtime qualification."""

from __future__ import annotations

import hashlib
import io
import tarfile
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path


class RecordingRuntimeRunner:
    """Record runtime provisioning commands without executing them."""

    def __init__(self) -> None:
        """Initialize empty command capture."""

        self.commands: list[list[str]] = []
        self.environments: list[dict[str, str]] = []

    def run(self, command: Sequence[str], *, cwd: Path, env: Mapping[str, str]) -> None:
        """Record one command invocation."""

        self.commands.append(list(command))
        self.environments.append(dict(env))


def write_uv_archive(path: Path, *, executable_name: str = "uv.exe") -> Path:
    """Write a minimal uv release archive fixture."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"uv-test-target/{executable_name}", b"uv")
    return path


def write_posix_uv_archive(path: Path) -> Path:
    """Write a minimal official-style POSIX uv archive fixture."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"uv"
    member = tarfile.TarInfo("uv-x86_64-unknown-linux-gnu/uv")
    member.size = len(payload)
    member.mode = 0o755
    with tarfile.open(path, "w:gz") as archive:
        archive.addfile(member, io.BytesIO(payload))
    return path


def write_file(path: Path, content: str) -> None:
    """Write one fixture file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def sha256(path: Path) -> str:
    """Return the SHA256 hex digest for one file."""

    return hashlib.sha256(path.read_bytes()).hexdigest()
