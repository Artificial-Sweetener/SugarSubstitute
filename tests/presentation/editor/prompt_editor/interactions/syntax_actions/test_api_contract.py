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

"""Test the public prompt interaction API contract."""

from __future__ import annotations

import importlib


def test_prompt_interaction_controller_removes_old_flyout_entry_points() -> None:
    """The interaction controller no longer exposes retired flyout entry points."""

    mod = importlib.import_module(
        "substitute.presentation.editor.prompt_editor.interactions.controller"
    )

    assert hasattr(mod.PromptInteractionController, "handle_mouse_press")
    assert not hasattr(mod.PromptInteractionController, "show_emphasis_flyout")
    assert not hasattr(mod.PromptInteractionController, "handle_context_menu")
