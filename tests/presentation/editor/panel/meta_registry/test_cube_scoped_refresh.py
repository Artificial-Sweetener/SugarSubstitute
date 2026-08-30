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

"""Test cube-scoped link refresh through the EditorPanel façade."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def test_refresh_link_widgets_for_cube_refreshes_stack_scoped_node_widths() -> None:
    """Cube-scoped refresh should update all node-link selector widths."""

    panel_module = _panel_module()
    registry_calls: list[tuple[str, str | None]] = []
    panel = SimpleNamespace(
        meta_registry=SimpleNamespace(
            update_node_link_widgets=lambda: registry_calls.append(("node_all", None)),
            update_sampler_link_widgets_for_cube=lambda alias: registry_calls.append(
                ("sampler_cube", alias)
            ),
            update_scheduler_link_widgets_for_cube=lambda alias: registry_calls.append(
                ("scheduler_cube", alias)
            ),
        ),
    )

    panel_module.EditorPanel.refresh_link_widgets_for_cube(
        panel,
        "SDXL/Automask Detailer",
    )

    assert registry_calls == [
        ("node_all", None),
        ("sampler_cube", "SDXL/Automask Detailer"),
        ("scheduler_cube", "SDXL/Automask Detailer"),
    ]
