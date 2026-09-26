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

"""Integrate projection metadata failures with cube runtime issue presentation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

from substitute.application.node_behavior import LiveNodeDefinitionError
from substitute.application.workflows import CubeRuntimeIssueSource
from substitute.shared.logging.logger import get_logger, log_warning

from .projection_preparation import without_cube_aliases, without_stack_aliases

_LOGGER = get_logger("presentation.editor.panel.projection_lifecycle")
_T = TypeVar("_T")


class RuntimeIssueIntegrationPanelPort(Protocol):
    """Describe panel hooks used for projection-time runtime issue handoff."""

    _cube_states: dict[str, object] | None
    _stack_order: list[str] | None

    def hydrate_node_definitions_for_projection(self, *, reason: str) -> None:
        """Hydrate node definitions required by projection."""


class EditorProjectionRuntimeIssueIntegration:
    """Own projection-time runtime issue handoff to the issue presenter."""

    def __init__(self, panel: RuntimeIssueIntegrationPanelPort) -> None:
        """Store panel hooks used during runtime issue integration."""

        self._panel = panel

    def begin_live_node_definition_report_projection(self) -> None:
        """Start a projection-scoped live metadata report dedupe window."""

        begin_reports = getattr(
            self._panel,
            "begin_live_node_definition_report_projection",
            None,
        )
        if callable(begin_reports):
            begin_reports()

    def hydrate_node_definitions_for_projection(
        self,
        *,
        reason: str,
        workflow_id: str,
    ) -> None:
        """Hydrate definitions and update projection runtime issue state."""

        try:
            self._panel.hydrate_node_definitions_for_projection(reason=reason)
        except LiveNodeDefinitionError as error:
            if not self.register_recoverable_live_definition_error(
                error,
                reason=reason,
                workflow_id=workflow_id,
            ):
                raise
        else:
            clear_projection_issues = getattr(
                self._panel,
                "clear_projection_runtime_issues",
                None,
            )
            if callable(clear_projection_issues):
                clear_projection_issues()

    def register_recoverable_live_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
        workflow_id: str,
    ) -> bool:
        """Register a cube-attributed live metadata error or report fatal failure."""

        register = getattr(
            self._panel,
            "register_projection_live_node_definition_error",
            None,
        )
        handled = (
            bool(
                register(
                    error,
                    reason=reason,
                    source=CubeRuntimeIssueSource.PROJECTION,
                )
            )
            if callable(register)
            else False
        )
        if handled:
            present_recoverable = getattr(
                self._panel,
                "present_recoverable_live_node_definition_error",
                None,
            )
            if callable(present_recoverable):
                present_recoverable(error, reason=reason)
            else:
                self._present_live_node_definition_error(error, reason=reason)
            log_warning(
                _LOGGER,
                "Recovered editor projection from cube-attributed live metadata error",
                workflow_id=workflow_id,
                reason=reason,
                missing_node_classes=",".join(
                    item.class_type for item in error.missing_definitions
                ),
            )
            return True
        self._present_live_node_definition_error(error, reason=reason)
        return False

    def cube_runtime_error_aliases(self) -> frozenset[str]:
        """Return current runtime error aliases from the panel when available."""

        error_aliases = getattr(self._panel, "cube_runtime_error_aliases", None)
        return frozenset(error_aliases() if callable(error_aliases) else ())

    def is_errored_cube(self, cube_alias: str) -> bool:
        """Return whether a cube should render with the error section."""

        return cube_alias in self.cube_runtime_error_aliases()

    def run_projection_metadata_step(
        self,
        *,
        workflow_id: str,
        reason: str,
        action: Callable[[frozenset[str]], _T],
    ) -> _T:
        """Retry one metadata-dependent projection step after issue discovery."""

        errored_aliases = self.cube_runtime_error_aliases()
        while True:
            try:
                return action(errored_aliases)
            except LiveNodeDefinitionError as error:
                if not self.register_recoverable_live_definition_error(
                    error,
                    reason=reason,
                    workflow_id=workflow_id,
                ):
                    raise
                updated_aliases = self.cube_runtime_error_aliases()
                if updated_aliases == errored_aliases:
                    raise
                errored_aliases = updated_aliases

    def run_with_pruned_panel_state(
        self,
        errored_aliases: frozenset[str],
        action: Callable[[], _T],
    ) -> _T:
        """Run an operation while hiding errored cubes from live panel state."""

        full_cube_states = self._panel._cube_states
        full_stack_order = (
            list(self._panel._stack_order) if self._panel._stack_order else None
        )
        if errored_aliases and self._panel._cube_states is not None:
            self._panel._cube_states = dict(
                without_cube_aliases(self._panel._cube_states, errored_aliases) or {}
            )
            self._panel._stack_order = without_stack_aliases(
                self._panel._stack_order,
                errored_aliases,
            )
        try:
            return action()
        finally:
            self._panel._cube_states = full_cube_states
            self._panel._stack_order = full_stack_order

    def _present_live_node_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
    ) -> None:
        """Route a blocking live metadata report through the runtime presenter."""

        present = getattr(self._panel, "_present_live_node_definition_error", None)
        if callable(present):
            present(error, reason=reason)


__all__ = [
    "EditorProjectionRuntimeIssueIntegration",
    "RuntimeIssueIntegrationPanelPort",
]
