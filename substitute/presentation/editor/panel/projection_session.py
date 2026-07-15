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

"""Own panel projection session and clean-surface state."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, cast

from substitute.shared.logging.logger import get_logger, log_debug, log_info

from .projection_preparation import cube_projection_token

_LOGGER = get_logger("presentation.editor.panel.projection_session")

InsertCompletionPhase = Literal["first_usable", "complete"]


class ProjectionSurfaceStateHost(Protocol):
    """Describe panel state required to identify rendered projection surfaces."""

    _current_search_hidden_keys: set[object] | None
    _current_search_matching_nodes: set[object] | None
    _current_node_search_text: str | None
    _stack_order: list[str] | None

    def _workflow_overrides(self) -> Mapping[str, object]:
        """Return active workflow override values for projection signatures."""


@dataclass(frozen=True, slots=True)
class EditorSurfaceProjectionSignature:
    """Describe the structural workflow facts rendered by one editor surface."""

    workflow_id: str
    stack_order: tuple[str, ...]
    cube_state_map_id: int
    cube_tokens: tuple[tuple[Hashable, ...], ...]
    override_tokens: tuple[tuple[str, str], ...]
    hidden_field_tokens: tuple[str, ...]
    node_search_text: str | None
    search_match_tokens: tuple[str, ...]
    projection_mode: str = "live"


@dataclass(slots=True)
class EditorSurfaceProjectionState:
    """Track whether an editor surface is clean for one projection signature."""

    clean_signature: EditorSurfaceProjectionSignature | None = None
    invalidation_reason: str = "initial"


class ProjectionSurfaceStateController:
    """Own clean/stale projection surface identity for one editor panel."""

    def __init__(self, host: ProjectionSurfaceStateHost) -> None:
        """Store the panel host that supplies rendered-surface identity inputs."""

        self._host = host
        self._state = EditorSurfaceProjectionState()

    @property
    def clean_signature(self) -> EditorSurfaceProjectionSignature | None:
        """Return the current clean signature for tests and diagnostics."""

        return self._state.clean_signature

    def current_projection_signature(
        self,
        *,
        workflow_id: str,
        cube_entries: Sequence[tuple[str, object]],
        cube_states: Mapping[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> EditorSurfaceProjectionSignature:
        """Return the structural signature required by a full editor projection."""

        resolved_stack_order = tuple(
            stack_order or [alias for alias, _ in cube_entries]
        )
        state_map = cube_states or {}
        cube_tokens = tuple(
            cube_projection_token(alias, state_map.get(alias))
            for alias in resolved_stack_order
        )
        workflow_overrides_reader = cast(
            Callable[[], Mapping[str, object]] | None,
            getattr(self._host, "_workflow_overrides", None),
        )
        workflow_overrides = (
            workflow_overrides_reader() if workflow_overrides_reader is not None else {}
        )
        override_tokens = tuple(
            (str(key), repr(value))
            for key, value in sorted(
                workflow_overrides.items(),
                key=lambda item: str(item[0]),
            )
        )
        hidden_search_keys = cast(
            set[object] | None,
            getattr(self._host, "_current_search_hidden_keys", None),
        )
        matching_search_nodes = cast(
            set[object] | None,
            getattr(self._host, "_current_search_matching_nodes", None),
        )
        hidden_field_tokens = tuple(
            sorted(repr(key) for key in (hidden_search_keys or set()))
        )
        search_match_tokens = tuple(
            sorted(repr(key) for key in (matching_search_nodes or set()))
        )
        return EditorSurfaceProjectionSignature(
            workflow_id=workflow_id,
            stack_order=resolved_stack_order,
            cube_state_map_id=id(cube_states),
            cube_tokens=cube_tokens,
            override_tokens=override_tokens,
            hidden_field_tokens=hidden_field_tokens,
            node_search_text=cast(
                str | None,
                getattr(self._host, "_current_node_search_text", None),
            ),
            search_match_tokens=search_match_tokens,
            projection_mode="live",
        )

    def is_projection_clean(
        self,
        signature: EditorSurfaceProjectionSignature,
    ) -> bool:
        """Return whether this editor surface already renders the signature."""

        return self._state.clean_signature == signature

    def mark_projection_clean(
        self,
        signature: EditorSurfaceProjectionSignature,
    ) -> None:
        """Record that the editor surface fully renders the supplied signature."""

        self._state.clean_signature = signature
        self._state.invalidation_reason = ""
        log_info(
            _LOGGER,
            "Marked editor projection surface clean",
            workflow_id=signature.workflow_id,
            cube_section_count=len(signature.stack_order),
        )

    def invalidate_projection(self, *, reason: str) -> None:
        """Mark this editor surface as requiring full projection before reuse."""

        self._state.clean_signature = None
        self._state.invalidation_reason = reason
        log_info(
            _LOGGER,
            "Invalidated editor projection surface",
            reason=reason,
            cube_section_count=len(self._host._stack_order or []),
        )


@dataclass(slots=True)
class PendingInsertCompletion:
    """Carry an incremental insert completion across a replacing projection."""

    workflow_id: str
    cube_alias: str
    token: object
    completion_phase: InsertCompletionPhase
    on_complete: Callable[[], None] | None
    reason: str
    superseded_reason: str | None = None
    resolved: bool = False


@dataclass(slots=True)
class PendingProjectionCompletion:
    """Carry a full-projection completion across a replacing projection."""

    workflow_id: str
    aliases: frozenset[str]
    on_complete: Callable[[], None]
    reason: str
    superseded_reason: str | None = None
    resolved: bool = False


@dataclass(slots=True)
class ActiveProjectionSession:
    """Track full-projection ownership for aliases being rebuilt."""

    workflow_id: str
    aliases: set[str]
    token: object
    claimed_completions: list[PendingInsertCompletion]
    projection_completions: list[PendingProjectionCompletion]
    resolved: bool = False


@dataclass(frozen=True, slots=True)
class ProjectionCompletionTransferResult:
    """Report completion ownership moved while superseding a projection session."""

    transferred_insert_count: int
    cancelled_insert_count: int
    transferred_projection_count: int
    cancelled_projection_count: int


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
            [ActiveProjectionSession, ActiveProjectionSession, str],
            None,
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
            [ActiveProjectionSession, ActiveProjectionSession, str],
            None,
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
        """Return the active projection session that owns one alias, if any."""

        session = self._active_session
        if session is None or session.resolved:
            return None
        if session.workflow_id != workflow_id:
            return None
        if cube_alias not in session.aliases:
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
        """Forget a projection session when it is still the active session."""

        if self._active_session is not session:
            return False
        self._active_session = None
        return True


class ProjectionCompletionRegistry:
    """Own pending and session-scoped projection completion callbacks."""

    def __init__(self) -> None:
        """Initialize an empty projection completion registry."""

        self._pending_insert_completions: dict[
            tuple[str, str],
            PendingInsertCompletion,
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
        """Track a full-projection completion callback under session ownership."""

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
        """Track an incremental insert callback until it completes or transfers."""

        key = self.pending_insert_key(workflow_id, cube_alias)
        existing = self._pending_insert_completions.pop(key, None)
        if existing is not None and existing.token is not token:
            self.cancel_insert_completions(
                (existing,),
                reason="superseded_by_new_insert",
            )
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
        self.cancel_insert_completions((completion,), reason=reason)

    def cancel_all_pending_inserts(self, *, reason: str) -> None:
        """Cancel every pending insert callback still waiting outside a session."""

        completions = tuple(self._pending_insert_completions.values())
        self._pending_insert_completions.clear()
        self.cancel_insert_completions(completions, reason=reason)

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
        """Transfer one incremental insert callback to full-projection ownership."""

        key = self.pending_insert_key(workflow_id, cube_alias)
        completion = self._pending_insert_completions.get(key)
        if completion is None:
            return None
        if token is not None and completion.token is not token:
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

    def claim_superseded_inserts(
        self,
        *,
        workflow_id: str,
        cube_entries: Sequence[tuple[str, object]],
        projection_session: ActiveProjectionSession,
    ) -> None:
        """Claim superseded insert callbacks for the active full projection."""

        for cube_alias in {alias for alias, _cube_state in cube_entries}:
            key = self.pending_insert_key(workflow_id, cube_alias)
            completion = self._pending_insert_completions.get(key)
            if completion is None or completion.superseded_reason is None:
                continue
            self.claim_pending_insert_for_projection(
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                token=None,
                reason=completion.superseded_reason,
                projection_session=projection_session,
            )

    def attach_insert_to_active_projection(
        self,
        *,
        session: ActiveProjectionSession,
        workflow_id: str,
        cube_alias: str,
        completion_phase: InsertCompletionPhase,
        on_complete: Callable[[], None] | None,
        reason: str,
    ) -> None:
        """Attach an incoming incremental completion to active projection ownership."""

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

    def transfer_from_superseded_session(
        self,
        session: ActiveProjectionSession,
        *,
        replacement_session: ActiveProjectionSession,
        reason: str,
    ) -> ProjectionCompletionTransferResult:
        """Transfer matching callbacks from a superseded full projection."""

        transferred: list[PendingInsertCompletion] = []
        cancelled: list[PendingInsertCompletion] = []
        transferred_projection: list[PendingProjectionCompletion] = []
        cancelled_projection: list[PendingProjectionCompletion] = []
        for completion in session.claimed_completions:
            if completion.resolved:
                continue
            if (
                session.workflow_id == replacement_session.workflow_id
                and completion.cube_alias in replacement_session.aliases
            ):
                transferred.append(completion)
            else:
                cancelled.append(completion)
        for projection_completion in session.projection_completions:
            if projection_completion.resolved:
                continue
            if (
                session.workflow_id == replacement_session.workflow_id
                and projection_completion.aliases.issubset(replacement_session.aliases)
            ):
                projection_completion.superseded_reason = (
                    projection_completion.superseded_reason or reason
                )
                transferred_projection.append(projection_completion)
            else:
                cancelled_projection.append(projection_completion)
        replacement_session.claimed_completions.extend(transferred)
        replacement_session.projection_completions.extend(transferred_projection)
        self.cancel_insert_completions(cancelled, reason=reason)
        self.cancel_projection_completions(cancelled_projection, reason=reason)
        return ProjectionCompletionTransferResult(
            transferred_insert_count=len(transferred),
            cancelled_insert_count=len(cancelled),
            transferred_projection_count=len(transferred_projection),
            cancelled_projection_count=len(cancelled_projection),
        )

    def resolve_session(
        self,
        session: ActiveProjectionSession,
        *,
        reason: str,
    ) -> None:
        """Resolve all completion callbacks owned by one full projection."""

        self.resolve_insert_completions(session.claimed_completions, reason=reason)
        self.resolve_projection_completions(
            session.projection_completions,
            reason=reason,
        )

    def cancel_session(
        self,
        session: ActiveProjectionSession,
        *,
        reason: str,
    ) -> None:
        """Cancel all completion callbacks owned by one full projection."""

        self.cancel_insert_completions(session.claimed_completions, reason=reason)
        self.cancel_projection_completions(
            session.projection_completions,
            reason=reason,
        )

    def resolve_insert_completions(
        self,
        completions: Sequence[PendingInsertCompletion],
        *,
        reason: str,
    ) -> None:
        """Invoke claimed insert callbacks after replacement projection succeeds."""

        for completion in completions:
            if completion.resolved:
                continue
            completion.resolved = True
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="pending_insert_completion_resolved",
                workflow_id=completion.workflow_id,
                cube_alias=completion.cube_alias,
                reason=reason,
                superseded_reason=completion.superseded_reason or "",
                completion_phase=completion.completion_phase,
            )
            if completion.on_complete is not None:
                completion.on_complete()

    def resolve_projection_completions(
        self,
        completions: Sequence[PendingProjectionCompletion],
        *,
        reason: str,
    ) -> None:
        """Invoke full-projection callbacks after replacement projection succeeds."""

        for completion in completions:
            if completion.resolved:
                continue
            completion.resolved = True
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="projection_completion_resolved",
                workflow_id=completion.workflow_id,
                reason=reason,
                superseded_reason=completion.superseded_reason or "",
                completion_reason=completion.reason,
                projection_alias_count=len(completion.aliases),
            )
            completion.on_complete()

    def cancel_insert_completions(
        self,
        completions: Sequence[PendingInsertCompletion],
        *,
        reason: str,
    ) -> None:
        """Close claimed insert callbacks without reporting successful readiness."""

        for completion in completions:
            if completion.resolved:
                continue
            completion.resolved = True
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="pending_insert_completion_cancelled",
                workflow_id=completion.workflow_id,
                cube_alias=completion.cube_alias,
                reason=reason,
                superseded_reason=completion.superseded_reason or "",
                completion_phase=completion.completion_phase,
            )

    def cancel_projection_completions(
        self,
        completions: Sequence[PendingProjectionCompletion],
        *,
        reason: str,
    ) -> None:
        """Close full-projection callbacks without reporting successful readiness."""

        for completion in completions:
            if completion.resolved:
                continue
            completion.resolved = True
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="projection_completion_cancelled",
                workflow_id=completion.workflow_id,
                reason=reason,
                superseded_reason=completion.superseded_reason or "",
                completion_reason=completion.reason,
                projection_alias_count=len(completion.aliases),
            )
