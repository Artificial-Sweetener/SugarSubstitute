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

"""Declare the editor-panel state consumed by field synchronization."""

from __future__ import annotations

from typing import Protocol


class FieldSyncSnapshotProtocol(Protocol):
    """Describe the behavior snapshot payload consumed by field sync."""

    hidden_field_keys_by_alias: dict[str, set[object]]


class EditorPanelFieldSyncHost(Protocol):
    """Describe panel state required for field synchronization."""

    cube_widgets: dict[str, object]
    row_widgets: dict[object, tuple[object | None, object | None]]
    col_widgets: dict[object, tuple[object | None, object | None, object | None]]
    card_wrappers: dict[tuple[str, str], object]
    _hidden_field_keys: set[object]
    _field_search_active: bool
    _search_field_match_keys: set[object] | None
    advanced_field_keys: set[object]
    shown_advanced_input_nodes: set[tuple[str, str]]

    def _build_behavior_snapshot(
        self,
        *,
        search_hidden_keys: set[object] | None = None,
        node_search_text: str | None = None,
    ) -> FieldSyncSnapshotProtocol | None:
        """Build the latest hidden-field snapshot for the active panel state."""


__all__ = ["EditorPanelFieldSyncHost", "FieldSyncSnapshotProtocol"]
