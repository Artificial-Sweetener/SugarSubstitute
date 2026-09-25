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

"""Coordinate live node definitions and their editor runtime presentation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from PySide6.QtWidgets import QWidget

from substitute.application.node_behavior import (
    LiveNodeDefinitionError,
    required_node_definition_classes_for_editor_projection,
)
from substitute.application.workflows import CubeRuntimeIssue, CubeRuntimeIssueSource
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_info,
    log_warning,
)

from .choice_field_surface_reconciler import (
    ChoiceFieldSurfaceReconciliationResult,
)
from .runtime_access import (
    cube_registry_for_panel,
    projection_coordinator_for_panel,
    runtime_issue_presenter_for_panel,
)

_LOGGER = get_logger("presentation.editor.panel.node_definition_runtime")


class EditorPanelNodeDefinitionRuntime:
    """Provide the panel host API for live definition and runtime issue changes."""

    def hydrate_node_definitions_for_projection(self, *, reason: str) -> None:
        """Hydrate live node definitions before correctness-sensitive projection."""

        panel: Any = self
        if not panel._stack_order or not panel._cube_states:
            return
        result = panel._node_definition_hydration_service.hydrate_for_projection(
            cube_states=panel._cube_states,
            stack_order=panel._stack_order,
        )
        log_info(
            _LOGGER,
            "Editor projection node definition hydration completed",
            reason=reason,
            requested_count=len(result.requested) if result is not None else 0,
            unavailable_count=len(result.unavailable) if result is not None else 0,
        )

    def begin_live_node_definition_report_projection(self) -> None:
        """Start a projection-scoped live metadata report dedupe window."""

        runtime_issue_presenter_for_panel(
            self
        ).begin_live_node_definition_report_projection()

    def register_projection_live_node_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
        source: CubeRuntimeIssueSource,
    ) -> bool:
        """Register a cube-attributed projection hydration failure."""

        return runtime_issue_presenter_for_panel(
            self
        ).register_projection_live_node_definition_error(
            error,
            reason=reason,
            source=source,
        )

    def present_recoverable_live_node_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
    ) -> None:
        """Show a deduplicated non-fatal live metadata report for a cube issue."""

        runtime_issue_presenter_for_panel(
            self
        ).present_recoverable_live_node_definition_error(error, reason=reason)

    def _present_live_node_definition_error_once(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
    ) -> None:
        """Show one live metadata report unless the same report was already shown."""

        runtime_issue_presenter_for_panel(self).present_live_node_definition_error_once(
            error, reason=reason
        )

    def clear_projection_runtime_issues(self) -> None:
        """Clear projection-owned runtime issues after successful hydration."""

        runtime_issue_presenter_for_panel(self).clear_projection_runtime_issues()

    def set_cube_runtime_issues(
        self,
        cube_alias: str,
        issues: Sequence[CubeRuntimeIssue],
    ) -> None:
        """Apply runtime issue presentation to one rendered cube section."""

        runtime_issue_presenter_for_panel(self).set_cube_runtime_issues(
            cube_alias,
            issues,
        )

    def clear_cube_runtime_issues(self, cube_alias: str) -> None:
        """Clear runtime issues for one cube and refresh its rendered section."""

        runtime_issue_presenter_for_panel(self).clear_cube_runtime_issues(cube_alias)

    def cube_runtime_issues(
        self,
        cube_alias: str,
    ) -> tuple[CubeRuntimeIssue, ...]:
        """Return locally projected runtime issues for one cube."""

        return runtime_issue_presenter_for_panel(self).cube_runtime_issues(cube_alias)

    def cube_runtime_error_aliases(self) -> tuple[str, ...]:
        """Return aliases with error-severity runtime issues."""

        return runtime_issue_presenter_for_panel(self).cube_runtime_error_aliases()

    def _sync_cube_runtime_issues_from_state(self) -> None:
        """Refresh local issue projection from workflow-owned issue state."""

        runtime_issue_presenter_for_panel(self).sync_cube_runtime_issues_from_state()

    def _apply_cube_runtime_issues_to_widget(self, cube_alias: str) -> None:
        """Apply issue wash state to one cube section widget when it exists."""

        runtime_issue_presenter_for_panel(self).apply_cube_runtime_issues_to_widget(
            cube_alias
        )

    def _apply_cube_runtime_issues_to_stack(
        self,
        cube_alias: str,
        severity: str | None,
    ) -> None:
        """Apply issue severity to the matching cube-stack tab when available."""

        runtime_issue_presenter_for_panel(self).apply_cube_runtime_issues_to_stack(
            cube_alias,
            severity,
        )

    def _build_error_cube_widget(self, route_key: str, cube_state: object) -> QWidget:
        """Build a cube section that exposes recoverable runtime issues only."""

        return runtime_issue_presenter_for_panel(self).build_error_cube_widget(
            route_key,
            cube_state,
        )

    def _present_live_node_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
    ) -> None:
        """Show the blocking live-metadata report through the injected presenter."""

        runtime_issue_presenter_for_panel(self).present_live_node_definition_error(
            error,
            reason=reason,
        )

    def refresh_projection_after_node_definition_update(
        self,
        *,
        refreshed_node_classes: Sequence[str],
    ) -> bool:
        """Rebuild rendered widgets when a late node definition affects them."""

        panel: Any = self
        if not panel._stack_order or not panel._cube_states:
            return False
        normalized_refreshed = {
            node_class.strip()
            for node_class in refreshed_node_classes
            if isinstance(node_class, str) and node_class.strip()
        }
        if not normalized_refreshed:
            return False
        try:
            required_node_classes = set(
                required_node_definition_classes_for_editor_projection(
                    self._ordered_projection_buffers()
                )
            )
            affected_node_classes = tuple(
                sorted(required_node_classes.intersection(normalized_refreshed))
            )
        except (RuntimeError, TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Rebuilding editor projection after node definition refresh detection failed",
                refreshed_node_classes=tuple(sorted(normalized_refreshed)),
                error_type=type(error).__name__,
            )
            affected_node_classes = tuple(sorted(normalized_refreshed))
        if not affected_node_classes:
            log_debug(
                _LOGGER,
                "Skipped editor projection rebuild for unrelated node definition refresh",
                refreshed_node_classes=tuple(sorted(normalized_refreshed)),
            )
            return False

        cube_entries = self._current_cube_entries_for_projection()
        if not cube_entries:
            return False
        affected_cube_aliases = self._cube_aliases_for_node_classes(
            affected_node_classes
        )
        coordinator = projection_coordinator_for_panel(self)
        mark_stale = getattr(coordinator, "mark_cube_sections_stale", None)
        active_build_affected = False
        if callable(mark_stale):
            active_build_affected = bool(
                mark_stale(
                    affected_cube_aliases,
                    reason="node_definition_changed",
                )
            )
        panel.invalidate_projection(reason="node_definition_changed")
        panel.load_all_cubes(
            cube_entries,
            cube_states=panel._cube_states,
            stack_order=panel._stack_order,
            projection_signature=None,
        )
        log_info(
            _LOGGER,
            "Rebuilt editor projection after node definition refresh",
            affected_node_classes=affected_node_classes,
            affected_cube_aliases=tuple(affected_cube_aliases),
            refreshed_node_classes=tuple(sorted(normalized_refreshed)),
            cube_section_count=len(cube_entries),
            active_build_affected=active_build_affected,
        )
        return True

    def reconcile_choice_fields_after_node_definition_update(
        self,
        *,
        refreshed_node_classes: Sequence[str],
    ) -> ChoiceFieldSurfaceReconciliationResult:
        """Apply refreshed finite choices to controls without projection."""

        panel: Any = self
        result = panel._choice_field_surface_reconciler.reconcile(
            refreshed_node_classes
        )
        if result.reconciled_field_count:
            panel._preset_context_refresh.refresh(reason="model_options_changed")
        return cast(ChoiceFieldSurfaceReconciliationResult, result)

    def _cube_aliases_for_node_classes(
        self,
        node_classes: Sequence[str],
    ) -> tuple[str, ...]:
        """Return cube aliases whose buffers contain one of the node classes."""

        panel: Any = self
        if not panel._cube_states or not panel._stack_order:
            return ()
        target_classes = set(node_classes)
        aliases: list[str] = []
        for alias in panel._stack_order:
            cube_state = panel._cube_states.get(alias)
            buffer = getattr(cube_state, "buffer", None)
            nodes = buffer.get("nodes", {}) if isinstance(buffer, Mapping) else {}
            if not isinstance(nodes, Mapping):
                continue
            for node_data in nodes.values():
                if not isinstance(node_data, Mapping):
                    continue
                if node_data.get("class_type") in target_classes:
                    aliases.append(alias)
                    break
        return tuple(aliases)

    def _ordered_projection_buffers(self) -> dict[str, Mapping[str, object]]:
        """Return active cube buffers in stack order for dependency checks."""

        return cube_registry_for_panel(self).ordered_projection_buffers()

    def _current_cube_entries_for_projection(self) -> list[tuple[str, object]]:
        """Return active cube entries in stack order for projection rebuilds."""

        return cube_registry_for_panel(self).current_cube_entries_for_projection()


__all__ = ["EditorPanelNodeDefinitionRuntime"]
