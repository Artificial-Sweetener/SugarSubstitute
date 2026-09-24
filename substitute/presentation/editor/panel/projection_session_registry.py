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

"""Own active full-projection session transitions."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .projection_session_models import ActiveProjectionSession


class ActiveProjectionSessionRegistry:
    """Own the current full-projection session state machine."""

    def __init__(self) -> None:
        """Initialize an empty active projection session registry."""

        self._active_session: ActiveProjectionSession | None = None

    @property
    def active_session(self) -> ActiveProjectionSession | None:
        """Return the current active projection session, if one exists."""

        return self._active_session

    def start(
        self,
        *,
        workflow_id: str,
        cube_entries: Sequence[tuple[str, object]],
        supersede_existing: Callable[
            [ActiveProjectionSession, ActiveProjectionSession, str], None
        ],
        session_cleared: Callable[[ActiveProjectionSession, str], None],
        discard_pending_visible_commit: Callable[[str], None],
    ) -> ActiveProjectionSession:
        """Open full-projection ownership for the aliases being reconciled."""

        session = ActiveProjectionSession(
            workflow_id=workflow_id,
            aliases={alias for alias, _cube_state in cube_entries},
            token=object(),
            claimed_completions=[],
            projection_completions=[],
        )
        existing_session = self._active_session
        if existing_session is not None and not existing_session.resolved:
            self.supersede(
                existing_session,
                replacement_session=session,
                reason="superseded_by_new_full_projection",
                supersede_existing=supersede_existing,
                session_cleared=session_cleared,
            )
        discard_pending_visible_commit("superseded_by_new_full_projection")
        self._active_session = session
        return session

    def supersede(
        self,
        session: ActiveProjectionSession,
        *,
        replacement_session: ActiveProjectionSession,
        reason: str,
        supersede_existing: Callable[
            [ActiveProjectionSession, ActiveProjectionSession, str], None
        ],
        session_cleared: Callable[[ActiveProjectionSession, str], None] | None = None,
    ) -> bool:
        """Supersede one active session with a newer full projection."""

        if session.resolved:
            return False
        supersede_existing(session, replacement_session, reason)
        session.resolved = True
        if self.clear(session, reason=reason) and session_cleared is not None:
            session_cleared(session, reason)
        return True

    def owns(
        self,
        *,
        workflow_id: str,
        cube_alias: str,
    ) -> ActiveProjectionSession | None:
        """Return the active session that owns one alias, if any."""

        session = self._active_session
        if session is None or session.resolved:
            return None
        if session.workflow_id != workflow_id or cube_alias not in session.aliases:
            return None
        return session

    def is_current(self, session: ActiveProjectionSession) -> bool:
        """Return whether a session still owns active full-projection work."""

        return self._active_session is session and not session.resolved

    def resolve(
        self,
        session: ActiveProjectionSession,
        *,
        reason: str,
        resolve_session: Callable[[ActiveProjectionSession, str], None],
    ) -> bool:
        """Resolve callbacks for a successful full projection and clear it."""

        if session.resolved:
            return False
        resolve_session(session, reason)
        session.resolved = True
        self.clear(session, reason=reason)
        return True

    def cancel(
        self,
        session: ActiveProjectionSession,
        *,
        reason: str,
        cancel_session: Callable[[ActiveProjectionSession, str], None],
    ) -> bool:
        """Cancel callbacks for an abandoned full projection and clear it."""

        if session.resolved:
            return False
        cancel_session(session, reason)
        session.resolved = True
        self.clear(session, reason=reason)
        return True

    def clear(self, session: ActiveProjectionSession, *, reason: str) -> bool:
        """Forget a projection session when it remains the active session."""

        del reason
        if self._active_session is not session:
            return False
        self._active_session = None
        return True
