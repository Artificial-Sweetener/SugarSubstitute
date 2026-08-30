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

"""Build deterministic shell state for feedback presenter tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


from substitute.application.ports import (
    ModelLoadProgressUpdate,
)
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    OutputVisualIdentity,
    SourceOnlyOutputIdentity,
)
from substitute.domain.generation import OutputResultPosition


def _live_output(tmp_path: Path) -> LiveFinalOutputEvent:
    """Build a strict live output event for presenter tests."""

    return LiveFinalOutputEvent(
        identity=OutputVisualIdentity(
            workflow_id="wf-1",
            generation_run_id="run-output",
            prompt_id="prompt-output",
            client_id="client-output",
            source_key="wf-1:N1",
            source_label="MyCube",
            scene=SourceOnlyOutputIdentity(),
        ),
        node_id="N1",
        workflow_payload={"N1": {"_meta": {"title": "MyCube.KSampler"}}},
        file_path=tmp_path / "007_cube_preview.png",
        position=OutputResultPosition(list_index=0, batch_index=0),
        artifact_width=640,
        artifact_height=480,
    )


def _model_load_update() -> ModelLoadProgressUpdate:
    """Build source-enriched model-load progress for presenter tests."""

    return ModelLoadProgressUpdate(
        workflow_id="wf-1",
        prompt_id="pid-1",
        node_id="4",
        display_node_id="4",
        phase="dynamic_vram_staging",
        state="running",
        percent=42.5,
        value=2048.0,
        maximum=4897.0,
        unit="bytes",
        model_class="SDXL",
        model_name="example.safetensors",
        source_node_id="2",
        source_input_key="ckpt_name",
        source_cube_alias="Cube",
        source_workflow_node_name="checkpoint",
        detail=None,
    )


def _feedback_shell(**overrides: object) -> SimpleNamespace:
    """Build a shell fake with default feedback collaborators."""

    values: dict[str, object] = {
        "active_editor_panel": None,
        "editor_panels": {},
        "generation_action_controller": SimpleNamespace(
            clear_generation_progress=lambda: None
        ),
        "workspace_controller": None,
        "_comfy_output_stream": SimpleNamespace(append_line=lambda _line: None),
        "_error_presenter": None,
        "_taskbar_progress_presenter": SimpleNamespace(clear_progress=lambda: None),
        "workflow_session_service": SimpleNamespace(
            workflows={},
            active_workflow_id="wf-1",
        ),
        "output_canvas_projection_coordinator": SimpleNamespace(
            clear_output_for_workflow=lambda _workflows, _workflow_id: None
        ),
        "output_image_pipeline": SimpleNamespace(
            submit_live_output_event=lambda _event: None,
            schedule_output_projection=lambda _intent: None,
        ),
        "output_canvas_timing_service": SimpleNamespace(
            apply_output_source_timing=lambda *_args, **_kwargs: SimpleNamespace(
                projection_intent=SimpleNamespace(should_schedule=False)
            )
        ),
        "output_navigation_session_service": SimpleNamespace(
            begin_session=lambda *_args: None
        ),
        "progress_service": SimpleNamespace(
            build_model_load_view_state=lambda **_kwargs: SimpleNamespace(
                show_overlay=False,
                display_percent=None,
            )
        ),
        "preview_image_signal": SimpleNamespace(emit=lambda _event: None),
        "clear_output_signal": SimpleNamespace(emit=lambda _workflow_id: None),
    }
    values.update(overrides)
    return SimpleNamespace(**values)
