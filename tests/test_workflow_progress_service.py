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

"""Tests for workflow-owned generation progress lifecycle state."""

from __future__ import annotations

from substitute.application.generation import GenerationRunStarted
from substitute.application.generation.progress_service import ProgressViewState
from substitute.application.generation.workflow_progress_service import (
    WorkflowProgressService,
)
from substitute.application.ports import ProgressUpdate


def test_progress_update_without_registered_run_is_ignored() -> None:
    """Progress must not become visible without an accepted workflow run."""

    service = WorkflowProgressService()

    assert (
        service.apply_update(
            _progress_update(workflow_percent=25.0, sampler_percent=5.0)
        )
        is None
    )
    assert service.view_for_workflow("wf") == ProgressViewState.hidden(workflow_id="wf")


def test_registered_run_accepts_matching_progress() -> None:
    """A matching update should become the workflow's latest view state."""

    service = WorkflowProgressService()
    service.register_run(_run_started())

    view = service.apply_update(
        _progress_update(workflow_percent=25.0, sampler_percent=5.0)
    )

    assert view == ProgressViewState(
        show_overlay=True,
        workflow_value=25,
        sampler_value=5,
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
    )
    assert service.view_for_workflow("wf") == view


def test_progress_is_latest_state_by_workflow() -> None:
    """Separate workflows should retain independent latest progress views."""

    service = WorkflowProgressService()
    service.register_run(_run_started(workflow_id="wf-a"))
    service.register_run(_run_started(workflow_id="wf-b"))

    service.apply_update(
        _progress_update(
            workflow_id="wf-a",
            workflow_percent=20.0,
            sampler_percent=2.0,
        )
    )
    service.apply_update(
        _progress_update(
            workflow_id="wf-b",
            workflow_percent=70.0,
            sampler_percent=7.0,
        )
    )

    assert service.view_for_workflow("wf-a").workflow_value == 20
    assert service.view_for_workflow("wf-b").workflow_value == 70


def test_registering_other_workflow_does_not_retire_current_workflow() -> None:
    """Accepting a run for one workflow must not hide another workflow."""

    service = WorkflowProgressService()
    service.register_run(_run_started(workflow_id="wf-a"))
    service.apply_update(
        _progress_update(
            workflow_id="wf-a",
            workflow_percent=20.0,
            sampler_percent=2.0,
        )
    )

    retirement = service.register_run(_run_started(workflow_id="wf-b"))

    assert retirement is None
    assert service.view_for_workflow("wf-a").show_overlay is True
    assert service.view_for_workflow("wf-a").workflow_value == 20


def test_replacing_run_retires_only_previous_run_for_same_workflow() -> None:
    """A newer run should clear old progress only for its workflow."""

    service = WorkflowProgressService()
    service.register_run(_run_started(workflow_id="wf-a"))
    service.register_run(_run_started(workflow_id="wf-b"))
    service.apply_update(
        _progress_update(
            workflow_id="wf-a",
            workflow_percent=20.0,
            sampler_percent=2.0,
        )
    )
    service.apply_update(
        _progress_update(
            workflow_id="wf-b",
            workflow_percent=80.0,
            sampler_percent=8.0,
        )
    )

    retirement = service.register_run(
        _run_started(
            workflow_id="wf-a",
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )

    assert retirement == ProgressViewState.hidden(
        workflow_id="wf-a",
        generation_run_id="run-1",
        prompt_id="pid-1",
    )
    assert service.view_for_workflow("wf-a").show_overlay is False
    assert service.view_for_workflow("wf-b").workflow_value == 80


def test_stale_progress_from_old_run_cannot_reopen_workflow() -> None:
    """Progress from a superseded identity should be ignored."""

    service = WorkflowProgressService()
    service.register_run(_run_started())
    service.register_run(
        _run_started(
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )

    stale_view = service.apply_update(
        _progress_update(workflow_percent=40.0, sampler_percent=4.0)
    )
    current_view = service.apply_update(
        _progress_update(
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
            workflow_percent=60.0,
            sampler_percent=6.0,
        )
    )

    assert stale_view is None
    assert current_view is not None
    assert service.view_for_workflow("wf").workflow_value == 60


def test_retiring_workflow_does_not_hide_other_workflow() -> None:
    """A workflow-scoped retirement must not mutate another workflow."""

    service = WorkflowProgressService()
    service.register_run(_run_started(workflow_id="wf-a"))
    service.register_run(_run_started(workflow_id="wf-b"))
    service.apply_update(
        _progress_update(
            workflow_id="wf-a",
            workflow_percent=20.0,
            sampler_percent=2.0,
        )
    )
    service.apply_update(
        _progress_update(
            workflow_id="wf-b",
            workflow_percent=80.0,
            sampler_percent=8.0,
        )
    )

    service.retire_progress(reason="stopped", workflow_id="wf-a")

    assert service.view_for_workflow("wf-a").show_overlay is False
    assert service.view_for_workflow("wf-b").workflow_value == 80


def test_retire_all_hides_every_active_workflow() -> None:
    """Queue-wide cancellation should retire all active workflow progress."""

    service = WorkflowProgressService()
    service.register_run(_run_started(workflow_id="wf-a"))
    service.register_run(_run_started(workflow_id="wf-b"))
    service.apply_update(
        _progress_update(
            workflow_id="wf-a",
            workflow_percent=20.0,
            sampler_percent=2.0,
        )
    )
    service.apply_update(
        _progress_update(
            workflow_id="wf-b",
            workflow_percent=80.0,
            sampler_percent=8.0,
        )
    )

    retired = service.retire_all(reason="stopped")

    assert retired == (
        ProgressViewState.hidden(
            workflow_id="wf-a",
            generation_run_id="run-1",
            prompt_id="pid-1",
        ),
        ProgressViewState.hidden(
            workflow_id="wf-b",
            generation_run_id="run-1",
            prompt_id="pid-1",
        ),
    )
    assert service.view_for_workflow("wf-a").show_overlay is False
    assert service.view_for_workflow("wf-b").show_overlay is False


def test_retiring_old_run_does_not_hide_newer_active_run() -> None:
    """A stale explicit retirement should not hide current workflow progress."""

    service = WorkflowProgressService()
    service.register_run(_run_started())
    service.register_run(
        _run_started(
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )
    service.apply_update(
        _progress_update(
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
            workflow_percent=60.0,
            sampler_percent=6.0,
        )
    )

    retirement = service.retire_progress(
        reason="completed",
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
    )

    assert retirement is None
    assert service.view_for_workflow("wf").workflow_value == 60


def test_view_for_unknown_workflow_returns_hidden_state() -> None:
    """Unknown workflows should project as hidden progress."""

    assert WorkflowProgressService().view_for_workflow(
        "missing"
    ) == ProgressViewState.hidden(workflow_id="missing")


def test_remove_workflow_drops_progress_state() -> None:
    """Closed workflows should lose runtime progress state."""

    service = WorkflowProgressService()
    service.register_run(_run_started())
    service.apply_update(_progress_update(workflow_percent=35.0, sampler_percent=3.0))

    service.remove_workflow("wf")

    assert service.view_for_workflow("wf") == ProgressViewState.hidden(workflow_id="wf")


def test_rename_workflow_preserves_latest_progress_under_new_id() -> None:
    """Workflow id changes should move active runtime progress state."""

    service = WorkflowProgressService()
    service.register_run(_run_started())
    service.apply_update(_progress_update(workflow_percent=35.0, sampler_percent=3.0))

    service.rename_workflow("wf", "wf-renamed")

    assert service.view_for_workflow("wf") == ProgressViewState.hidden(workflow_id="wf")
    renamed = service.view_for_workflow("wf-renamed")
    assert renamed.workflow_id == "wf-renamed"
    assert renamed.workflow_value == 35


def _run_started(
    *,
    workflow_id: str = "wf",
    generation_run_id: str = "run-1",
    prompt_id: str = "pid-1",
    client_id: str = "client-1",
) -> GenerationRunStarted:
    """Build one generation run-start event."""

    return GenerationRunStarted(
        workflow_id=workflow_id,
        generation_run_id=generation_run_id,
        prompt_id=prompt_id,
        client_id=client_id,
    )


def _progress_update(
    *,
    workflow_id: str = "wf",
    generation_run_id: str = "run-1",
    prompt_id: str = "pid-1",
    client_id: str = "client-1",
    workflow_percent: float | None,
    sampler_percent: float | None,
) -> ProgressUpdate:
    """Build one identity-bearing progress update."""

    return ProgressUpdate(
        workflow_id=workflow_id,
        generation_run_id=generation_run_id,
        prompt_id=prompt_id,
        client_id=client_id,
        workflow_percent=workflow_percent,
        sampler_percent=sampler_percent,
    )
