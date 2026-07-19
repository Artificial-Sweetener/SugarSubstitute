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

"""Resolve output-canvas route state without touching widgets or QPane."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_compare_state import OutputCompareSelection

OutputCanvasRouteKind = Literal["empty", "image", "source_grid", "scene_overview"]


@dataclass(frozen=True, slots=True)
class OutputCanvasRouteCommand:
    """Describe the display route that QPane should show."""

    kind: OutputCanvasRouteKind
    image_id: UUID | None = None
    source_key: str | None = None
    scene_key: str | None = None
    set_index: int = 1


class OutputCanvasRouteModel:
    """Resolve output route choices from projection and workflow-owned state."""

    @staticmethod
    def scene_groups_by_key(
        projection: OutputCanvasProjection | None,
        *,
        preview_scene_groups_by_key: Mapping[str, OutputCanvasSceneGroup],
    ) -> dict[str, OutputCanvasSceneGroup]:
        """Return projection scenes overlaid with transient preview scene groups."""

        groups = (
            {scene.scene_key: scene for scene in projection.scene_groups}
            if projection is not None
            else {}
        )
        for scene_key, preview_group in preview_scene_groups_by_key.items():
            groups.setdefault(scene_key, preview_group)
        return groups

    @staticmethod
    def visible_source_groups_by_key(
        projection: OutputCanvasProjection | None,
        *,
        scene_groups_by_key: Mapping[str, OutputCanvasSceneGroup],
        active_scene_overview: bool,
        active_scene_key: str | None,
        scene_count: int,
    ) -> dict[str, OutputCanvasSourceGroup]:
        """Return source selector groups visible for the current scene context."""

        if projection is None:
            if active_scene_overview:
                return {}
            if active_scene_key is None:
                return {}
            scene = scene_groups_by_key.get(active_scene_key)
            if scene is None or not scene.sources:
                return {}
            return {source.source_key: source for source in scene.sources}
        if active_scene_overview:
            return {}
        sources = (
            OutputCanvasRouteModel.sources_for_active_scene(
                projection,
                scene_groups=scene_groups_by_key,
                scene_count=scene_count,
                active_scene_key=active_scene_key,
            )
            if scene_count > 1
            else projection.sources
        )
        return {source.source_key: source for source in sources}

    @staticmethod
    def resolved_active_source_key(
        source_groups: Mapping[str, OutputCanvasSourceGroup],
        projection_source_key: str | None,
        *,
        previous_source_key: str | None,
        preserve_previous: bool,
    ) -> str | None:
        """Choose the active source after projection state changes."""

        if preserve_previous and previous_source_key in source_groups:
            return previous_source_key
        if projection_source_key in source_groups:
            return projection_source_key
        return next(iter(source_groups), None)

    @staticmethod
    def resolved_active_scene_key(
        scene_groups: Mapping[str, OutputCanvasSceneGroup],
        projection_scene_key: str | None,
        *,
        previous_scene_key: str | None,
    ) -> str | None:
        """Choose the active scene after projection state changes."""

        if projection_scene_key in scene_groups:
            return projection_scene_key
        if previous_scene_key in scene_groups:
            return previous_scene_key
        return next(iter(scene_groups), None)

    @staticmethod
    def sources_for_active_scene(
        projection: OutputCanvasProjection,
        *,
        scene_groups: Mapping[str, OutputCanvasSceneGroup],
        scene_count: int,
        active_scene_key: str | None,
    ) -> tuple[OutputCanvasSourceGroup, ...]:
        """Return source groups scoped to the active scene when scenes exist."""

        if scene_count <= 1:
            return projection.sources
        if active_scene_key is None:
            return ()
        scene = scene_groups.get(active_scene_key)
        return () if scene is None else scene.sources

    @staticmethod
    def set_count_for_sources(sources: tuple[OutputCanvasSourceGroup, ...]) -> int:
        """Return the maximum batch count across source groups."""

        return max((len(source.images_by_set) for source in sources), default=0)

    @staticmethod
    def item_for_source_and_set(
        source_groups: Mapping[str, OutputCanvasSourceGroup],
        source_key: str | None,
        set_index: int,
    ) -> OutputCanvasImageItem | None:
        """Return the exact item for a source/set selection."""

        if source_key is None:
            return None
        source = source_groups.get(source_key)
        if source is None:
            return None
        return source.images_by_set.get(set_index)

    @staticmethod
    def output_item_for_image_id(
        source_groups: Mapping[str, OutputCanvasSourceGroup],
        image_id: UUID,
    ) -> tuple[str, OutputCanvasImageItem] | None:
        """Return the source and set item matching one output image UUID."""

        for source_key, source in source_groups.items():
            for item in source.images_by_set.values():
                if item.image_id == image_id:
                    return source_key, item
        return None

    @classmethod
    def concrete_set_selection(
        cls,
        source_groups: Mapping[str, OutputCanvasSourceGroup],
        *,
        active_source_key: str | None,
        set_index: int,
    ) -> tuple[str, OutputCanvasImageItem] | None:
        """Return the exact active-source target for a set selector change."""

        if active_source_key is None:
            return None
        item = cls.item_for_source_and_set(
            source_groups,
            active_source_key,
            set_index,
        )
        if item is None:
            return None
        return active_source_key, item

    @staticmethod
    def grid_available_for_source(source: OutputCanvasSourceGroup) -> bool:
        """Return whether a source has any tile that a grid can render."""

        return bool(source.images_by_set)

    @staticmethod
    def batch_overview_available_for_source(source: OutputCanvasSourceGroup) -> bool:
        """Return whether a source provides a meaningful multi-batch overview."""

        return len(source.images_by_set) > 1

    @classmethod
    def grid_available_for_current_source(
        cls,
        source_groups: Mapping[str, OutputCanvasSourceGroup],
        active_source_key: str | None,
    ) -> bool:
        """Return whether the active source can be displayed as a grid."""

        if active_source_key is None:
            return False
        source = source_groups.get(active_source_key)
        return source is not None and cls.grid_available_for_source(source)

    @classmethod
    def first_grid_source_key(
        cls,
        source_groups: Mapping[str, OutputCanvasSourceGroup],
    ) -> str | None:
        """Return the first source key that can render as a grid."""

        for source_key, source in source_groups.items():
            if cls.grid_available_for_source(source):
                return source_key
        return None

    @classmethod
    def first_batch_overview_source_key(
        cls,
        source_groups: Mapping[str, OutputCanvasSourceGroup],
    ) -> str | None:
        """Return the first source that provides more than one batch tile."""

        for source_key, source in source_groups.items():
            if cls.batch_overview_available_for_source(source):
                return source_key
        return None

    @staticmethod
    def current_output_compare_selection(
        *,
        active_source_key: str | None,
        active_set_index: int,
        scene_count: int,
        active_scene_key: str | None,
    ) -> OutputCompareSelection | None:
        """Return the current concrete output selection, if one is active."""

        if active_source_key is None or active_set_index <= 0:
            return None
        return OutputCompareSelection(
            scene_key=active_scene_key if scene_count > 1 else None,
            set_index=active_set_index,
            source_key=active_source_key,
        )

    @staticmethod
    def route_command_for_selection(
        *,
        active_scene_overview: bool,
        scene_count: int,
        active_set_index: int,
        active_source_key: str | None,
        active_scene_key: str | None,
        active_image_id: UUID | None,
    ) -> OutputCanvasRouteCommand:
        """Return a declarative QPane route command for the active selection."""

        if active_scene_overview and scene_count > 1:
            return OutputCanvasRouteCommand(
                kind="scene_overview",
                scene_key=active_scene_key,
            )
        if active_set_index == 0 and active_source_key is not None:
            return OutputCanvasRouteCommand(
                kind="source_grid",
                source_key=active_source_key,
                scene_key=active_scene_key,
                set_index=active_set_index,
            )
        if active_image_id is not None:
            return OutputCanvasRouteCommand(
                kind="image",
                image_id=active_image_id,
                source_key=active_source_key,
                scene_key=active_scene_key,
                set_index=active_set_index,
            )
        return OutputCanvasRouteCommand(kind="empty")


__all__ = [
    "OutputCanvasRouteCommand",
    "OutputCanvasRouteKind",
    "OutputCanvasRouteModel",
]
