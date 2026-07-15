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

"""Coordinate pending Cube Library update prompts without owning UI widgets."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from threading import Lock
from typing import Protocol

from substitute.application.execution import (
    CancellationToken,
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.cube_library.update_detection import (
    CubeLibraryUpdateDetectionService,
    LoadedCubeUpdateAction,
    LoadedCubeUpdateCandidate,
    LoadedCubeUpdateSelection,
)
from substitute.domain.cube_library import CubeCatalog, CubeUpdatePolicy
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_warning,
)

_LOGGER = get_logger("application.cube_library.update_coordinator")


class CubeLibraryCatalogClient(Protocol):
    """Describe catalog refresh behavior needed by the update coordinator."""

    def get_catalog(self) -> CubeCatalog | None:
        """Return the current Cube Library catalog, or ``None`` when unavailable."""


class CubeLibraryChangedUpdateProtocol(Protocol):
    """Describe change notification fields consumed by the coordinator."""

    catalog_revision: str
    previous_catalog_revision: str
    reason: str


WorkflowProvider = Callable[[], Mapping[str, object]]
WorkflowNameProvider = Callable[[], Mapping[str, str]]
PendingChangedCallback = Callable[[tuple[LoadedCubeUpdateCandidate, ...]], None]
AutomaticSelectionsCallback = Callable[[tuple[LoadedCubeUpdateSelection, ...]], None]


class CubeLibraryUpdateCoordinator:
    """Refresh catalogs, detect stale loaded cubes, and batch prompt candidates."""

    def __init__(
        self,
        *,
        catalog_client: CubeLibraryCatalogClient,
        workflow_provider: WorkflowProvider,
        workflow_name_provider: WorkflowNameProvider,
        detection_service: CubeLibraryUpdateDetectionService | None = None,
        pending_changed: PendingChangedCallback | None = None,
        automatic_selections_requested: AutomaticSelectionsCallback | None = None,
        refresh_submitter: TaskSubmitter | None = None,
    ) -> None:
        """Store update detection collaborators and initialize pending state."""

        self._catalog_client = catalog_client
        self._workflow_provider = workflow_provider
        self._workflow_name_provider = workflow_name_provider
        self._detection_service = (
            detection_service or CubeLibraryUpdateDetectionService()
        )
        self._pending_changed = pending_changed
        self._automatic_selections_requested = automatic_selections_requested
        self._refresh_submitter = refresh_submitter
        self._refresh_scope = (
            TaskScope(
                submitter=refresh_submitter,
                scope_id=f"cube_library_update_refresh_{id(self):x}",
            )
            if refresh_submitter is not None
            else None
        )
        self._pending: dict[tuple[str, str, str, str], LoadedCubeUpdateCandidate] = {}
        self._refresh_running = False
        self._refresh_again = False
        self._shutdown_requested = False
        self._refresh_request_id = 0
        self._lock = Lock()

    def on_library_changed(self, update: CubeLibraryChangedUpdateProtocol) -> None:
        """Schedule catalog refresh after a backend library-change event."""

        log_info(
            _LOGGER,
            "Cube Library change notification received",
            catalog_revision=update.catalog_revision,
            previous_catalog_revision=update.previous_catalog_revision,
            reason=update.reason,
        )
        self.refresh_async()

    def refresh_async(self) -> None:
        """Start one background refresh or collapse into a follow-up refresh."""

        with self._lock:
            if self._shutdown_requested:
                return
            if self._refresh_running:
                self._refresh_again = True
                return
            self._refresh_running = True
            self._refresh_request_id += 1
            request_id = self._refresh_request_id
        if self._refresh_submitter is None:
            self._refresh_task(None)
            return
        refresh_scope = self._refresh_scope
        if refresh_scope is None:
            self._clear_refresh_running()
            return
        request: TaskRequest[None] = TaskRequest(
            identity=TaskIdentity(
                request_id=request_id,
                domain="cube_library_update_refresh",
            ),
            context=ExecutionContext(
                operation="cube_library_update_refresh",
                reason="cube_library_changed",
                lane="cube_library_update",
                safe_fields=(("request_id", request_id),),
            ),
            work=lambda token: self._refresh_task(token),
        )
        try:
            handle = refresh_scope.submit(request)
        except Exception as error:
            self._clear_refresh_running()
            log_exception(
                _LOGGER,
                "Cube Library update refresh submission failed",
                error=error,
            )
            return
        handle.add_done_callback(
            self._on_refresh_task_finished,
            reason="cube_library_update_refresh_completed",
        )

    def refresh_now(self) -> tuple[LoadedCubeUpdateCandidate, ...]:
        """Refresh catalog synchronously and return the current pending candidates."""

        catalog = self._catalog_client.get_catalog()
        if catalog is None:
            log_warning(_LOGGER, "Cube Library update refresh skipped missing catalog")
            return self.collect_pending_on_focus()
        candidates = self._detection_service.detect_updates(
            workflows=self._workflow_provider(),
            workflow_names=self._workflow_name_provider(),
            catalog=catalog,
        )
        automatic_selections, pending_candidates = _split_update_candidates(candidates)
        if automatic_selections and self._automatic_selections_requested is None:
            self._replace_pending(candidates)
        else:
            self._request_automatic_updates(automatic_selections)
            self._replace_pending(pending_candidates)
        return self.collect_pending_on_focus()

    def shutdown(self) -> None:
        """Stop accepting refresh work and cancel pending refresh tasks."""

        with self._lock:
            self._shutdown_requested = True
            self._refresh_again = False
            self._refresh_running = False
        if self._refresh_scope is not None:
            self._refresh_scope.close(reason="cube_library_update_shutdown")

    def collect_pending_on_focus(self) -> tuple[LoadedCubeUpdateCandidate, ...]:
        """Return pending candidates for the next focus-triggered modal."""

        with self._lock:
            return tuple(self._pending.values())

    def queue_pending(
        self,
        candidates: Sequence[LoadedCubeUpdateCandidate],
    ) -> None:
        """Replace pending candidates discovered outside the refresh task."""

        self._replace_pending(candidates)

    def mark_presented(self, candidates: Sequence[LoadedCubeUpdateCandidate]) -> None:
        """Remove candidates from the current modal cycle after presentation."""

        with self._lock:
            for candidate in candidates:
                self._pending.pop(_candidate_key(candidate), None)

    def mark_resolved(self, candidates: Sequence[LoadedCubeUpdateCandidate]) -> None:
        """Remove candidates after their loaded cube state has been updated."""

        self.mark_presented(candidates)

    def _refresh_task(self, cancellation: CancellationToken | None) -> None:
        """Run refresh work until collapsed follow-up events are drained."""

        try:
            while True:
                if cancellation is not None and cancellation.is_cancelled:
                    self._clear_refresh_running()
                    return
                self.refresh_now()
                with self._lock:
                    if self._shutdown_requested:
                        self._refresh_running = False
                        self._refresh_again = False
                        return
                    if not self._refresh_again:
                        self._refresh_running = False
                        return
                    self._refresh_again = False
        except Exception:
            with self._lock:
                self._refresh_running = False
            self._refresh_again = False
            log_exception(_LOGGER, "Cube Library update refresh task failed")

    def _on_refresh_task_finished(self, outcome: TaskOutcome[None]) -> None:
        """Reset refresh state when execution cancels before task entry."""

        if outcome.status == "succeeded":
            return
        self._clear_refresh_running()
        if outcome.status == "cancelled":
            log_warning(
                _LOGGER,
                "Cube Library update refresh was cancelled",
                reason=outcome.cancellation_reason,
            )
            return
        log_warning(
            _LOGGER,
            "Cube Library update refresh task failed",
            error_type=type(outcome.error).__name__ if outcome.error else "unknown",
        )

    def _clear_refresh_running(self) -> None:
        """Clear refresh in-flight state after a failed submission or cancellation."""

        with self._lock:
            self._refresh_running = False
            self._refresh_again = False

    def _replace_pending(
        self,
        candidates: Sequence[LoadedCubeUpdateCandidate],
    ) -> None:
        """Replace pending state with currently stale candidates."""

        with self._lock:
            self._pending = {
                _candidate_key(candidate): candidate for candidate in candidates
            }
            pending = tuple(self._pending.values())
        log_info(_LOGGER, "Updated pending Cube Library candidates", count=len(pending))
        if self._pending_changed is not None:
            self._pending_changed(pending)

    def _request_automatic_updates(
        self,
        selections: tuple[LoadedCubeUpdateSelection, ...],
    ) -> None:
        """Request automatic follow-latest updates through the shell owner."""

        if not selections:
            return
        log_info(
            _LOGGER,
            "Requesting automatic follow-latest Cube Library updates",
            selection_count=len(selections),
            selection_keys=[
                f"{selection.candidate.workflow_id}:"
                f"{selection.candidate.cube_alias}:"
                f"{selection.candidate.cube_id}"
                for selection in selections
            ],
        )
        if self._automatic_selections_requested is None:
            return
        self._automatic_selections_requested(selections)


def _candidate_key(
    candidate: LoadedCubeUpdateCandidate,
) -> tuple[str, str, str, str]:
    """Return the deduplication identity for one update candidate."""

    return (
        candidate.workflow_id,
        candidate.cube_alias,
        candidate.cube_id,
        candidate.latest_version,
    )


def _split_update_candidates(
    candidates: Sequence[LoadedCubeUpdateCandidate],
) -> tuple[
    tuple[LoadedCubeUpdateSelection, ...], tuple[LoadedCubeUpdateCandidate, ...]
]:
    """Split stale cubes into automatic follow-latest and user-facing candidates."""

    automatic: list[LoadedCubeUpdateSelection] = []
    pending: list[LoadedCubeUpdateCandidate] = []
    for candidate in candidates:
        if candidate.update_policy == CubeUpdatePolicy.FOLLOW_LATEST:
            automatic.append(
                LoadedCubeUpdateSelection(
                    candidate=candidate,
                    action=LoadedCubeUpdateAction.FOLLOW_LATEST,
                    target_version=candidate.latest_version,
                )
            )
            continue
        pending.append(candidate)
    return tuple(automatic), tuple(pending)


__all__ = [
    "CubeLibraryCatalogClient",
    "CubeLibraryUpdateCoordinator",
    "LoadedCubeUpdateCandidate",
]
