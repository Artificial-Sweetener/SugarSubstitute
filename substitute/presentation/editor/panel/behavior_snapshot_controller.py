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

"""Own editor behavior snapshot construction and refresh-scope reuse."""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from dataclasses import dataclass
from typing import Protocol

from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("presentation.editor.panel.prompt.context")


@dataclass(slots=True)
class PanelBehaviorRefreshTransaction:
    """Track one explicit editor behavior snapshot reuse boundary."""

    reason: str
    snapshot: EditorBehaviorSnapshot | None = None
    reuse_key: tuple[Hashable, ...] | None = None


class NodeBehaviorServiceProtocol(Protocol):
    """Describe behavior snapshot construction."""

    def build_snapshot(
        self,
        *,
        cube_states: Mapping[str, object],
        stack_order: list[str],
        workflow_overrides: Mapping[str, object],
        search_hidden_keys: set[object],
        override_hidden_field_keys: set[object] | None,
        node_search_text: str | None,
        search_matching_nodes: set[tuple[str, str]] | None,
    ) -> EditorBehaviorSnapshot:
        """Build a behavior snapshot for the supplied workflow state."""


class BehaviorSnapshotHost(Protocol):
    """Describe live panel inputs needed to build behavior snapshots."""

    node_behavior_service: NodeBehaviorServiceProtocol
    _cube_states: dict[str, object] | None
    _stack_order: list[str] | None
    _current_search_hidden_keys: set[object] | None
    _current_node_search_text: str | None
    _current_search_matching_nodes: set[tuple[str, str]] | None
    _last_behavior_snapshot: EditorBehaviorSnapshot | None

    def _workflow_overrides(self) -> Mapping[str, object]:
        """Return workflow overrides included in snapshot identity."""


class BehaviorSnapshotController:
    """Build behavior snapshots and reuse them within explicit transactions."""

    def __init__(self, host: BehaviorSnapshotHost) -> None:
        """Store live inputs and initialize without an active transaction."""

        self._host = host
        self._transaction: PanelBehaviorRefreshTransaction | None = None

    def set_current(self, snapshot: EditorBehaviorSnapshot | None) -> None:
        """Publish the latest behavior snapshot through the mounted host."""

        self._host._last_behavior_snapshot = snapshot

    def current(self) -> EditorBehaviorSnapshot | None:
        """Return the latest cached behavior snapshot."""

        return self._host._last_behavior_snapshot

    def build(
        self,
        *,
        search_hidden_keys: set[object] | None = None,
        override_hidden_field_keys: set[object] | None = None,
        node_search_text: str | None = None,
        search_matching_nodes: set[tuple[str, str]] | None = None,
    ) -> EditorBehaviorSnapshot | None:
        """Build or safely reuse a behavior snapshot for current panel state."""

        if not self._host._stack_order or not self._host._cube_states:
            return None
        effective_hidden = (
            search_hidden_keys
            if search_hidden_keys is not None
            else (self._host._current_search_hidden_keys or set())
        )
        effective_search_text = (
            node_search_text
            if node_search_text is not None
            else self._host._current_node_search_text
        )
        effective_matches = (
            search_matching_nodes
            if search_matching_nodes is not None
            else self._host._current_search_matching_nodes
        )
        workflow_overrides = self._host._workflow_overrides()
        reuse_key = self.reuse_key(
            workflow_overrides=workflow_overrides,
            search_hidden_keys=effective_hidden,
            override_hidden_field_keys=override_hidden_field_keys,
            node_search_text=effective_search_text,
            search_matching_nodes=effective_matches,
        )
        transaction = self._transaction
        if (
            transaction is not None
            and transaction.snapshot is not None
            and transaction.reuse_key == reuse_key
        ):
            self.set_current(transaction.snapshot)
            log_info(
                _LOGGER,
                "Reused editor behavior snapshot from refresh transaction",
                reason=transaction.reason,
                cube_section_count=len(self._host._stack_order),
            )
            return transaction.snapshot
        snapshot = self._host.node_behavior_service.build_snapshot(
            cube_states=self._host._cube_states,
            stack_order=list(self._host._stack_order),
            workflow_overrides=workflow_overrides,
            search_hidden_keys=effective_hidden,
            override_hidden_field_keys=override_hidden_field_keys,
            node_search_text=effective_search_text,
            search_matching_nodes=effective_matches,
        )
        self.set_current(snapshot)
        if transaction is not None:
            transaction.snapshot = snapshot
            transaction.reuse_key = reuse_key
        return snapshot

    def begin(self, *, reason: str) -> None:
        """Start an explicit behavior snapshot reuse boundary."""

        self._transaction = PanelBehaviorRefreshTransaction(reason=reason)
        log_info(
            _LOGGER,
            "Started editor behavior snapshot refresh transaction",
            reason=reason,
            cube_section_count=len(self._host._stack_order or []),
        )

    def end(self, *, reason: str) -> None:
        """Complete the active behavior snapshot reuse boundary."""

        transaction = self._transaction
        if transaction is None:
            return
        self._transaction = None
        log_info(
            _LOGGER,
            "Completed editor behavior snapshot refresh transaction",
            reason=reason,
            transaction_reason=transaction.reason,
            reused_snapshot=transaction.snapshot is not None,
        )

    def invalidate(self, *, reason: str) -> None:
        """Drop the active transaction before a state-changing refresh."""

        transaction = self._transaction
        if transaction is None:
            return
        self._transaction = None
        log_info(
            _LOGGER,
            "Invalidated editor behavior snapshot refresh transaction",
            reason=reason,
            transaction_reason=transaction.reason,
        )

    def reuse_key(
        self,
        *,
        workflow_overrides: Mapping[str, object],
        search_hidden_keys: set[object] | None,
        override_hidden_field_keys: set[object] | None,
        node_search_text: str | None,
        search_matching_nodes: set[tuple[str, str]] | None,
    ) -> tuple[Hashable, ...]:
        """Return the identity key that makes transaction reuse safe."""

        cube_states = self._host._cube_states or {}
        stack_order = tuple(self._host._stack_order or [])
        cube_tokens = tuple(
            (alias, id(cube_states.get(alias))) for alias in stack_order
        )
        override_tokens = tuple(
            (str(key), repr(value))
            for key, value in sorted(
                workflow_overrides.items(), key=lambda item: str(item[0])
            )
        )
        hidden_tokens = tuple(
            sorted(repr(key) for key in (search_hidden_keys or set()))
        )
        override_hidden_tokens = tuple(
            sorted(repr(key) for key in (override_hidden_field_keys or set()))
        )
        matching_tokens = tuple(
            sorted(repr(key) for key in (search_matching_nodes or set()))
        )
        return (
            stack_order,
            id(cube_states),
            cube_tokens,
            override_tokens,
            hidden_tokens,
            override_hidden_tokens,
            node_search_text,
            matching_tokens,
        )


__all__ = ["BehaviorSnapshotController", "BehaviorSnapshotHost"]
