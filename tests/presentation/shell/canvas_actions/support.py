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

"""Provide workspace canvas action test support."""

from __future__ import annotations

import importlib
import uuid
from types import ModuleType
from typing import TypeVar


from substitute.application.ports import PreviewImageUpdate
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_canvas_session import (
    bind_output_canvas_session,
)
from substitute.application.workflows.output_canvas_state_service import (
    OutputImageRegistrationResult,
    OutputPreviewCloseIdentity,
    OutputProjectionSchedulingIntent,
)
from substitute.application.workflows.output_canvas_focus_service import (
    OutputFocusMutationResult,
    OutputFocusSnapshot,
)
from substitute.application.workflows.output_visual_events import LivePreviewEvent
from substitute.domain.workflow import (
    CanvasSessionBoundary,
    OutputFocusMode,
)

_RecordT = TypeVar("_RecordT")
_ResultT = TypeVar("_ResultT")


def _import_module() -> ModuleType:
    """Import the workspace canvas actions module."""

    return importlib.import_module(
        "substitute.presentation.shell.workspace_canvas_actions"
    )


def _record_and_return(
    records: list[_RecordT],
    record: _RecordT,
    result: _ResultT,
) -> _ResultT:
    """Record one collaborator call and return its configured result."""

    records.append(record)
    return result


def _registration_result(
    *,
    workflow_id: str,
    image_id: uuid.UUID | None,
    registered: bool = True,
    should_schedule: bool = True,
    preview_close_identity: OutputPreviewCloseIdentity | None = None,
) -> OutputImageRegistrationResult:
    """Return an Output registration result for workspace action stubs."""

    snapshot = OutputFocusSnapshot(
        active_uuid=None,
        set_index=1,
        source_key=None,
        scene_key=None,
        scene_overview=False,
        focus_mode=OutputFocusMode.AUTOMATIC,
    )
    return OutputImageRegistrationResult(
        workflow_id=workflow_id,
        image_id=image_id,
        registered=registered,
        focus_change=OutputFocusMutationResult(before=snapshot, after=snapshot),
        preview_close_identity=preview_close_identity,
        projection_intent=OutputProjectionSchedulingIntent(
            workflow_id=workflow_id,
            registered_image_id=image_id,
            should_schedule=should_schedule,
        ),
    )


def _live_preview(*, workflow_id: str = "wf-1") -> LivePreviewEvent:
    """Return a strict live preview event for workspace action tests."""

    event = LivePreviewEvent.from_update(
        PreviewImageUpdate(
            workflow_id=workflow_id,
            image=object(),
            generation_run_id="run-1",
            prompt_id="prompt-1",
            client_id="client-1",
            node_id="preview-node",
            source_key=f"{workflow_id}:node",
            source_label="Cube",
        )
    )
    assert event is not None
    return event


def _output_session(workflow_id: str = "wf-1") -> object:
    """Return a real Output session for preview acceptance contract tests."""

    return bind_output_canvas_session(
        CanvasSessionBoundary(),
        workflow_id=workflow_id,
        projection=OutputCanvasProjection(
            sources=(),
            active_source_key=None,
            active_set_index=1,
            active_uuid=None,
            set_count=0,
        ),
        image_metadata_lookup={},
    )
