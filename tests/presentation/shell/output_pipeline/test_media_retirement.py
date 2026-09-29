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

"""Verify dependency-safe Output video retirement ordering."""

from __future__ import annotations

from uuid import UUID, uuid4

from substitute.application.workflows.canvas_image_registry import (
    CanvasImageRecord,
    CanvasImageRegistry,
)
from substitute.domain.output_media import OutputMediaKind
from substitute.domain.workflow import ImageMeta
from substitute.presentation.shell.output_media_retirement import (
    OutputMediaRetirementCoordinator,
)


class _Canvas:
    """Record decoder retirement decisions."""

    def __init__(self, events: list[tuple[str, object]], *, succeeds: bool) -> None:
        """Store event sink and deterministic unload outcome."""

        self._events = events
        self._succeeds = succeeds

    def retire_media(self, media_id: UUID) -> bool:
        """Record decoder unload before returning its result."""

        self._events.append(("unload", media_id))
        return self._succeeds


def test_registry_retirement_unloads_video_before_releasing_artifact() -> None:
    """The sole registry removal path should preserve decoder/file ordering."""

    events: list[tuple[str, object]] = []
    canvas = _Canvas(events, succeeds=True)
    coordinator = OutputMediaRetirementCoordinator(
        video_presentation=lambda: canvas,
        release_artifact=lambda metadata: events.append(("release", metadata)),
    )
    registry = CanvasImageRegistry(on_record_removed=coordinator.retire_record)
    media_id = uuid4()
    metadata = _video_metadata()
    registry.store(media_id, payload=object(), metadata=metadata)

    assert registry.remove(media_id)
    assert events == [("unload", media_id), ("release", metadata)]


def test_failed_decoder_unload_defers_artifact_release() -> None:
    """A failed unload should leave the store lease for shutdown cleanup."""

    events: list[tuple[str, object]] = []
    canvas = _Canvas(events, succeeds=False)
    coordinator = OutputMediaRetirementCoordinator(
        video_presentation=lambda: canvas,
        release_artifact=lambda metadata: events.append(("release", metadata)),
    )

    coordinator.retire_record(uuid4(), CanvasImageRecord(None, _video_metadata()))

    assert [event[0] for event in events] == ["unload"]


def _video_metadata() -> ImageMeta:
    """Build temporary video metadata for retirement tests."""

    return ImageMeta(
        workflow_name="Workflow",
        cube_name="Cube",
        image_number=1,
        suffix="",
        path="clip.webm",
        media_kind=OutputMediaKind.VIDEO,
        temporary=True,
    )
