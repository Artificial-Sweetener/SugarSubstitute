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

"""Apply accepted Output previews through locked CuteCanvas compositions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewLane,
    OutputPreviewLanePlacement,
    OutputPreviewRegistry,
)
from substitute.application.workflows.output_preview_results import (
    OutputPreviewAcceptance,
)


class OutputPreviewDocumentPort(Protocol):
    """Describe the locked Output document mutations needed by preview lifecycle."""

    def admit_image(self, image_id: UUID, image: object, *, title: str = "") -> bool:
        """Admit or replace one transient preview composition."""

    def retire_image(self, image_id: UUID) -> bool:
        """Retire one transient preview composition."""


@dataclass(frozen=True, slots=True)
class OutputDocumentPreviewPresenter:
    """Own preview document admission and presentation intent without legacy catalogs."""

    preview_registry: Callable[[], OutputPreviewRegistry]
    document: OutputPreviewDocumentPort
    output_session: Callable[[], OutputCanvasSession | None]
    refresh_preview_scope: Callable[[], None]
    present_source_preview: Callable[[UUID, bool], None]
    present_scene_previews: Callable[[tuple[OutputPreviewLane, ...]], bool]

    def apply_preview_acceptance(self, acceptance: OutputPreviewAcceptance) -> None:
        """Apply one session-authorized preview acceptance to Output document content."""

        for preview_id in acceptance.retired_preview_ids:
            self.document.retire_image(preview_id)
        if not acceptance.accepted:
            return
        session = self.output_session()
        if session is None:
            return
        lanes = tuple(
            lane
            for lane in acceptance.lanes
            if lane.key.workflow_id == session.workflow_id.value
            and lane.session_revision == session.revision
        )
        if not lanes:
            return
        for lane in lanes:
            self.document.admit_image(lane.preview_id, lane.image, title="Preview")
        self.refresh_preview_scope()
        scene_lanes = tuple(
            lane
            for lane in lanes
            if lane.key.placement is OutputPreviewLanePlacement.SCENE
        )
        if scene_lanes and self.present_scene_previews(scene_lanes):
            return
        source_lane = _source_lane(lanes)
        if source_lane is not None:
            self.present_source_preview(
                source_lane.preview_id,
                source_lane.preview_id in acceptance.created_preview_ids,
            )

    def close_final_output_preview_lane(self, preview_ids: tuple[UUID, ...]) -> None:
        """Retire preview compositions superseded by one finalized output lane."""

        for preview_id in preview_ids:
            self.document.retire_image(preview_id)

    def clear_previews(self, source_key: str | None = None) -> None:
        """Retire registry-cleared preview compositions without touching final content."""

        for preview_id in self.preview_registry().clear(source_key=source_key):
            self.document.retire_image(preview_id)


def _source_lane(
    lanes: tuple[OutputPreviewLane, ...],
) -> OutputPreviewLane | None:
    """Return the source preview that retains precedence over a scene placeholder."""

    return next(
        (
            lane
            for lane in lanes
            if lane.key.placement is OutputPreviewLanePlacement.SOURCE
        ),
        None,
    )


__all__ = ["OutputDocumentPreviewPresenter", "OutputPreviewDocumentPort"]
