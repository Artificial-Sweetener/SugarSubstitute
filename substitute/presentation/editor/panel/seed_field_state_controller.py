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

"""Own persisted random/fixed mode state for node seed controls."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from substitute.domain.generation.seed_control import (
    SeedControlState,
    SeedMode,
    seed_mode_from_value,
)


class SeedFieldBinding(Protocol):
    """Identify the node field whose seed mode is persisted."""

    @property
    def node_name(self) -> str | None:
        """Return the owning node name."""

    @property
    def field_key(self) -> str:
        """Return the canonical seed field key."""


class SeedModeControl(Protocol):
    """Expose semantic mode operations implemented by a seed widget."""

    def setMode(self, mode: str) -> None:  # noqa: N802
        """Project one persisted mode into the control."""


class SeedFieldStateController:
    """Bind node seed-mode intent to cube-owned control state."""

    def __init__(self, mark_dirty: Callable[[object], None]) -> None:
        """Store the cube dirty-state callback."""

        self._mark_dirty = mark_dirty

    def bind_mode(
        self,
        control: SeedModeControl,
        cube_state: object,
        binding: SeedFieldBinding,
    ) -> None:
        """Restore and persist one seed control's random/fixed mode."""

        if binding.node_name is None:
            return
        set_mode = getattr(control, "setMode", None)
        if not callable(set_mode):
            return
        set_mode(self.mode_for(cube_state, binding).value)
        signal = getattr(control, "modeChanged", None)
        if signal is None or not hasattr(signal, "connect"):
            return

        def on_mode_changed(mode: object) -> None:
            """Persist one semantic seed-mode change."""

            self.set_mode(cube_state, binding, seed_mode_from_value(mode))

        signal.connect(on_mode_changed)

    def mode_for(self, cube_state: object, binding: SeedFieldBinding) -> SeedMode:
        """Return the persisted mode for one seed field."""

        if binding.node_name is None:
            return SeedMode.RANDOM
        states = getattr(cube_state, "field_control_states", None)
        if not isinstance(states, dict):
            return SeedMode.RANDOM
        node_states = states.get(binding.node_name)
        if not isinstance(node_states, dict):
            return SeedMode.RANDOM
        state = node_states.get(binding.field_key)
        return state.mode if isinstance(state, SeedControlState) else SeedMode.RANDOM

    def set_mode(
        self,
        cube_state: object,
        binding: SeedFieldBinding,
        mode: SeedMode,
    ) -> bool:
        """Persist one seed mode and mark its cube dirty when changed."""

        if binding.node_name is None:
            return False
        states = getattr(cube_state, "field_control_states", None)
        if not isinstance(states, dict):
            states = {}
            setattr(cube_state, "field_control_states", states)
        node_states = states.setdefault(binding.node_name, {})
        previous = node_states.get(binding.field_key)
        if isinstance(previous, SeedControlState) and previous.mode == mode:
            return False
        node_states[binding.field_key] = SeedControlState(mode)
        self._mark_dirty(cube_state)
        return True


__all__ = ["SeedFieldStateController"]
