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

"""Build shell-side generation snapshots from prepared request state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from substitute.application.generation import (
    CapturedGenerationRequest,
    GenerationJobSnapshot,
    GenerationPreparationResult,
    GenerationRequest,
)

if TYPE_CHECKING:
    from substitute.application.node_behavior import EditorBehaviorSnapshot


class QueuedSnapshotPreparationService(Protocol):
    """Prepare detached queued generation snapshots."""

    def prepare_queued_snapshots(
        self,
        *,
        request: CapturedGenerationRequest,
    ) -> GenerationPreparationResult:
        """Return immutable queued snapshots from a captured request."""


class SceneRunPreparedCallback(Protocol):
    """Apply presentation scene-run bookkeeping for prepared snapshots."""

    def __call__(
        self,
        *,
        workflow_id: str,
        workflow_name: str,
        scene_run_id: str,
        scene_count: int,
        snapshots: tuple[GenerationJobSnapshot, ...],
    ) -> None:
        """Record that a prepared scene run is beginning."""


@dataclass(frozen=True, slots=True)
class QueuedSnapshotPreparation:
    """Carry detached queued snapshot preparation callbacks."""

    prepare_snapshots: Callable[[], GenerationPreparationResult]
    on_prepared: Callable[
        [GenerationPreparationResult], tuple[GenerationJobSnapshot, ...]
    ]


def capture_queued_snapshot_preparation(
    *,
    request: GenerationRequest,
    behavior_snapshot: "EditorBehaviorSnapshot | None",
    preparation_service: QueuedSnapshotPreparationService,
    on_scene_run_prepared: SceneRunPreparedCallback,
) -> QueuedSnapshotPreparation:
    """Capture detached queued snapshot preparation callbacks."""

    captured_request = CapturedGenerationRequest.capture(
        request=request,
        behavior_snapshot=behavior_snapshot,
    )

    def prepare_snapshots() -> GenerationPreparationResult:
        """Prepare queued snapshots from detached state."""

        return preparation_service.prepare_queued_snapshots(request=captured_request)

    def on_prepared(
        result: GenerationPreparationResult,
    ) -> tuple[GenerationJobSnapshot, ...]:
        """Apply scene-run bookkeeping for a prepared queued snapshot result."""

        if result.scene_run_id is not None and result.scene_count is not None:
            on_scene_run_prepared(
                workflow_id=request.workflow_id,
                workflow_name=request.workflow_name,
                scene_run_id=result.scene_run_id,
                scene_count=result.scene_count,
                snapshots=result.snapshots,
            )
        return result.snapshots

    return QueuedSnapshotPreparation(
        prepare_snapshots=prepare_snapshots,
        on_prepared=on_prepared,
    )


__all__ = [
    "capture_queued_snapshot_preparation",
    "QueuedSnapshotPreparation",
    "QueuedSnapshotPreparationService",
    "SceneRunPreparedCallback",
]
