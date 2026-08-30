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

"""Read autocomplete owner state for real-shell snapshots and tracing."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.support.prompt_editor.autocomplete_owner_state import (
    autocomplete_owner_state,
)


def autocomplete_preview_state(editor: PromptEditor) -> object | None:
    """Return projection-owned autocomplete preview state without popup state."""

    surface = getattr(editor, "_surface", None)
    session = getattr(surface, "_session", None)
    return getattr(session, "autocomplete_preview", None)


def autocomplete_preview_suffix(preview: object | None) -> str:
    """Return the projection-owned autocomplete preview suffix."""

    suffix = getattr(preview, "suffix_text", "")
    return suffix if isinstance(suffix, str) else ""


def autocomplete_preview_source_position(preview: object | None) -> int | None:
    """Return the projection-owned autocomplete preview source position."""

    position = getattr(preview, "source_position", None)
    return position if isinstance(position, int) else None


def compact_editor_state(editor: PromptEditor) -> dict[str, Any]:
    """Return cheap state used around observed production-owner calls."""

    cursor = cast(Any, editor).textCursor()
    preview = autocomplete_preview_state(editor)
    autocomplete_state = autocomplete_owner_state(editor)
    return {
        "source": editor.toPlainText(),
        "cursor": cursor.position(),
        "preview": (
            "<none>"
            if preview is None
            else (
                f"{autocomplete_preview_source_position(preview)}:"
                f"{autocomplete_preview_suffix(preview)!r}"
            )
        ),
        "session": (
            f"{autocomplete_state['lifecycle']}:"
            f"{autocomplete_state['mode']}:"
            f"{autocomplete_state['prefix']!r}:"
            f"{autocomplete_state['selected_index']}"
        ),
        "panel": (
            f"presenter={autocomplete_state['presenter_panel_visible']}:"
            f"active={autocomplete_state['has_active']}"
        ),
    }


def short_repr(value: object) -> str:
    """Return a bounded representation for observed call results."""

    text = repr(value)
    return f"{text[:117]}..." if len(text) > 120 else text


def autocomplete_panel(editor: PromptEditor) -> QWidget | None:
    """Return the composed autocomplete panel when normal construction created it."""

    panel = getattr(editor, "_autocomplete_panel", None)
    return panel if isinstance(panel, QWidget) else None


def expected_ghost_suffix(editor: PromptEditor, preview: object | None) -> str:
    """Return the diagnostic autocomplete preview suffix when available."""

    suffix = autocomplete_preview_suffix(preview)
    if suffix:
        return suffix
    autocomplete = getattr(editor, "_autocomplete", None)
    session = getattr(autocomplete, "_session_controller", None)
    current = getattr(session, "current_suggestion", None)
    if callable(current):
        suggestion = current()
        tag = getattr(suggestion, "tag", "")
        source = editor.toPlainText()
        if isinstance(tag, str) and tag.startswith(source):
            return tag[len(source) :]
    fallback_preview = getattr(editor, "_autocomplete_preview_state", None)
    fallback_suffix = getattr(fallback_preview, "suffix", "")
    return fallback_suffix if isinstance(fallback_suffix, str) else ""
