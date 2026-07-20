#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Refresh locale-sensitive Output canvas chrome without replacing canvas state."""

from __future__ import annotations

from typing import Protocol, cast

from substitute.presentation.canvas.output.output_canvas_navigation_chrome import (
    update_output_tabbar_container,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    sync_output_scene_selector_button,
    sync_output_source_selector_button,
)
from substitute.presentation.canvas.output.output_compare_projection_presenter import (
    sync_output_comparison_navigation_buttons,
)


class _SourceTabs(Protocol):
    """Describe the locale refresh exposed by the source-tab owner."""

    def retranslate_source_tabs(self, *, active_source_key: str | None) -> None:
        """Rebuild translated source tabs while preserving selection."""


def retranslate_output_canvas(host: object) -> None:
    """Refresh all app-owned Output labels after a Qt language change."""

    runtime = getattr(host, "_runtime", None)
    navigation = getattr(runtime, "navigation", None)
    source_tabs = getattr(navigation, "source_tabs", None)
    if source_tabs is not None:
        cast(_SourceTabs, source_tabs).retranslate_source_tabs(
            active_source_key=_active_source_key(host)
        )
    sync_output_scene_selector_button(host)
    sync_output_source_selector_button(host)
    sync_output_comparison_navigation_buttons(host)
    update_output_tabbar_container(host)


def _active_source_key(host: object) -> str | None:
    """Return one valid source key from an opaque Output host."""

    value = getattr(host, "active_source_key", None)
    return value if isinstance(value, str) else None


__all__ = ["retranslate_output_canvas"]
