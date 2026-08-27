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

"""Cube-load node-behavior runtime preparation contracts."""

from __future__ import annotations

from types import SimpleNamespace


from tests.presentation.shell.cube_actions.support import (
    _import_module,
)


def test_prepare_node_behavior_runtime_delegates_to_service() -> None:
    """Runtime preparation should use the node-behavior service directly."""

    mod = _import_module()
    runtime_state = object()
    service_calls: list[str] = []
    loaded_cube = SimpleNamespace(
        cube_id="CubeA", version="1.0.0", display_name="Cube A", ui_payload={}
    )

    def prepare_runtime_state(_loaded_cube: object, alias_name: str) -> object:
        """Record runtime preparation and return the stable state."""
        service_calls.append(alias_name)
        return runtime_state

    view = SimpleNamespace(
        node_behavior_service=SimpleNamespace(
            prepare_runtime_state=prepare_runtime_state,
        )
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
    )

    result = actions.prepare_node_behavior_runtime(loaded_cube, "AliasA")

    assert result is runtime_state
    assert service_calls == ["AliasA"]
