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

"""Apply resolved Output navigation routes to an opaque canvas host."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.presentation.canvas.output.output_canvas_navigation_policy import (
    OutputCanvasNavigationPolicy,
)
from substitute.presentation.canvas.output.output_navigation_selector_sync import (
    sync_output_scene_selector_button,
    sync_output_set_selector_button,
    sync_output_source_selector_button,
)


def activate_output_scene(
    host: object,
    scene_key: str,
    *,
    scene_groups_by_key: Mapping[str, OutputCanvasSceneGroup],
    update_tabbar_container: Callable[[], None],
) -> OutputSceneNavigationSelection | None:
    """Apply and describe one complete concrete scene route transition."""

    active_source_key = getattr(host, "active_source_key", None)
    plan = OutputCanvasNavigationPolicy.scene_activation_plan(
        scene_key=scene_key,
        scene_groups_by_key=scene_groups_by_key,
        was_scene_overview=bool(getattr(host, "active_scene_overview", False)),
        active_source_key=(
            active_source_key if isinstance(active_source_key, str) else None
        ),
    )
    if plan is None:
        return None
    scene = scene_groups_by_key.get(plan.scene_key)
    if scene is None:
        return None
    source_groups_for_scene = {source.source_key: source for source in scene.sources}
    selected_image_id: UUID | None = None
    setattr(host, "active_scene_key", plan.scene_key)
    setattr(host, "active_scene_overview", False)
    setattr(host, "set_count", plan.set_count)
    setattr(host, "active_source_key", plan.active_source_key)

    source_tabs_controller = _source_tabs_controller(host)
    rebuild_source_tabs = getattr(source_tabs_controller, "rebuild_source_tabs", None)
    if callable(rebuild_source_tabs):
        rebuild_source_tabs(active_source_key=plan.active_source_key)

    if plan.followup == "activate_grid":
        activate_output_grid_for_source(
            host,
            plan.active_source_key,
            source_groups_by_key=source_groups_for_scene,
            emit_selection=False,
            update_tabbar_container=update_tabbar_container,
        )
    elif plan.followup == "activate_source_fallback" and plan.active_source_key:
        item = OutputCanvasNavigationPolicy.source_fallback_item(
            source_groups_for_scene,
            plan.active_source_key,
            last_real_set_index=int(getattr(host, "last_real_set_index", 1)),
        )
        if item is not None:
            selected_image_id = item.image_id
            activate_output_item(
                host,
                plan.active_source_key,
                item,
                emit_selection=False,
                update_tabbar_container=update_tabbar_container,
            )
        else:
            setattr(host, "active_set_index", 1)
    else:
        setattr(host, "active_set_index", 1)

    sync_output_scene_selector_button(host)
    sync_output_source_selector_button(host)
    update_tabbar_container()
    active_source_key = getattr(host, "active_source_key", None)
    source_key = active_source_key if isinstance(active_source_key, str) else None
    active_set_index = int(getattr(host, "active_set_index", 1))
    image_id = None if active_set_index == 0 else selected_image_id
    return OutputSceneNavigationSelection(
        scene_key=plan.scene_key,
        overview=False,
        source_key=source_key,
        set_index=active_set_index,
        image_id=image_id,
    )


def activate_output_scene_overview(
    host: object,
    *,
    update_tabbar_container: Callable[[], None],
) -> bool:
    """Apply all-scenes overview navigation state through the Output host."""

    plan = OutputCanvasNavigationPolicy.scene_overview_activation_plan(
        scene_count=int(getattr(host, "scene_count", 0)),
    )
    if plan is None:
        return False
    setattr(host, "active_scene_overview", True)
    setattr(host, "active_set_index", plan.active_set_index)
    setattr(host, "active_source_key", plan.active_source_key)
    setattr(host, "set_count", plan.set_count)
    if hasattr(host, "tabbar"):
        source_tabs_controller = _source_tabs_controller(host)
        rebuild_source_tabs = getattr(
            source_tabs_controller,
            "rebuild_source_tabs",
            None,
        )
        if callable(rebuild_source_tabs):
            rebuild_source_tabs(active_source_key=None)
    sync_output_scene_selector_button(host)
    sync_output_set_selector_button(host)
    sync_output_source_selector_button(host)
    update_tabbar_container()
    _set_grid_interaction_locked(host, True)
    return True


def activate_output_grid_for_source(
    host: object,
    source_key: str | None,
    *,
    source_groups_by_key: Mapping[str, OutputCanvasSourceGroup],
    emit_selection: bool = False,
    update_tabbar_container: Callable[[], None],
) -> bool:
    """Apply source-grid navigation state through the Output host."""

    plan = OutputCanvasNavigationPolicy.grid_activation_plan(
        source_key=source_key,
        source_groups_by_key=source_groups_by_key,
    )
    if plan is None:
        return False
    setattr(host, "active_scene_overview", False)
    setattr(host, "active_source_key", plan.source_key)
    setattr(host, "active_set_index", 0)
    _select_source_tab(host, plan.source_key)
    sync_output_set_selector_button(host)
    sync_output_scene_selector_button(host)
    sync_output_source_selector_button(host)
    update_tabbar_container()
    _set_grid_interaction_locked(host, True)
    if emit_selection:
        _emit_signal(getattr(host, "activeOutputGridChanged", None), plan.source_key)
    return True


def activate_output_item(
    host: object,
    source_key: str,
    item: OutputCanvasImageItem,
    *,
    emit_selection: bool = True,
    update_tabbar_container: Callable[[], None],
) -> None:
    """Apply concrete output item navigation state through the Output host."""

    plan = OutputCanvasNavigationPolicy.item_activation_plan(
        source_key=source_key,
        item=item,
    )
    _set_grid_interaction_locked(host, False)
    setattr(host, "active_scene_overview", False)
    setattr(host, "active_source_key", plan.source_key)
    setattr(host, "active_set_index", plan.active_set_index)
    setattr(host, "last_real_set_index", plan.last_real_set_index)
    _select_source_tab(host, plan.source_key)
    sync_output_set_selector_button(host)
    if hasattr(host, "tabbar"):
        source_tabs_controller = _source_tabs_controller(host)
        refresh_tooltips = getattr(
            source_tabs_controller,
            "refresh_source_tab_tooltips",
            None,
        )
        if callable(refresh_tooltips):
            refresh_tooltips()
    sync_output_scene_selector_button(host)
    sync_output_source_selector_button(host)
    if emit_selection:
        _emit_signal(getattr(host, "activeOutputChanged", None), str(plan.image_id))
    update_tabbar_container()


def _select_source_tab(host: object, source_key: str) -> None:
    """Project the active source into the tabbar without user-change feedback."""

    tabbar = getattr(host, "tabbar", None)
    tabbar_items = getattr(tabbar, "items", {})
    if not isinstance(tabbar_items, Mapping) or source_key not in tabbar_items:
        return
    set_current_item = getattr(tabbar, "setCurrentItem", None)
    if not callable(set_current_item):
        return
    setattr(host, "_suppress_tab_change", True)
    try:
        set_current_item(source_key)
    finally:
        setattr(host, "_suppress_tab_change", False)


def _source_tabs_controller(host: object) -> object | None:
    """Return runtime-owned source tabs with lightweight-host fallback."""

    runtime = getattr(host, "_runtime", None)
    navigation = getattr(runtime, "navigation", None)
    controller = getattr(navigation, "source_tabs", None)
    return controller or getattr(host, "_source_tabs_controller", None)


def _set_grid_interaction_locked(host: object, locked: bool) -> None:
    """Apply grid interaction locking through the composed pointer owner."""

    runtime = getattr(host, "_runtime", None)
    interaction = getattr(runtime, "interaction", None)
    controller = getattr(interaction, "pointer", None) or getattr(
        host,
        "_interaction_controller",
        None,
    )
    setter = getattr(controller, "set_grid_interaction_locked", None)
    if callable(setter):
        setter(locked)


def _emit_signal(signal: object, *args: object) -> None:
    """Emit a Qt-like signal when the host exposes one."""

    emit = getattr(signal, "emit", None)
    if callable(emit):
        emit(*args)


__all__ = [
    "activate_output_grid_for_source",
    "activate_output_item",
    "activate_output_scene",
    "activate_output_scene_overview",
]
