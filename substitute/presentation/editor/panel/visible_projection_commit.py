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

"""Publish completed panel projections into the visible editor layout."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import perf_counter

from PySide6.QtCore import QTimer

from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_debug,
    log_info,
    log_warning,
)

from .projection_observability import log_panel_projection_event
from .projection_session import ActiveProjectionSession
from .rendering.render_reconciler import ProjectedCubeBuildProtocol

_LOGGER = get_logger("presentation.editor.panel.visible_projection_commit")
_PENDING_VISIBLE_PROJECTION_RETRY_LIMIT = 5


def editor_panel_is_visible(panel: object) -> bool:
    """Return whether a panel can safely publish a visible projection."""

    is_visible = getattr(panel, "isVisible", None)
    if not callable(is_visible):
        return True
    try:
        return bool(is_visible())
    except RuntimeError:
        return False


@dataclass(frozen=True, slots=True)
class EditorVisibleProjectionCommitPorts:
    """Group typed collaborators used by visible projection commit publication."""

    active_workflow_id: Callable[[], str]
    panel_is_visible: Callable[[], bool]
    is_projection_session_current: Callable[[ActiveProjectionSession], bool]
    reveal_projected_cube_builds: Callable[
        [Sequence[ProjectedCubeBuildProtocol], str],
        None,
    ]
    mark_build_complete: Callable[[str, object], object]
    mark_build_failed: Callable[[str, object, object], object]


@dataclass(slots=True)
class PendingVisibleProjectionCommit:
    """Hold completed staged builds until the panel can safely reveal them."""

    workflow_id: str
    projection_session: ActiveProjectionSession
    projected_builds: tuple[ProjectedCubeBuildProtocol, ...]
    finish_refresh: Callable[[], None]
    cancel_refresh: Callable[[str], None]
    created_at: float


class EditorVisibleProjectionCommitPipeline:
    """Own deferred visible projection commits and reveal publication."""

    def __init__(self, ports: EditorVisibleProjectionCommitPorts) -> None:
        """Store collaborators used to publish visible projection commits."""

        self._ports = ports
        self._pending_visible_projection_commit: PendingVisibleProjectionCommit | None
        self._pending_visible_projection_commit = None
        self._pending_visible_projection_retry_scheduled = False
        self._pending_visible_projection_retry_attempts = 0

    def has_pending_visible_projection_commit(self) -> bool:
        """Return whether completed staged builds are waiting for visible reveal."""

        return self._pending_visible_projection_commit is not None

    def finalize_pending_visible_projection(self) -> bool:
        """Reveal a completed background projection when the panel is active."""

        pending = self._pending_visible_projection_commit
        if pending is None:
            return False
        if not self.can_commit_visible_projection(pending.workflow_id):
            log_debug(
                _LOGGER,
                "Deferred editor visible projection commit because panel is inactive",
                workflow_id=pending.workflow_id,
                active_workflow_id=self._ports.active_workflow_id(),
                panel_visible=self._ports.panel_is_visible(),
                pending_build_count=len(pending.projected_builds),
            )
            return False
        return self.commit_visible_projection(pending)

    def commit_or_defer(
        self,
        *,
        workflow_id: str,
        projection_session: ActiveProjectionSession,
        projected_builds: Sequence[ProjectedCubeBuildProtocol],
        finish_refresh: Callable[[], None],
        cancel_refresh: Callable[[str], None],
    ) -> bool:
        """Reveal a staged projection now or store it until the panel is visible."""

        pending = PendingVisibleProjectionCommit(
            workflow_id=workflow_id,
            projection_session=projection_session,
            projected_builds=tuple(projected_builds),
            finish_refresh=finish_refresh,
            cancel_refresh=cancel_refresh,
            created_at=perf_counter(),
        )
        if not self.can_commit_visible_projection(workflow_id):
            self.store_pending_visible_projection_commit(pending)
            return False
        return self.commit_visible_projection(pending)

    def store_pending_visible_projection_commit(
        self,
        pending: PendingVisibleProjectionCommit,
    ) -> None:
        """Remember a completed staged projection until activation can reveal it."""

        self.discard_pending_visible_projection_commit(
            reason="superseded_by_new_pending_visible_commit",
        )
        self._pending_visible_projection_commit = pending
        log_info(
            _LOGGER,
            "Deferred editor visible projection commit",
            workflow_id=pending.workflow_id,
            active_workflow_id=self._ports.active_workflow_id(),
            panel_visible=self._ports.panel_is_visible(),
            pending_build_count=len(pending.projected_builds),
            projection_aliases=tuple(
                projected_build.cube_alias
                for projected_build in pending.projected_builds
            ),
        )
        self.schedule_pending_visible_projection_retry(pending.workflow_id)

    def schedule_pending_visible_projection_retry(self, workflow_id: str) -> None:
        """Retry a transient active-panel reveal after Qt finishes route visibility."""

        if self._pending_visible_projection_retry_scheduled:
            return
        if workflow_id != self._ports.active_workflow_id():
            return
        if (
            self._pending_visible_projection_retry_attempts
            >= _PENDING_VISIBLE_PROJECTION_RETRY_LIMIT
        ):
            return
        self._pending_visible_projection_retry_attempts += 1
        self._pending_visible_projection_retry_scheduled = True
        log_panel_projection_event(
            "visible_commit.retry_scheduled",
            workflow_id=workflow_id,
            active_workflow_id=self._ports.active_workflow_id(),
            panel_visible=self._ports.panel_is_visible(),
            pending_build_count=(
                len(self._pending_visible_projection_commit.projected_builds)
                if self._pending_visible_projection_commit is not None
                else 0
            ),
            retry_attempts=self._pending_visible_projection_retry_attempts,
            retry_limit=_PENDING_VISIBLE_PROJECTION_RETRY_LIMIT,
        )
        QTimer.singleShot(0, self.retry_pending_visible_projection_commit)

    def retry_pending_visible_projection_commit(self) -> None:
        """Commit a deferred active-panel reveal once the stacked route is visible."""

        self._pending_visible_projection_retry_scheduled = False
        pending = self._pending_visible_projection_commit
        if pending is None:
            return
        if pending.workflow_id != self._ports.active_workflow_id():
            return
        if not self.can_commit_visible_projection(pending.workflow_id):
            log_debug(
                _LOGGER,
                "Deferred editor visible projection retry because panel remains hidden",
                workflow_id=pending.workflow_id,
                active_workflow_id=self._ports.active_workflow_id(),
                panel_visible=self._ports.panel_is_visible(),
                pending_build_count=len(pending.projected_builds),
                retry_attempts=self._pending_visible_projection_retry_attempts,
            )
            self.schedule_pending_visible_projection_retry(pending.workflow_id)
            return
        self.commit_visible_projection(pending)

    def commit_visible_projection(
        self,
        pending: PendingVisibleProjectionCommit,
    ) -> bool:
        """Attach staged widgets, finalize layout, and resolve projection callbacks."""

        if self._pending_visible_projection_commit is pending:
            self._pending_visible_projection_commit = None
            self._pending_visible_projection_retry_attempts = 0
        if not self._ports.is_projection_session_current(pending.projection_session):
            pending.cancel_refresh("visible_projection_session_stale")
            return False
        try:
            log_info(
                _LOGGER,
                "Started editor visible projection commit",
                workflow_id=pending.workflow_id,
                active_workflow_id=self._ports.active_workflow_id(),
                panel_visible=self._ports.panel_is_visible(),
                pending_build_count=len(pending.projected_builds),
                projection_aliases=tuple(
                    projected_build.cube_alias
                    for projected_build in pending.projected_builds
                ),
            )
            self._ports.reveal_projected_cube_builds(
                pending.projected_builds,
                pending.workflow_id,
            )
            for completed_build in pending.projected_builds:
                self._ports.mark_build_complete(
                    completed_build.cube_alias,
                    completed_build.token,
                )
            pending.finish_refresh()
        except (RuntimeError, TypeError, ValueError) as error:
            for projected_build in pending.projected_builds:
                self._ports.mark_build_failed(
                    projected_build.cube_alias,
                    projected_build.token,
                    error,
                )
            log_warning(
                _LOGGER,
                "Failed editor visible projection commit",
                workflow_id=pending.workflow_id,
                active_workflow_id=self._ports.active_workflow_id(),
                panel_visible=self._ports.panel_is_visible(),
                pending_build_count=len(pending.projected_builds),
                error_type=type(error).__name__,
            )
            pending.cancel_refresh("visible_projection_commit_failed")
            return False
        log_info(
            _LOGGER,
            "Completed editor visible projection commit",
            workflow_id=pending.workflow_id,
            pending_build_count=len(pending.projected_builds),
            elapsed_ms=f"{elapsed_ms_since(pending.created_at):.3f}",
        )
        log_panel_projection_event(
            "visible_commit.completed",
            level="info",
            workflow_id=pending.workflow_id,
            pending_build_count=0,
            elapsed_ms=f"{elapsed_ms_since(pending.created_at):.3f}",
        )
        return True

    def discard_pending_visible_projection_commit(self, *, reason: str) -> None:
        """Cancel any deferred visible commit that can no longer be adopted."""

        pending = self._pending_visible_projection_commit
        if pending is None:
            return
        self._pending_visible_projection_commit = None
        self._pending_visible_projection_retry_attempts = 0
        pending.cancel_refresh(reason)
        log_info(
            _LOGGER,
            "Cancelled pending editor visible projection commit",
            workflow_id=pending.workflow_id,
            pending_build_count=len(pending.projected_builds),
            reason=reason,
        )

    def can_commit_visible_projection(self, workflow_id: str) -> bool:
        """Return whether this panel can safely run visible layout work now."""

        active_workflow_id = self._ports.active_workflow_id()
        return (
            not active_workflow_id or active_workflow_id == workflow_id
        ) and self._ports.panel_is_visible()
