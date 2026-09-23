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

"""Translate Output selector intent into concrete route activation."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.presentation.canvas.output.output_canvas_navigation_policy import (
    OutputCanvasNavigationPolicy,
)
from substitute.presentation.canvas.output.output_navigation_activation import (
    activate_output_grid_for_source,
    activate_output_item,
    activate_output_scene,
    activate_output_scene_overview,
)
from substitute.presentation.canvas.output.output_navigation_selector_sync import (
    sync_output_source_selector_button,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.output.navigation_selection")


def select_output_set(
    host: object,
    set_index: int,
    *,
    source_groups_by_key: Mapping[str, OutputCanvasSourceGroup],
    update_tabbar_container: Callable[[], None],
) -> None:
    """Apply a set-picker selection through the Output navigation host."""

    active_source_key = getattr(host, "active_source_key", None)
    action = OutputCanvasNavigationPolicy.set_selection_action(
        set_index=set_index,
        active_source_key=(
            active_source_key if isinstance(active_source_key, str) else None
        ),
        source_groups_by_key=source_groups_by_key,
    )
    if action.kind == "activate_grid":
        activate_output_grid_for_source(
            host,
            action.source_key,
            source_groups_by_key=source_groups_by_key,
            emit_selection=True,
            update_tabbar_container=update_tabbar_container,
        )
    elif action.kind not in {"none", "missing_set"}:
        if action.source_key is not None and action.item is not None:
            activate_output_item(
                host,
                action.source_key,
                action.item,
                update_tabbar_container=update_tabbar_container,
            )


def select_output_source(
    host: object,
    route_key: str,
    *,
    source_groups_by_key: Mapping[str, OutputCanvasSourceGroup],
    update_tabbar_container: Callable[[], None],
) -> None:
    """Apply a source-tab selection through the Output navigation host."""

    current_set_index = int(getattr(host, "active_set_index", 0))
    action = OutputCanvasNavigationPolicy.tab_change_action(
        route_key=route_key,
        suppress_tab_change=bool(getattr(host, "_suppress_tab_change", False)),
        active_set_index=current_set_index,
        source_groups_by_key=source_groups_by_key,
    )
    if action.kind == "none":
        return
    if action.kind == "activate_grid":
        activate_output_grid_for_source(
            host,
            action.source_key,
            source_groups_by_key=source_groups_by_key,
            emit_selection=True,
            update_tabbar_container=update_tabbar_container,
        )
        return
    if action.kind == "activate_source_fallback":
        item = OutputCanvasNavigationPolicy.source_fallback_item(
            source_groups_by_key,
            action.source_key,
            last_real_set_index=int(getattr(host, "last_real_set_index", 1)),
        )
        if item is not None:
            activate_output_item(
                host,
                action.source_key,
                item,
                update_tabbar_container=update_tabbar_container,
            )
        return
    if action.kind in {"missing_set", "unknown_source"}:
        _restore_active_source_selection(
            host,
            update_tabbar_container=update_tabbar_container,
        )
        if action.kind == "missing_set":
            log_warning(
                _LOGGER,
                "Ignored output source without exact active batch",
                requested_source_key=route_key,
                requested_set_index=current_set_index,
                available_set_indices=sorted(
                    source_groups_by_key[route_key].images_by_set
                ),
            )
        else:
            log_warning(
                _LOGGER,
                "Ignored unknown output source route key",
                route_key=route_key,
            )
        return
    if action.item is not None:
        activate_output_item(
            host,
            action.source_key,
            action.item,
            update_tabbar_container=update_tabbar_container,
        )


def select_output_scene(
    host: object,
    scene_key: str,
    *,
    scene_groups_by_key: Mapping[str, OutputCanvasSceneGroup],
    update_tabbar_container: Callable[[], None],
) -> None:
    """Apply a scene-picker selection through the Output navigation host."""

    action = OutputCanvasNavigationPolicy.scene_selection_action(scene_key)
    selection: OutputSceneNavigationSelection | None
    if action.kind == "activate_scene_overview":
        activated = activate_output_scene_overview(
            host,
            update_tabbar_container=update_tabbar_container,
        )
        selection = (
            OutputSceneNavigationSelection(
                scene_key=None,
                overview=True,
                source_key=None,
                set_index=1,
                image_id=None,
            )
            if activated
            else None
        )
    else:
        selection = activate_output_scene(
            host,
            action.scene_key,
            scene_groups_by_key=scene_groups_by_key,
            update_tabbar_container=update_tabbar_container,
        )
    if selection is not None:
        _emit_signal(getattr(host, "activeOutputSceneChanged", None), selection)


def _restore_active_source_selection(
    host: object,
    *,
    update_tabbar_container: Callable[[], None],
) -> None:
    """Restore source chrome after rejecting an inexact source/set route."""

    active_source_key = getattr(host, "active_source_key", None)
    tabbar = getattr(host, "tabbar", None)
    tabbar_items = getattr(tabbar, "items", {})
    if (
        isinstance(active_source_key, str)
        and isinstance(tabbar_items, Mapping)
        and active_source_key in tabbar_items
    ):
        set_current_item = getattr(tabbar, "setCurrentItem", None)
        if callable(set_current_item):
            setattr(host, "_suppress_tab_change", True)
            try:
                set_current_item(active_source_key)
            finally:
                setattr(host, "_suppress_tab_change", False)
    sync_output_source_selector_button(host)
    update_tabbar_container()


def _emit_signal(signal: object, *args: object) -> None:
    """Emit a Qt-like signal when the host exposes one."""

    emit = getattr(signal, "emit", None)
    if callable(emit):
        emit(*args)


__all__ = [
    "select_output_scene",
    "select_output_set",
    "select_output_source",
]
