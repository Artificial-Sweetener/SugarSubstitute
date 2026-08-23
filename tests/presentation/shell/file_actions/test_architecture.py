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

"""Test workspace file action ownership boundaries."""

from __future__ import annotations

from pathlib import Path


def test_workspace_file_actions_do_not_register_output_images_directly() -> None:
    """File actions must delegate Output materialization to the registrar port."""

    source = Path("substitute/presentation/shell/workspace_file_actions.py").read_text(
        encoding="utf-8"
    )

    assert "output_canvas_state_service" not in source
    assert ".register_output_image(" not in source
