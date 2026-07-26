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

"""Read autocomplete owner state for real-shell harness assertions."""

from __future__ import annotations

from typing import Any


def autocomplete_owner_state(editor: object) -> dict[str, Any]:
    """Return session and presentation facts from their production owners."""

    autocomplete = getattr(editor, "_autocomplete", None)
    if autocomplete is None:
        interaction = getattr(editor, "_interaction_controller", None)
        autocomplete = getattr(interaction, "_autocomplete", None)
    publication = getattr(autocomplete, "_session_publication", None)
    state = getattr(publication, "state", None)
    session = getattr(state, "session", None)
    ghost_snapshot = getattr(state, "ghost_text_source_snapshot", None)
    suggestions = tuple(
        suggestion.tag
        for suggestion in getattr(session, "suggestions", ())
        if isinstance(getattr(suggestion, "tag", None), str)
    )
    has_active_session = getattr(publication, "has_active_session", None)
    panel_visible = getattr(publication, "panel_visible", None)
    panel_under_mouse = getattr(publication, "panel_under_mouse", None)
    return {
        "lifecycle": _safe_enum_value(getattr(state, "lifecycle", "idle")),
        "mode": str(getattr(session, "mode", "none")),
        "selected_index": int(getattr(session, "selected_index", -1)),
        "prefix": str(getattr(session, "prefix", "")),
        "word_start": getattr(session, "word_start", None),
        "word_end": getattr(session, "word_end", None),
        "active_tag_end": getattr(session, "active_tag_end", None),
        "suggestions": suggestions,
        "has_active": bool(has_active_session())
        if callable(has_active_session)
        else False,
        "presenter_panel_visible": bool(panel_visible())
        if callable(panel_visible)
        else False,
        "presenter_panel_under_mouse": bool(panel_under_mouse())
        if callable(panel_under_mouse)
        else False,
        "source_revision": getattr(ghost_snapshot, "source_revision", None),
        "snapshot_source_length": getattr(ghost_snapshot, "source_length", None),
        "snapshot_cursor_position": getattr(ghost_snapshot, "cursor_position", None),
    }


def _safe_enum_value(value: object) -> str:
    """Return a stable string for enum-like state values."""

    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return str(value)
