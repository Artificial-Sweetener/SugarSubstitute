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

"""Own active editor projection session lifecycle orchestration."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from substitute.shared.logging.logger import get_logger, log_debug

from .projection_session import (
    ActiveProjectionSession,
    ActiveProjectionSessionRegistry,
    ProjectionCompletionRegistry,
)

_LOGGER = get_logger("presentation.editor.panel.projection_active_session_controller")


class EditorActiveProjectionSessionController:
    """Coordinate active full-projection session state and callback ownership."""

    def __init__(
        self,
        *,
        sessions: ActiveProjectionSessionRegistry,
        completions: ProjectionCompletionRegistry,
        discard_pending_visible_commit: Callable[[str], None],
    ) -> None:
        """Store session registries and visible-commit cancellation port."""

        self._sessions = sessions
        self._completions = completions
        self._discard_pending_visible_commit = discard_pending_visible_commit

    @property
    def active_session(self) -> ActiveProjectionSession | None:
        """Return the active projection session for diagnostics."""

        return self._sessions.active_session

    def start(
        self,
        *,
        workflow_id: str,
        cube_entries: Sequence[tuple[str, object]],
    ) -> ActiveProjectionSession:
        """Open full-projection ownership for the aliases being reconciled."""

        session = self._sessions.start(
            workflow_id=workflow_id,
            cube_entries=cube_entries,
            supersede_existing=self._supersede_session,
            session_cleared=self._log_session_cleared,
            discard_pending_visible_commit=self._discard_pending_visible_commit,
        )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="active_projection_session_started",
            workflow_id=workflow_id,
            projection_alias_count=len(session.aliases),
            projection_aliases=tuple(sorted(session.aliases)),
        )
        return session

    def resolve(
        self,
        session: ActiveProjectionSession,
        *,
        reason: str,
    ) -> None:
        """Resolve all callbacks owned by a successful full projection."""

        if self._sessions.resolve(
            session,
            reason=reason,
            resolve_session=self._resolve_session_callbacks,
        ):
            self._log_session_cleared(session, reason)

    def cancel(
        self,
        session: ActiveProjectionSession,
        *,
        reason: str,
    ) -> None:
        """Cancel all callbacks owned by an abandoned full projection."""

        if self._sessions.cancel(
            session,
            reason=reason,
            cancel_session=self._cancel_session_callbacks,
        ):
            self._log_session_cleared(session, reason)

    def _supersede_session(
        self,
        session: ActiveProjectionSession,
        replacement_session: ActiveProjectionSession,
        reason: str,
    ) -> None:
        """Transfer still-owned callbacks into a newer full projection."""

        transfer_result = self._completions.transfer_from_superseded_session(
            session,
            replacement_session=replacement_session,
            reason=reason,
        )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="active_projection_session_superseded",
            workflow_id=session.workflow_id,
            replacement_workflow_id=replacement_session.workflow_id,
            reason=reason,
            projection_alias_count=len(session.aliases),
            replacement_alias_count=len(replacement_session.aliases),
            transferred_completion_count=transfer_result.transferred_insert_count,
            cancelled_completion_count=transfer_result.cancelled_insert_count,
            transferred_projection_completion_count=(
                transfer_result.transferred_projection_count
            ),
            cancelled_projection_completion_count=(
                transfer_result.cancelled_projection_count
            ),
        )

    def _log_session_cleared(
        self,
        session: ActiveProjectionSession,
        reason: str,
    ) -> None:
        """Log that a no-longer-active projection session was cleared."""

        log_debug(
            _LOGGER,
            "Cube load detail",
            event="active_projection_session_cleared",
            workflow_id=session.workflow_id,
            reason=reason,
            projection_alias_count=len(session.aliases),
            claimed_completion_count=len(session.claimed_completions),
            projection_completion_count=len(session.projection_completions),
        )

    def _resolve_session_callbacks(
        self,
        session: ActiveProjectionSession,
        reason: str,
    ) -> None:
        """Resolve completion callbacks for one successful full projection."""

        log_debug(
            _LOGGER,
            "Cube load detail",
            event="active_projection_session_resolved",
            workflow_id=session.workflow_id,
            reason=reason,
            projection_alias_count=len(session.aliases),
            claimed_completion_count=len(session.claimed_completions),
            projection_completion_count=len(session.projection_completions),
        )
        self._completions.resolve_session(session, reason=reason)

    def _cancel_session_callbacks(
        self,
        session: ActiveProjectionSession,
        reason: str,
    ) -> None:
        """Cancel completion callbacks for one abandoned full projection."""

        log_debug(
            _LOGGER,
            "Cube load detail",
            event="active_projection_session_cancelled",
            workflow_id=session.workflow_id,
            reason=reason,
            projection_alias_count=len(session.aliases),
            claimed_completion_count=len(session.claimed_completions),
            projection_completion_count=len(session.projection_completions),
        )
        self._completions.cancel_session(session, reason=reason)
