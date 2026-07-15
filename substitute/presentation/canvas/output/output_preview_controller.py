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

"""Apply Output preview registry mutations to the QPane presentation surface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
)
from substitute.application.workflows.output_canvas_state_service import (
    OutputPreviewCloseIdentity,
)
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewAcceptance,
    OutputPreviewLane,
    OutputPreviewLanePlacement,
    OutputPreviewRegistry,
)
from substitute.application.workflows.output_preview_lifecycle_service import (
    PreviewSlotKey,
    ScenePreviewSlot,
    scene_has_completed_source_label_set,
    scene_has_completed_source_set,
)


class OutputPreviewPanePresenter(Protocol):
    """Register and remove transient preview images in the QPane catalog."""

    def register_image(
        self,
        image_id: UUID,
        image: object,
        path: Path | None,
    ) -> None:
        """Register one preview image with QPane."""

    def remove_image(self, image_id: UUID) -> None:
        """Remove one preview image from QPane."""


def _missing_session() -> OutputCanvasSession | None:
    """Return no Output session for commands that do not need session state."""

    return None


def _zero_scene_count() -> int:
    """Return the default scene count for commands that do not inspect scenes."""

    return 0


def _set_scene_count_noop(scene_count: int) -> None:
    """Ignore scene count updates for commands that do not mutate scene state."""

    _ = scene_count


def _missing_scene_key() -> str | None:
    """Return no active scene key for commands that do not inspect scenes."""

    return None


def _set_scene_key_noop(scene_key: str | None) -> None:
    """Ignore active scene key updates for commands that do not mutate scenes."""

    _ = scene_key


def _inactive_scene_overview() -> bool:
    """Return no active scene overview for commands that do not inspect scenes."""

    return False


def _set_scene_overview_noop(active: bool) -> None:
    """Ignore active scene overview updates for commands that do not mutate scenes."""

    _ = active


def _set_current_output_image_noop(image_id: UUID) -> bool:
    """Ignore preview image activation for commands that do not activate previews."""

    _ = image_id
    return False


def _preview_slot_is_completed_false(slot_key: PreviewSlotKey) -> bool:
    """Return that no scene preview slot has completed final output."""

    _ = slot_key
    return False


def _missing_scene_preview_id(
    *,
    generation_run_id: str,
    scene_run_id: str,
    scene_key: str,
    source_key: str,
    set_index: int,
) -> UUID:
    """Raise when scene preview mutation lacks a preview ID provider."""

    _ = generation_run_id, scene_run_id, scene_key, source_key, set_index
    raise RuntimeError("Scene preview ID provider is required.")


def _empty_scene_groups() -> dict[str, OutputCanvasSceneGroup]:
    """Return no scene groups for commands that do not inspect scenes."""

    return {}


def _scene_preview_rejected(*, scene_key: str, source_key: str) -> bool:
    """Reject scene overview representative updates by default."""

    _ = scene_key, source_key
    return False


def _empty_scene_preview_slots() -> dict[str, ScenePreviewSlot]:
    """Return empty scene preview slots for commands that do not mutate scenes."""

    return {}


def _empty_preview_image_cache() -> dict[UUID, object]:
    """Return empty preview image cache for commands that do not mutate images."""

    return {}


def _empty_preview_scene_groups() -> dict[str, OutputCanvasSceneGroup]:
    """Return empty preview scene groups for commands that do not mutate scenes."""

    return {}


def _noop() -> None:
    """Do nothing for optional preview controller callbacks."""


@dataclass(frozen=True, slots=True)
class OutputPreviewController:
    """Own preview close and clear commands for the Output canvas."""

    preview_registry: Callable[[], OutputPreviewRegistry]
    qpane_presenter: Callable[[], OutputPreviewPanePresenter]
    output_session: Callable[[], OutputCanvasSession | None] = _missing_session
    scene_count: Callable[[], int] = _zero_scene_count
    set_scene_count: Callable[[int], None] = _set_scene_count_noop
    active_scene_key: Callable[[], str | None] = _missing_scene_key
    set_active_scene_key: Callable[[str | None], None] = _set_scene_key_noop
    active_scene_overview: Callable[[], bool] = _inactive_scene_overview
    set_active_scene_overview: Callable[[bool], None] = _set_scene_overview_noop
    set_current_output_image: Callable[[UUID], bool] = _set_current_output_image_noop
    activate_scene_overview: Callable[[], None] = _noop
    mark_output_activity: Callable[[], None] = _noop
    preview_slot_is_completed: Callable[[PreviewSlotKey], bool] = (
        _preview_slot_is_completed_false
    )
    scene_preview_id_for_source: Callable[..., UUID] = _missing_scene_preview_id
    scene_groups_by_key: Callable[[], dict[str, OutputCanvasSceneGroup]] = (
        _empty_scene_groups
    )
    scene_preview_matches_representative: Callable[..., bool] = _scene_preview_rejected
    scene_preview_slots: Callable[[], dict[str, ScenePreviewSlot]] = (
        _empty_scene_preview_slots
    )
    preview_image_cache: Callable[[], dict[UUID, object]] = _empty_preview_image_cache
    preview_scene_groups_by_key: Callable[[], dict[str, OutputCanvasSceneGroup]] = (
        _empty_preview_scene_groups
    )

    def apply_preview_acceptance(
        self,
        acceptance: OutputPreviewAcceptance,
    ) -> None:
        """Apply a session-authorized preview acceptance to QPane catalog/routes."""

        presenter = self.qpane_presenter()
        for preview_id in acceptance.retired_preview_ids:
            presenter.remove_image(preview_id)
        if not acceptance.accepted:
            return
        session = self.output_session()
        if not isinstance(session, OutputCanvasSession):
            return
        lanes = tuple(
            lane
            for lane in acceptance.lanes
            if lane.key.workflow_id == session.workflow_id.value
            and lane.session_revision == session.revision
        )
        if not lanes:
            return
        source_lane: OutputPreviewLane | None = None
        scene_overview_changed = False
        for lane in lanes:
            presenter.register_image(lane.preview_id, lane.image, None)
            if lane.key.placement is OutputPreviewLanePlacement.SOURCE:
                source_lane = lane
            elif lane.key.placement is OutputPreviewLanePlacement.SCENE:
                scene_overview_changed = True
                if lane.scene_count is not None:
                    self.set_scene_count(max(self.scene_count(), lane.scene_count))
                if self.scene_count() > 1 and self.active_scene_key() is None:
                    self.set_active_scene_key(lane.key.scene_key)
                    self.set_active_scene_overview(True)
        if source_lane is not None:
            self._activate_source_preview(source_lane.preview_id)
        elif scene_overview_changed and self.active_scene_overview():
            self.activate_scene_overview()
        self.mark_output_activity()

    def _activate_source_preview(self, preview_id: UUID) -> None:
        """Show a source preview through the authoritative Output route command."""

        self.set_current_output_image(preview_id)

    def set_scene_preview_image(
        self,
        image: object,
        *,
        scene_key: str,
        scene_title: str,
        scene_order: int | None,
        scene_count: int,
        generation_run_id: str = "",
        scene_run_id: str,
        source_key: str = "",
        source_label: str = "",
    ) -> None:
        """Store a transient scene preview and refresh overview state when active."""

        set_index = 1
        preview_slot_key = PreviewSlotKey(
            scene_run_id=scene_run_id,
            generation_run_id=generation_run_id,
            scene_key=scene_key,
            source_key=source_key,
            set_index=set_index,
        )
        if self.preview_slot_is_completed(preview_slot_key):
            return
        preview_id = self.scene_preview_id_for_source(
            generation_run_id=generation_run_id,
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            source_key=source_key,
            set_index=set_index,
        )
        scene_groups = self.scene_groups_by_key()
        scene = scene_groups.get(scene_key)
        final_already_registered = (
            scene is not None
            and bool(source_key)
            and (
                scene_has_completed_source_set(
                    scene,
                    source_key=source_key,
                    set_index=set_index,
                )
                or scene_has_completed_source_label_set(
                    scene,
                    source_label=source_label,
                    set_index=set_index,
                )
            )
        )
        if final_already_registered:
            return
        accepted_for_overview = self.scene_preview_matches_representative(
            scene_key=scene_key,
            source_key=source_key,
        )
        if accepted_for_overview:
            self.scene_preview_slots()[scene_key] = ScenePreviewSlot(
                scene_run_id=scene_run_id,
                generation_run_id=generation_run_id,
                scene_key=scene_key,
                source_key=source_key,
                set_index=set_index,
                preview_id=preview_id,
                source_label=source_label,
            )
        preview_image_cache = self.preview_image_cache()
        preview_image_cache[preview_id] = image
        self.qpane_presenter().register_image(preview_id, image, None)
        self._update_preview_scene_group(
            scene_groups=scene_groups,
            scene_key=scene_key,
            scene_title=scene_title,
            scene_order=scene_order,
            scene_count=scene_count,
            scene_run_id=scene_run_id,
            source_key=source_key,
            set_index=set_index,
            preview_id=preview_id,
            accepted_for_overview=accepted_for_overview,
        )
        self.set_scene_count(max(self.scene_count(), scene_count))
        if self.scene_count() > 1 and self.active_scene_key() is None:
            self.set_active_scene_key(scene_key)
            self.set_active_scene_overview(True)
        if self.active_scene_overview():
            self.activate_scene_overview()

    def _update_preview_scene_group(
        self,
        *,
        scene_groups: dict[str, OutputCanvasSceneGroup],
        scene_key: str,
        scene_title: str,
        scene_order: int | None,
        scene_count: int,
        scene_run_id: str,
        source_key: str,
        set_index: int,
        preview_id: UUID,
        accepted_for_overview: bool,
    ) -> None:
        """Update the preview scene group cache for one scene preview."""

        preview_scene_groups = self.preview_scene_groups_by_key()
        if scene_key not in scene_groups:
            preview_scene_groups[scene_key] = OutputCanvasSceneGroup(
                scene_run_id=scene_run_id,
                scene_key=scene_key,
                title=scene_title,
                order=scene_order if scene_order is not None else len(scene_groups),
                sources=(),
                preview_image_id=preview_id,
                primary_image_id=None,
                representative_source_key=source_key or None,
                representative_set_index=set_index if source_key else None,
                status="running",
            )
            return
        scene = scene_groups[scene_key]
        if scene.scene_run_id and scene.scene_run_id != scene_run_id:
            preview_scene_groups[scene_key] = OutputCanvasSceneGroup(
                scene_run_id=scene_run_id,
                scene_key=scene.scene_key,
                title=scene_title or scene.title,
                order=scene.order,
                sources=(),
                preview_image_id=preview_id,
                primary_image_id=None,
                representative_source_key=source_key or None,
                representative_set_index=set_index if source_key else None,
                status="running",
            )
            return
        preview_scene_groups[scene_key] = OutputCanvasSceneGroup(
            scene_run_id=scene.scene_run_id or scene_run_id,
            scene_key=scene.scene_key,
            title=scene.title or scene_title,
            order=scene.order,
            sources=scene.sources,
            preview_image_id=preview_id
            if accepted_for_overview
            else scene.preview_image_id,
            primary_image_id=scene.primary_image_id,
            representative_source_key=(
                scene.representative_source_key or (source_key or None)
            ),
            representative_set_index=(
                scene.representative_set_index or (set_index if source_key else None)
            ),
            status=scene.status,
        )

    def close_final_output_preview_lane(
        self,
        identity: OutputPreviewCloseIdentity,
    ) -> None:
        """Close a final-output preview lane without displaying final output."""

        close_result = self.preview_registry().close_final_output_lane(identity)
        presenter = self.qpane_presenter()
        for preview_id in close_result.closed_preview_ids:
            presenter.remove_image(preview_id)

    def clear_previews(self, source_key: str | None = None) -> None:
        """Remove transient preview catalog entries for one source or all sources."""

        presenter = self.qpane_presenter()
        for preview_id in self.preview_registry().clear(source_key=source_key):
            presenter.remove_image(preview_id)


__all__ = [
    "OutputPreviewController",
    "OutputPreviewPanePresenter",
]
