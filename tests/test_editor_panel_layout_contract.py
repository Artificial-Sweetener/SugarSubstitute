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

"""Source contracts for editor-panel workspace layout margins."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EDITOR_PANEL_PATH = (
    REPO_ROOT / "substitute" / "presentation" / "editor" / "panel" / "view.py"
)


def test_editor_panel_content_has_asymmetric_workspace_gutters() -> None:
    """Editor content should not sit directly against the cube-stack edge."""

    source = EDITOR_PANEL_PATH.read_text(encoding="utf-8")

    assert "EDITOR_PANEL_LEFT_GUTTER = 6" in source
    assert "EDITOR_PANEL_RIGHT_GUTTER = 14" in source
    assert (
        "content.setContentsMargins(\n            EDITOR_PANEL_LEFT_GUTTER," in source
    )
    assert "            EDITOR_PANEL_RIGHT_GUTTER," in source
    assert "content.setContentsMargins(0, 0, 20, 0)" not in source
