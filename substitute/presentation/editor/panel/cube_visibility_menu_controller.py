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

"""Own cube visibility-menu projection and command routing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction

from substitute.application.display_labels import beautify_label


class VisibilityButtonProtocol(Protocol):
    """Describe reveal-menu button state APIs."""

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        """Set whether the reveal menu button is enabled."""

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        """Set whether the reveal menu button is visible."""


class CubeVisibilityEntryProtocol(Protocol):
    """Describe one behavior-projected visibility menu entry."""

    label: str
    checked: bool
    node_name: str


class CubeVisibilitySnapshotProtocol(Protocol):
    """Describe behavior snapshot entries consumed by the menu projector."""

    reveal_entries_by_alias: Mapping[str, Sequence[CubeVisibilityEntryProtocol]]


class CubeVisibilityMenuHost(Protocol):
    """Describe behavior and widget state used by cube visibility menus."""

    _cube_states: dict[str, object] | None
    _cube_visibility_btns: dict[str, VisibilityButtonProtocol]
    _cube_visibility_menus: dict[str, object]
    _stack_order: Sequence[str] | None
    node_behavior_service: object

    def sender(self) -> object | None:
        """Return the Qt signal sender for action routing."""

    def current_behavior_snapshot(self) -> CubeVisibilitySnapshotProtocol | None:
        """Return the latest prepared behavior snapshot."""

    def refresh_node_behavior_state(self, *, reason: str) -> None:
        """Refresh node behavior after reveal-policy mutation."""


class CubeVisibilityMenuController:
    """Project behavior entries into menus and route visibility commands."""

    def __init__(self, host: CubeVisibilityMenuHost) -> None:
        """Store the host that owns menu widgets and workflow state."""

        self._host = host

    def rebuild_all(self) -> None:
        """Rebuild all per-cube menus from the latest behavior snapshot."""

        for alias in self._host._stack_order or ():
            if alias in self._host._cube_visibility_menus:
                self.rebuild(alias)

    def route_triggered_action(self, action: object) -> None:
        """Resolve an action's cube alias and apply its visibility toggle."""

        data_reader = getattr(action, "data", None)
        data = data_reader() if callable(data_reader) else {}
        alias = data.get("alias") if isinstance(data, Mapping) else None
        if not alias:
            sender = self._host.sender()
            for current_alias, menu in self._host._cube_visibility_menus.items():
                if menu is sender:
                    alias = current_alias
                    break
        if alias:
            self.route_toggled_action(str(alias), action)

    def rebuild(self, alias: str) -> None:
        """Rebuild one menu from the latest snapshot reveal entries."""

        menu = self._host._cube_visibility_menus.get(alias)
        if menu is None:
            return
        clear = getattr(menu, "clear", None)
        if callable(clear):
            clear()
        snapshot = self._host.current_behavior_snapshot()
        entries = snapshot.reveal_entries_by_alias.get(alias, []) if snapshot else []
        button = self._host._cube_visibility_btns.get(alias)
        if not entries:
            if button is not None:
                button.setEnabled(False)
                button.setVisible(False)
            return
        if button is not None:
            button.setEnabled(True)
            button.setVisible(True)
        for entry in entries:
            action_parent = menu if isinstance(menu, QObject) else None
            action = QAction(beautify_label(entry.label), action_parent)
            action.setCheckable(True)
            action.setChecked(bool(entry.checked))
            action.setData({"alias": alias, "node_name": entry.node_name})
            action.toggled.connect(
                lambda checked, *, current_alias=alias, node_name=entry.node_name: (
                    self.apply_toggle(current_alias, node_name, bool(checked))
                )
            )
            add_action = getattr(menu, "addAction", None)
            if callable(add_action):
                add_action(action)

    def route_toggled_action(self, alias: str, action: object) -> None:
        """Read one QAction-like object and apply its checked state."""

        data_reader = getattr(action, "data", None)
        data = data_reader() if callable(data_reader) else {}
        node_name = data.get("node_name") if isinstance(data, Mapping) else None
        if not node_name:
            return
        is_checked = getattr(action, "isChecked", None)
        self.apply_toggle(
            alias,
            str(node_name),
            bool(is_checked()) if callable(is_checked) else False,
        )

    def apply_toggle(self, alias: str, node_name: str, checked: bool) -> None:
        """Persist one checked state through the behavior command surface."""

        cube_state = (
            self._host._cube_states.get(alias)
            if isinstance(self._host._cube_states, dict)
            else None
        )
        if cube_state is None:
            return
        set_override = getattr(
            self._host.node_behavior_service,
            "set_node_visibility_override",
            None,
        )
        if not callable(set_override):
            return
        set_override(cube_state, node_name, True if checked else None)
        self._host.refresh_node_behavior_state(reason="node_activation_changed")
        self.rebuild(alias)


__all__ = ["CubeVisibilityMenuController", "CubeVisibilityMenuHost"]
