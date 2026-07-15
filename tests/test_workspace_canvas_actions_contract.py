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

"""Contract tests for extracted workspace canvas actions."""

from __future__ import annotations

import importlib
import logging
import uuid
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType
from typing import Any

from PySide6.QtGui import QImage

from substitute.application.ports import PreviewImageUpdate
from substitute.application.ports.file_manager_gateway import (
    FileRevealResult,
    FileRevealStatus,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewAcceptance,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_canvas_session import (
    bind_output_canvas_session,
)
from substitute.application.workflows.output_canvas_state_service import (
    OutputFocusMutationResult,
    OutputFocusSnapshot,
    OutputImageRegistrationResult,
    OutputPreviewCloseIdentity,
    OutputProjectionSchedulingIntent,
)
from substitute.application.workflows.output_visual_events import LivePreviewEvent
from substitute.domain.workflow import (
    CanvasSessionBoundary,
    OutputCompareSelection,
    OutputCompareState,
    OutputFocusMode,
    WorkflowState,
)


def _import_module() -> ModuleType:
    """Import the workspace canvas actions module."""

    return importlib.import_module(
        "substitute.presentation.shell.workspace_canvas_actions"
    )


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


def test_reveal_output_asset_delegates_metadata_path_to_application_service() -> None:
    """Output-context intent should remain a thin adapter over the reveal use case."""

    mod = _import_module()
    paths: list[str] = []
    reveal_service = SimpleNamespace(
        reveal_asset=lambda path: (
            paths.append(path),
            FileRevealResult(FileRevealStatus.REVEALED),
        )[1]
    )
    actions = mod.WorkspaceCanvasActions(
        SimpleNamespace(),
        asset_reveal_service=reveal_service,
    )

    revealed = actions.reveal_output_asset(SimpleNamespace(path="C:/outputs/image.png"))

    assert revealed is True
    assert paths == ["C:/outputs/image.png"]


def test_reveal_output_asset_rejects_metadata_without_path() -> None:
    """Malformed metadata should not invoke the application reveal service."""

    mod = _import_module()
    reveal_service = SimpleNamespace(
        reveal_asset=lambda _path: (_ for _ in ()).throw(
            AssertionError("missing paths must not be revealed")
        )
    )
    actions = mod.WorkspaceCanvasActions(
        SimpleNamespace(),
        asset_reveal_service=reveal_service,
    )

    assert actions.reveal_output_asset(SimpleNamespace(path=None)) is False


def test_workspace_canvas_actions_no_longer_owns_input_phase16_policy() -> None:
    """Input mask tools, presenter intent, and picker refresh live outside actions."""

    mod = _import_module()
    action_names = set(dir(mod.WorkspaceCanvasActions))
    retired_names = {
        "on_input_image_changed",
        "on_input_canvas_image_loaded",
        "reconcile_active_input_canvas_image",
        "on_input_image_clicked",
        "refresh_active_mask_pickers",
        "on_input_mask_changed",
        "on_input_mask_clicked",
        "on_mask_save_completed",
        "materialize_loaded_cube_input_canvas",
    }

    assert action_names.isdisjoint(retired_names)


def test_display_preview_image_updates_only_active_workflow() -> None:
    """Strict previews should display only after registry/session acceptance."""

    mod = _import_module()
    previews: list[OutputPreviewAcceptance] = []
    registry_calls: list[str] = []
    focused: list[str] = []
    accepted = OutputPreviewAcceptance(accepted=True)
    output_canvas = SimpleNamespace(
        _output_session=_output_session(),
        apply_preview_acceptance=previews.append,
    )
    registry = SimpleNamespace(
        accept_preview=lambda preview, **_kwargs: (
            registry_calls.append(preview.identity.workflow_id),
            accepted
            if preview.identity.workflow_id == "wf-1"
            else OutputPreviewAcceptance(accepted=False),
        )[1]
    )
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-1"),
        canvas_tabs=SimpleNamespace(
            canvas_map={"Output": output_canvas},
            focus_attached_canvas=lambda label: focused.append(label),
        ),
        output_preview_registry=registry,
        visual_authorization_service=SimpleNamespace(
            authorize_preview=lambda _identity: True
        ),
        _log_missing_output_canvas=lambda _workflow_id: None,
    )
    actions = mod.WorkspaceCanvasActions(view)

    actions.display_preview_image(_live_preview(workflow_id="wf-2"))
    actions.display_preview_image(_live_preview(workflow_id="wf-1"))

    assert registry_calls == ["wf-2", "wf-1"]
    assert previews == [accepted]
    assert focused == []


def test_clear_output_previews_updates_only_active_workflow() -> None:
    """Preview cleanup should only reach the output canvas for the active workflow."""

    mod = _import_module()
    clear_calls: list[bool] = []
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-1"),
        canvas_tabs=SimpleNamespace(
            canvas_map={
                "Output": SimpleNamespace(
                    clear_previews=lambda: clear_calls.append(True)
                )
            }
        ),
        _log_missing_output_canvas=lambda _workflow_id: None,
    )
    actions = mod.WorkspaceCanvasActions(view)

    actions.clear_output_previews("wf-2")
    actions.clear_output_previews("wf-1")

    assert clear_calls == [True]


def test_active_output_selection_records_manual_uuid() -> None:
    """Concrete output selection should delegate to OutputCanvasStateService."""

    mod = _import_module()
    workflow = WorkflowState()
    calls: list[tuple[object, str]] = []
    view = SimpleNamespace(
        get_active_workflow=lambda: workflow,
        output_canvas_state_service=SimpleNamespace(
            set_active_output_uuid=lambda active_workflow, uuid_str: calls.append(
                (active_workflow, uuid_str)
            )
        ),
    )

    mod.WorkspaceCanvasActions(view).on_active_output_changed("out-1")

    assert calls == [(workflow, "out-1")]


def test_active_output_grid_selection_records_manual_grid() -> None:
    """Grid output selection should delegate to OutputCanvasStateService."""

    mod = _import_module()
    workflow = WorkflowState()
    calls: list[tuple[object, str, object]] = []
    view = SimpleNamespace(
        get_active_workflow=lambda: workflow,
        output_canvas_state_service=SimpleNamespace(
            set_active_output_grid=lambda active_workflow, source_key, scene_key=None: (
                calls.append((active_workflow, source_key, scene_key))
            )
        ),
    )

    mod.WorkspaceCanvasActions(view).on_active_output_grid_changed("wf:node")

    assert calls == [(workflow, "wf:node", None)]


def test_active_output_scene_selection_records_manual_scene() -> None:
    """Scene output selection should delegate to OutputCanvasStateService."""

    mod = _import_module()
    workflow = WorkflowState()
    calls: list[tuple[object, str | None, bool]] = []
    view = SimpleNamespace(
        get_active_workflow=lambda: workflow,
        output_canvas_state_service=SimpleNamespace(
            set_active_output_scene=lambda active_workflow, scene_key, *, overview: (
                calls.append((active_workflow, scene_key, overview))
            )
        ),
    )

    mod.WorkspaceCanvasActions(view).on_active_output_scene_changed("scene-a", False)
    mod.WorkspaceCanvasActions(view).on_active_output_scene_changed("", True)

    assert calls == [(workflow, "scene-a", False), (workflow, None, True)]


def test_output_compare_selection_records_compare_state() -> None:
    """Output compare changes should delegate to OutputCanvasStateService."""

    mod = _import_module()
    workflow = WorkflowState()
    calls: list[tuple[WorkflowState, OutputCompareState]] = []
    view = SimpleNamespace(
        get_active_workflow=lambda: workflow,
        output_canvas_state_service=SimpleNamespace(
            set_output_compare_state=lambda active_workflow, state: calls.append(
                (active_workflow, state)
            )
        ),
    )
    state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "source-a"),
        comparison=OutputCompareSelection(None, 1, "source-b"),
    )

    mod.WorkspaceCanvasActions(view).on_output_compare_changed(state)

    assert calls == [(workflow, state)]


def test_output_selection_intents_schedule_active_projection() -> None:
    """Persisted Output selection intents should schedule active workflow projection."""

    mod = _import_module()
    workflow = WorkflowState()
    scheduled: list[str] = []
    view = SimpleNamespace(
        get_active_workflow=lambda: workflow,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf"),
        output_canvas_state_service=SimpleNamespace(
            set_active_output_uuid=lambda *_args: None,
            set_active_output_grid=lambda *_args, **_kwargs: None,
            set_active_output_scene=lambda *_args, **_kwargs: None,
            set_output_compare_state=lambda *_args: None,
        ),
        output_image_pipeline=SimpleNamespace(
            schedule_user_selected_output_projection=scheduled.append,
        ),
    )
    state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "source-a"),
        comparison=OutputCompareSelection(None, 1, "source-b"),
    )
    actions = mod.WorkspaceCanvasActions(view)

    actions.on_active_output_changed("out-1")
    actions.on_active_output_grid_changed("wf:node")
    actions.on_active_output_scene_changed("scene-a", False)
    actions.on_output_compare_changed(state)

    assert scheduled == ["wf", "wf", "wf", "wf"]


def test_update_canvas_callback_submits_output_update_to_pipeline(
    tmp_path: Path,
) -> None:
    """Generated output callbacks should delegate to the async output pipeline."""

    mod = _import_module()

    submitted: list[object] = []
    image_path = tmp_path / "007_output.png"
    image_path.write_text("x")
    view = SimpleNamespace(
        output_image_pipeline=SimpleNamespace(
            submit_legacy_output_update=lambda update: submitted.append(update)
        ),
    )
    actions = mod.WorkspaceCanvasActions(view)

    actions.update_canvas_callback(
        workflow_id="wf-1",
        workflow={"save-node": {"_meta": {"title": "LocalCube.CubeOutput"}}},
        file_path=str(image_path),
        node_id="save-node",
        source_key="wf-1:websocket-node",
        source_label="Resolved Output",
        scene_run_id="run-1",
        scene_key="portrait",
        scene_title="Portrait",
        scene_order=0,
        scene_count=2,
    )

    assert len(submitted) == 1
    update = submitted[0]
    assert update.workflow_id == "wf-1"
    assert update.workflow_payload == {
        "save-node": {"_meta": {"title": "LocalCube.CubeOutput"}}
    }
    assert update.file_path == image_path
    assert update.node_id == "save-node"
    assert update.source_key == "wf-1:websocket-node"
    assert update.source_label == "Resolved Output"
    assert update.scene_run_id == "run-1"
    assert update.scene_key == "portrait"
    assert update.scene_title == "Portrait"
    assert update.scene_order == 0
    assert update.scene_count == 2


def test_output_image_preparation_failure_reports_error(
    tmp_path: Path,
) -> None:
    """Generated output load failures should use the unified error modal presenter."""

    mod = _import_module()
    from substitute.presentation.shell.output_image_commit_pipeline import (
        FailedOutputImagePreparation,
        OutputImageCommitRequest,
    )

    image_path = tmp_path / "missing.png"
    reports: list[Any] = []
    critical_calls: list[object] = []
    actions = mod.WorkspaceCanvasActions(
        SimpleNamespace(),
        error_presenter=SimpleNamespace(
            show_error_report=lambda report: reports.append(report)
        ),
    )

    actions.handle_output_image_preparation_failed(
        FailedOutputImagePreparation(
            request=OutputImageCommitRequest(
                workflow_id="wf-1",
                file_path=image_path,
                node_id="save-node",
                node_meta_title="",
                workflow_name="Workflow",
                source_key="wf-1:websocket-node",
                source_label="Resolved Output",
                scene_run_id="run-1",
                scene_key="portrait",
                scene_title="Portrait",
                scene_order=0,
                scene_count=2,
            ),
            message="failed",
        ),
        message_box=SimpleNamespace(
            critical=lambda *args, **_kwargs: critical_calls.append(args)
        ),
    )

    assert critical_calls == []
    report = reports[0]
    assert report.kind.value == "substitute_internal"
    assert report.title == "Generated image load failed"
    assert report.stage == "canvas"
    assert report.workflow_id == "wf-1"
    assert report.operation_context.operation == "load_generated_output_image"
    assert report.operation_context.node_id == "save-node"
    assert report.operation_context.path == str(image_path)
    assert report.operation_context.values["source_key"] == "wf-1:websocket-node"
    assert report.operation_context.values["scene_key"] == "portrait"


def test_handle_add_output_image_registers_without_direct_output_route_mutation() -> (
    None
):
    """Final outputs should register state without directly mutating Output routes."""

    mod = _import_module()
    added: list[tuple[object, ...]] = []
    closed_preview_lanes: list[OutputPreviewCloseIdentity] = []
    preview_acceptances: list[OutputPreviewAcceptance] = []
    scheduled_projection: list[OutputProjectionSchedulingIntent] = []
    unread_tabs: list[tuple[str, bool]] = []
    recorded_activity: list[tuple[str, str]] = []
    first_image_id = uuid.uuid4()
    second_image_id = uuid.uuid4()
    preview_identity = OutputPreviewCloseIdentity(
        workflow_id="wf-a",
        image_id=first_image_id,
        source_key="wf-a:save",
        source_label="Save",
        generation_run_id="run-1",
        prompt_id="prompt-1",
        client_id="client-1",
        node_id="save",
        list_index=0,
        scene_run_id=None,
        scene_key=None,
        scene_title=None,
        scene_order=None,
        scene_count=None,
    )

    def register_output(
        _workflows: object,
        workflow_id: str,
        active_workflow_id: str,
        image: object,
        image_meta: object,
    ) -> OutputImageRegistrationResult:
        image_id = first_image_id if workflow_id == "wf-a" else second_image_id
        added.append(("register", workflow_id, active_workflow_id, image, image_meta))
        return _registration_result(
            workflow_id=workflow_id,
            image_id=image_id,
            should_schedule=workflow_id == active_workflow_id,
            preview_close_identity=preview_identity
            if workflow_id == active_workflow_id
            else None,
        )

    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            workflows={"wf-a": object()},
            active_workflow_id="wf-a",
        ),
        output_canvas_state_service=SimpleNamespace(
            register_output_image=register_output,
        ),
        output_image_pipeline=SimpleNamespace(
            schedule_output_projection=scheduled_projection.append
        ),
        output_preview_registry=SimpleNamespace(
            close_final_output_lane=lambda identity: (
                closed_preview_lanes.append(identity),
                SimpleNamespace(closed=True, closed_preview_ids=(uuid.uuid4(),)),
            )[1]
        ),
        canvas_tabs=SimpleNamespace(
            canvas_map={
                "Output": SimpleNamespace(
                    apply_preview_acceptance=preview_acceptances.append
                )
            },
            focus_attached_canvas=lambda _label: (_ for _ in ()).throw(
                AssertionError("registration must not focus Output")
            ),
        ),
        workflow_activity_service=SimpleNamespace(
            record_output=lambda workflow_id, active_workflow_id: (
                recorded_activity.append((workflow_id, active_workflow_id)),
                workflow_id != active_workflow_id,
            )[1]
        ),
        workflow_tabbar=SimpleNamespace(
            set_workflow_unread_result=lambda workflow_id, unread: unread_tabs.append(
                (workflow_id, unread)
            )
        ),
    )

    actions = mod.WorkspaceCanvasActions(view)
    actions.handle_add_output_image("wf-a", "image-a", "meta-a")
    actions.handle_add_output_image("wf-b", "image-b", "meta-b")

    assert [entry[0] for entry in added] == ["register", "register"]
    assert closed_preview_lanes == [preview_identity]
    assert len(preview_acceptances) == 1
    assert preview_acceptances[0].retired_preview_ids
    assert len(scheduled_projection) == 1
    assert scheduled_projection[0].workflow_id == "wf-a"
    assert scheduled_projection[0].registered_image_id == first_image_id
    assert recorded_activity == [("wf-a", "wf-a"), ("wf-b", "wf-a")]
    assert unread_tabs == [("wf-b", True)]


def test_handle_loaded_output_image_schedules_without_generated_output_side_effects() -> (
    None
):
    """Loaded recipe outputs should not trigger generated-output maintenance."""

    mod = _import_module()
    added: list[tuple[object, ...]] = []
    scheduled_projection: list[OutputProjectionSchedulingIntent] = []
    image_id = uuid.uuid4()

    def register_output(
        _workflows: object,
        workflow_id: str,
        active_workflow_id: str,
        image: object,
        image_meta: object,
    ) -> OutputImageRegistrationResult:
        added.append(("register", workflow_id, active_workflow_id, image, image_meta))
        return _registration_result(
            workflow_id=workflow_id,
            image_id=image_id,
            should_schedule=workflow_id == active_workflow_id,
        )

    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            workflows={"wf-a": object()},
            active_workflow_id="wf-a",
        ),
        output_canvas_state_service=SimpleNamespace(
            register_output_image=register_output,
        ),
        output_image_pipeline=SimpleNamespace(
            schedule_output_projection=scheduled_projection.append
        ),
        output_preview_registry=SimpleNamespace(
            close_final_output_lane=lambda _identity: (_ for _ in ()).throw(
                AssertionError("loaded output must not close preview lanes")
            )
        ),
        workflow_activity_service=SimpleNamespace(
            record_output=lambda *_args: (_ for _ in ()).throw(
                AssertionError("loaded output must not record generated activity")
            )
        ),
        workflow_surface_invalidation_service=SimpleNamespace(
            mark_dirty=lambda *_args: (_ for _ in ()).throw(
                AssertionError("loaded output must not dirty generation surfaces")
            )
        ),
    )

    mod.WorkspaceCanvasActions(view).handle_loaded_output_image(
        "wf-a",
        "image-a",
        "meta-a",
    )

    assert added == [("register", "wf-a", "wf-a", "image-a", "meta-a")]
    assert len(scheduled_projection) == 1
    assert scheduled_projection[0].workflow_id == "wf-a"
    assert scheduled_projection[0].registered_image_id == image_id


def test_handle_add_output_image_leaves_inactive_preview_lane_visible() -> None:
    """Inactive final output registration should not close visible preview lanes."""

    mod = _import_module()
    image_id = uuid.uuid4()
    close_identity = OutputPreviewCloseIdentity(
        workflow_id="wf-b",
        image_id=image_id,
        source_key="wf-b:save",
        source_label="Save",
        generation_run_id="run-1",
        prompt_id="prompt-1",
        client_id="client-1",
        node_id="save",
        list_index=0,
        scene_run_id=None,
        scene_key=None,
        scene_title=None,
        scene_order=None,
        scene_count=None,
    )
    closed_preview_lanes: list[OutputPreviewCloseIdentity] = []
    preview_acceptances: list[OutputPreviewAcceptance] = []
    scheduled_projection: list[OutputProjectionSchedulingIntent] = []
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            workflows={"wf-a": object(), "wf-b": object()},
            active_workflow_id="wf-a",
        ),
        output_canvas_state_service=SimpleNamespace(
            register_output_image=lambda *_args: _registration_result(
                workflow_id="wf-b",
                image_id=image_id,
                should_schedule=False,
                preview_close_identity=close_identity,
            )
        ),
        output_image_pipeline=SimpleNamespace(
            schedule_output_projection=scheduled_projection.append
        ),
        output_preview_registry=SimpleNamespace(
            close_final_output_lane=lambda identity: (
                closed_preview_lanes.append(identity),
                SimpleNamespace(closed=True, closed_preview_ids=(uuid.uuid4(),)),
            )[1]
        ),
        canvas_tabs=SimpleNamespace(
            canvas_map={
                "Output": SimpleNamespace(
                    apply_preview_acceptance=preview_acceptances.append
                )
            }
        ),
        workflow_activity_service=SimpleNamespace(
            record_output=lambda *_args: False,
        ),
        workflow_tabbar=SimpleNamespace(
            set_workflow_unread_result=lambda *_args: None,
        ),
    )

    mod.WorkspaceCanvasActions(view).handle_add_output_image("wf-b", "image", "meta")

    assert closed_preview_lanes == [close_identity]
    assert preview_acceptances == []
    assert scheduled_projection == []


def test_commit_prepared_output_image_registers_without_direct_pane_mutation() -> None:
    """Prepared output commits should register state and return scheduling intent."""

    mod = _import_module()
    from substitute.presentation.shell.output_image_commit_pipeline import (
        OutputImageCommitRequest,
        PreparedOutputImage,
    )

    image_id = uuid.uuid4()
    calls: list[tuple[str, object]] = []
    focused_canvases: list[str] = []
    metadata_calls: list[dict[str, object]] = []
    timing_calls: list[dict[str, str]] = []
    image = QImage(8, 8, QImage.Format.Format_ARGB32)
    image_meta = SimpleNamespace(path="E:/out.png")
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            workflows={"wf-a": object()},
            active_workflow_id="wf-a",
        ),
        canvas_io_service=SimpleNamespace(
            build_output_image_metadata=lambda **kwargs: (
                metadata_calls.append(kwargs),
                image_meta,
            )[1]
        ),
        output_canvas_state_service=SimpleNamespace(
            register_output_image=lambda *args: (
                calls.append(("register", args)),
                _registration_result(
                    workflow_id="wf-a",
                    image_id=image_id,
                    should_schedule=True,
                ),
            )[1],
        ),
        canvas_tabs=SimpleNamespace(
            canvas_map={},
            focus_attached_canvas=lambda label: focused_canvases.append(label),
        ),
        workflow_activity_service=SimpleNamespace(
            record_output=lambda *_args: False,
        ),
        workflow_tabbar=SimpleNamespace(
            set_workflow_unread_result=lambda *_args: None,
        ),
        generation_job_queue_service=SimpleNamespace(
            cube_execution_duration_ms=lambda **kwargs: (
                timing_calls.append(kwargs),
                2400.0,
            )[1]
        ),
    )

    result = mod.WorkspaceCanvasActions(view).commit_prepared_output_image(
        PreparedOutputImage(
            request=OutputImageCommitRequest(
                workflow_id="wf-a",
                file_path=Path("E:/out.png"),
                node_id="save",
                node_meta_title="Cube.Output",
                workflow_name="Workflow",
                source_key="wf-a:save",
                source_label="Save",
            ),
            image=image,
        )
    )

    assert result.image_id == image_id
    assert metadata_calls[0]["source_key"] == "wf-a:save"
    assert metadata_calls[0]["node_id"] == "save"
    assert metadata_calls[0]["cube_execution_duration_ms"] == 2400.0
    assert timing_calls == [
        {
            "workflow_id": "wf-a",
            "source_key": "wf-a:save",
            "cube_alias": "Save",
        }
    ]
    assert calls[0][0] == "register"
    assert len(calls) == 1
    assert result.projection_intent.should_schedule is True
    assert result.projection_intent.registered_image_id == image_id
    assert focused_canvases == []


def test_commit_prepared_live_output_uses_generated_registration() -> None:
    """Live final commits should register with strict backend event identity."""

    mod = _import_module()
    from substitute.application.workflows.output_visual_events import (
        LiveFinalOutputEvent,
        OutputVisualIdentity,
        SourceOnlyOutputIdentity,
    )
    from substitute.presentation.shell.output_image_commit_pipeline import (
        OutputImageCommitRequest,
        PreparedOutputImage,
    )

    image_id = uuid.uuid4()
    calls: list[tuple[str, object]] = []
    metadata_calls: list[dict[str, object]] = []
    image = QImage(8, 8, QImage.Format.Format_ARGB32)
    image_meta = SimpleNamespace(
        path="E:/out.png",
        source_key="wf-a:save",
        source_label="Save",
        generation_run_id="run-1",
        prompt_id="prompt-1",
        client_id="client-1",
        list_index=2,
    )
    live_event = LiveFinalOutputEvent(
        identity=OutputVisualIdentity(
            workflow_id="wf-a",
            generation_run_id="run-1",
            prompt_id="prompt-1",
            client_id="client-1",
            source_key="wf-a:save",
            source_label="Save",
            scene=SourceOnlyOutputIdentity(),
        ),
        node_id="save",
        workflow_payload={"save": {"class_type": "SugarCubes.CubeOutput"}},
        file_path=Path("E:/out.png"),
        list_index=2,
        artifact_width=640,
        artifact_height=480,
    )
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            workflows={"wf-a": object()},
            active_workflow_id="wf-a",
        ),
        canvas_io_service=SimpleNamespace(
            build_output_image_metadata=lambda **kwargs: (
                metadata_calls.append(kwargs),
                image_meta,
            )[1]
        ),
        output_canvas_state_service=SimpleNamespace(
            register_generated_output=lambda *args, **kwargs: (
                calls.append(("generated", (args, kwargs))),
                _registration_result(
                    workflow_id="wf-a",
                    image_id=image_id,
                    should_schedule=True,
                ),
            )[1],
            register_output_image=lambda *args: calls.append(("legacy", args)),
        ),
        canvas_tabs=SimpleNamespace(canvas_map={}),
        workflow_activity_service=SimpleNamespace(
            record_output=lambda *_args: False,
        ),
        workflow_tabbar=SimpleNamespace(
            set_workflow_unread_result=lambda *_args: None,
        ),
    )

    result = mod.WorkspaceCanvasActions(view).commit_prepared_output_image(
        PreparedOutputImage(
            request=OutputImageCommitRequest(
                workflow_id="wf-a",
                file_path=Path("E:/out.png"),
                node_id="save",
                node_meta_title="Cube.Output",
                workflow_name="Workflow",
                source_key="wf-a:save",
                source_label="Save",
                generation_run_id="run-1",
                prompt_id="prompt-1",
                client_id="client-1",
                list_index=2,
                artifact_width=640,
                artifact_height=480,
                live_event=live_event,
            ),
            image=image,
        )
    )

    assert result.image_id == image_id
    assert metadata_calls[0]["list_index"] == 2
    assert metadata_calls[0]["node_id"] == "save"
    assert metadata_calls[0]["width"] == 640
    assert metadata_calls[0]["height"] == 480
    assert calls[0][0] == "generated"
    assert calls[0][1][1]["event"] == live_event
    assert len(calls) == 1
    assert result.projection_intent.should_schedule is True


def test_commit_prepared_live_output_rejection_skips_routes_and_activity() -> None:
    """Live registration rejection should not mutate visible Output routes."""

    mod = _import_module()
    from substitute.application.workflows.output_visual_events import (
        LiveFinalOutputEvent,
        OutputVisualIdentity,
        SourceOnlyOutputIdentity,
    )
    from substitute.presentation.shell.output_image_commit_pipeline import (
        OutputImageCommitRequest,
        PreparedOutputImage,
    )

    calls: list[tuple[str, object]] = []
    image = QImage(8, 8, QImage.Format.Format_ARGB32)
    image_meta = SimpleNamespace(
        path="E:/out.png",
        source_key="wf-a:save",
        source_label="Save",
        generation_run_id="run-1",
        prompt_id="prompt-1",
        client_id="client-1",
        list_index=2,
    )
    live_event = LiveFinalOutputEvent(
        identity=OutputVisualIdentity(
            workflow_id="wf-a",
            generation_run_id="run-1",
            prompt_id="prompt-1",
            client_id="client-1",
            source_key="wf-a:save",
            source_label="Save",
            scene=SourceOnlyOutputIdentity(),
        ),
        node_id="save",
        workflow_payload={"save": {"class_type": "SugarCubes.CubeOutput"}},
        file_path=Path("E:/out.png"),
        list_index=2,
        artifact_width=640,
        artifact_height=480,
    )
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            workflows={"wf-a": object()},
            active_workflow_id="wf-a",
        ),
        canvas_io_service=SimpleNamespace(
            build_output_image_metadata=lambda **_kwargs: image_meta,
        ),
        output_canvas_state_service=SimpleNamespace(
            register_generated_output=lambda *args, **kwargs: (
                calls.append(("generated", (args, kwargs))),
                _registration_result(
                    workflow_id="wf-a",
                    image_id=None,
                    registered=False,
                    should_schedule=False,
                ),
            )[1],
            register_output_image=lambda *args: calls.append(("legacy", args)),
        ),
        canvas_tabs=SimpleNamespace(canvas_map={}),
        workflow_activity_service=SimpleNamespace(
            record_output=lambda *_args: calls.append(("activity", ())),
        ),
        workflow_tabbar=SimpleNamespace(
            set_workflow_unread_result=lambda *_args: None,
        ),
    )

    result = mod.WorkspaceCanvasActions(view).commit_prepared_output_image(
        PreparedOutputImage(
            request=OutputImageCommitRequest(
                workflow_id="wf-a",
                file_path=Path("E:/out.png"),
                node_id="save",
                node_meta_title="Cube.Output",
                workflow_name="Workflow",
                source_key="wf-a:save",
                source_label="Save",
                generation_run_id="run-1",
                prompt_id="prompt-1",
                client_id="client-1",
                list_index=2,
                artifact_width=640,
                artifact_height=480,
                live_event=live_event,
            ),
            image=image,
        )
    )

    assert result.registered is False
    assert [name for name, _call in calls] == ["generated"]


def test_commit_prepared_output_image_rejects_stale_authorized_run(
    caplog,
) -> None:
    """Prepared output commits should re-authorize before state mutation."""

    mod = _import_module()
    from substitute.presentation.shell.output_image_commit_pipeline import (
        OutputImageCommitRequest,
        PreparedOutputImage,
    )

    metadata_calls: list[object] = []
    state_calls: list[tuple[str, object]] = []
    image = QImage(8, 8, QImage.Format.Format_ARGB32)
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            workflows={"wf-a": object()},
            active_workflow_id="wf-a",
        ),
        visual_authorization_service=SimpleNamespace(
            authorize_final_output=lambda _identity: False
        ),
        canvas_io_service=SimpleNamespace(
            build_output_image_metadata=lambda **kwargs: metadata_calls.append(kwargs)
        ),
        output_canvas_state_service=SimpleNamespace(
            register_output_image=lambda *args: state_calls.append(("register", args)),
        ),
    )
    caplog.set_level(
        logging.WARNING,
        logger="sugarsubstitute.presentation.shell.workspace_canvas_actions",
    )

    result = mod.WorkspaceCanvasActions(view).commit_prepared_output_image(
        PreparedOutputImage(
            request=OutputImageCommitRequest(
                workflow_id="wf-a",
                file_path=Path("E:/out.png"),
                node_id="save",
                node_meta_title="Cube.Output",
                workflow_name="Workflow",
                source_key="wf-a:save",
                source_label="Save",
                generation_run_id="run-stale",
                prompt_id="prompt-1",
                client_id="client-1",
            ),
            image=image,
        )
    )

    assert result.workflow_id == "wf-a"
    assert result.projection_intent.should_schedule is False
    assert result.active_output_changed is False
    assert metadata_calls == []
    assert state_calls == []
    assert "post_prepare_authorization_failed" in caplog.text
