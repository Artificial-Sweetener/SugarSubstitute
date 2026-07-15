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

"""Provide structured prompt editor owner-state debug logging."""

from __future__ import annotations

from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.editor.prompt_editor.debug_probe")
_MAX_TEXT_LENGTH = 1800


def log_prompt_editor_probe(event: str, **payload: object) -> None:
    """Log one prompt editor owner-state event when debug logging is enabled."""

    log_debug(
        _LOGGER,
        event,
        **{key: _json_safe(value) for key, value in payload.items()},
    )


def surface_probe_state(surface: object) -> dict[str, object]:
    """Return compact projection, paint-cache, and caret state."""

    session = getattr(surface, "_session", None)
    preview = getattr(session, "autocomplete_preview", None)
    document_view = getattr(surface, "_document_view", None)
    projection_document = getattr(surface, "_projection_document", None)
    active_projection_document = getattr(surface, "_active_projection_document", None)
    layout = getattr(surface, "_layout", None)
    paint_cache = getattr(surface, "_projection_paint_cache", None)
    freshness_controller = getattr(surface, "_projection_freshness_controller", None)
    pending_update = getattr(freshness_controller, "has_pending_update", None)
    stale_geometry = getattr(
        freshness_controller,
        "has_stale_projection_geometry",
        None,
    )
    return {
        "surface_id": id(surface),
        "source_text": _text(_call(surface, "toPlainText")),
        "cursor_position": _safe_int(getattr(surface, "cursor_position", None)),
        "anchor_position": _safe_int(getattr(surface, "anchor_position", None)),
        "preview": preview_probe_state(preview),
        "document_view_source_text": _text(getattr(document_view, "source_text", "")),
        "projection_source_text": _text(
            getattr(projection_document, "source_text", "")
        ),
        "active_projection_source_text": _text(
            getattr(active_projection_document, "source_text", "")
        ),
        "projection_text": _text(getattr(projection_document, "projection_text", "")),
        "active_projection_text": _text(
            getattr(active_projection_document, "projection_text", "")
        ),
        "layout_projection_document_id": id(
            getattr(layout, "projection_document", None)
        ),
        "base_projection_document_id": id(projection_document),
        "active_projection_document_id": id(active_projection_document),
        "paint_cache_key_present": getattr(paint_cache, "cache_key", None) is not None,
        "paint_cache_key": repr(getattr(paint_cache, "cache_key", None)),
        "projection_pending": bool(pending_update())
        if callable(pending_update)
        else False,
        "projection_stale_geometry": bool(stale_geometry())
        if callable(stale_geometry)
        else False,
    }


def autocomplete_probe_state(coordinator: object) -> dict[str, object]:
    """Return compact autocomplete lifecycle and presenter state."""

    sessions = getattr(coordinator, "_sessions", None)
    state = getattr(sessions, "state", None)
    session = getattr(state, "session", None)
    presenter = getattr(coordinator, "_presenter", None)
    has_active_session = getattr(sessions, "has_active_session", None)
    panel_visible = getattr(presenter, "panel_visible", None)
    suggestions = tuple(
        str(getattr(suggestion, "tag", ""))
        for suggestion in getattr(session, "suggestions", ())
    )
    return {
        "autocomplete_id": id(coordinator),
        "lifecycle": _enum_value(getattr(state, "lifecycle", "missing")),
        "mode": str(getattr(session, "mode", "missing")),
        "prefix": str(getattr(session, "prefix", "")),
        "word_start": _safe_int(getattr(session, "word_start", None)),
        "word_end": _safe_int(getattr(session, "word_end", None)),
        "active_tag_end": _safe_int(getattr(session, "active_tag_end", None)),
        "selected_index": _safe_int(getattr(session, "selected_index", None)),
        "suggestions": suggestions[:8],
        "has_active_session": bool(has_active_session())
        if callable(has_active_session)
        else False,
        "panel_visible": bool(panel_visible()) if callable(panel_visible) else False,
    }


def preview_probe_state(preview: object | None) -> dict[str, object] | None:
    """Return compact autocomplete preview state."""

    if preview is None:
        return None
    return {
        "source_position": _safe_int(getattr(preview, "source_position", None)),
        "suffix_text": _text(getattr(preview, "suffix_text", "")),
    }


def _call(target: object, method_name: str) -> object:
    """Call a no-arg method when available."""

    method = getattr(target, method_name, None)
    if not callable(method):
        return ""
    try:
        return method()
    except Exception:
        return "<probe-call-failed>"


def _json_safe(value: object) -> object:
    """Return a JSON-safe representation for probe payload values."""

    if value is None or isinstance(value, bool | int | float | str):
        return _text(value) if isinstance(value, str) else value
    if isinstance(value, tuple | list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return repr(value)


def _text(value: object) -> str:
    """Return a bounded text value for the probe log."""

    text = str(value)
    if len(text) <= _MAX_TEXT_LENGTH:
        return text
    return f"{text[:_MAX_TEXT_LENGTH]}...<truncated:{len(text)}>"


def _safe_int(value: object) -> int | None:
    """Return integer values without bool coercion."""

    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _enum_value(value: object) -> str:
    """Return a stable string for enum-like objects."""

    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return str(value)


__all__ = [
    "autocomplete_probe_state",
    "log_prompt_editor_probe",
    "preview_probe_state",
    "surface_probe_state",
]
