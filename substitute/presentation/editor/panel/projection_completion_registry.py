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

"""Own incremental and full-projection completion callback transfer."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from substitute.shared.logging.logger import get_logger, log_debug

from .projection_completion_resolution import (
    cancel_insert_completions,
    cancel_projection_completions,
    resolve_insert_completions,
    resolve_projection_completions,
)
from .projection_session_models import (
    ActiveProjectionSession,
    InsertCompletionPhase,
    PendingInsertCompletion,
    PendingProjectionCompletion,
    ProjectionCompletionTransferResult,
)

_LOGGER = get_logger("presentation.editor.panel.projection_completion_registry")


class ProjectionCompletionRegistry:
    """Own pending and session-scoped projection completion callbacks."""

    def __init__(self) -> None:
        """Initialize an empty projection completion registry."""

        self._pending_insert_completions: dict[
            tuple[str, str], PendingInsertCompletion
        ] = {}

    @property
    def pending_insert_completions(
        self,
    ) -> dict[tuple[str, str], PendingInsertCompletion]:
        """Return a copy of pending insert completions for diagnostics."""

        return dict(self._pending_insert_completions)

    @staticmethod
    def pending_insert_key(workflow_id: str, cube_alias: str) -> tuple[str, str]:
        """Return the stable owner key for one pending insert completion."""

        return workflow_id, cube_alias

    def register_projection_completion(
        self,
        session: ActiveProjectionSession,
        *,
        workflow_id: str,
        aliases: set[str],
        on_complete: Callable[[], None] | None,
        reason: str,
    ) -> None:
        """Track a full-projection callback under session ownership."""

        if on_complete is None:
            return
        session.projection_completions.append(
            PendingProjectionCompletion(
                workflow_id=workflow_id,
                aliases=frozenset(aliases),
                on_complete=on_complete,
                reason=reason,
            )
        )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="projection_completion_registered",
            workflow_id=workflow_id,
            reason=reason,
            projection_alias_count=len(aliases),
        )

    def register_pending_insert(
        self,
        *,
        workflow_id: str,
        cube_alias: str,
        token: object,
        completion_phase: InsertCompletionPhase,
        on_complete: Callable[[], None] | None,
    ) -> None:
        """Track an insert callback until it completes or transfers."""

        key = self.pending_insert_key(workflow_id, cube_alias)
        existing = self._pending_insert_completions.pop(key, None)
        if existing is not None and existing.token is not token:
            cancel_insert_completions((existing,), reason="superseded_by_new_insert")
        if on_complete is None:
            return
        self._pending_insert_completions[key] = PendingInsertCompletion(
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            token=token,
            completion_phase=completion_phase,
            on_complete=on_complete,
            reason="incremental_insert",
        )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="pending_insert_completion_registered",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            completion_phase=completion_phase,
        )

    def forget_pending_insert(
        self,
        *,
        workflow_id: str,
        cube_alias: str,
        token: object,
        reason: str,
    ) -> None:
        """Remove a pending insert callback without invoking it."""

        key = self.pending_insert_key(workflow_id, cube_alias)
        completion = self._pending_insert_completions.get(key)
        if completion is None or completion.token is not token:
            return
        self._pending_insert_completions.pop(key, None)
        completion.resolved = True
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="pending_insert_completion_forgotten",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            reason=reason,
            superseded_reason=completion.superseded_reason or "",
        )

    def cancel_pending_insert(
        self,
        *,
        workflow_id: str,
        cube_alias: str,
        token: object,
        reason: str,
        cancel_superseded: bool,
    ) -> None:
        """Cancel one pending insert callback when ownership still matches."""

        key = self.pending_insert_key(workflow_id, cube_alias)
        completion = self._pending_insert_completions.get(key)
        if completion is None or completion.token is not token:
            return
        if completion.superseded_reason is not None and not cancel_superseded:
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="pending_insert_completion_preserved_for_projection",
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                reason=reason,
                superseded_reason=completion.superseded_reason,
            )
            return
        self._pending_insert_completions.pop(key, None)
        cancel_insert_completions((completion,), reason=reason)

    def cancel_all_pending_inserts(self, *, reason: str) -> None:
        """Cancel every pending insert callback outside a session."""

        completions = tuple(self._pending_insert_completions.values())
        self._pending_insert_completions.clear()
        cancel_insert_completions(completions, reason=reason)

    def mark_pending_insert_superseded(
        self,
        *,
        workflow_id: str,
        cube_alias: str,
        token: object,
        reason: str,
    ) -> bool:
        """Mark one pending insert as transferable to a replacement projection."""

        key = self.pending_insert_key(workflow_id, cube_alias)
        completion = self._pending_insert_completions.get(key)
        if completion is None or completion.token is not token:
            return False
        if reason != "node_definition_changed":
            self.cancel_pending_insert(
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                token=token,
                reason=reason,
                cancel_superseded=True,
            )
            return False
        completion.superseded_reason = reason
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="pending_insert_completion_superseded",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            reason=reason,
            completion_phase=completion.completion_phase,
        )
        return True

    def claim_pending_insert_for_projection(
        self,
        *,
        workflow_id: str,
        cube_alias: str,
        token: object | None,
        reason: str,
        projection_session: ActiveProjectionSession,
    ) -> PendingInsertCompletion | None:
        """Transfer one incremental callback to full-projection ownership."""

        key = self.pending_insert_key(workflow_id, cube_alias)
        completion = self._pending_insert_completions.get(key)
        if completion is None or (token is not None and completion.token is not token):
            return None
        self._pending_insert_completions.pop(key, None)
        completion.superseded_reason = completion.superseded_reason or reason
        projection_session.claimed_completions.append(completion)
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="pending_insert_completion_claimed_by_projection",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            reason=reason,
            superseded_reason=completion.superseded_reason,
            completion_phase=completion.completion_phase,
            projection_alias_count=len(projection_session.aliases),
        )
        return completion


class ProjectionSessionCompletionController:
    """Attach, transfer, resolve, and cancel session-owned callbacks."""

    def __init__(self, pending_inserts: ProjectionCompletionRegistry) -> None:
        """Store the registry that owns callbacks before session attachment."""

        self._pending_inserts = pending_inserts

    def claim_superseded_inserts(
        self,
        *,
        workflow_id: str,
        cube_entries: Sequence[tuple[str, object]],
        projection_session: ActiveProjectionSession,
    ) -> None:
        """Claim superseded insert callbacks for the active projection."""

        for cube_alias in {alias for alias, _cube_state in cube_entries}:
            key = self._pending_inserts.pending_insert_key(workflow_id, cube_alias)
            completion = self._pending_inserts.pending_insert_completions.get(key)
            if completion is None or completion.superseded_reason is None:
                continue
            self._pending_inserts.claim_pending_insert_for_projection(
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                token=None,
                reason=completion.superseded_reason,
                projection_session=projection_session,
            )

    def attach_insert(
        self,
        *,
        session: ActiveProjectionSession,
        workflow_id: str,
        cube_alias: str,
        completion_phase: InsertCompletionPhase,
        on_complete: Callable[[], None] | None,
        reason: str,
    ) -> None:
        """Attach an incoming incremental callback to an active projection."""

        if on_complete is not None:
            session.claimed_completions.append(
                PendingInsertCompletion(
                    workflow_id=workflow_id,
                    cube_alias=cube_alias,
                    token=session.token,
                    completion_phase=completion_phase,
                    on_complete=on_complete,
                    reason=reason,
                    superseded_reason=reason,
                )
            )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="pending_insert_completion_attached_to_projection",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            reason=reason,
            completion_phase=completion_phase,
            callback_attached=on_complete is not None,
            projection_alias_count=len(session.aliases),
            claimed_completion_count=len(session.claimed_completions),
        )

    def transfer(
        self,
        session: ActiveProjectionSession,
        *,
        replacement_session: ActiveProjectionSession,
        reason: str,
    ) -> ProjectionCompletionTransferResult:
        """Transfer matching callbacks from a superseded projection."""

        transferred = [
            completion
            for completion in session.claimed_completions
            if not completion.resolved
            and session.workflow_id == replacement_session.workflow_id
            and completion.cube_alias in replacement_session.aliases
        ]
        cancelled = [
            completion
            for completion in session.claimed_completions
            if not completion.resolved and completion not in transferred
        ]
        transferred_projection = [
            completion
            for completion in session.projection_completions
            if not completion.resolved
            and session.workflow_id == replacement_session.workflow_id
            and completion.aliases.issubset(replacement_session.aliases)
        ]
        cancelled_projection = [
            completion
            for completion in session.projection_completions
            if not completion.resolved and completion not in transferred_projection
        ]
        for completion in transferred_projection:
            completion.superseded_reason = completion.superseded_reason or reason
        replacement_session.claimed_completions.extend(transferred)
        replacement_session.projection_completions.extend(transferred_projection)
        cancel_insert_completions(cancelled, reason=reason)
        cancel_projection_completions(cancelled_projection, reason=reason)
        return ProjectionCompletionTransferResult(
            transferred_insert_count=len(transferred),
            cancelled_insert_count=len(cancelled),
            transferred_projection_count=len(transferred_projection),
            cancelled_projection_count=len(cancelled_projection),
        )

    def resolve(self, session: ActiveProjectionSession, *, reason: str) -> None:
        """Resolve all completion callbacks owned by one projection."""

        resolve_insert_completions(session.claimed_completions, reason=reason)
        resolve_projection_completions(session.projection_completions, reason=reason)

    def cancel(self, session: ActiveProjectionSession, *, reason: str) -> None:
        """Cancel all completion callbacks owned by one projection."""

        cancel_insert_completions(session.claimed_completions, reason=reason)
        cancel_projection_completions(session.projection_completions, reason=reason)
