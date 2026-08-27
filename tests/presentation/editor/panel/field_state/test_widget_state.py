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

"""Qualify seed and integer widget state persistence through the field-state owner."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from _pytest.monkeypatch import MonkeyPatch

from substitute.domain.generation.seed_control import SeedControlState, SeedMode
import substitute.presentation.editor.panel.field_state_controller as field_state_mod
from substitute.presentation.editor.panel.field_state_controller import (
    EditorPanelFieldStateController,
)


from tests.presentation.editor.panel.field_state.controller_support import (
    _LineEditDouble,
    _SeedBoxDouble,
)


def test_wire_seedbox_state_restores_and_persists_seed_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    """SeedBox mode should round-trip through cube field control state."""

    monkeypatch.setattr(field_state_mod, "SeedBox", _SeedBoxDouble)
    seedbox = _SeedBoxDouble(
        {"cube_alias": "CubeA", "node_name": "KSampler", "key": "seed"}
    )
    cube_state = SimpleNamespace(
        buffer={"nodes": {"KSampler": {"inputs": {"seed": 123}}}},
        dirty=False,
        field_control_states={"KSampler": {"seed": SeedControlState(SeedMode.FIXED)}},
    )

    EditorPanelFieldStateController().bind_node_widget_state(seedbox, cube_state, {})

    assert seedbox.value() == 123
    assert seedbox.mode() == "fixed"

    seedbox.setMode("random")

    assert cube_state.field_control_states["KSampler"]["seed"].mode == SeedMode.RANDOM
    assert cube_state.dirty is True


def test_wire_integer_lineedit_state_persists_python_integer() -> None:
    """Large INT fallbacks should commit integer values instead of strings."""

    lineedit = _LineEditDouble(
        {
            "cube_alias": "DirectWorkflow",
            "node_name": "PrimitiveInt",
            "key": "value",
            "type": "INT",
        },
        text="stale",
    )
    cube_state = SimpleNamespace(
        buffer={"nodes": {"PrimitiveInt": {"inputs": {"value": 0}}}},
        dirty=False,
    )

    EditorPanelFieldStateController().wire_lineedit_state(
        cast(Any, lineedit), cube_state
    )

    assert lineedit.text() == "0"
    lineedit.setText("18446744073709551615")
    assert cube_state.buffer["nodes"]["PrimitiveInt"]["inputs"]["value"] == 0

    lineedit.editingFinished.emit()

    stored_value = cube_state.buffer["nodes"]["PrimitiveInt"]["inputs"]["value"]
    assert stored_value == 18_446_744_073_709_551_615
    assert isinstance(stored_value, int)
    assert cube_state.dirty is True
