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

"""Test workspace prepared-output commit actions."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtGui import QImage

from substitute.domain.generation import OutputResultPosition


from tests.presentation.shell.canvas_actions.support import (
    _import_module,
    _record_and_return,
    _registration_result,
)


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
            build_output_image_metadata=lambda **kwargs: _record_and_return(
                metadata_calls,
                kwargs,
                image_meta,
            )
        ),
        output_canvas_state_service=SimpleNamespace(
            register_output_image=lambda *args: _record_and_return(
                calls,
                ("register", args),
                _registration_result(
                    workflow_id="wf-a",
                    image_id=image_id,
                    should_schedule=True,
                ),
            ),
        ),
        canvas_host=SimpleNamespace(
            canvas_for={}.get,
            focus_attached_canvas=lambda label: focused_canvases.append(label),
        ),
        workflow_activity_service=SimpleNamespace(
            record_output=lambda *_args: False,
        ),
        workflow_tabbar=SimpleNamespace(
            set_workflow_unread_result=lambda *_args: None,
        ),
        generation_job_queue_service=SimpleNamespace(
            cube_execution_duration_ms=lambda **kwargs: _record_and_return(
                timing_calls,
                kwargs,
                2400.0,
            )
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
        batch_index=0,
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
        position=OutputResultPosition(list_index=2, batch_index=0),
        artifact_width=640,
        artifact_height=480,
    )
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            workflows={"wf-a": object()},
            active_workflow_id="wf-a",
        ),
        canvas_io_service=SimpleNamespace(
            build_output_image_metadata=lambda **kwargs: _record_and_return(
                metadata_calls,
                kwargs,
                image_meta,
            )
        ),
        output_generated_result_service=SimpleNamespace(
            commit_generated_output=lambda *args, **kwargs: _record_and_return(
                calls,
                ("generated", (args, kwargs)),
                _registration_result(
                    workflow_id="wf-a",
                    image_id=image_id,
                    should_schedule=True,
                ),
            ),
        ),
        output_canvas_state_service=SimpleNamespace(
            register_output_image=lambda *args: calls.append(("legacy", args)),
        ),
        canvas_host=SimpleNamespace(canvas_for={}.get),
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
                position=OutputResultPosition(list_index=2, batch_index=0),
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
    generated_call = calls[0][1]
    assert isinstance(generated_call, tuple)
    assert generated_call[1]["event"] == live_event
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
        batch_index=0,
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
        position=OutputResultPosition(list_index=2, batch_index=0),
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
        output_generated_result_service=SimpleNamespace(
            commit_generated_output=lambda *args, **kwargs: _record_and_return(
                calls,
                ("generated", (args, kwargs)),
                _registration_result(
                    workflow_id="wf-a",
                    image_id=None,
                    registered=False,
                    should_schedule=False,
                ),
            ),
        ),
        output_canvas_state_service=SimpleNamespace(
            register_output_image=lambda *args: calls.append(("legacy", args)),
        ),
        canvas_host=SimpleNamespace(canvas_for={}.get),
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
                position=OutputResultPosition(list_index=2, batch_index=0),
                artifact_width=640,
                artifact_height=480,
                live_event=live_event,
            ),
            image=image,
        )
    )

    assert result.registered is False
    assert [name for name, _call in calls] == ["generated"]
