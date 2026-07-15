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

"""Contract tests for generation feedback UI coalescing policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.application.generation import GenerationFailure, GenerationRunStarted
from substitute.application.generation.progress_service import ProgressViewState
from substitute.application.ports import (
    GenerationExecutionTiming,
    ListenerCompleted,
    ModelLoadProgressUpdate,
    OutputImageUpdate,
    PreviewImageUpdate,
    ProgressUpdate,
)
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    LivePreviewEvent,
)
from substitute.presentation.shell.generation_feedback_coalescer import (
    GenerationFeedbackCoalescer,
)


def test_progress_latest_value_wins_before_flush() -> None:
    """Progress coalescing should deliver only the newest pending value."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())

    coalescer.submit_progress(
        _progress_update(workflow_percent=10.0, sampler_percent=1.0)
    )
    coalescer.submit_progress(
        _progress_update(workflow_percent=20.0, sampler_percent=2.0)
    )

    batch = coalescer.drain_due()

    assert batch.progress_updates == (
        _progress_update(workflow_percent=20.0, sampler_percent=2.0),
    )


def test_progress_latest_value_wins_per_workflow_before_flush() -> None:
    """Progress coalescing should retain newest progress for each workflow."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started(workflow_id="wf-a"))
    coalescer.submit_run_started(_run_started(workflow_id="wf-b"))

    coalescer.submit_progress(
        _progress_update(
            workflow_id="wf-a",
            workflow_percent=10.0,
            sampler_percent=1.0,
        )
    )
    coalescer.submit_progress(
        _progress_update(
            workflow_id="wf-a",
            workflow_percent=20.0,
            sampler_percent=2.0,
        )
    )
    coalescer.submit_progress(
        _progress_update(
            workflow_id="wf-b",
            workflow_percent=70.0,
            sampler_percent=7.0,
        )
    )

    assert coalescer.drain_due().progress_updates == (
        _progress_update(
            workflow_id="wf-a",
            workflow_percent=20.0,
            sampler_percent=2.0,
        ),
        _progress_update(
            workflow_id="wf-b",
            workflow_percent=70.0,
            sampler_percent=7.0,
        ),
    )


def test_starting_other_workflow_does_not_retire_current_progress() -> None:
    """Run registration for wf-b must not emit hidden progress for wf-a."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started(workflow_id="wf-a"))
    coalescer.submit_progress(
        _progress_update(
            workflow_id="wf-a",
            workflow_percent=10.0,
            sampler_percent=1.0,
        )
    )
    coalescer.drain_all()

    intent = coalescer.submit_run_started(_run_started(workflow_id="wf-b"))

    assert intent.flush_now is False
    assert coalescer.drain_all().progress_states == ()


def test_progress_without_active_lifecycle_is_ignored() -> None:
    """Progress cannot become visible without an active generation lifecycle."""

    coalescer = GenerationFeedbackCoalescer()

    coalescer.submit_progress(
        _progress_update(workflow_percent=20.0, sampler_percent=2.0)
    )

    assert coalescer.drain_due().progress_updates == ()


def test_progress_completion_forces_immediate_flush() -> None:
    """Progress completion should request immediate GUI delivery."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())

    intent = coalescer.submit_progress(
        _progress_update(workflow_percent=100.0, sampler_percent=None)
    )

    assert intent.flush_now is True


def test_progress_sampler_start_forces_immediate_flush() -> None:
    """Sampler start should flush promptly so model-load overlays clear."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    coalescer.submit_progress(
        _progress_update(workflow_percent=0.0, sampler_percent=0.0)
    )

    intent = coalescer.submit_progress(
        _progress_update(workflow_percent=5.0, sampler_percent=0.5)
    )

    assert intent.flush_now is True


def test_retire_progress_drops_pending_progress_and_emits_hidden_state() -> None:
    """Explicit retirement should clear stale pending progress and hide surfaces."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    coalescer.submit_progress(
        _progress_update(workflow_percent=43.0, sampler_percent=9.0)
    )

    coalescer.retire_progress(reason="stopped")
    batch = coalescer.drain_all()

    assert batch.progress_updates == ()
    assert batch.progress_states == (
        ProgressViewState.hidden(
            workflow_id="wf",
            generation_run_id="run-1",
            prompt_id="pid-1",
        ),
    )


def test_late_progress_after_retire_is_ignored() -> None:
    """Progress from a retired lifecycle should not reopen the overlay."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    coalescer.retire_progress(reason="stopped")
    coalescer.drain_all()

    coalescer.submit_progress(
        _progress_update(workflow_percent=43.0, sampler_percent=9.0)
    )

    assert coalescer.drain_due().progress_updates == ()


def test_progress_for_old_lifecycle_is_ignored_after_replacement() -> None:
    """A newer run for the workflow should make the previous run's progress stale."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    coalescer.submit_run_started(
        GenerationRunStarted(
            workflow_id="wf",
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )
    coalescer.drain_all()

    coalescer.submit_progress(
        _progress_update(workflow_percent=40.0, sampler_percent=4.0)
    )
    coalescer.submit_progress(
        _progress_update(
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
            workflow_percent=50.0,
            sampler_percent=5.0,
        )
    )

    assert coalescer.drain_due().progress_updates == (
        _progress_update(
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
            workflow_percent=50.0,
            sampler_percent=5.0,
        ),
    )


def test_old_lifecycle_retirement_does_not_hide_new_active_progress() -> None:
    """A stale explicit retirement should not clear a newer active run."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    coalescer.submit_run_started(
        _run_started(
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )
    coalescer.drain_all()

    coalescer.retire_progress(
        reason="completed",
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
    )
    current_progress = _progress_update(
        generation_run_id="run-2",
        prompt_id="pid-2",
        client_id="client-2",
        workflow_percent=50.0,
        sampler_percent=5.0,
    )
    coalescer.submit_progress(current_progress)

    batch = coalescer.drain_all()

    assert batch.progress_states == ()
    assert batch.progress_updates == (current_progress,)


def test_stale_completion_does_not_retire_newer_lifecycle() -> None:
    """Completion from run A should not hide or complete run B."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    coalescer.submit_run_started(
        _run_started(
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )
    coalescer.drain_all()

    coalescer.submit_completed(
        ListenerCompleted(
            workflow_id="wf",
            generation_run_id="run-1",
            prompt_id="pid-1",
        )
    )
    current_progress = _progress_update(
        generation_run_id="run-2",
        prompt_id="pid-2",
        client_id="client-2",
        workflow_percent=55.0,
        sampler_percent=6.0,
    )
    coalescer.submit_progress(current_progress)

    batch = coalescer.drain_all()

    assert batch.completed_events == ()
    assert batch.progress_states == ()
    assert batch.progress_updates == (current_progress,)


def test_scene_lifecycle_progress_is_keyed_by_generation_run() -> None:
    """Scene jobs sharing a workflow id should reject prior scene-run progress."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started(generation_run_id="scene-a"))
    coalescer.submit_run_started(
        _run_started(
            generation_run_id="scene-b",
            prompt_id="pid-b",
            client_id="client-b",
        )
    )
    coalescer.drain_all()

    coalescer.submit_progress(
        _progress_update(
            generation_run_id="scene-a",
            prompt_id="pid-1",
            client_id="client-1",
            workflow_percent=40.0,
            sampler_percent=4.0,
        )
    )
    scene_b_progress = _progress_update(
        generation_run_id="scene-b",
        prompt_id="pid-b",
        client_id="client-b",
        workflow_percent=60.0,
        sampler_percent=7.0,
    )
    coalescer.submit_progress(scene_b_progress)

    assert coalescer.drain_due().progress_updates == (scene_b_progress,)


def test_preview_latest_frame_wins_per_source() -> None:
    """Preview coalescing should keep only the newest frame per source."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    first = _preview_update(image="first")
    second = _preview_update(image="second")

    coalescer.submit_preview(first)
    coalescer.submit_preview(second)

    assert coalescer.drain_due().preview_updates == (_live_preview(second),)


def test_preview_keeps_separate_scene_slots() -> None:
    """Scene preview slots should not overwrite unrelated scene previews."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    first = PreviewImageUpdate(
        workflow_id="wf",
        image="first",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        node_id="N1",
        source_key="wf:N1",
        source_label="Cube",
        scene_run_id="run",
        scene_key="scene-a",
        scene_title="Scene A",
        scene_order=0,
        scene_count=2,
    )
    second = PreviewImageUpdate(
        workflow_id="wf",
        image="second",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        node_id="N1",
        source_key="wf:N1",
        source_label="Cube",
        scene_run_id="run",
        scene_key="scene-b",
        scene_title="Scene B",
        scene_order=1,
        scene_count=2,
    )

    coalescer.submit_preview(first)
    coalescer.submit_preview(second)

    assert coalescer.drain_due().preview_updates == (
        _live_preview(first),
        _live_preview(second),
    )


def test_output_images_are_not_coalesced(tmp_path: Path) -> None:
    """Final output image updates should remain lossless."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    first = _output_update(tmp_path / "first.png")
    second = _output_update(tmp_path / "second.png")

    coalescer.submit_output_image(first)
    coalescer.submit_output_image(second)

    assert coalescer.drain_all().output_image_updates == (
        _live_output(first),
        _live_output(second),
    )


def test_final_output_without_list_index_is_dropped(tmp_path: Path) -> None:
    """Live final output updates must carry backend list index identity."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())

    coalescer.submit_output_image(
        _output_update(tmp_path / "missing-index.png", list_index=None)
    )

    assert coalescer.drain_all().output_image_updates == ()


def test_rejected_live_visual_logging_includes_node_and_client(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Rejected visual updates should log useful prompt-safe routing context."""

    coalescer = GenerationFeedbackCoalescer()
    caplog.set_level(
        "DEBUG",
        logger="sugarsubstitute.presentation.shell.generation_feedback_coalescer",
    )

    coalescer.submit_output_image(
        OutputImageUpdate(
            workflow_id="wf",
            workflow_payload={"N1": {"class_type": "SaveImage"}},
            file_path=Path("missing.png"),
            node_id="N1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
            source_key="wf:N1",
            source_label="Cube",
            list_index=None,
            artifact_width=640,
            artifact_height=480,
        )
    )

    assert "client_id=client-1" in caplog.text
    assert "node_id=N1" in caplog.text
    assert "reason=missing_output_identity" in caplog.text


def test_failures_are_not_coalesced() -> None:
    """Failure updates should remain lossless and ordered."""

    coalescer = GenerationFeedbackCoalescer()
    first = GenerationFailure(stage="queue", workflow_id="wf", message="first")
    second = GenerationFailure(stage="listen", workflow_id="wf", message="second")

    coalescer.submit_failure(first)
    coalescer.submit_failure(second)

    assert coalescer.drain_all().failures == (first, second)


def test_completions_are_not_coalesced() -> None:
    """Completion updates should remain lossless and ordered."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())

    coalescer.submit_run_started(
        GenerationRunStarted(
            workflow_id="wf-2",
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )
    first = ListenerCompleted(
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
    )
    second = ListenerCompleted(
        workflow_id="wf-2",
        generation_run_id="run-2",
        prompt_id="pid-2",
    )

    coalescer.submit_completed(first)
    coalescer.submit_completed(second)

    assert coalescer.drain_all().completed_events == (first, second)


def test_timing_updates_are_not_coalesced_and_flush_immediately() -> None:
    """Timing updates should remain lossless durable metadata updates."""

    coalescer = GenerationFeedbackCoalescer()
    first = GenerationExecutionTiming(
        workflow_id="wf",
        prompt_id="pid-1",
        job_duration_ms=850.0,
    )
    second = GenerationExecutionTiming(
        workflow_id="wf",
        prompt_id="pid-2",
        job_duration_ms=1200.0,
    )

    first_intent = coalescer.submit_timing(first)
    second_intent = coalescer.submit_timing(second)

    assert first_intent.flush_now is True
    assert second_intent.flush_now is True
    assert coalescer.pending_counts().timing_count == 2
    assert coalescer.has_terminal_or_durable_updates() is True
    assert coalescer.drain_all().timing_updates == (first, second)


def test_failure_discards_stale_preview_for_failed_workflow() -> None:
    """Failure cleanup should not render stale pending previews first."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    failed_preview = PreviewImageUpdate(
        workflow_id="wf",
        image="failed",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        node_id="N1",
        source_key="wf:N1",
        source_label="Cube",
    )
    coalescer.submit_run_started(
        GenerationRunStarted(
            workflow_id="other",
            generation_run_id="other-run",
            prompt_id="other-pid",
            client_id="other-client",
        )
    )
    other_preview = PreviewImageUpdate(
        workflow_id="other",
        image="other",
        generation_run_id="other-run",
        prompt_id="other-pid",
        client_id="other-client",
        node_id="N1",
        source_key="other:N1",
        source_label="Cube",
    )
    failure = GenerationFailure(
        stage="listen",
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
        message="failed",
    )

    coalescer.submit_preview(failed_preview)
    coalescer.submit_preview(other_preview)
    coalescer.submit_failure(failure)

    batch = coalescer.drain_all()

    assert batch.preview_updates == (_live_preview(other_preview),)
    assert batch.failures == (failure,)


def test_completion_forces_terminal_progress_and_discards_stale_preview() -> None:
    """Completion should flush terminal progress without rendering stale previews."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    preview = _preview_update(image="old")
    completed = ListenerCompleted(
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
    )

    coalescer.submit_preview(preview)
    coalescer.submit_completed(completed)

    batch = coalescer.drain_all()

    assert batch.progress_updates == ()
    assert batch.progress_states == (
        ProgressViewState.hidden(
            workflow_id="wf",
            generation_run_id="run-1",
            prompt_id="pid-1",
        ),
    )
    assert batch.preview_updates == ()
    assert batch.completed_events == (completed,)


def test_failure_retires_matching_lifecycle() -> None:
    """Failure should hide matching active progress and preserve the failure event."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    failure = GenerationFailure(
        stage="listen",
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
        message="failed",
    )

    coalescer.submit_progress(
        _progress_update(workflow_percent=43.0, sampler_percent=9.0)
    )
    coalescer.submit_failure(failure)

    batch = coalescer.drain_all()

    assert batch.progress_updates == ()
    assert batch.progress_states == (
        ProgressViewState.hidden(
            workflow_id="wf",
            generation_run_id="run-1",
            prompt_id="pid-1",
        ),
    )
    assert batch.failures == (failure,)


def test_preview_without_run_identity_is_dropped() -> None:
    """Preview events must not render until they can prove run ownership."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())

    coalescer.submit_preview(
        PreviewImageUpdate(workflow_id="wf", image="old", source_key="wf:N1")
    )

    assert coalescer.drain_due().preview_updates == ()


def test_requeue_stale_preview_is_dropped() -> None:
    """A new active run should make late previews from the previous prompt inert."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    coalescer.submit_run_started(
        GenerationRunStarted(
            workflow_id="wf",
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )

    coalescer.submit_preview(_preview_update(image="stale"))
    coalescer.submit_preview(
        _preview_update(
            image="current",
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )

    current_preview = _preview_update(
        image="current",
        generation_run_id="run-2",
        prompt_id="pid-2",
        client_id="client-2",
    )
    assert coalescer.drain_due().preview_updates == (_live_preview(current_preview),)


def test_final_output_closes_late_preview_lane(tmp_path: Path) -> None:
    """A final image should remove pending previews and reject later matching ones."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    preview = _preview_update(image="preview")
    output = _output_update(tmp_path / "final.png")

    coalescer.submit_preview(preview)
    coalescer.submit_output_image(output)
    coalescer.submit_preview(_preview_update(image="late"))

    batch = coalescer.drain_all()

    assert batch.preview_updates == ()
    assert batch.output_image_updates == (_live_output(output),)


def test_final_output_does_not_close_other_cube_preview(tmp_path: Path) -> None:
    """Final lifecycle closure must be scoped to one output source."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    cube_two = _preview_update(image="cube-2", source_key="wf:N2")

    coalescer.submit_output_image(_output_update(tmp_path / "cube-1.png"))
    coalescer.submit_preview(cube_two)

    assert coalescer.drain_all().preview_updates == (_live_preview(cube_two),)


def test_final_output_does_not_close_other_scene_preview(tmp_path: Path) -> None:
    """Scene lane identity should keep unrelated scenes independent."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    scene_b = _preview_update(
        image="scene-b",
        scene_run_id="scene-run",
        scene_key="scene-b",
    )

    coalescer.submit_output_image(
        _output_update(
            tmp_path / "scene-a.png",
            scene_run_id="scene-run",
            scene_key="scene-a",
        )
    )
    coalescer.submit_preview(scene_b)

    assert coalescer.drain_all().preview_updates == (_live_preview(scene_b),)


def test_batch_final_closes_ambiguous_source_preview(tmp_path: Path) -> None:
    """A list item final should close less-specific previews for that source."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())

    coalescer.submit_output_image(_output_update(tmp_path / "item-0.png", list_index=0))
    coalescer.submit_preview(_preview_update(image="ambiguous"))

    assert coalescer.drain_all().preview_updates == ()


def test_model_load_progress_latest_value_wins_per_field() -> None:
    """Model-load progress should coalesce repeated updates for one editor field."""

    coalescer = GenerationFeedbackCoalescer()
    first = _model_load_update(percent=10.0, state="running")
    second = _model_load_update(percent=20.0, state="running")

    coalescer.submit_model_load_progress(first)
    coalescer.submit_model_load_progress(second)

    assert coalescer.drain_due().model_load_updates == (second,)


def test_model_load_running_progress_uses_scheduled_flush() -> None:
    """Intermediate model-load progress should stay on the coalesced visual lane."""

    coalescer = GenerationFeedbackCoalescer()

    intent = coalescer.submit_model_load_progress(
        _model_load_update(percent=10.0, state="running")
    )

    assert intent.flush_now is False


def test_model_load_state_transition_forces_flush() -> None:
    """Terminal model-load state changes should request immediate GUI delivery."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_model_load_progress(_model_load_update(state="running"))

    intent = coalescer.submit_model_load_progress(_model_load_update(state="finished"))

    assert intent.flush_now is True


def _model_load_update(
    *,
    percent: float = 10.0,
    phase: str = "dynamic_vram_staging",
    state: str = "running",
) -> ModelLoadProgressUpdate:
    """Build one source-enriched model-load progress update."""

    return ModelLoadProgressUpdate(
        workflow_id="wf",
        prompt_id="pid",
        node_id="4",
        display_node_id="4",
        phase=phase,
        state=state,
        percent=percent,
        value=None,
        maximum=None,
        unit=None,
        model_class=None,
        model_name=None,
        source_node_id="2",
        source_input_key="ckpt_name",
        source_cube_alias="Cube",
        source_workflow_node_name="checkpoint",
        detail=None,
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


def _preview_update(
    *,
    image: object,
    generation_run_id: str = "run-1",
    prompt_id: str = "pid-1",
    client_id: str = "client-1",
    node_id: str = "N1",
    source_key: str = "wf:N1",
    scene_run_id: str | None = None,
    scene_key: str | None = None,
) -> PreviewImageUpdate:
    """Build one scoped preview update for coalescer lifecycle tests."""

    scene_title = None
    scene_order = None
    scene_count = None
    if scene_run_id is not None or scene_key is not None:
        scene_title = scene_key or "scene"
        scene_order = 0
        scene_count = 2
    return PreviewImageUpdate(
        workflow_id="wf",
        image=image,
        generation_run_id=generation_run_id,
        prompt_id=prompt_id,
        client_id=client_id,
        node_id=node_id,
        source_key=source_key,
        source_label="Cube",
        scene_run_id=scene_run_id,
        scene_key=scene_key,
        scene_title=scene_title,
        scene_order=scene_order,
        scene_count=scene_count,
    )


def _output_update(
    path: Path,
    *,
    list_index: int | None = 0,
    scene_run_id: str | None = None,
    scene_key: str | None = None,
) -> OutputImageUpdate:
    """Build one scoped final output image update."""

    scene_title = None
    scene_order = None
    scene_count = None
    if scene_run_id is not None or scene_key is not None:
        scene_title = scene_key or "scene"
        scene_order = 0
        scene_count = 2
    return OutputImageUpdate(
        workflow_id="wf",
        workflow_payload={"N1": {"class_type": "SaveImage"}},
        file_path=path,
        node_id="N1",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        source_key="wf:N1",
        source_label="Cube",
        list_index=list_index,
        artifact_width=640,
        artifact_height=480,
        scene_run_id=scene_run_id,
        scene_key=scene_key,
        scene_title=scene_title,
        scene_order=scene_order,
        scene_count=scene_count,
    )


def _live_preview(update: PreviewImageUpdate) -> LivePreviewEvent:
    """Build a strict preview event for coalescer assertions."""

    event = LivePreviewEvent.from_update(update)
    assert event is not None
    return event


def _live_output(update: OutputImageUpdate) -> LiveFinalOutputEvent:
    """Build a strict final event for coalescer assertions."""

    event = LiveFinalOutputEvent.from_update(update)
    assert event is not None
    return event


def _run_started(
    *,
    workflow_id: str = "wf",
    generation_run_id: str = "run-1",
    prompt_id: str = "pid-1",
    client_id: str = "client-1",
) -> GenerationRunStarted:
    """Build one active-run registration event."""

    return GenerationRunStarted(
        workflow_id=workflow_id,
        generation_run_id=generation_run_id,
        prompt_id=prompt_id,
        client_id=client_id,
    )
