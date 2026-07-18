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

"""Resolve pure Output canvas navigation actions and hierarchy transitions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_canvas_route_model import (
    OutputCanvasRouteModel,
)

OutputTabChangeKind = Literal[
    "none",
    "activate_grid",
    "activate_source_fallback",
    "activate_output_item",
    "unknown_source",
]
OutputSceneSelectionKind = Literal[
    "activate_scene_overview",
    "activate_scene",
]
OutputSetSelectionKind = Literal[
    "none",
    "activate_grid",
    "activate_output_item",
]
OutputSceneActivationFollowup = Literal[
    "none",
    "activate_grid",
    "activate_source_fallback",
]


@dataclass(frozen=True, slots=True)
class OutputTabChangeAction:
    """Describe the visible action required for one source-tab change."""

    kind: OutputTabChangeKind
    source_key: str
    item: OutputCanvasImageItem | None = None


@dataclass(frozen=True, slots=True)
class OutputSceneSelectionAction:
    """Describe the visible action required for one scene selection."""

    kind: OutputSceneSelectionKind
    scene_key: str


@dataclass(frozen=True, slots=True)
class OutputSetSelectionAction:
    """Describe the visible action required for one set selection."""

    kind: OutputSetSelectionKind
    set_index: int
    source_key: str | None = None
    item: OutputCanvasImageItem | None = None


@dataclass(frozen=True, slots=True)
class OutputSceneActivationPlan:
    """Describe state and follow-up activation for one concrete scene."""

    scene_key: str
    active_source_key: str | None
    set_count: int
    followup: OutputSceneActivationFollowup


@dataclass(frozen=True, slots=True)
class OutputGridActivationPlan:
    """Describe the source-grid target selected for activation."""

    source_key: str


@dataclass(frozen=True, slots=True)
class OutputSceneOverviewActivationPlan:
    """Describe state required to activate the all-scenes overview."""

    active_set_index: int = 1
    active_source_key: None = None
    set_count: int = 0


@dataclass(frozen=True, slots=True)
class OutputItemActivationPlan:
    """Describe state required to activate one concrete output item."""

    source_key: str
    active_set_index: int
    last_real_set_index: int
    image_id: UUID


class OutputCanvasNavigationPolicy:
    """Resolve navigation intent without mutating widgets or durable state."""

    @staticmethod
    def source_fallback_item(
        source_groups: Mapping[str, OutputCanvasSourceGroup],
        source_key: str,
        *,
        last_real_set_index: int,
    ) -> OutputCanvasImageItem | None:
        """Return the concrete item used when a source grid cannot be activated."""

        source = source_groups.get(source_key)
        if source is None:
            return None
        item = source.nearest_item(last_real_set_index)
        if item is not None:
            return item
        return source.nearest_item(1)

    @staticmethod
    def tab_change_action(
        *,
        route_key: str,
        suppress_tab_change: bool,
        active_set_index: int,
        source_groups_by_key: Mapping[str, OutputCanvasSourceGroup],
    ) -> OutputTabChangeAction:
        """Return the widget action required by one source-tab route key."""

        if suppress_tab_change:
            return OutputTabChangeAction("none", route_key)
        if active_set_index == 0:
            source = source_groups_by_key.get(route_key)
            if source is not None and OutputCanvasRouteModel.grid_available_for_source(
                source
            ):
                return OutputTabChangeAction("activate_grid", route_key)
            return OutputTabChangeAction("unknown_source", route_key)
        item = OutputCanvasRouteModel.item_for_source_and_set(
            source_groups_by_key,
            route_key,
            active_set_index,
        )
        if item is None:
            source = source_groups_by_key.get(route_key)
            if source is not None:
                item = source.nearest_item(active_set_index)
        if item is None:
            return OutputTabChangeAction("unknown_source", route_key)
        return OutputTabChangeAction("activate_output_item", route_key, item)

    @staticmethod
    def scene_selection_action(scene_key: str) -> OutputSceneSelectionAction:
        """Return the widget action required by one scene picker selection."""

        if scene_key == "all":
            return OutputSceneSelectionAction("activate_scene_overview", scene_key)
        return OutputSceneSelectionAction("activate_scene", scene_key)

    @staticmethod
    def set_selection_action(
        *,
        set_index: int,
        active_source_key: str | None,
        source_groups_by_key: Mapping[str, OutputCanvasSourceGroup],
    ) -> OutputSetSelectionAction:
        """Return the widget action required by one set picker selection."""

        if set_index == 0:
            return OutputSetSelectionAction(
                "activate_grid",
                set_index,
                active_source_key,
            )
        target = OutputCanvasRouteModel.concrete_set_selection(
            source_groups_by_key,
            active_source_key=active_source_key,
            set_index=set_index,
        )
        if target is None:
            return OutputSetSelectionAction("none", set_index)
        source_key, item = target
        return OutputSetSelectionAction(
            "activate_output_item",
            set_index,
            source_key,
            item,
        )

    @classmethod
    def scene_activation_plan(
        cls,
        *,
        scene_key: str,
        scene_groups_by_key: Mapping[str, OutputCanvasSceneGroup],
        was_scene_overview: bool,
        active_source_key: str | None,
    ) -> OutputSceneActivationPlan | None:
        """Return concrete scene activation state without mutating widgets."""

        scene = scene_groups_by_key.get(scene_key)
        if scene is None:
            return None
        source_groups_by_key = {source.source_key: source for source in scene.sources}
        preferred_source_key = (
            scene.representative_source_key if was_scene_overview else None
        )
        resolved_source_key = OutputCanvasRouteModel.resolved_active_source_key(
            source_groups_by_key,
            preferred_source_key or active_source_key,
            previous_source_key=active_source_key,
            preserve_previous=not was_scene_overview,
        )
        if was_scene_overview:
            resolved_source = (
                source_groups_by_key.get(resolved_source_key)
                if resolved_source_key is not None
                else None
            )
            if resolved_source is None or not (
                OutputCanvasRouteModel.batch_overview_available_for_source(
                    resolved_source
                )
            ):
                resolved_source_key = (
                    OutputCanvasRouteModel.first_batch_overview_source_key(
                        source_groups_by_key
                    )
                    or resolved_source_key
                )
        grid_plan = cls.grid_activation_plan(
            source_key=resolved_source_key,
            source_groups_by_key=source_groups_by_key,
        )
        if grid_plan is not None:
            resolved_source_key = grid_plan.source_key
            followup: OutputSceneActivationFollowup = "activate_grid"
        elif resolved_source_key is not None:
            followup = "activate_source_fallback"
        else:
            followup = "none"
        return OutputSceneActivationPlan(
            scene_key=scene_key,
            active_source_key=resolved_source_key,
            set_count=OutputCanvasRouteModel.set_count_for_sources(
                tuple(source_groups_by_key.values())
            ),
            followup=followup,
        )

    @staticmethod
    def grid_activation_plan(
        *,
        source_key: str | None,
        source_groups_by_key: Mapping[str, OutputCanvasSourceGroup],
    ) -> OutputGridActivationPlan | None:
        """Return the source-grid activation target, if one can render a grid."""

        resolved_source_key = source_key
        if resolved_source_key is not None:
            source = source_groups_by_key.get(resolved_source_key)
            if source is None:
                return None
            if not OutputCanvasRouteModel.grid_available_for_source(source):
                return None
        if resolved_source_key is None:
            resolved_source_key = (
                OutputCanvasRouteModel.first_batch_overview_source_key(
                    source_groups_by_key
                )
                or OutputCanvasRouteModel.first_grid_source_key(source_groups_by_key)
            )
        if resolved_source_key is None:
            return None
        source = source_groups_by_key.get(resolved_source_key)
        if source is None or not OutputCanvasRouteModel.grid_available_for_source(
            source
        ):
            return None
        return OutputGridActivationPlan(resolved_source_key)

    @staticmethod
    def scene_overview_activation_plan(
        *,
        scene_count: int,
    ) -> OutputSceneOverviewActivationPlan | None:
        """Return all-scenes overview activation state when overview is available."""

        if scene_count <= 1:
            return None
        return OutputSceneOverviewActivationPlan()

    @staticmethod
    def item_activation_plan(
        *,
        source_key: str,
        item: OutputCanvasImageItem,
    ) -> OutputItemActivationPlan:
        """Return concrete output item activation state."""

        return OutputItemActivationPlan(
            source_key=source_key,
            active_set_index=item.set_index,
            last_real_set_index=item.set_index,
            image_id=item.image_id,
        )


__all__ = [
    "OutputCanvasNavigationPolicy",
    "OutputGridActivationPlan",
    "OutputItemActivationPlan",
    "OutputSceneActivationPlan",
    "OutputSceneOverviewActivationPlan",
    "OutputSceneSelectionAction",
    "OutputSetSelectionAction",
    "OutputTabChangeAction",
]
