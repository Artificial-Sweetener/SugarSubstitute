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

"""Build Output canvas navigation-bar tab decisions without owning widgets."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_source_tooltip_presenter import (
    source_tab_tooltip_text,
)

SourceTabSignature = tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class SourceTabTooltip:
    """Describe the tooltip content and hover behavior for one source tab."""

    source_key: str
    text: str
    installs_hover_filter: bool


@dataclass(frozen=True, slots=True)
class SourceTabsRebuildPlan:
    """Describe whether source tabs need Qt reconstruction."""

    signature: SourceTabSignature
    rebuild_required: bool
    active_source_key: str | None


@dataclass(frozen=True, slots=True)
class SourceTabItem:
    """Describe one source tab to add to the Qt tabbar."""

    source_key: str
    label: str
    source: OutputCanvasSourceGroup


@dataclass(frozen=True, slots=True)
class SourceTabTooltipRefreshItem:
    """Describe one source tab whose tooltip should be refreshed."""

    source_key: str
    source: OutputCanvasSourceGroup
    tab_item: object


@dataclass(frozen=True, slots=True)
class SourceSelectorButtonState:
    """Describe collapsed source selector button presentation state."""

    text: str
    tooltip: str
    width: int
    visible: bool


@dataclass(frozen=True, slots=True)
class SetSelectorButtonState:
    """Describe set selector button presentation state."""

    text: str
    visible: bool


@dataclass(frozen=True, slots=True)
class SceneSelectorButtonState:
    """Describe scene selector button presentation state."""

    text: str
    tooltip: str
    width: int
    visible: bool


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


def source_tab_signature(
    sources: Iterable[OutputCanvasSourceGroup],
) -> SourceTabSignature:
    """Return stable source-tab identity values for rebuild cache checks."""

    return tuple((source.source_key, source.label) for source in sources)


def source_tabs_rebuild_plan(
    sources: Iterable[OutputCanvasSourceGroup],
    *,
    cached_signature: SourceTabSignature | None,
    active_source_key: str | None,
) -> SourceTabsRebuildPlan:
    """Return whether source tabs must be rebuilt from visible source identity."""

    signature = source_tab_signature(sources)
    return SourceTabsRebuildPlan(
        signature=signature,
        rebuild_required=signature != cached_signature,
        active_source_key=active_source_key,
    )


def source_tab_items(
    sources: Iterable[OutputCanvasSourceGroup],
) -> tuple[SourceTabItem, ...]:
    """Return source-tab add instructions in visible source order."""

    return tuple(
        SourceTabItem(
            source_key=source.source_key,
            label=source.label,
            source=source,
        )
        for source in sources
    )


def source_tab_removal_keys(tab_items: Mapping[str, object]) -> tuple[str, ...]:
    """Return source-tab keys to remove using a stable key snapshot."""

    return tuple(tab_items.keys())


def source_tab_tooltip(
    source: OutputCanvasSourceGroup,
    *,
    active_set_index: int,
) -> SourceTabTooltip:
    """Return the tooltip plan for one source tab."""

    text = source_tab_tooltip_text(source, active_set_index=active_set_index)
    return SourceTabTooltip(
        source_key=source.source_key,
        text=text,
        installs_hover_filter=bool(text),
    )


def source_tab_tooltip_refresh_items(
    sources: Iterable[OutputCanvasSourceGroup],
    tab_items: Mapping[str, object],
) -> tuple[SourceTabTooltipRefreshItem, ...]:
    """Return visible source/tab pairs that can receive refreshed tooltips."""

    return tuple(
        SourceTabTooltipRefreshItem(
            source_key=source.source_key,
            source=source,
            tab_item=tab_item,
        )
        for source in sources
        if (tab_item := tab_items.get(source.source_key)) is not None
    )


def source_selector_full_text(
    sources: Iterable[OutputCanvasSourceGroup],
    *,
    active_source_key: str | None,
) -> str:
    """Return the unelided label for the collapsed source selector."""

    source_groups = {source.source_key: source for source in sources}
    if active_source_key in source_groups:
        return str(source_groups[active_source_key].label)
    first_source = next(iter(source_groups.values()), None)
    if first_source is not None:
        return str(first_source.label)
    return "Output"


def source_selector_button_state(
    *,
    full_text: str,
    display_text: str,
    width: int,
    source_tabs_collapsed: bool,
    tab_count: int,
    active_scene_overview: bool,
) -> SourceSelectorButtonState:
    """Return collapsed source selector text, tooltip, width, and visibility."""

    return SourceSelectorButtonState(
        text=display_text,
        tooltip=full_text if display_text != full_text else "",
        width=width,
        visible=source_tabs_collapsed and tab_count > 1 and not active_scene_overview,
    )


def apply_source_selector_button_state(
    button: object,
    *,
    full_text: str,
    display_text: str,
    width: int,
    source_tabs_collapsed: bool,
    tab_count: int,
    active_scene_overview: bool,
) -> SourceSelectorButtonState:
    """Apply collapsed source selector text, tooltip, width, and visibility."""

    button_state = source_selector_button_state(
        full_text=full_text,
        display_text=display_text,
        width=width,
        source_tabs_collapsed=source_tabs_collapsed,
        tab_count=tab_count,
        active_scene_overview=active_scene_overview,
    )
    apply_source_button_state(button, button_state)
    return button_state


def compare_source_button_state(
    *,
    full_text: str,
    display_text: str,
    width: int,
) -> SourceSelectorButtonState:
    """Return compare source selector text, tooltip, width, and visibility."""

    return SourceSelectorButtonState(
        text=display_text,
        tooltip=full_text if display_text != full_text else "",
        width=width,
        visible=True,
    )


def apply_compare_source_button_state(
    button: object,
    *,
    full_text: str,
    display_text: str,
    width: int,
) -> SourceSelectorButtonState:
    """Apply compare source selector text, tooltip, width, and visibility."""

    button_state = compare_source_button_state(
        full_text=full_text,
        display_text=display_text,
        width=width,
    )
    apply_source_button_state(button, button_state)
    return button_state


def apply_source_button_state(
    button: object,
    button_state: SourceSelectorButtonState,
) -> None:
    """Apply source-like selector presentation state to an opaque host button."""

    set_text = getattr(button, "setText", None)
    if callable(set_text):
        set_text(button_state.text)
    set_tooltip = getattr(button, "setToolTip", None)
    if callable(set_tooltip):
        set_tooltip(button_state.tooltip)
    set_fixed_width = getattr(button, "setFixedWidth", None)
    if callable(set_fixed_width):
        set_fixed_width(button_state.width)
    set_visible = getattr(button, "setVisible", None)
    if callable(set_visible):
        set_visible(button_state.visible)


def set_selector_button_state(
    *,
    active_set_index: int,
    active_scene_overview: bool,
    set_count: int,
    grid_available: bool,
) -> SetSelectorButtonState:
    """Return set selector text and visibility."""

    return SetSelectorButtonState(
        text=str(active_set_index),
        visible=not active_scene_overview and (set_count > 1 or grid_available),
    )


def apply_set_selector_button_state(
    button: object,
    *,
    active_set_index: int,
    active_scene_overview: bool,
    set_count: int,
    grid_available: bool,
) -> SetSelectorButtonState:
    """Apply set selector text and visibility to an opaque host button."""

    button_state = set_selector_button_state(
        active_set_index=active_set_index,
        active_scene_overview=active_scene_overview,
        set_count=set_count,
        grid_available=grid_available,
    )
    set_text = getattr(button, "setText", None)
    if callable(set_text):
        set_text(button_state.text)
    set_visible = getattr(button, "setVisible", None)
    if callable(set_visible):
        set_visible(button_state.visible)
    return button_state


def compare_set_button_state(
    *,
    set_index: int,
    set_count: int,
) -> SetSelectorButtonState:
    """Return compare set selector text and visibility."""

    return SetSelectorButtonState(
        text=str(set_index),
        visible=set_count > 1,
    )


def apply_compare_set_button_state(
    button: object,
    *,
    set_index: int,
    set_count: int,
) -> SetSelectorButtonState:
    """Apply compare set selector text and visibility to an opaque host button."""

    button_state = compare_set_button_state(
        set_index=set_index,
        set_count=set_count,
    )
    set_text = getattr(button, "setText", None)
    if callable(set_text):
        set_text(button_state.text)
    set_visible = getattr(button, "setVisible", None)
    if callable(set_visible):
        set_visible(button_state.visible)
    return button_state


def sync_comparison_navigation_buttons(
    *,
    comparison_nav_container: object,
    enabled: bool,
    comparison_selection: object | None,
    scene_button: object,
    set_button: object,
    source_button: object,
    sync_scene_button: Callable[[object, object], None],
    sync_set_button: Callable[[object, object], None],
    sync_source_button: Callable[[object, object], None],
) -> bool:
    """Refresh comparison navigation buttons when compare selection is visible."""

    if not enabled or comparison_selection is None:
        hide_container = getattr(comparison_nav_container, "hide", None)
        if callable(hide_container):
            hide_container()
        return False

    sync_scene_button(scene_button, comparison_selection)
    sync_set_button(set_button, comparison_selection)
    sync_source_button(source_button, comparison_selection)
    return True


def scene_selector_full_text(
    scene_groups: Iterable[OutputCanvasSceneGroup],
    *,
    active_scene_key: str | None,
    active_scene_overview: bool,
) -> str:
    """Return the unelided label for the normal scene selector."""

    if active_scene_overview:
        return "All"
    scenes_by_key = {scene.scene_key: scene for scene in scene_groups}
    if active_scene_key in scenes_by_key:
        return scenes_by_key[active_scene_key].title
    return "All"


def scene_selector_button_state(
    *,
    full_text: str,
    display_text: str,
    width: int,
    scene_count: int,
) -> SceneSelectorButtonState:
    """Return scene selector text, tooltip, width, and visibility."""

    return SceneSelectorButtonState(
        text=display_text,
        tooltip=full_text if display_text != full_text else "",
        width=width,
        visible=scene_count > 1,
    )


def apply_scene_selector_button_state(
    button: object,
    *,
    full_text: str,
    display_text: str,
    width: int,
    scene_count: int,
) -> SceneSelectorButtonState:
    """Apply normal scene selector text, tooltip, width, and visibility."""

    button_state = scene_selector_button_state(
        full_text=full_text,
        display_text=display_text,
        width=width,
        scene_count=scene_count,
    )
    apply_scene_button_state(button, button_state)
    return button_state


def compare_scene_full_text(
    scene_groups: Iterable[OutputCanvasSceneGroup],
    *,
    scene_key: str | None,
    scene_count: int,
) -> str:
    """Return the unelided label for one compare scene selector."""

    scenes_by_key = {scene.scene_key: scene for scene in scene_groups}
    if scene_count > 1 and scene_key in scenes_by_key:
        return scenes_by_key[scene_key].title
    return "All"


def compare_scene_button_state(
    *,
    full_text: str,
    display_text: str,
    width: int,
    scene_count: int,
) -> SceneSelectorButtonState:
    """Return compare scene selector text, tooltip, width, and visibility."""

    return SceneSelectorButtonState(
        text=display_text,
        tooltip=full_text if display_text != full_text else "",
        width=width,
        visible=scene_count > 1,
    )


def apply_compare_scene_button_state(
    button: object,
    *,
    full_text: str,
    display_text: str,
    width: int,
    scene_count: int,
) -> SceneSelectorButtonState:
    """Apply compare scene selector text, tooltip, width, and visibility."""

    button_state = compare_scene_button_state(
        full_text=full_text,
        display_text=display_text,
        width=width,
        scene_count=scene_count,
    )
    apply_scene_button_state(button, button_state)
    return button_state


def apply_scene_button_state(
    button: object,
    button_state: SceneSelectorButtonState,
) -> None:
    """Apply scene-like selector presentation state to an opaque host button."""

    set_text = getattr(button, "setText", None)
    if callable(set_text):
        set_text(button_state.text)
    set_tooltip = getattr(button, "setToolTip", None)
    if callable(set_tooltip):
        set_tooltip(button_state.tooltip)
    set_fixed_width = getattr(button, "setFixedWidth", None)
    if callable(set_fixed_width):
        set_fixed_width(button_state.width)
    set_visible = getattr(button, "setVisible", None)
    if callable(set_visible):
        set_visible(button_state.visible)


__all__ = [
    "SceneSelectorButtonState",
    "SetSelectorButtonState",
    "SourceTabSignature",
    "SourceSelectorButtonState",
    "SourceTabTooltip",
    "SourceTabItem",
    "SourceTabTooltipRefreshItem",
    "SourceTabsRebuildPlan",
    "apply_compare_scene_button_state",
    "apply_compare_set_button_state",
    "apply_compare_source_button_state",
    "apply_scene_button_state",
    "apply_scene_selector_button_state",
    "apply_set_selector_button_state",
    "apply_source_button_state",
    "apply_source_selector_button_state",
    "compare_scene_button_state",
    "compare_scene_full_text",
    "compare_set_button_state",
    "compare_source_button_state",
    "scene_selector_button_state",
    "scene_selector_current_width",
    "scene_selector_full_text",
    "selector_display_text",
    "selector_display_text_for_metrics",
    "selector_font_metrics_for_widget",
    "selector_current_width",
    "selector_text_width",
    "selector_width_for_text",
    "selector_width_for_metrics_text",
    "selector_width_for_widget_text",
    "set_selector_button_state",
    "source_selector_button_state",
    "source_selector_current_width",
    "source_selector_full_text",
    "source_tab_items",
    "source_tab_removal_keys",
    "source_tab_signature",
    "source_tab_tooltip",
    "source_tab_tooltip_refresh_items",
    "source_tabs_rebuild_plan",
    "sync_comparison_navigation_buttons",
]
