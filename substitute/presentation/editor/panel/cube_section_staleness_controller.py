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

"""Own stale marking for editor cube-section projection records."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from substitute.shared.logging.logger import get_logger, log_info

from .projection_build_registry import CubeSectionBuildStaleResult
from .projection_preparation import CubeDefinitionIdentity

_LOGGER = get_logger("presentation.editor.panel.cube_section_staleness_controller")


class CubeSectionStalenessPanelProtocol(Protocol):
    """Describe rendered cube widgets available for stale-record adoption."""

    cube_widgets: dict[str, object]


class CubeSectionStalenessBuildRegistryProtocol(Protocol):
    """Describe build-registry operations required for stale marking."""

    def record_for(self, alias: str) -> object | None:
        """Return the current build record for an alias."""

    def adopt_complete(
        self,
        *,
        alias: str,
        widget: object,
        snapshot_identity: object | None,
        definition_identity: CubeDefinitionIdentity | None,
    ) -> None:
        """Adopt a visible widget as a complete build record."""

    def mark_stale(self, alias: str, reason: str) -> CubeSectionBuildStaleResult:
        """Mark one build record stale and return the lifecycle impact."""


class CubeSectionStalenessCompletionRegistryProtocol(Protocol):
    """Describe pending insert completion updates for stale active builds."""

    def mark_pending_insert_superseded(
        self,
        *,
        workflow_id: str,
        cube_alias: str,
        token: object,
        reason: str,
    ) -> bool:
        """Mark a pending insert completion as superseded by projection."""


class CubeSectionStalenessWorkflowContextProtocol(Protocol):
    """Describe workflow identity lookup for stale completion ownership."""

    def active_workflow_id(self) -> str:
        """Return the active workflow id for pending insert completion lookup."""


class CubeSectionStalenessController:
    """Mark cube-section build records stale and preserve affected callbacks."""

    def __init__(
        self,
        *,
        panel: CubeSectionStalenessPanelProtocol,
        build_registry: CubeSectionStalenessBuildRegistryProtocol,
        completion_registry: CubeSectionStalenessCompletionRegistryProtocol,
        workflow_context: CubeSectionStalenessWorkflowContextProtocol,
    ) -> None:
        """Store stale-marking collaborators."""

        self._panel = panel
        self._build_registry = build_registry
        self._completion_registry = completion_registry
        self._workflow_context = workflow_context

    def mark_cube_sections_stale(
        self,
        cube_aliases: Sequence[str],
        *,
        reason: str,
    ) -> bool:
        """Mark affected cube sections stale and report active-build impact."""

        active_build_affected = False
        for cube_alias in cube_aliases:
            self._adopt_visible_widget_when_untracked(cube_alias)
            stale_result = self._build_registry.mark_stale(cube_alias, reason)
            active_build_affected = stale_result.was_building or active_build_affected
            if stale_result.active_token is not None:
                self._completion_registry.mark_pending_insert_superseded(
                    workflow_id=self._workflow_context.active_workflow_id(),
                    cube_alias=cube_alias,
                    token=stale_result.active_token,
                    reason=reason,
                )
        log_info(
            _LOGGER,
            "Marked editor cube sections stale",
            cube_aliases=tuple(cube_aliases),
            reason=reason,
            active_build_affected=active_build_affected,
        )
        return active_build_affected

    def _adopt_visible_widget_when_untracked(self, cube_alias: str) -> None:
        """Adopt a visible cube widget so stale marking records its lifecycle."""

        if self._build_registry.record_for(cube_alias) is not None:
            return
        widget = self._panel.cube_widgets.get(cube_alias)
        if widget is None:
            return
        self._build_registry.adopt_complete(
            alias=cube_alias,
            widget=widget,
            snapshot_identity=None,
            definition_identity=None,
        )
