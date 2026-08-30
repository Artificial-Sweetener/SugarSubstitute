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

"""Tests for pure mask color selection policy."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.domain.canvas.mask_color_scheme import mask_color_hue


def test_mask_color_hue_uses_color_theory_spacing() -> None:
    """Mask hue selection should be deterministic and evenly distinguish masks."""

    assert mask_color_hue(30, 0, 4) == 30
    assert mask_color_hue(30, 1, 2) == 210
    assert mask_color_hue(30, 1, 3) == 180
    assert mask_color_hue(30, 2, 3) == 240
    assert mask_color_hue(30, 3, 4) == 300
    assert mask_color_hue(30, 2, 5) == 174
    assert mask_color_hue(390, 1, 2) == 210


def test_mask_color_scheme_domain_import_boundary() -> None:
    """Domain mask color policy must not import Qt or presentation modules."""

    source_path = Path("substitute/domain/canvas/mask_color_scheme.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_prefixes = (
        "PySide6",
        "qfluentwidgets",
        "qframelesswindow",
        "substitute.presentation",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names = tuple(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_names = (node.module or "",)
        else:
            continue

        assert not any(
            name == prefix or name.startswith(f"{prefix}.")
            for name in imported_names
            for prefix in forbidden_prefixes
        )
