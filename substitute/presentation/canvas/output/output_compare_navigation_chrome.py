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

"""Render comparison navigation chrome from document-backed Output state."""

from __future__ import annotations

from typing import Any

from sugarsubstitute_shared.presentation.localization import app_text
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    apply_compare_scene_button_state,
    apply_compare_source_button_state,
    apply_compare_set_button_state,
    compare_scene_full_text,
    selector_display_text_for_metrics,
    selector_font_metrics_for_widget,
    selector_width_for_metrics_text,
    sync_comparison_navigation_buttons,
)
from substitute.presentation.canvas.output.output_canvas_route_model import (
    OutputCanvasRouteModel,
)

_SCENE_SELECTOR_MIN_WIDTH = 58
_SCENE_SELECTOR_MAX_WIDTH = 260
_SCENE_SELECTOR_HORIZONTAL_PADDING = 28
_SOURCE_SELECTOR_MIN_WIDTH = 58
_SOURCE_SELECTOR_MAX_WIDTH = 260
_SOURCE_SELECTOR_HORIZONTAL_PADDING = 28


def sync_output_comparison_navigation_buttons(view: Any) -> None:
    """Refresh comparison navigation controls from the bound document host."""

    state = getattr(
        view,
        "_visible_compare_state",
        getattr(view, "output_compare_state", None),
    )
    sync_comparison_navigation_buttons(
        comparison_nav_container=getattr(view, "comparison_nav_container", None),
        enabled=bool(getattr(state, "enabled", False)),
        base_selection=getattr(state, "base", None),
        comparison_selection=getattr(state, "comparison", None),
        base_scene_button=getattr(view, "scene_selector_button", None),
        base_set_button=getattr(view, "set_selector_button", None),
        base_source_button=getattr(view, "source_selector_button", None),
        comparison_scene_button=getattr(
            view,
            "comparison_scene_selector_button",
            None,
        ),
        comparison_set_button=getattr(view, "comparison_set_selector_button", None),
        comparison_source_button=getattr(
            view,
            "comparison_source_selector_button",
            None,
        ),
        sync_scene_button=lambda _side, button, selection: (
            sync_output_compare_scene_button(
                view,
                button,
                selection,
            )
        ),
        sync_set_button=lambda side, button, selection: sync_output_compare_set_button(
            view,
            button,
            selection,
            side=side,
        ),
        sync_source_button=lambda _side, button, selection: (
            sync_output_compare_source_button(
                view,
                button,
                selection,
            )
        ),
    )


def sync_output_compare_scene_button(
    view: Any,
    button: object,
    selection: object,
) -> None:
    """Refresh one comparison scene selector from the current projection."""

    projection = getattr(view, "_output_projection", None)
    revision_cache = getattr(
        view,
        "_revision_cache",
        getattr(view, "_output_revision_cache", None),
    )
    scene_groups = OutputCanvasRouteModel.scene_groups_by_key(
        projection if isinstance(projection, OutputCanvasProjection) else None,
        preview_scene_groups_by_key=getattr(
            revision_cache,
            "preview_scene_groups_by_key",
            {},
        ),
    )
    scene_count = int(getattr(view, "scene_count", 0))
    full_text = compare_scene_full_text(
        scene_groups.values(),
        scene_key=getattr(selection, "scene_key", None),
        scene_count=scene_count,
    )
    font_metrics = selector_font_metrics_for_widget(button)
    display_text = selector_display_text_for_metrics(
        full_text,
        font_metrics=font_metrics,
        text_elide_mode=getattr(view, "_selector_text_elide_mode", None),
        max_width=_SCENE_SELECTOR_MAX_WIDTH,
        horizontal_padding=_SCENE_SELECTOR_HORIZONTAL_PADDING,
    )
    apply_compare_scene_button_state(
        button,
        full_text=full_text,
        display_text=display_text,
        width=selector_width_for_metrics_text(
            full_text,
            font_metrics=font_metrics,
            minimum_width=_SCENE_SELECTOR_MIN_WIDTH,
            maximum_width=_SCENE_SELECTOR_MAX_WIDTH,
            horizontal_padding=_SCENE_SELECTOR_HORIZONTAL_PADDING,
        ),
        scene_count=scene_count,
    )


def sync_output_compare_set_button(
    view: Any,
    button: object,
    selection: object,
    *,
    side: str,
) -> None:
    """Refresh one side's set selector from its comparison selection."""

    compare_controller = getattr(view, "_compare_controller", None)
    compare_set_count = getattr(compare_controller, "compare_set_count", None)
    set_count = int(compare_set_count(side)) if callable(compare_set_count) else 0
    apply_compare_set_button_state(
        button,
        set_index=int(getattr(selection, "set_index", 0)),
        set_count=set_count,
    )


def sync_output_compare_source_button(
    view: Any,
    button: object,
    selection: object,
) -> None:
    """Refresh one comparison source selector from the navigation controller."""

    compare_controller = getattr(view, "_compare_controller", None)
    compare_source_label = getattr(compare_controller, "compare_source_label", None)
    text = (
        str(compare_source_label(selection))
        if callable(compare_source_label)
        else render_application_text(app_text("Output"))
    )
    font_metrics = selector_font_metrics_for_widget(button)
    display_text = selector_display_text_for_metrics(
        text,
        font_metrics=font_metrics,
        text_elide_mode=getattr(view, "_selector_text_elide_mode", None),
        max_width=_SOURCE_SELECTOR_MAX_WIDTH,
        horizontal_padding=_SOURCE_SELECTOR_HORIZONTAL_PADDING,
    )
    apply_compare_source_button_state(
        button,
        full_text=text,
        display_text=display_text,
        width=selector_width_for_metrics_text(
            text,
            font_metrics=font_metrics,
            minimum_width=_SOURCE_SELECTOR_MIN_WIDTH,
            maximum_width=_SOURCE_SELECTOR_MAX_WIDTH,
            horizontal_padding=_SOURCE_SELECTOR_HORIZONTAL_PADDING,
        ),
    )


__all__: list[str] = []
