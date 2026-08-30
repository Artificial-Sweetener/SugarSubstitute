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

"""Verify the standalone launcher package boundary."""

from __future__ import annotations

import ast
from pathlib import Path

from launcher import sugarsubstitute_launcher


LAUNCHER_PACKAGE_ROOT = Path(sugarsubstitute_launcher.__file__).parent


def test_launcher_package_does_not_import_app_payload() -> None:
    """The standalone launcher package stays independent from substitute code."""

    import_names: set[str] = set()
    for path in LAUNCHER_PACKAGE_ROOT.rglob("*.py"):
        module = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                import_names.update(
                    alias.name.split(".", maxsplit=1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                import_names.add(node.module.split(".", maxsplit=1)[0])

    assert "substitute" not in import_names
