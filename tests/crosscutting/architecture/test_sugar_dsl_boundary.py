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

"""Verify the frontend runtime remains independent of Sugar-DSL."""

from __future__ import annotations

import ast
from pathlib import Path


def test_frontend_runtime_package_does_not_import_sugar_dsl() -> None:
    """Keep backend-owned Sugar-DSL imports out of frontend runtime code."""
    runtime_root = Path(__file__).resolve().parents[3] / "substitute"
    offenders: list[str] = []

    for path in runtime_root.rglob("*.py"):
        parsed = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(parsed):
            if isinstance(node, ast.Import):
                if any(
                    alias.name == "sugar" or alias.name.startswith("sugar.")
                    for alias in node.names
                ):
                    offenders.append(str(path.relative_to(runtime_root.parent)))
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                if module_name == "sugar" or module_name.startswith("sugar."):
                    offenders.append(str(path.relative_to(runtime_root.parent)))

    assert offenders == []
