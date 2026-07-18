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

"""Adapt MainWindow override controls to their reconciliation port."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from time import perf_counter
from typing import cast

from PySide6.QtCore import QTimer


from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurface,
)
from substitute.presentation.shell.workflow_surface_results import (
    ReconciliationToken,
    SurfaceRefreshResult,
    SurfaceRefreshStatus,
    surface_result,
)
from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_debug,
    log_exception,
)

_LOGGER = get_logger("presentation.shell.main_window_override_surface_adapter")
_RECONCILER_LOGGER = get_logger("presentation.shell.workflow_surface_reconciler")


class MainWindowOverrideSurfaceAdapter:
    """Expose override toolbar operations through a narrow port."""

    def __init__(self, shell: object) -> None:
        """Store the shell object behind an override-surface API."""

        self._shell = shell
        self._materialized_defaults: dict[str, bool] = {}
        self._latest_token: ReconciliationToken | None = None

    def last_materialized_defaults(self, workflow_id: str) -> bool:
        """Return whether defaults were materialized for the latest workflow pass."""

        return self._materialized_defaults.get(workflow_id, False)

    def project_workflow_overrides(self, workflow_id: str) -> SurfaceRefreshResult:
        """Project one workflow's override state into shared toolbar widgets."""

        def action(manager: object) -> None:
            """Synchronize state and rebuild visible override presentation."""

            self._detach_non_target_managers(workflow_id)
            self._call_optional(manager, "sync_state_from_workflow")
            self._call_optional(manager, "rebuild_override_menu")
            self._call_optional(manager, "rebuild_active_override_controls")

        return self._with_manager(
            workflow_id,
            operation="project_workflow_overrides",
            action=action,
        )

    def sync_override_state(self, workflow_id: str) -> SurfaceRefreshResult:
        """Synchronize override state for the active workflow."""

        return self._with_manager(
            workflow_id,
            operation="sync_override_state",
            action=lambda manager: self._call_optional(
                manager,
                "sync_state_from_workflow",
            ),
        )

    def apply_overrides_before_projection(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Apply overrides before editor projection."""

        def action(manager: object) -> None:
            """Run preferred pre-projection override API with fallback."""

            pre_projection_apply = getattr(
                manager,
                "apply_global_overrides_without_snapshot_fallback",
                None,
            )
            if callable(pre_projection_apply):
                pre_projection_apply()
                return
            apply_global_overrides = getattr(manager, "apply_global_overrides", None)
            if callable(apply_global_overrides):
                apply_global_overrides(use_cached_behavior_snapshot=False)

        return self._with_manager(
            workflow_id,
            operation="apply_overrides_before_projection",
            action=action,
        )

    def materialize_default_overrides(self, workflow_id: str) -> SurfaceRefreshResult:
        """Materialize default pinned override controls after editor projection."""

        def action(manager: object) -> None:
            """Record whether default override materialization changed controls."""

            materialize_default_overrides = getattr(
                manager,
                "materialize_default_overrides",
                None,
            )
            self._materialized_defaults[workflow_id] = (
                bool(materialize_default_overrides())
                if callable(materialize_default_overrides)
                else False
            )

        return self._with_manager(
            workflow_id,
            operation="materialize_default_overrides",
            action=action,
        )

    def apply_overrides_after_projection(
        self,
        workflow_id: str,
        *,
        materialized_defaults: bool,
    ) -> SurfaceRefreshResult:
        """Apply override values after editor projection exists."""

        def action(manager: object) -> None:
            """Run post-projection override application."""

            apply_global_overrides = getattr(manager, "apply_global_overrides", None)
            if callable(apply_global_overrides):
                apply_global_overrides(
                    use_cached_behavior_snapshot=not materialized_defaults
                )

        return self._with_manager(
            workflow_id,
            operation="apply_overrides_after_projection",
            action=action,
        )

    def schedule_override_presentation_rebuild(
        self,
        workflow_id: str,
        token: ReconciliationToken,
        on_complete: Callable[[SurfaceRefreshResult], None] | None = None,
    ) -> SurfaceRefreshResult:
        """Schedule override presentation rebuild for the active workflow."""

        started_at = perf_counter()
        manager = self._manager(workflow_id)
        if manager is None:
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.OVERRIDES,
                status=SurfaceRefreshStatus.SKIPPED_MISSING,
                operation="schedule_override_presentation_rebuild",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error="override manager missing",
            )
        self._latest_token = token
        log_debug(
            _RECONCILER_LOGGER,
            "Scheduled deferred active override presentation rebuild",
            workflow_id=workflow_id,
        )

        def rebuild_if_current() -> None:
            """Rebuild override controls when the token is still current."""

            if self._latest_token != token or workflow_id != self._active_workflow_id():
                result = surface_result(
                    workflow_id=workflow_id,
                    surface=WorkflowSurface.OVERRIDES,
                    status=SurfaceRefreshStatus.SKIPPED_STALE,
                    operation="schedule_override_presentation_rebuild",
                    elapsed_ms=elapsed_ms_since(started_at),
                    cleanable=False,
                )
                if on_complete is not None:
                    on_complete(result)
                return
            result = self._rebuild_override_presentation(
                workflow_id,
                manager,
                started_at=started_at,
            )
            if on_complete is not None:
                on_complete(result)

        QTimer.singleShot(0, rebuild_if_current)
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.OVERRIDES,
            status=SurfaceRefreshStatus.SUCCESS,
            operation="schedule_override_presentation_rebuild",
            elapsed_ms=elapsed_ms_since(started_at),
            cleanable=False,
        )

    def _rebuild_override_presentation(
        self,
        workflow_id: str,
        manager: object,
        *,
        started_at: float,
    ) -> SurfaceRefreshResult:
        """Rebuild override menu and active controls with result reporting."""

        try:
            self._call_optional(manager, "rebuild_override_menu")
            self._call_optional(manager, "rebuild_active_override_controls")
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to rebuild override presentation",
                workflow_id=workflow_id,
                surface=WorkflowSurface.OVERRIDES.value,
                operation="schedule_override_presentation_rebuild",
                error=error,
            )
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.OVERRIDES,
                status=SurfaceRefreshStatus.FAILED,
                operation="schedule_override_presentation_rebuild",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error=repr(error),
            )
        log_debug(
            _RECONCILER_LOGGER,
            "Rebuilt active override presentation",
            workflow_id=workflow_id,
        )
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.OVERRIDES,
            status=SurfaceRefreshStatus.SUCCESS,
            operation="schedule_override_presentation_rebuild",
            elapsed_ms=elapsed_ms_since(started_at),
        )

    def _with_manager(
        self,
        workflow_id: str,
        *,
        operation: str,
        action: Callable[[object], None],
    ) -> SurfaceRefreshResult:
        """Run an override operation with common result and error handling."""

        started_at = perf_counter()
        if workflow_id != self._active_workflow_id():
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.OVERRIDES,
                status=SurfaceRefreshStatus.SKIPPED_STALE,
                operation=operation,
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
            )
        manager = self._manager(workflow_id)
        if manager is None:
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.OVERRIDES,
                status=SurfaceRefreshStatus.SKIPPED_MISSING,
                operation=operation,
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error="override manager missing",
            )
        try:
            action(manager)
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to refresh override surface",
                workflow_id=workflow_id,
                surface=WorkflowSurface.OVERRIDES.value,
                operation=operation,
                error=error,
            )
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.OVERRIDES,
                status=SurfaceRefreshStatus.FAILED,
                operation=operation,
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error=repr(error),
            )
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.OVERRIDES,
            status=SurfaceRefreshStatus.SUCCESS,
            operation=operation,
            elapsed_ms=elapsed_ms_since(started_at),
        )

    @staticmethod
    def _call_optional(target: object, name: str) -> None:
        """Call an optional zero-argument method."""

        method = getattr(target, name, None)
        if callable(method):
            method()

    def _manager(self, workflow_id: str) -> object | None:
        """Return the override manager for one workflow."""

        override_managers = cast(
            Mapping[str, object | None],
            getattr(self._shell, "override_managers", {}),
        )
        manager = override_managers.get(workflow_id)
        if manager is not None:
            return manager
        active_manager = getattr(self._shell, "active_override_manager", None)
        return active_manager

    def _detach_non_target_managers(self, workflow_id: str) -> None:
        """Detach cached toolbar widgets owned by inactive workflow managers."""

        override_managers = cast(
            Mapping[str, object | None],
            getattr(self._shell, "override_managers", {}),
        )
        for manager_workflow_id, manager in override_managers.items():
            if manager_workflow_id == workflow_id or manager is None:
                continue
            self._call_optional(manager, "detach_override_widgets")

    def _active_workflow_id(self) -> str:
        """Return the active workflow id known to the shell."""

        session = getattr(self._shell, "workflow_session_service", None)
        return str(getattr(session, "active_workflow_id", ""))
