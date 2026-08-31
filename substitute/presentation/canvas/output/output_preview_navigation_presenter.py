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

"""Present transient preview routes without changing durable Output navigation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast
from uuid import UUID

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_session import (
    OutputCanvasSession,
    output_route_identity_for_projection,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewLane,
    OutputPreviewRegistry,
)
from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.presentation.canvas.output.output_canvas_navigation_chrome import (
    update_output_tabbar_container,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    activate_output_scene,
    activate_output_scene_overview,
)
from substitute.presentation.canvas.output.output_canvas_navigation_policy import (
    OutputCanvasNavigationPolicy,
)
from substitute.presentation.canvas.output.output_document_route_projector import (
    OutputDocumentRouteProjector,
)


class _OutputPreviewDocumentPort(Protocol):
    """Describe document presentation used by transient preview navigation."""

    def present_grid(self, image_ids: tuple[UUID, ...]) -> bool:
        """Present a grid of admitted images."""


class _OutputPreviewDocumentNavigationPort(Protocol):
    """Describe the preview-aware projection exposed by document navigation."""

    def visible_sources(self) -> dict[str, OutputCanvasSourceGroup]:
        """Return sources overlaid with transient preview placeholders."""

    def scene_groups(self) -> dict[str, OutputCanvasSceneGroup]:
        """Return scenes overlaid with transient preview placeholders."""

    def synchronize_projection(self) -> None:
        """Synchronize navigation chrome with current host state."""


class _OutputPreviewSignalPort(Protocol):
    """Describe a Qt-compatible navigation signal."""

    def emit(self, *args: object) -> None:
        """Publish one navigation event."""


class _OutputPreviewNavigationHost(Protocol):
    """Describe Output host state required by transient preview presentation."""

    _preview_registry: OutputPreviewRegistry
    _output_session: OutputCanvasSession | None
    _output_projection: OutputCanvasProjection | None
    _document_navigation: _OutputPreviewDocumentNavigationPort
    document: _OutputPreviewDocumentPort
    activeOutputSceneChanged: _OutputPreviewSignalPort
    active_source_key: str | None
    active_scene_key: str | None
    active_scene_overview: bool
    active_set_index: int
    scene_count: int

    @property
    def route_projector(self) -> OutputDocumentRouteProjector:
        """Return the authorized document route projector."""

    def _bind_preview_scope(self) -> None:
        """Refresh authorized document members after preview mutation."""


class OutputPreviewNavigationPresenter:
    """Own transient focus, preview routes, and preview-backed scene navigation."""

    def __init__(self, host: object) -> None:
        """Bind one Output host while keeping transient lock state private."""

        self._host = cast(_OutputPreviewNavigationHost, host)
        self._locked = False

    def restore_selection(
        self,
        previous_source_key: str | None,
        previous_set_index: int,
    ) -> None:
        """Preserve a user-selected placeholder across final projection refreshes."""

        if not self._locked:
            return
        source = self._host._document_navigation.visible_sources().get(
            previous_source_key or ""
        )
        if source is None or (
            previous_set_index != 0 and previous_set_index not in source.images_by_set
        ):
            self._locked = False
            return
        self._host.active_source_key = previous_source_key
        self._host.active_set_index = previous_set_index

    def present_active_item(self, projection: OutputCanvasProjection) -> bool:
        """Present the active final or preview item from the overlaid projection."""

        sources = self._host._document_navigation.visible_sources()
        source = sources.get(self._host.active_source_key or "")
        item = (
            None
            if source is None
            else source.images_by_set.get(self._host.active_set_index)
        )
        if item is None:
            return False
        route = (
            _preview_route(item.image_id)
            if self._host._preview_registry.lane_for_id(item.image_id) is not None
            else output_route_identity_for_projection(projection)
        )
        self._host.route_projector.apply_final_image_route(route, item.image_id)
        return True

    def present_source_preview(self, preview_id: UUID, is_new: bool) -> None:
        """Stream a placeholder without stealing deliberate earlier-source focus."""

        lane = self._host._preview_registry.lane_for_id(preview_id)
        if lane is None or self._host.active_scene_overview:
            return
        sources = self._host._document_navigation.visible_sources()
        source_keys = tuple(sources)
        if lane.key.source_key not in sources:
            return
        if self._host.active_source_key != lane.key.source_key:
            source_index = source_keys.index(lane.key.source_key)
            follows_current_tail = (
                source_index == 0
                and self._host.active_source_key is None
                or source_index > 0
                and self._host.active_source_key == source_keys[source_index - 1]
            )
            if (
                not is_new
                or not follows_current_tail
                or self._host.active_set_index != 1
            ):
                return
            self._host.active_source_key = lane.key.source_key
            self._host._document_navigation.synchronize_projection()
        self._host.route_projector.apply_final_image_route(
            _preview_route(preview_id),
            preview_id,
        )

    def present_selection(self, preview_id: UUID) -> None:
        """Present a user-selected placeholder until durable navigation resumes."""

        self._locked = True
        self._host._bind_preview_scope()
        self.present_source_preview(preview_id, False)

    def present_grid(self, image_ids: tuple[UUID, ...]) -> None:
        """Present a user-selected grid containing a transient placeholder."""

        self._locked = True
        self._host._bind_preview_scope()
        self._host.document.present_grid(image_ids)

    def release(self) -> None:
        """Return navigation ownership to durable final outputs."""

        self._locked = False

    def present_scene_previews(
        self,
        lanes: tuple[OutputPreviewLane, ...],
    ) -> bool:
        """Present accepted scene representatives when scene overview is active."""

        if self._host._output_session is None:
            return False
        preview_scenes = self._host._document_navigation.scene_groups()
        if not preview_scenes:
            return False
        reported_scene_count = max(
            (lane.scene_count or 0 for lane in lanes),
            default=0,
        )
        self._host.scene_count = max(
            self._host.scene_count,
            reported_scene_count,
            len(preview_scenes),
        )
        if self._host.scene_count > 1 and self._host.active_scene_key is None:
            self._host.active_scene_key = next(iter(preview_scenes), None)
            self._host.active_scene_overview = True
        if not self._host.active_scene_overview:
            return False
        self._host.document.present_grid(
            scene_overview_image_ids(
                self._host._output_projection,
                preview_scenes=preview_scenes,
            )
        )
        self._host._document_navigation.synchronize_projection()
        return True

    def select_scene(
        self,
        scene_key: str,
        scene_groups: Mapping[str, OutputCanvasSceneGroup],
    ) -> None:
        """Apply scene navigation while keeping placeholder routes transient."""

        action = OutputCanvasNavigationPolicy.scene_selection_action(scene_key)

        def update_chrome() -> None:
            """Refresh Output navigation chrome after one scene transition."""

            update_output_tabbar_container(self._host)

        if action.kind == "activate_scene_overview":
            if activate_output_scene_overview(
                self._host,
                update_tabbar_container=update_chrome,
            ):
                self._host.activeOutputSceneChanged.emit(
                    OutputSceneNavigationSelection(
                        scene_key=None,
                        overview=True,
                        source_key=None,
                        set_index=1,
                        image_id=None,
                    )
                )
            return
        selection = activate_output_scene(
            self._host,
            action.scene_key,
            scene_groups_by_key=scene_groups,
            update_tabbar_container=update_chrome,
        )
        if selection is None or self._present_scene_selection(selection, scene_groups):
            return
        self._host.activeOutputSceneChanged.emit(selection)

    def _present_scene_selection(
        self,
        selection: OutputSceneNavigationSelection,
        scene_groups: Mapping[str, OutputCanvasSceneGroup],
    ) -> bool:
        """Present a preview-backed concrete scene selection when one exists."""

        preview_id = selection.image_id
        if (
            preview_id is not None
            and self._host._preview_registry.lane_for_id(preview_id) is not None
        ):
            self.present_selection(preview_id)
            return True
        if selection.set_index != 0 or selection.source_key is None:
            return False
        scene = scene_groups.get(selection.scene_key or "")
        source = next(
            (
                candidate
                for candidate in (() if scene is None else scene.sources)
                if candidate.source_key == selection.source_key
            ),
            None,
        )
        image_ids = (
            ()
            if source is None
            else tuple(
                item.image_id
                for _set_index, item in sorted(source.images_by_set.items())
            )
        )
        if not any(
            self._host._preview_registry.lane_for_id(image_id) is not None
            for image_id in image_ids
        ):
            return False
        self.present_grid(image_ids)
        return True


def scene_overview_image_ids(
    projection: OutputCanvasProjection | None,
    *,
    preview_scenes: Mapping[str, object] | None = None,
) -> tuple[UUID, ...]:
    """Return ordered final or live-preview representatives for scene overview."""

    preview_by_key = preview_scenes or {}
    image_ids: list[UUID] = []
    final_scene_keys: set[str] = set()
    if projection is not None:
        for scene in projection.scene_groups:
            final_scene_keys.add(scene.scene_key)
            preview_id = getattr(
                preview_by_key.get(scene.scene_key), "preview_image_id", None
            )
            image_id = preview_id or scene.primary_image_id
            if isinstance(image_id, UUID):
                image_ids.append(image_id)
    for scene_key, preview in sorted(
        preview_by_key.items(),
        key=lambda item: int(getattr(item[1], "order", 0)),
    ):
        if scene_key in final_scene_keys:
            continue
        preview_id = getattr(preview, "preview_image_id", None)
        if isinstance(preview_id, UUID):
            image_ids.append(preview_id)
    return tuple(dict.fromkeys(image_ids))


def _preview_route(preview_id: UUID) -> CanvasRouteIdentity:
    """Build the transient document route for one preview placeholder."""

    return CanvasRouteIdentity(
        route_kind="output_image",
        route_key=f"image:{preview_id}",
        primary_image_id=preview_id,
    )


__all__ = ["OutputPreviewNavigationPresenter", "scene_overview_image_ids"]
