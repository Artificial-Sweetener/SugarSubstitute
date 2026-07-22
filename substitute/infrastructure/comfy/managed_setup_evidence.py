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

"""Own durable managed-setup evidence and filesystem signatures."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile


def load_json_object(path: Path) -> dict[str, object] | None:
    """Load a JSON object, treating missing or invalid evidence as absent."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def write_json_object_atomic(path: Path, payload: Mapping[str, object]) -> None:
    """Commit JSON evidence through a durable same-directory replacement."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
        ) as file:
            json.dump(payload, file, indent=2, sort_keys=True)
            file.flush()
            os.fsync(file.fileno())
            temporary_path = Path(file.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def path_signature(path: Path) -> dict[str, object]:
    """Return a cheap filesystem identity for non-contract paths."""

    try:
        stat = path.stat()
    except OSError:
        return {"exists": False}
    return {
        "exists": True,
        "is_dir": path.is_dir(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def content_signature(path: Path) -> dict[str, object]:
    """Return a timestamp-independent identity for an authoritative contract."""

    try:
        content = path.read_bytes()
    except OSError:
        return {"exists": False}
    return {
        "exists": True,
        "size": len(content),
        "sha256": sha256(content).hexdigest(),
    }


__all__ = [
    "content_signature",
    "load_json_object",
    "path_signature",
    "write_json_object_atomic",
]
