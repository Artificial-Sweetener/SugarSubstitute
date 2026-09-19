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

"""Test cube-header refresh through the EditorPanel façade."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace


class _Label:
    """Record title text shown by a cube header."""

    def __init__(self) -> None:
        """Initialize the displayed text."""

        self.text = ""
        self.identity: tuple[object, str] | None = None

    def setText(self, text: str) -> None:  # noqa: N802
        """Record displayed title text."""

        self.text = text

    def setTargetModel(self, target_model: str) -> None:  # noqa: N802
        """Record the target model without changing the retained icon."""

        self.identity = (None, target_model)


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def test_refresh_cube_header_delegates_to_registry_controller() -> None:
    """EditorPanel should expose the header refresh hook used by cube actions."""

    panel_module = _panel_module()
    label = _Label()
    cube_state = SimpleNamespace(
        buffer={"nodes": {}},
        bypassed=True,
        ui={"canonical_cube": {"metadata": {"target_model": "SDXL"}}},
    )
    panel = SimpleNamespace(
        cube_headers={"SDXL/Automask Detailer": label},
        cube_positions={},
        cube_widgets={},
        cube_sections={},
        row_widgets={},
        col_widgets={},
        input_widgets_by_field_key={},
        card_wrappers={},
        sampler_link_widgets={},
        scheduler_link_widgets={},
        _cube_visibility_btns={},
        _cube_visibility_menus={},
        _cube_states={"SDXL/Automask Detailer": cube_state},
        _stack_order=["SDXL/Automask Detailer"],
        _node_card_mode_controller=SimpleNamespace(),
    )

    panel_module.EditorPanel.refresh_cube_header(panel, "SDXL/Automask Detailer")

    assert label.text == "Automask Detailer (bypassed)"
    assert label.identity == (None, "SDXL")
