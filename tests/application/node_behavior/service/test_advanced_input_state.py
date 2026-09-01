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

"""Verify durable advanced-input disclosure state."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.application.node_behavior import AdvancedInputStateService


def test_imported_comfy_state_seeds_disclosure_without_mutating_ui() -> None:
    """An imported showAdvanced flag should seed a card until the user overrides it."""

    state = SimpleNamespace(
        ui={},
        dirty=False,
        buffer={
            "nodes": {
                "7": {"_workflow": {"show_advanced_inputs": True}},
            }
        },
    )

    assert AdvancedInputStateService().is_shown(state, "7") is True
    assert state.ui == {}
    assert state.dirty is False


def test_explicit_hidden_state_overrides_imported_shown_state() -> None:
    """A user hide action should durably override a true imported default."""

    state = SimpleNamespace(
        ui={},
        dirty=False,
        buffer={
            "nodes": {
                "7": {"_workflow": {"show_advanced_inputs": True}},
            }
        },
    )
    service = AdvancedInputStateService()

    assert service.set_shown(state, "7", False) is True
    assert service.is_shown(state, "7") is False
    assert state.ui == {"advanced_input_visibility": {"7": False}}
    assert state.dirty is True


def test_disclosure_change_does_not_touch_node_inputs() -> None:
    """Toggling disclosure should preserve executable values byte-for-byte."""

    inputs = {"steps": 20, "cfg": 7.0}
    state = SimpleNamespace(
        ui=None,
        dirty=False,
        buffer={"nodes": {"sampler": {"inputs": inputs}}},
    )

    AdvancedInputStateService().set_shown(state, "sampler", True)

    assert state.buffer["nodes"]["sampler"]["inputs"] == inputs
    assert state.ui == {"advanced_input_visibility": {"sampler": True}}
