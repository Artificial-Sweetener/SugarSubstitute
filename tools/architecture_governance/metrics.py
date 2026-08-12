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

"""Own stable source measurements used by architecture governance."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

from .model import ArchitecturePolicy


def production_line_count(path: Path) -> int:
    """Count nonblank physical lines that are not comment-only lines."""

    return sum(
        1
        for line in normalized_source(path).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def source_fingerprint(root: Path, paths: Iterable[str]) -> str:
    """Return a newline-stable fingerprint for exact repository paths."""

    digest = hashlib.sha256()
    for relative_path in sorted(paths):
        normalized_path = relative_path.replace("\\", "/")
        digest.update(normalized_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(normalized_source(root / normalized_path).encode("utf-8"))
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def normalized_source(path: Path) -> str:
    """Read UTF-8 source with canonical newlines for cross-platform identity."""

    return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")


def governed_source_paths(
    root: Path,
    policy: ArchitecturePolicy,
) -> tuple[Path, ...]:
    """Return exact Python source paths below the configured runtime roots."""

    candidates = (
        path
        for source_root in policy.source_roots
        for path in (root / source_root).rglob("*")
        if path.is_file() and path.suffix in {".py", ".pyi"}
    )
    return tuple(
        path
        for path in sorted(candidates)
        if path.relative_to(root).as_posix() not in policy.excluded_paths
        and "__pycache__" not in path.parts
    )
