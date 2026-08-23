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

"""Test settings-route queue chrome contracts."""

from __future__ import annotations


from substitute.application.generation import GenerationQueueStateChange

from .support import (
    _availability_view,
)


def test_generation_queue_observer_uses_supplied_jobs_without_projection() -> None:
    """Queue observer path should not ask the queue service to project jobs again."""

    view = _availability_view(
        route="workflow-a",
        queue_active=True,
        queue_cancellable=True,
    )
    view.generation_action_controller.handle_generation_queue_state_changed(
        GenerationQueueStateChange(
            jobs=(),
            change_kind="progress",
            changed_job_id="job-1",
        ),
    )

    assert view.generation_job_queue_service.jobs_calls == 0
    assert view.generationActionCluster.presentation_calls[-1].queue_segment_visible


def test_visible_queue_panel_removes_titlebar_queue_segment() -> None:
    """Full queue panel visibility should hide the redundant titlebar queue segment."""

    view = _availability_view(
        route="workflow-a",
        queue_panel_visible=True,
        queue_visible_jobs=(object(),),
    )

    view.generation_action_controller.apply_generation_action_availability()

    assert view.generationActionCluster.availability_calls == [
        {
            "can_generate": True,
            "can_skip": False,
            "can_stop": False,
            "can_show_queue": True,
        }
    ]
    assert view.generationActionCluster.queue_segment_visible_calls == [False]
