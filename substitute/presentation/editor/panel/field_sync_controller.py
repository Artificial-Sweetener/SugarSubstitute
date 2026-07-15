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

"""Own editor-panel hidden-field and search visibility synchronization."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

import shiboken6

from substitute.presentation.editor.panel.widgets.node_card import (
    reconcile_node_card_body_separators,
)


class FieldSyncSnapshotProtocol(Protocol):
    """Describe the behavior snapshot payload consumed by field sync."""

    hidden_field_keys_by_alias: Mapping[str, set[object]]


class EditorPanelFieldSyncHost(Protocol):
    """Describe panel state required for field synchronization."""

    cube_widgets: Mapping[str, object]
    row_widgets: Mapping[object, tuple[object | None, object | None]]
    col_widgets: Mapping[object, tuple[object | None, object | None, object | None]]
    card_wrappers: Mapping[tuple[str, str], object]
    _hidden_field_keys: set[object]
    _field_search_active: bool
    _search_field_match_keys: set[object] | None

    def _build_behavior_snapshot(
        self,
        *,
        search_hidden_keys: set[object] | None = None,
        node_search_text: str | None = None,
    ) -> FieldSyncSnapshotProtocol | None:
        """Build the latest hidden-field snapshot for the active panel state."""


class EditorPanelFieldSyncController:
    """Coordinate row, column, card, and search-driven field visibility."""

    def __init__(self, host: EditorPanelFieldSyncHost) -> None:
        """Store the panel host whose field state is managed."""

        self._host = host

    def update_all_hidden_fields(
        self,
        *,
        overrides: object = None,
        search_hidden_keys: set[object] | None = None,
    ) -> None:
        """Recompute and apply merged hidden keys from the latest snapshot."""

        _ = overrides
        snapshot = self._host._build_behavior_snapshot(
            search_hidden_keys=set(search_hidden_keys or set()),
        )
        if snapshot is None:
            self.apply_hidden_field_keys(set())
            return

        merged_hidden: set[object] = set()
        for keys in snapshot.hidden_field_keys_by_alias.values():
            merged_hidden.update(keys)
        self.apply_hidden_field_keys(merged_hidden)

    def set_hidden_field_keys(self, hidden_keys: set[object]) -> None:
        """Apply one hidden-field set through the field-sync owner."""

        self.apply_hidden_field_keys(set(hidden_keys))

    def set_search_field_match_keys(
        self,
        match_keys: set[tuple[str, str, str]] | None,
        *,
        active: bool,
    ) -> None:
        """Apply field-search matches and refresh current row/card visibility."""

        self._host._field_search_active = active
        self._host._search_field_match_keys = (
            None if match_keys is None else set(match_keys)
        )
        self.apply_hidden_field_keys(set(self._host._hidden_field_keys))

    def apply_hidden_field_keys(self, hidden_keys: set[object]) -> None:
        """Apply one hidden-key set to tracked rows, columns, and cards."""

        self._host._hidden_field_keys = set(hidden_keys)
        self._apply_row_visibility(hidden_keys)
        self._apply_column_visibility(hidden_keys)
        self._reconcile_node_card_body_separators()
        self._apply_empty_card_visibility(hidden_keys)

    @staticmethod
    def _is_hidden(field_key: object, hidden_keys: set[object]) -> bool:
        """Return whether one field key should currently be hidden."""

        return bool(
            field_key in hidden_keys
            or (isinstance(field_key, tuple) and field_key[-1] in hidden_keys)
            or (isinstance(field_key, str) and field_key in hidden_keys)
        )

    @staticmethod
    def _matches_field_search(
        host: EditorPanelFieldSyncHost,
        field_key: object,
    ) -> bool:
        """Return whether one field should stay visible for active field search."""

        if not getattr(host, "_field_search_active", False):
            return True
        match_keys = getattr(host, "_search_field_match_keys", None)
        if match_keys is None:
            return False
        if field_key in match_keys:
            return True
        return bool(isinstance(field_key, tuple) and field_key[-1] in match_keys)

    @staticmethod
    def _is_live_widget(widget: object | None) -> bool:
        """Return whether one widget-like object is still safe to manipulate."""

        if widget is None:
            return False
        try:
            return bool(shiboken6.isValid(widget))
        except TypeError:
            return True

    @staticmethod
    def _normalized_field_key(value: object) -> object:
        """Normalize list-backed Qt dynamic properties into tuple keys."""

        if isinstance(value, list):
            return tuple(value)
        return value

    def _apply_row_visibility(self, hidden_keys: set[object]) -> None:
        """Update single-row widgets and dividers for the current hidden keys."""

        for field_key, (divider, row_widget) in self._host.row_widgets.items():
            hide = self._is_hidden(
                field_key, hidden_keys
            ) or not self._matches_field_search(self._host, field_key)
            self._set_widget_visible(divider, not hide)
            self._set_widget_visible(row_widget, not hide)

    def _apply_column_visibility(self, hidden_keys: set[object]) -> None:
        """Update grouped-column rows, vertical dividers, and row containers."""

        row_container_to_columns: dict[object, list[tuple[object | None, bool]]] = {}
        for field_key, (
            row_container,
            col_widget,
            _input_widget,
        ) in self._host.col_widgets.items():
            hide = self._is_hidden(
                field_key, hidden_keys
            ) or not self._matches_field_search(self._host, field_key)
            self._set_widget_visible(col_widget, not hide)
            row_container_to_columns.setdefault(row_container, []).append(
                (
                    col_widget,
                    hide,
                )
            )

        for row_container, columns in row_container_to_columns.items():
            self._apply_row_container_visibility(row_container, columns)

    def _apply_row_container_visibility(
        self,
        row_container: object,
        columns: list[tuple[object | None, bool]],
    ) -> None:
        """Apply row-container and divider visibility for one grouped row."""

        num_visible = sum(not hide for _, hide in columns)
        for col_widget, hide in columns:
            self._apply_vertical_dividers(
                col_widget, hide=hide, num_visible=num_visible
            )

        all_hidden = all(hide for _, hide in columns)
        self._set_widget_visible(row_container, not all_hidden)

        if columns:
            self._apply_horizontal_divider(columns[0][0], all_hidden=all_hidden)

    def _apply_vertical_dividers(
        self,
        col_widget: object | None,
        *,
        hide: bool,
        num_visible: int,
    ) -> None:
        """Update vertical dividers attached to one grouped column widget."""

        if not self._is_live_widget(col_widget):
            return

        parent_getter = getattr(col_widget, "parentWidget", None)
        parent_widget = parent_getter() if callable(parent_getter) else None
        if parent_widget is None:
            return
        layout_getter = getattr(parent_widget, "layout", None)
        layout = layout_getter() if callable(layout_getter) else None
        if layout is None:
            return

        field_key = self._normalized_field_key(
            self._widget_property(col_widget, "field_key")
        )
        for index in range(layout.count()):
            widget = layout.itemAt(index).widget()
            if widget is None:
                continue
            divider_key = self._normalized_field_key(
                widget.property("vertical_divider_for_field")
            )
            if divider_key != field_key:
                continue
            if num_visible <= 1:
                self._set_widget_visible(widget, False)
            else:
                self._set_widget_visible(widget, not hide)

    def _apply_horizontal_divider(
        self,
        first_col_widget: object | None,
        *,
        all_hidden: bool,
    ) -> None:
        """Update the grouped-row horizontal divider keyed by the first column."""

        if not self._is_live_widget(first_col_widget):
            return

        field_key = self._normalized_field_key(
            self._widget_property(first_col_widget, "field_key")
        )
        if field_key not in self._host.row_widgets:
            return

        divider, _ = self._host.row_widgets[field_key]
        self._set_widget_visible(divider, not all_hidden)

    def _reconcile_node_card_body_separators(self) -> None:
        """Let node-card bodies enforce visible-row separator adjacency."""

        row_widgets = getattr(self._host, "row_widgets", {})
        if isinstance(row_widgets, Mapping):
            reconcile_node_card_body_separators(row_widgets)

    def _apply_empty_card_visibility(self, hidden_keys: set[object]) -> None:
        """Hide policy-visible cards when no local rows remain visible."""

        card_wrappers = getattr(self._host, "card_wrappers", {})
        if not isinstance(card_wrappers, Mapping):
            return
        for card_key, wrapper in card_wrappers.items():
            if (
                not isinstance(card_key, tuple)
                or len(card_key) != 2
                or not isinstance(card_key[0], str)
                or not isinstance(card_key[1], str)
            ):
                continue
            if not self._is_live_widget(wrapper):
                continue
            alias, node_name = card_key
            final_visible = self._wrapper_base_visible(wrapper) and (
                self._wrapper_has_title_controls(wrapper)
                or self._card_has_visible_fields(
                    alias=alias,
                    node_name=node_name,
                    hidden_keys=hidden_keys,
                )
            )
            self._set_card_visible(wrapper, final_visible)

    def _card_has_visible_fields(
        self,
        *,
        alias: str,
        node_name: str,
        hidden_keys: set[object],
    ) -> bool:
        """Return whether one card has at least one tuple-scoped visible field."""

        for field_key in self._card_field_keys(alias=alias, node_name=node_name):
            if not self._is_hidden(
                field_key, hidden_keys
            ) and self._matches_field_search(self._host, field_key):
                return True
        return False

    def _card_field_keys(self, *, alias: str, node_name: str) -> set[object]:
        """Return tuple-scoped row and column keys owned by one card."""

        field_keys: set[object] = set()
        for field_key in self._host.row_widgets:
            normalized_key = self._normalized_field_key(field_key)
            if self._is_card_field_key(
                normalized_key,
                alias=alias,
                node_name=node_name,
            ):
                field_keys.add(normalized_key)
        for field_key in self._host.col_widgets:
            normalized_key = self._normalized_field_key(field_key)
            if self._is_card_field_key(
                normalized_key,
                alias=alias,
                node_name=node_name,
            ):
                field_keys.add(normalized_key)
        return field_keys

    @staticmethod
    def _is_card_field_key(
        field_key: object,
        *,
        alias: str,
        node_name: str,
    ) -> bool:
        """Return whether a normalized key identifies a field on one card."""

        return bool(
            isinstance(field_key, tuple)
            and len(field_key) >= 3
            and field_key[0] == alias
            and field_key[1] == node_name
        )

    @staticmethod
    def _widget_property(widget: object | None, name: str) -> object:
        """Return one Qt-style dynamic property when the widget exposes it."""

        property_getter = getattr(widget, "property", None)
        if not callable(property_getter):
            return None
        try:
            return property_getter(name)
        except (RuntimeError, TypeError):
            return None

    def _set_widget_visible(self, widget: object | None, visible: bool) -> None:
        """Set widget visibility when the object is live and exposes the method."""

        if not self._is_live_widget(widget):
            return
        set_visible = getattr(widget, "setVisible", None)
        if callable(set_visible):
            set_visible(bool(visible))

    def _wrapper_has_title_controls(self, wrapper: object) -> bool:
        """Return whether a card wrapper contains title-level controls."""

        return self._widget_property(wrapper, "has_title_controls") is True

    def _wrapper_base_visible(self, wrapper: object) -> bool:
        """Return the node policy/search visibility stored on one wrapper."""

        base_visible = self._widget_property(wrapper, "base_card_visible")
        return True if base_visible is None else bool(base_visible)

    def _set_card_visible(self, wrapper: object, visible: bool) -> None:
        """Apply final empty-card visibility and refresh the owning cube height."""

        previous_visible = self._widget_is_visible(wrapper)
        set_visible = getattr(wrapper, "setVisible", None)
        if not callable(set_visible):
            return
        set_visible(bool(visible))
        if previous_visible is None or previous_visible != bool(visible):
            self._refresh_owner_cube_height(wrapper)

    @staticmethod
    def _widget_is_visible(widget: object) -> bool | None:
        """Return current widget visibility when available."""

        is_visible = getattr(widget, "isVisible", None)
        if not callable(is_visible):
            return None
        try:
            return bool(is_visible())
        except (RuntimeError, TypeError):
            return None

    @staticmethod
    def _refresh_owner_cube_height(widget: object) -> None:
        """Ask the nearest cube section parent to recompute its height."""

        parent_getter = getattr(widget, "parentWidget", None)
        parent = parent_getter() if callable(parent_getter) else None
        while parent is not None:
            defer_update = getattr(parent, "defer_update_cube_height", None)
            if callable(defer_update):
                defer_update()
                return
            update = getattr(parent, "update_cube_height", None)
            if callable(update):
                update()
                return
            parent_getter = getattr(parent, "parentWidget", None)
            parent = parent_getter() if callable(parent_getter) else None


__all__ = [
    "EditorPanelFieldSyncController",
    "EditorPanelFieldSyncHost",
    "FieldSyncSnapshotProtocol",
]
