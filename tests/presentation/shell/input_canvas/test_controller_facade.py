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

"""Tests for WorkspaceController input-canvas facade behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from substitute.presentation.shell import workspace_controller as mod


def test_input_canvas_intents_delegate_to_input_presenter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WorkspaceController should route Input canvas intents to the presenter."""

    calls: list[tuple[str, tuple[object, ...]]] = []
    interaction_controller = SimpleNamespace(
        handle_image_changed=lambda *args: calls.append(("image_changed", args)),
        handle_image_clicked=lambda *args: calls.append(("image_clicked", args)),
        handle_mask_changed=lambda *args: calls.append(("mask_changed", args)),
    )
    controller = cast(Any, object.__new__(mod.WorkspaceController))
    controller._views = SimpleNamespace(
        canvas=SimpleNamespace(input_node_interaction_controller=interaction_controller)
    )

    controller.on_input_image_changed("CubeA", "ImageNode", "C:/images/input.png")
    controller.on_input_image_clicked("CubeA", "ImageNode", "C:/images/input.png")
    controller.on_input_mask_changed("CubeA", "MaskNode", "C:/masks/mask.png")

    assert calls == [
        ("image_changed", ("CubeA", "ImageNode", "C:/images/input.png")),
        ("image_clicked", ("CubeA", "ImageNode", "C:/images/input.png")),
        ("mask_changed", ("CubeA", "MaskNode", "C:/masks/mask.png")),
    ]
