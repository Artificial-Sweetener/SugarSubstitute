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

"""Fingerprint declared cache producers without formatting-only churn."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path
import tokenize

from substitute.shared.util.path_safety import ensure_within_root


class SemanticSourceFingerprintService:
    """Hash declared Python semantics and byte-sensitive producer assets."""

    def fingerprint(
        self,
        *,
        source_root: Path,
        python_sources: Iterable[Path] = (),
        asset_sources: Iterable[Path] = (),
    ) -> str:
        """Return a deterministic digest for cache-relevant producer inputs.

        Python syntax is normalized through the AST and owned docstrings are
        removed so comments, formatting, and documentation edits preserve cache
        compatibility. Assets remain byte-sensitive because their exact content
        can affect rendered or projected output.
        """

        resolved_root = source_root.resolve()
        records: list[tuple[str, str, bytes]] = []
        for source in python_sources:
            path = self._validated_source(source, root=resolved_root)
            records.append(
                (
                    "python",
                    path.relative_to(resolved_root).as_posix(),
                    _normalized_python(path),
                )
            )
        for source in asset_sources:
            path = self._validated_source(source, root=resolved_root)
            records.append(
                (
                    "asset",
                    path.relative_to(resolved_root).as_posix(),
                    path.read_bytes(),
                )
            )
        if not records:
            raise ValueError("Cache producer fingerprint requires declared sources.")
        digest = sha256()
        for source_kind, relative_path, payload in sorted(records):
            digest.update(source_kind.encode("ascii"))
            digest.update(b"\0")
            digest.update(relative_path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(payload)
            digest.update(b"\0")
        return digest.hexdigest()

    @staticmethod
    def _validated_source(source: Path, *, root: Path) -> Path:
        """Return one declared source after containment and file validation."""

        candidate = source if source.is_absolute() else root / source
        resolved = ensure_within_root(
            candidate,
            root_path=root,
            subject="Cache producer source",
        )
        if not resolved.is_file():
            raise ValueError(f"Cache producer source is not a file: {resolved}.")
        return resolved


def _normalized_python(path: Path) -> bytes:
    """Return position-independent Python syntax with docstrings removed."""

    with tokenize.open(path) as stream:
        tree = ast.parse(stream.read(), filename=path.name)
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body = node.body[1:]
    return ast.dump(tree, annotate_fields=True, include_attributes=False).encode(
        "utf-8"
    )


__all__ = ["SemanticSourceFingerprintService"]
