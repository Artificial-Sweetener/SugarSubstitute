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

"""Verify queue ownership of native Cube stage transitions."""

from __future__ import annotations

from substitute.application.generation import GenerationRunStarted

from ..queue_service_test_support import (
    _FakeDispatcher,
    _callbacks,
    _service,
    _snapshot,
)


def test_stage_advance_keeps_one_job_active_and_accepts_next_prompt() -> None:
    """An intermediate prompt cannot complete the user-visible queue job."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    job = service.enqueue_snapshot(_snapshot("Mixed"), _callbacks())
    callbacks = dispatcher.callbacks[0]
    assert callbacks.request_stage_advance is not None
    advanced: list[str] = []

    callbacks.request_stage_advance(lambda: advanced.append("video"))
    assert advanced == ["video"]
    assert service.jobs()[0].status == "running"

    assert callbacks.on_run_started is not None
    callbacks.on_run_started(
        GenerationRunStarted(
            workflow_id=job.snapshot.workflow_id,
            generation_run_id="run-1",
            output_session_id="run-1",
            prompt_id="video-prompt",
            client_id="client-1",
        )
    )
    assert service.jobs()[0].job_id == job.job_id
    assert service.jobs()[0].prompt_id == "video-prompt"


def test_cancelled_job_rejects_pending_stage_advance() -> None:
    """A completion racing with cancellation cannot queue the next Cube."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    job = service.enqueue_snapshot(_snapshot("Mixed"), _callbacks())
    callbacks = dispatcher.callbacks[0]
    assert callbacks.request_stage_advance is not None
    service.cancel_job(job.job_id)
    advanced: list[str] = []

    callbacks.request_stage_advance(lambda: advanced.append("video"))

    assert advanced == []
    assert service.jobs()[0].status == "cancelled"
