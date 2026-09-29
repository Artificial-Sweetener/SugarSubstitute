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

"""Define focused host ports for cube-section realization."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from substitute.application.node_behavior import ResolvedFieldSpec


class CubeSectionBuildSessionPanelProtocol(Protocol):
    """Describe node-card realization used by one cube build session."""

    def build_node_card(
        self,
        node_name: str,
        inputs: dict[str, object],
        node_type: str,
        field_specs: Mapping[str, ResolvedFieldSpec],
        cube_state: dict[str, object],
        resolved_behavior: object,
        display_decision: object | None = None,
        *,
        alias: str | None = None,
        parent: object | None = None,
    ) -> object:
        """Build one node card for the session."""

    def register_card_wrapper(
        self,
        cube_alias: str,
        node_name: str,
        wrapper: object,
    ) -> None:
        """Register the live wrapper for one node card."""

    def remove_card_wrapper_if_current(
        self,
        cube_alias: str,
        node_name: str,
        wrapper: object,
    ) -> None:
        """Remove a wrapper while it still owns its registry entry."""


class CubeSectionBuildPanelProtocol(CubeSectionBuildSessionPanelProtocol, Protocol):
    """Describe snapshot and section realization needed to prepare cube builds."""

    def current_behavior_snapshot(self) -> object | None:
        """Return the current prepared behavior snapshot when available."""

    def _build_behavior_snapshot(self, **kwargs: object) -> object:
        """Build a behavior snapshot when no prepared snapshot exists."""

    def _prepare_cube_section_widget(self, route_key: str) -> object:
        """Create the passive cube-section shell for one alias."""
