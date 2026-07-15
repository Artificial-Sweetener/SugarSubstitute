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

"""Refresh cheap editor affordances for already-clean projection surfaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from .projection_preparation import BehaviorRefreshReason


class CleanProjectionRefreshPanelProtocol(Protocol):
    """Describe panel state and refresh hooks for clean projection reuse."""

    _cube_states: dict[str, object] | None
    _stack_order: list[str] | None

    def sync_prompt_editor_values_from_buffers(self) -> None:
        """Synchronize prompt editor widgets from cube buffers."""

    def _refresh_link_widgets(self) -> None:
        """Refresh rendered prompt-link widgets."""

    def refresh_node_behavior_state(
        self,
        *,
        reason: BehaviorRefreshReason = "full_workflow_projection",
        use_cached_snapshot: bool = False,
    ) -> None:
        """Refresh node behavior state for the already-rendered surface."""


class EditorCleanProjectionRefreshController:
    """Own cheap active-state refreshes when a projection is already clean."""

    def __init__(self, panel: CleanProjectionRefreshPanelProtocol) -> None:
        """Store the panel whose already-rendered affordances should refresh."""

        self._panel = panel

    def refresh_clean_projection(
        self,
        *,
        cube_states: Mapping[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> None:
        """Refresh cheap active-state affordances for an already-clean surface."""

        panel = self._panel
        panel._cube_states = dict(cube_states) if cube_states is not None else None
        panel._stack_order = list(stack_order) if stack_order is not None else None
        panel.sync_prompt_editor_values_from_buffers()
        panel._refresh_link_widgets()
        panel.refresh_node_behavior_state(use_cached_snapshot=True)
