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

"""Apply resolved editor behavior snapshots to live card and field state."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol, cast

from shiboken6 import isValid

from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.editor.panel.behavior.behavior_applier")


class CardWrapperProtocol(Protocol):
    """Describe the card-wrapper visibility surface used by the applier."""

    def setProperty(self, name: str, value: object) -> None:  # noqa: N802
        """Set one Qt dynamic property."""

    def setVisible(self, visible: bool) -> None:
        """Update wrapper visibility."""


CardDecisionSnapshot = tuple[bool, bool, str]


@dataclass(slots=True)
class EditorBehaviorState:
    """Store the last behavior application needed for fallback restoration."""

    last_card_decisions: dict[tuple[str, str], CardDecisionSnapshot] = field(
        default_factory=dict
    )
    last_hidden_field_keys: set[object] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class EditorBehaviorApplicationPorts:
    """Group side-effect collaborators used by behavior application."""

    card_wrapper: Callable[[str, str], object | None]
    apply_hidden_field_keys: Callable[[set[object]], None]
    apply_node_card_decisions: Callable[[Mapping[str, Mapping[str, object]]], None]
    publish_behavior_snapshot: Callable[[EditorBehaviorSnapshot | None], None]
    rebuild_cube_visibility_menus: Callable[[], None]


class EditorBehaviorApplier:
    """Own the side effects of applying behavior snapshots to an editor panel."""

    def __init__(
        self,
        state: EditorBehaviorState,
        ports: EditorBehaviorApplicationPorts,
    ) -> None:
        """Store behavior fallback state and typed side-effect ports."""

        self._state = state
        self._ports = ports

    def restore_previous_state(self) -> None:
        """Restore the last applied card and hidden-field state after snapshot failure."""

        for (alias, node_name), previous in self._state.last_card_decisions.items():
            try:
                self._set_wrapper_visible(alias, node_name, previous[0])
            except (AttributeError, KeyError, RuntimeError, TypeError) as error:
                log_warning(
                    _LOGGER,
                    "Failed to restore previous editor behavior fallback state",
                    cube_alias=alias,
                    node_name=node_name,
                    error_type=type(error).__name__,
                )

        try:
            self._ports.apply_hidden_field_keys(set(self._state.last_hidden_field_keys))
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Failed to restore previous hidden-field state after snapshot failure",
                error_type=type(error).__name__,
            )

    def apply_snapshot(self, snapshot: EditorBehaviorSnapshot) -> None:
        """Apply one resolved behavior snapshot into wrappers, hidden fields, and menus."""

        for alias, per_node in snapshot.card_decisions_by_alias.items():
            for node_name, decision in per_node.items():
                self._set_wrapper_visible(alias, node_name, decision.visible)

        next_card_decisions = {
            (alias, node_name): (
                bool(decision.visible),
                bool(decision.enabled),
                str(decision.reason),
            )
            for alias, per_node in snapshot.card_decisions_by_alias.items()
            for node_name, decision in per_node.items()
        }
        self._state.last_card_decisions.clear()
        self._state.last_card_decisions.update(next_card_decisions)

        merged_hidden: set[object] = set()
        for keys in snapshot.hidden_field_keys_by_alias.values():
            merged_hidden.update(keys)

        self._ports.apply_hidden_field_keys(merged_hidden)
        self._ports.apply_node_card_decisions(snapshot.card_decisions_by_alias)
        self._state.last_hidden_field_keys.clear()
        self._state.last_hidden_field_keys.update(merged_hidden)
        self._ports.publish_behavior_snapshot(snapshot)
        self._ports.rebuild_cube_visibility_menus()

    def _set_wrapper_visible(self, alias: str, node_name: str, visible: bool) -> None:
        """Update one wrapper's policy visibility when the wrapper is still valid."""

        wrapper = self._ports.card_wrapper(alias, node_name)
        if wrapper is None or not isValid(wrapper):
            return
        card_wrapper = cast(CardWrapperProtocol, wrapper)
        card_wrapper.setProperty("base_card_visible", bool(visible))
        card_wrapper.setVisible(bool(visible))
