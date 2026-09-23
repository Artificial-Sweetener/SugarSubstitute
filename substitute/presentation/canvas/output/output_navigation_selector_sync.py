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

"""Synchronize normal Output selector widgets from visible route state."""

from __future__ import annotations

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_canvas_navigation_visibility import (
    OutputCanvasNavigationVisibilityPolicy,
    OutputNavigationVisibility,
)
from substitute.presentation.canvas.output.output_canvas_route_state import (
    output_route_state_snapshot,
    output_scene_groups_by_key,
    visible_output_source_groups_by_key,
)
from substitute.presentation.canvas.output.output_navigation_selector_metrics import (
    selector_display_text_for_metrics,
    selector_font_metrics_for_widget,
    selector_width_for_metrics_text,
)
from substitute.presentation.canvas.output.output_navigation_selector_state import (
    scene_selector_full_text,
    source_selector_full_text,
)
from substitute.presentation.canvas.output.output_navigation_widget_adapter import (
    apply_scene_selector_button_state,
    apply_set_selector_button_state,
    apply_source_selector_button_state,
)

_SCENE_SELECTOR_MIN_WIDTH = 58
_SCENE_SELECTOR_MAX_WIDTH = 260
_SCENE_SELECTOR_HORIZONTAL_PADDING = 28
_SOURCE_SELECTOR_MIN_WIDTH = 58
_SOURCE_SELECTOR_MAX_WIDTH = 260
_SOURCE_SELECTOR_HORIZONTAL_PADDING = 28


def sync_output_scene_selector_button(host: object) -> None:
    """Refresh the normal scene selector from an opaque Output host."""

    button = getattr(host, "scene_selector_button", None)
    scene_groups = _scene_groups_for_host(host)
    full_text = scene_selector_full_text(
        scene_groups.values(),
        active_scene_key=getattr(host, "active_scene_key", None),
        active_scene_overview=bool(getattr(host, "active_scene_overview", False)),
    )
    font_metrics = selector_font_metrics_for_widget(button)
    display_text = selector_display_text_for_metrics(
        full_text,
        font_metrics=font_metrics,
        text_elide_mode=getattr(host, "_selector_text_elide_mode", None),
        max_width=_SCENE_SELECTOR_MAX_WIDTH,
        horizontal_padding=_SCENE_SELECTOR_HORIZONTAL_PADDING,
    )
    apply_scene_selector_button_state(
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
        visible=_normal_visibility_for_host(host).show_scene_selector,
    )


def sync_output_set_selector_button(host: object) -> None:
    """Refresh the normal set selector from an opaque Output host."""

    apply_set_selector_button_state(
        getattr(host, "set_selector_button", None),
        active_set_index=int(getattr(host, "active_set_index", 0)),
        visible=_normal_visibility_for_host(host).show_set_selector,
    )


def sync_output_source_selector_button(host: object) -> None:
    """Refresh the collapsed source selector from an opaque Output host."""

    button = getattr(host, "source_selector_button", None)
    if button is None:
        return
    sources = _visible_source_groups_for_host(host)
    full_text = source_selector_full_text(
        sources.values(),
        active_source_key=getattr(host, "active_source_key", None),
    )
    font_metrics = selector_font_metrics_for_widget(button)
    display_text = selector_display_text_for_metrics(
        full_text,
        font_metrics=font_metrics,
        text_elide_mode=getattr(host, "_selector_text_elide_mode", None),
        max_width=_SOURCE_SELECTOR_MAX_WIDTH,
        horizontal_padding=_SOURCE_SELECTOR_HORIZONTAL_PADDING,
    )
    apply_source_selector_button_state(
        button,
        full_text=full_text,
        display_text=display_text,
        width=selector_width_for_metrics_text(
            full_text,
            font_metrics=font_metrics,
            minimum_width=_SOURCE_SELECTOR_MIN_WIDTH,
            maximum_width=_SOURCE_SELECTOR_MAX_WIDTH,
            horizontal_padding=_SOURCE_SELECTOR_HORIZONTAL_PADDING,
        ),
        visible=(
            bool(getattr(host, "_source_tabs_collapsed", False))
            and _normal_visibility_for_host(host).show_source_navigation
        ),
    )


def _normal_visibility_for_host(host: object) -> OutputNavigationVisibility:
    """Return authoritative normal navigation visibility for an opaque host."""

    return OutputCanvasNavigationVisibilityPolicy.normal(
        scene_count=int(getattr(host, "scene_count", 0)),
        source_count=len(getattr(getattr(host, "tabbar", None), "items", {})),
        set_count=int(getattr(host, "set_count", 0)),
        active_scene_overview=bool(getattr(host, "active_scene_overview", False)),
    )


def _visible_source_groups_for_host(
    host: object,
) -> dict[str, OutputCanvasSourceGroup]:
    """Return visible source groups for the host's current scene context."""

    document_navigation = getattr(host, "_document_navigation", None)
    visible_sources = getattr(document_navigation, "visible_sources", None)
    if callable(visible_sources):
        return dict(visible_sources())
    return visible_output_source_groups_by_key(output_route_state_snapshot(host))


def _scene_groups_for_host(host: object) -> dict[str, OutputCanvasSceneGroup]:
    """Return scene groups from the composed navigation owner when available."""

    document_navigation = getattr(host, "_document_navigation", None)
    scene_groups = getattr(document_navigation, "scene_groups", None)
    if callable(scene_groups):
        return dict(scene_groups())
    return output_scene_groups_by_key(output_route_state_snapshot(host))


__all__ = [
    "sync_output_scene_selector_button",
    "sync_output_set_selector_button",
    "sync_output_source_selector_button",
]
