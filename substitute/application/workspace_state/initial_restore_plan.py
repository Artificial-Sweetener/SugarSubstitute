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

"""Build startup session restore plans without depending on Qt."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.ports import SessionSnapshotRepository
from substitute.application.workspace_state.snapshot_normalization_service import (
    SnapshotNormalizationService,
)
from substitute.application.workspace_state.restore_projection_cache import (
    RestoreProjectionArtifact,
    RestoreProjectionCacheRepository,
    RestoreProjectionCacheState,
    RestoreProjectionValidationResult,
    RestoreProjectionValidationService,
)
from substitute.domain.workspace_snapshot import (
    WindowGeometrySnapshot,
    WorkspaceSnapshot,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_warning,
)
from substitute.shared.startup_trace import trace_mark

_LOGGER = get_logger("application.workspace_state.initial_restore_plan")


@dataclass(frozen=True, slots=True)
class InitialShellPlacement:
    """Describe outer shell placement to apply before first show."""

    geometry: WindowGeometrySnapshot | None
    window_display_state: str
    maximized: bool


@dataclass(frozen=True, slots=True)
class InitialWorkspaceRestorePlan:
    """Describe normalized startup session restore data."""

    workspace: WorkspaceSnapshot | None
    shell_placement: InitialShellPlacement | None
    warnings: tuple[str, ...]
    provisional_restore_projection: RestoreProjectionArtifact | None = None
    restore_projection_validation: RestoreProjectionValidationResult | None = None


class InitialWorkspaceRestorePlanService:
    """Load and normalize startup session restore data once."""

    def __init__(
        self,
        *,
        repository: SessionSnapshotRepository,
        normalizer: SnapshotNormalizationService,
        restore_projection_repository: RestoreProjectionCacheRepository | None = None,
        restore_projection_target_key: str = "",
    ) -> None:
        """Store restore planning dependencies."""

        self._repository = repository
        self._normalizer = normalizer
        self._restore_projection_repository = restore_projection_repository
        self._restore_projection_target_key = restore_projection_target_key

    def build(self) -> InitialWorkspaceRestorePlan:
        """Return the normalized startup restore plan when a session exists."""

        try:
            session_snapshot = self._repository.load()
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            log_exception(
                _LOGGER,
                "Failed to load initial session restore plan",
                error=error,
            )
            return _empty_plan()
        if session_snapshot is None:
            log_info(_LOGGER, "Initial session restore plan skipped no snapshot")
            return _empty_plan()

        normalization = self._normalizer.normalize(session_snapshot.workspace)
        shell_layout = normalization.snapshot.shell_layout
        shell_placement = (
            _shell_placement_from_layout(shell_layout)
            if shell_layout is not None
            else None
        )
        log_info(
            _LOGGER,
            "Built initial session restore plan",
            captured_at=session_snapshot.captured_at.isoformat(),
            active_route=normalization.snapshot.active_route,
            active_workflow_id=normalization.snapshot.active_workflow_id,
            workflow_count=len(normalization.snapshot.workflows),
            shell_layout_present=shell_layout is not None,
            shell_placement_present=shell_placement is not None,
            warning_count=len(normalization.warnings),
        )
        provisional_projection, projection_validation = (
            self._load_provisional_restore_projection(normalization.snapshot)
        )
        return InitialWorkspaceRestorePlan(
            workspace=normalization.snapshot,
            shell_placement=shell_placement,
            warnings=normalization.warnings,
            provisional_restore_projection=provisional_projection,
            restore_projection_validation=projection_validation,
        )

    def _load_provisional_restore_projection(
        self,
        workspace: WorkspaceSnapshot,
    ) -> tuple[
        RestoreProjectionArtifact | None,
        RestoreProjectionValidationResult | None,
    ]:
        """Load and prevalidate a restore projection cache without backend access."""

        repository = self._restore_projection_repository
        if repository is None:
            return None, None
        trace_mark("restore_projection_cache.load.start")
        artifact = repository.load()
        if artifact is None:
            trace_mark("restore_projection_cache.load.missing")
            return None, RestoreProjectionValidationResult(
                state=RestoreProjectionCacheState.MISSING,
                reasons=("No restore projection cache artifact is available.",),
            )
        result = RestoreProjectionValidationService().validate_before_backend(
            artifact,
            target_key=self._restore_projection_target_key,
            workspace=workspace,
        )
        if result.can_build_provisionally:
            trace_mark(
                "restore_projection_cache.prebackend.valid",
                state=result.state.value,
                reason_count=len(result.reasons),
            )
            return artifact, result
        trace_mark(
            "restore_projection_cache.prebackend.invalid",
            state=result.state.value,
            reason_count=len(result.reasons),
        )
        _clear_invalid_restore_projection_cache(repository, result)
        return None, result


def _clear_invalid_restore_projection_cache(
    repository: RestoreProjectionCacheRepository,
    result: RestoreProjectionValidationResult,
) -> None:
    """Discard projection cache artifacts that cannot safely rebuild the editor."""

    try:
        repository.clear()
    except (OSError, RuntimeError) as error:
        log_exception(
            _LOGGER,
            "Failed to clear invalid restore projection cache",
            error=error,
            state=result.state.value,
            reasons=result.reasons,
        )
        return
    log_warning(
        _LOGGER,
        "Cleared invalid restore projection cache",
        state=result.state.value,
        reasons=result.reasons,
    )


def _empty_plan() -> InitialWorkspaceRestorePlan:
    """Return a plan that preserves default startup behavior."""

    return InitialWorkspaceRestorePlan(
        workspace=None,
        shell_placement=None,
        warnings=(),
    )


def _shell_placement_from_layout(
    shell_layout: object,
) -> InitialShellPlacement | None:
    """Return pre-show placement when a shell layout carries visible intent."""

    geometry = getattr(shell_layout, "geometry", None)
    display_state = str(getattr(shell_layout, "window_display_state", "normal"))
    maximized = bool(getattr(shell_layout, "maximized", False))
    if geometry is None and display_state == "normal" and not maximized:
        return None
    if not isinstance(geometry, WindowGeometrySnapshot):
        geometry = None
    return InitialShellPlacement(
        geometry=geometry,
        window_display_state=display_state,
        maximized=maximized,
    )


__all__ = [
    "InitialShellPlacement",
    "InitialWorkspaceRestorePlan",
    "InitialWorkspaceRestorePlanService",
]
