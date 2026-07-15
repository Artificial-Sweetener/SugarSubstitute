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

"""Build, reuse, and discard projected editor cube widgets."""

from __future__ import annotations

from collections.abc import Sequence
from time import perf_counter
from typing import Protocol

from substitute.shared.logging.logger import get_logger, log_debug, log_info

from .projection_preparation import (
    CubeDefinitionIdentity,
    cube_definition_identity,
)
from .projected_widget_lifecycle import prepare_projected_widget_for_hidden_build
from .projection_build_registry import CubeSectionBuildReuseDecision
from .projection_models import ProjectedCubeBuild
from .projection_observability import (
    log_panel_projection_timing,
    panel_projection_observability_started_at,
)
from .projection_session import (
    ActiveProjectionSession,
    PendingInsertCompletion,
)
from .runtime_issue_projection_adapter import RuntimeIssueProjectionPort

_LOGGER = get_logger("presentation.editor.panel.projected_widget_builder")


class ProjectedWidgetPanelProtocol(Protocol):
    """Describe panel widget APIs required by projected-widget building."""

    cube_widgets: dict[str, object]
    cube_sections: dict[str, object]

    def _build_cube_widget(self, cube_alias: str, cube_state: object) -> object:
        """Build one cube widget synchronously."""


class ProjectedWidgetBuildRegistryProtocol(Protocol):
    """Describe build-registry operations used by projected-widget building."""

    def reuse_decision(
        self,
        alias: str,
        widget: object,
        definition_identity: CubeDefinitionIdentity | None,
    ) -> CubeSectionBuildReuseDecision:
        """Return whether an existing widget can be reused."""

    def start(
        self,
        *,
        alias: str,
        widget: object,
        session: object,
        snapshot_identity: object | None,
        definition_identity: CubeDefinitionIdentity | None,
    ) -> object:
        """Register one active projected build."""

    def adopt_complete(
        self,
        *,
        alias: str,
        widget: object,
        snapshot_identity: object | None,
        definition_identity: CubeDefinitionIdentity | None,
    ) -> None:
        """Adopt an already complete projected widget."""


class ProjectedWidgetCompletionRegistryProtocol(Protocol):
    """Describe completion transfers used by projected-widget building."""

    def claim_pending_insert_for_projection(
        self,
        *,
        workflow_id: str,
        cube_alias: str,
        token: object | None,
        reason: str,
        projection_session: ActiveProjectionSession,
    ) -> PendingInsertCompletion | None:
        """Transfer an active insert completion to a full projection."""


class ProjectedWidgetLifecycleProtocol(Protocol):
    """Describe projection lifecycle cleanup used by widget building."""

    def discard_cube_widget(self, cube_alias: str, *, reason: str) -> None:
        """Discard one current cube widget."""

    def clear_alias_scoped_panel_registries(self, cube_alias: str) -> None:
        """Clear panel registries owned by one cube alias."""


class ProjectedWidgetBuilder:
    """Own projected widget reuse, build, and cancellation cleanup decisions."""

    def __init__(
        self,
        *,
        panel: ProjectedWidgetPanelProtocol,
        build_registry: ProjectedWidgetBuildRegistryProtocol,
        projection_completions: ProjectedWidgetCompletionRegistryProtocol,
        projection_lifecycle: ProjectedWidgetLifecycleProtocol,
        runtime_issue_projection: RuntimeIssueProjectionPort,
    ) -> None:
        """Store explicit collaborators required for projected-widget decisions."""

        self._panel = panel
        self._build_registry = build_registry
        self._projection_completions = projection_completions
        self._projection_lifecycle = projection_lifecycle
        self._runtime_issue_projection = runtime_issue_projection

    def build_ordered_widgets(
        self,
        cube_entries: Sequence[tuple[str, object]],
        *,
        workflow_id: str,
        snapshot_identity: object | None,
        projection_session: ActiveProjectionSession,
    ) -> tuple[list[tuple[str, object]], list[ProjectedCubeBuild]]:
        """Return ordered visible widgets and hidden projected build sessions."""

        panel = self._panel
        ordered_widgets: list[tuple[str, object]] = []
        projected_builds: list[ProjectedCubeBuild] = []
        for route_key, cube_state in cube_entries:
            cube_widget = panel.cube_widgets.get(route_key)
            if (
                cube_widget is not None
                and self._runtime_issue_projection.should_replace_visible_widget_for_runtime_issue(
                    route_key,
                    cube_widget,
                )
            ):
                self._projection_lifecycle.discard_cube_widget(
                    route_key,
                    reason="runtime_issue_state",
                )
                cube_widget = None
            if cube_widget is not None:
                reuse_decision = self._build_registry.reuse_decision(
                    route_key,
                    cube_widget,
                    cube_definition_identity(route_key, cube_state),
                )
                if not reuse_decision.can_reuse:
                    if reuse_decision.active_token is not None:
                        self._projection_completions.claim_pending_insert_for_projection(
                            workflow_id=workflow_id,
                            cube_alias=route_key,
                            token=reuse_decision.active_token,
                            reason="stale_projection",
                            projection_session=projection_session,
                        )
                    self._projection_lifecycle.discard_cube_widget(
                        route_key,
                        reason="stale_projection",
                    )
                    cube_widget = None
            if cube_widget is None:
                error_widget = (
                    self._runtime_issue_projection.build_error_widget_if_required(
                        route_key,
                        cube_state,
                    )
                )
                if error_widget is not None:
                    cube_widget = error_widget
                    projected_build = None
                    self._build_registry.adopt_complete(
                        alias=route_key,
                        widget=cube_widget,
                        snapshot_identity=snapshot_identity,
                        definition_identity=cube_definition_identity(
                            route_key,
                            cube_state,
                        ),
                    )
                else:
                    cube_widget, projected_build = self.begin_or_build_cube_widget(
                        route_key,
                        cube_state,
                        workflow_id=workflow_id,
                        snapshot_identity=snapshot_identity,
                    )
                if projected_build is not None:
                    projected_builds.append(projected_build)
                    continue
                if cube_widget is None:
                    continue
                panel.cube_widgets[route_key] = cube_widget
                panel.cube_sections[route_key] = cube_widget
            ordered_widgets.append((route_key, cube_widget))
        return ordered_widgets, projected_builds

    def begin_or_build_cube_widget(
        self,
        route_key: str,
        cube_state: object,
        *,
        workflow_id: str,
        snapshot_identity: object | None,
    ) -> tuple[object | None, ProjectedCubeBuild | None]:
        """Create one visible widget or one hidden projected build session."""

        panel = self._panel
        begin_build = getattr(panel, "_begin_build_cube_widget", None)
        if callable(begin_build):
            section_started_at = panel_projection_observability_started_at()
            build_session = begin_build(route_key, cube_state)
            log_panel_projection_timing(
                "hidden_build.section_started",
                started_at=section_started_at,
                workflow_id=workflow_id,
                cube_alias=route_key,
                projection_mode="live",
            )
            final_widget = getattr(build_session, "widget")
            prepare_projected_widget_for_hidden_build(final_widget)
            token = self._build_registry.start(
                alias=route_key,
                widget=final_widget,
                session=build_session,
                snapshot_identity=snapshot_identity,
                definition_identity=cube_definition_identity(route_key, cube_state),
            )
            log_info(
                _LOGGER,
                "Started staged editor cube section build",
                workflow_id=workflow_id,
                cube_alias=route_key,
                build_state="building",
            )
            return None, ProjectedCubeBuild(
                cube_alias=route_key,
                final_widget=final_widget,
                build_session=build_session,
                started_at=perf_counter(),
                token=token,
            )

        widget = panel._build_cube_widget(route_key, cube_state)
        self._build_registry.adopt_complete(
            alias=route_key,
            widget=widget,
            snapshot_identity=snapshot_identity,
            definition_identity=cube_definition_identity(route_key, cube_state),
        )
        return widget, None

    def discard_cancelled_projected_build(
        self,
        projected_build: ProjectedCubeBuild,
        *,
        workflow_id: str,
        reason: str,
    ) -> None:
        """Detach an unrevealed projected widget abandoned by projection cancellation."""

        panel = self._panel
        cube_alias = projected_build.cube_alias
        final_widget = projected_build.final_widget
        if (
            panel.cube_widgets.get(cube_alias) is final_widget
            or panel.cube_sections.get(cube_alias) is final_widget
        ):
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="cancelled_projected_cube_preserved",
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                reason=reason,
            )
            return

        self._projection_lifecycle.clear_alias_scoped_panel_registries(cube_alias)
        set_parent = getattr(final_widget, "setParent", None)
        if callable(set_parent):
            set_parent(None)
        delete_later = getattr(final_widget, "deleteLater", None)
        if callable(delete_later):
            delete_later()
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="cancelled_projected_cube_discarded",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            reason=reason,
        )
