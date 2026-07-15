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

"""Guard context-menu construction behind the shared menu renderer."""

from __future__ import annotations

import ast
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PRESENTATION_ROOT = _REPO_ROOT / "substitute" / "presentation"
_DIRECT_ROW_ALLOWLIST = {
    Path("widgets/qfluent_menu_renderer.py"),
    Path("widgets/seed_box.py"),
}
_DIRECT_MENU_ALLOWLIST = {
    Path("widgets/qfluent_menu_renderer.py"),
    Path("widgets/seed_box.py"),
}


def test_production_context_menus_use_shared_renderer() -> None:
    """Reject direct production menu row construction outside approved adapters."""

    row_violations: list[str] = []
    menu_violations: list[str] = []
    for path in _python_files(_PRESENTATION_ROOT):
        relative_path = path.relative_to(_PRESENTATION_ROOT)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _is_menu_row_call(node) and relative_path not in _DIRECT_ROW_ALLOWLIST:
                row_violations.append(_location(relative_path, node))
            if (
                _is_direct_menu_call(node)
                and relative_path not in _DIRECT_MENU_ALLOWLIST
            ):
                menu_violations.append(_location(relative_path, node))

    assert row_violations == []
    assert menu_violations == []


def _python_files(root: Path) -> tuple[Path, ...]:
    """Return production Python files under one root."""

    return tuple(sorted(path for path in root.rglob("*.py") if path.is_file()))


def _is_menu_row_call(node: ast.Call) -> bool:
    """Return whether a call directly mutates menu rows."""

    return isinstance(node.func, ast.Attribute) and node.func.attr in {
        "addAction",
        "addMenu",
    }


def _is_direct_menu_call(node: ast.Call) -> bool:
    """Return whether a call constructs a Qt/QFluent menu directly."""

    return isinstance(node.func, ast.Name) and node.func.id in {"RoundMenu", "QMenu"}


def _location(path: Path, node: ast.AST) -> str:
    """Return a stable source location for one architecture violation."""

    return f"{path.as_posix()}:{getattr(node, 'lineno', 0)}"
