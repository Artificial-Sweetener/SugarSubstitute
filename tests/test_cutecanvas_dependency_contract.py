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

"""Enforce CuteCanvas as SugarSubstitute's sole canvas package boundary."""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_CANVAS_BOUNDARY_PATHS = (
    _ROOT / "substitute" / "presentation" / "canvas",
    _ROOT / "substitute" / "infrastructure" / "execution",
    _ROOT / "substitute" / "app" / "bootstrap" / "execution_runtime.py",
)


def test_canvas_boundary_never_imports_qpane_directly() -> None:
    """Require CuteCanvas to encapsulate every production QPane canvas seam."""

    direct_imports = tuple(
        location
        for path in _python_sources()
        for location in _qpane_import_locations(path)
    )

    assert direct_imports == ()


def test_runtime_requirements_do_not_pin_qpane_directly() -> None:
    """Let CuteCanvas declare and resolve its renderer dependency."""

    requirements = (_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert not any(
        line.strip().lower().startswith("qpane") for line in requirements.splitlines()
    )


def _python_sources() -> tuple[Path, ...]:
    """Return deterministic production sources that form the canvas boundary."""

    sources: list[Path] = []
    for boundary in _CANVAS_BOUNDARY_PATHS:
        if boundary.is_file():
            sources.append(boundary)
        else:
            sources.extend(boundary.rglob("*.py"))
    return tuple(sorted(sources))


def _qpane_import_locations(path: Path) -> tuple[str, ...]:
    """Return direct QPane import locations from one production source."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    locations: list[str] = []
    for node in ast.walk(tree):
        names: tuple[str, ...]
        if isinstance(node, ast.Import):
            names = tuple(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names = () if node.module is None else (node.module,)
        else:
            continue
        if any(name == "qpane" or name.startswith("qpane.") for name in names):
            locations.append(f"{path.relative_to(_ROOT)}:{node.lineno}")
    return tuple(locations)
