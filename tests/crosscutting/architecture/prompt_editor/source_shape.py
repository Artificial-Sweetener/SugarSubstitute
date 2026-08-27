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

"""Inspect focused prompt-editor source-shape invariants."""

from __future__ import annotations

import ast
from pathlib import Path


def protocol_class_count(source_path: Path) -> int:
    """Return Protocol-derived class count in one source module."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    return sum(
        isinstance(node, ast.ClassDef)
        and any(
            (isinstance(base, ast.Name) and base.id == "Protocol")
            or (isinstance(base, ast.Attribute) and base.attr == "Protocol")
            for base in node.bases
        )
        for node in ast.walk(tree)
    )


def immediate_python_files(package_root: Path) -> set[str]:
    """Return Python filenames placed directly in one package."""

    return {path.name for path in package_root.glob("*.py")}


def immediate_package_names(package_root: Path) -> frozenset[str]:
    """Return immediate child packages beneath one package root."""

    return frozenset(
        path.name
        for path in package_root.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    )
