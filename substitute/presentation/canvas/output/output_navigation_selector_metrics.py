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

"""Measure and elide Output navigation selector text."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_navigation_selector_state import (
    scene_selector_full_text,
    source_selector_full_text,
)


def selector_display_text(
    text: str,
    *,
    text_width: int,
    max_width: int,
    horizontal_padding: int,
    elide_text: Callable[[str, int], str] | None = None,
    fallback_chrome_width: int = 36,
) -> str:
    """Return selector text that fits the bounded content area."""

    available_width = max_width - horizontal_padding
    if text_width <= available_width:
        return text
    if elide_text is not None:
        return elide_text(text, available_width)
    max_chars = max(1, (max_width - fallback_chrome_width) // 7)
    return text if len(text) <= max_chars else f"{text[: max_chars - 1]}..."


def selector_width_for_text(
    text_width: int,
    *,
    minimum_width: int,
    maximum_width: int,
    horizontal_padding: int,
) -> int:
    """Return selector width bounded by design chrome limits."""

    desired_width = text_width + horizontal_padding
    return max(minimum_width, min(maximum_width, desired_width))


def selector_text_width(text: str, font_metrics: object) -> int:
    """Measure selector text with host font metrics and a deterministic fallback."""

    horizontal_advance = getattr(font_metrics, "horizontalAdvance", None)
    if callable(horizontal_advance):
        return int(horizontal_advance(text))
    return len(text) * 7


def selector_font_metrics_for_widget(widget: object | None) -> object:
    """Return selector font metrics from an opaque host widget when available."""

    font_metrics = getattr(widget, "fontMetrics", None)
    if callable(font_metrics):
        return font_metrics()
    return object()


def selector_display_text_for_metrics(
    text: str,
    *,
    font_metrics: object,
    text_elide_mode: object | None,
    max_width: int,
    horizontal_padding: int,
) -> str:
    """Return selector display text using host elision when available."""

    elided_text = getattr(font_metrics, "elidedText", None)
    elide_adapter = (
        (lambda value, width: str(elided_text(value, text_elide_mode, width)))
        if callable(elided_text) and text_elide_mode is not None
        else None
    )
    return selector_display_text(
        text,
        text_width=selector_text_width(text, font_metrics),
        max_width=max_width,
        horizontal_padding=horizontal_padding,
        elide_text=elide_adapter,
    )


def selector_width_for_metrics_text(
    text: str,
    *,
    font_metrics: object,
    minimum_width: int,
    maximum_width: int,
    horizontal_padding: int,
) -> int:
    """Return bounded selector width using host font metrics."""

    return selector_width_for_text(
        selector_text_width(text, font_metrics),
        minimum_width=minimum_width,
        maximum_width=maximum_width,
        horizontal_padding=horizontal_padding,
    )


def selector_width_for_widget_text(
    text: str,
    *,
    widget: object | None,
    minimum_width: int,
    maximum_width: int,
    horizontal_padding: int,
) -> int:
    """Return bounded selector width using an opaque host widget's metrics."""

    return selector_width_for_metrics_text(
        text,
        font_metrics=selector_font_metrics_for_widget(widget),
        minimum_width=minimum_width,
        maximum_width=maximum_width,
        horizontal_padding=horizontal_padding,
    )


def selector_current_width(
    widget: object | None,
    *,
    minimum_width: int,
    fallback_width: int,
) -> int:
    """Return live selector width when settled, otherwise the fallback width."""

    widget_width = getattr(widget, "width", None)
    width = int(widget_width()) if callable(widget_width) else 0
    if width > minimum_width:
        return width
    return fallback_width


def scene_selector_current_width(
    scene_groups: Iterable[OutputCanvasSceneGroup],
    *,
    active_scene_key: str | None,
    active_scene_overview: bool,
    widget: object | None,
    minimum_width: int,
    maximum_width: int,
    horizontal_padding: int,
) -> int:
    """Return current scene selector width with label-aware fallback."""

    full_text = scene_selector_full_text(
        scene_groups,
        active_scene_key=active_scene_key,
        active_scene_overview=active_scene_overview,
    )
    fallback_width = selector_width_for_metrics_text(
        full_text,
        font_metrics=selector_font_metrics_for_widget(widget),
        minimum_width=minimum_width,
        maximum_width=maximum_width,
        horizontal_padding=horizontal_padding,
    )
    return selector_current_width(
        widget,
        minimum_width=minimum_width,
        fallback_width=fallback_width,
    )


def source_selector_current_width(
    sources: Iterable[OutputCanvasSourceGroup],
    *,
    active_source_key: str | None,
    widget: object | None,
    minimum_width: int,
    maximum_width: int,
    horizontal_padding: int,
) -> int:
    """Return current source selector width with label-aware fallback."""

    full_text = source_selector_full_text(
        sources,
        active_source_key=active_source_key,
    )
    fallback_width = selector_width_for_metrics_text(
        full_text,
        font_metrics=selector_font_metrics_for_widget(widget),
        minimum_width=minimum_width,
        maximum_width=maximum_width,
        horizontal_padding=horizontal_padding,
    )
    return selector_current_width(
        widget,
        minimum_width=minimum_width,
        fallback_width=fallback_width,
    )


__all__ = [
    "scene_selector_current_width",
    "selector_current_width",
    "selector_display_text",
    "selector_display_text_for_metrics",
    "selector_font_metrics_for_widget",
    "selector_text_width",
    "selector_width_for_metrics_text",
    "selector_width_for_text",
    "selector_width_for_widget_text",
    "source_selector_current_width",
]
