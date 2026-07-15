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

"""Present Output comparison projection and navigation state."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_compare_state import OutputCompareState
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
from substitute.presentation.canvas.output.output_canvas_source_tabs_controller import (
    OutputCanvasSourceTabsController,
)
from substitute.presentation.canvas.output.output_canvas_interaction_controller import (
    OutputCanvasInteractionController,
)
from substitute.presentation.canvas.output.output_compare_controller import (
    OutputCompareController,
)
from substitute.presentation.canvas.output.output_canvas_compare_rendering_controller import (
    OutputCanvasCompareRenderingController,
)

_SCENE_SELECTOR_MIN_WIDTH = 58
_SCENE_SELECTOR_MAX_WIDTH = 260
_SCENE_SELECTOR_HORIZONTAL_PADDING = 28
_SOURCE_SELECTOR_MIN_WIDTH = 58
_SOURCE_SELECTOR_MAX_WIDTH = 260
_SOURCE_SELECTOR_HORIZONTAL_PADDING = 28
logger = logging.getLogger(__name__)


def _compare_controller_for(view: Any) -> object | None:
    """Return the typed runtime compare controller or a lightweight test double."""

    runtime = getattr(view, "_runtime", None)
    compare_runtime = getattr(runtime, "compare", None)
    controller = getattr(compare_runtime, "controller", None)
    return controller or getattr(view, "_compare_controller", None)


@dataclass(frozen=True, slots=True)
class OutputCompareProjectionCallbacks:
    """Refresh chrome after applying a comparison projection plan."""

    sync_scene_selector: Callable[[], None]
    sync_set_selector: Callable[[], None]
    sync_source_selector: Callable[[], None]
    sync_comparison_navigation: Callable[[], None]
    update_tabbar: Callable[[], None]


@dataclass(frozen=True, slots=True)
class OutputCompareProjectionPresenter:
    """Apply compare projection selection and rendering to an Output host."""

    view: Any
    compare_controller: OutputCompareController
    source_tabs: OutputCanvasSourceTabsController
    interaction: OutputCanvasInteractionController
    rendering: OutputCanvasCompareRenderingController
    callbacks: OutputCompareProjectionCallbacks

    def present(
        self,
        projection: OutputCanvasProjection,
        state: OutputCompareState,
    ) -> None:
        """Apply one reconciled compare plan and refresh its visible chrome."""

        plan = self.compare_controller.compare_projection_plan(projection, state)
        base = plan.base
        if plan.state != state:
            _store_visible_output_compare_state(self.view, plan.state)
        if base is None:
            self.compare_controller.set_compare_mode_enabled(False)
            return
        self.view.active_scene_overview = False
        self.view.active_scene_key = (
            base.scene_key if projection.scene_count > 1 else None
        )
        self.view.active_source_key = base.source_key
        self.view.active_set_index = max(1, base.set_index)
        self.view.last_real_set_index = self.view.active_set_index
        self.view.set_count = plan.set_count
        self.source_tabs.rebuild_source_tabs(
            active_source_key=self.view.active_source_key
        )
        self.callbacks.sync_scene_selector()
        self.callbacks.sync_set_selector()
        self.callbacks.sync_source_selector()
        self.callbacks.sync_comparison_navigation()
        self.interaction.set_grid_interaction_locked(False)
        self.rendering.sync_compare_rendering()
        self.callbacks.update_tabbar()


def _store_visible_output_compare_state(
    view: object,
    state: OutputCompareState,
) -> None:
    """Store current compare control state without importing the widget module."""

    setattr(view, "_visible_compare_state", state)
    if hasattr(view, "output_compare_state"):
        setattr(view, "output_compare_state", state)


def sync_output_comparison_navigation_buttons(view: Any) -> None:
    """Refresh comparison navigation buttons from an opaque Output host."""

    state = getattr(
        view,
        "_visible_compare_state",
        getattr(view, "output_compare_state", None),
    )
    sync_comparison_navigation_buttons(
        comparison_nav_container=getattr(view, "comparison_nav_container", None),
        enabled=bool(getattr(state, "enabled", False)),
        comparison_selection=getattr(state, "comparison", None),
        scene_button=getattr(view, "comparison_scene_selector_button", None),
        set_button=getattr(view, "comparison_set_selector_button", None),
        source_button=getattr(view, "comparison_source_selector_button", None),
        sync_scene_button=lambda button, selection: sync_output_compare_scene_button(
            view,
            button,
            selection,
        ),
        sync_set_button=lambda button, selection: sync_output_compare_set_button(
            view,
            button,
            selection,
        ),
        sync_source_button=lambda button, selection: sync_output_compare_source_button(
            view,
            button,
            selection,
        ),
    )


def sync_output_compare_scene_button(
    view: Any, button: object, selection: object
) -> None:
    """Refresh one compare scene selector from an opaque Output host."""

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
    view: Any, button: object, selection: object
) -> None:
    """Refresh one compare set selector from an opaque Output host."""

    compare_controller = _compare_controller_for(view)
    compare_set_count = getattr(compare_controller, "compare_set_count", None)
    set_count = (
        int(compare_set_count("comparison")) if callable(compare_set_count) else 0
    )
    apply_compare_set_button_state(
        button,
        set_index=int(getattr(selection, "set_index", 0)),
        set_count=set_count,
    )


def sync_output_compare_source_button(
    view: Any, button: object, selection: object
) -> None:
    """Refresh one compare source selector from an opaque Output host."""

    compare_controller = _compare_controller_for(view)
    compare_source_label = getattr(compare_controller, "compare_source_label", None)
    text = (
        str(compare_source_label(selection))
        if callable(compare_source_label)
        else "Output"
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


__all__ = [
    "OutputCompareProjectionCallbacks",
    "OutputCompareProjectionPresenter",
    "sync_output_compare_scene_button",
    "sync_output_compare_set_button",
    "sync_output_compare_source_button",
    "sync_output_comparison_navigation_buttons",
]
