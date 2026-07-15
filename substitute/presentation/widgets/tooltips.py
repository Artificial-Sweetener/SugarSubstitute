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

"""Bind editor tooltip metadata to the shared QFluent tooltip system."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtWidgets import QWidget

from substitute.presentation.widgets.cursor_tooltip_filter import (
    CursorToolTipFilter,
    install_cursor_tooltip_filter,
)

_EDITOR_TOOLTIP_FILTER_ATTR = "_editor_tooltip_filter"


def normalized_tooltip(value: object) -> str | None:
    """Return stripped tooltip text when value is a non-empty string."""

    if not isinstance(value, str):
        return None
    tooltip = value.strip()
    return tooltip or None


def tooltip_from_field_meta(meta_info: Mapping[str, object]) -> str | None:
    """Return Comfy field tooltip text from resolved input metadata."""

    return normalized_tooltip(meta_info.get("tooltip"))


def tooltip_from_input_metadata(input_metadata: object) -> str | None:
    """Return field tooltip text from sanitized Qt input metadata."""

    if not isinstance(input_metadata, Mapping):
        return None
    direct_tooltip = normalized_tooltip(input_metadata.get("tooltip"))
    if direct_tooltip is not None:
        return direct_tooltip
    meta_info = input_metadata.get("meta_info")
    if isinstance(meta_info, Mapping):
        return tooltip_from_field_meta(meta_info)
    return None


def bind_fluent_tooltip(
    owner: QWidget,
    tooltip: str | None,
    *watched_widgets: QWidget,
    show_delay_ms: int = 600,
) -> CursorToolTipFilter | None:
    """Bind tooltip text to one owner-backed QFluent cursor tooltip filter."""

    text = tooltip or ""
    set_tooltip: Any = getattr(owner, "setToolTip", None)
    if callable(set_tooltip):
        set_tooltip(text)
    if not text:
        setattr(owner, _EDITOR_TOOLTIP_FILTER_ATTR, None)
        return None
    tooltip_filter = install_cursor_tooltip_filter(
        owner,
        *(watched_widgets or (owner,)),
        show_delay_ms=show_delay_ms,
    )
    setattr(owner, _EDITOR_TOOLTIP_FILTER_ATTR, tooltip_filter)
    return tooltip_filter
