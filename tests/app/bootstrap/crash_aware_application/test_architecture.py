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

"""Verify QApplication construction remains behind the crash boundary."""

from __future__ import annotations

import ast
from pathlib import Path

import substitute.app.bootstrap.composition as composition


def test_production_application_is_constructed_through_crash_aware_owner() -> None:
    """Composition must not regress to constructing a plain QApplication."""

    source_path = Path(composition.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    constructor_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "CrashAwareApplication" in constructor_names
    assert "QApplication" not in constructor_names
