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

"""Verify sequential four-cube previews settle into exactly four Output tabs."""

from __future__ import annotations

from substitute.application.generation import GenerationRunStarted
from substitute.application.generation.visual_run_context_builder import (
    VisualRunContextBuilder,
)
from substitute.application.ports import QueueVisualRunContext
from substitute.domain.common import WorkflowId
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import GenerationRunHandle, OutputSpec


def test_four_cube_previews_settle_into_four_matching_final_tabs(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Replace every stage preview in place while preserving earlier final tabs."""

    context = _build_visual_context()
    harness.add_workflow("brown-haired", activate=True)
    run = harness.start_run("brown-haired")
    _register_preview_sources(harness, run, context)
    stages = (
        ("9", "8", (95, 55, 40), (125, 75, 55)),
        ("11", "17", (70, 105, 155), (85, 125, 180)),
        ("25", "29", (125, 85, 145), (150, 105, 170)),
        ("32", "36", (155, 100, 90), (180, 125, 110)),
    )
    expected_source_keys: list[str] = []

    for output_count, (
        preview_node,
        output_node,
        preview_color,
        final_color,
    ) in enumerate(stages, start=1):
        preview_spec = _output_spec(context, preview_node, preview_color)
        expected_source_keys.append(preview_spec.source_key)
        harness.emit_preview(run, preview_spec)
        harness.wait_for_preview_count(1)
        harness.wait_until(
            lambda: (
                tuple(harness.shell.output_canvas.tabbar.items)
                == tuple(expected_source_keys)
            )
        )
        harness.assert_preview_displayed(color=preview_color)

        harness.emit_output(
            run,
            _output_spec(context, output_node, final_color),
        )
        harness.wait_for_output_count("brown-haired", output_count)
        harness.wait_for_preview_count(0)
        harness.wait_until(
            lambda: (
                "workflow-brown-haired"
                not in harness.fingerprint().pending_projection_workflows
            )
        )
        harness.wait_until(
            lambda: (
                tuple(harness.shell.output_canvas.tabbar.items)
                == tuple(expected_source_keys)
            )
        )
        try:
            harness.assert_showing_workflow("brown-haired", color=final_color)
        except AssertionError as error:
            raise AssertionError(
                f"four-cube stage {output_count} did not settle: {harness.fingerprint()}"
            ) from error

    harness.assert_no_previews()
    assert tuple(
        item.text() for item in harness.shell.output_canvas.tabbar.items.values()
    ) == (
        "Text to Image",
        "Diffusion Upscale",
        "Automask Detailer",
        "Automask Detailer 2",
    )


def _build_visual_context() -> QueueVisualRunContext:
    """Build routing context for the reported four-stage compiled graph shape."""

    return VisualRunContextBuilder().build(
        workflow_payload=_chained_cube_payload(),
        workflow_id=WorkflowId("workflow-brown-haired"),
        generation_run_id="workflow-brown-haired-run-1",
        client_id="workflow-brown-haired-client-1",
        scene_run_id=None,
        scene_key=None,
        scene_title=None,
        scene_order=None,
        scene_count=None,
    )


def _register_preview_sources(
    harness: RealShellOutputCanvasHarness,
    run: GenerationRunHandle,
    context: QueueVisualRunContext,
) -> None:
    """Publish the builder-derived preview placeholders through real ingress."""

    harness.shell.generation_feedback_dispatcher.on_run_started(
        GenerationRunStarted(
            workflow_id=run.workflow.workflow_id,
            generation_run_id=run.generation_run_id,
            output_session_id=run.output_session_id,
            prompt_id=run.prompt_id,
            client_id=run.client_id,
            preview_source_keys=frozenset(
                source["sourceKey"] for source in context.sources.values()
            ),
        )
    )
    harness.process_events()
    harness.shell.generation_feedback_dispatcher.flush_now()
    harness.process_events()


def _output_spec(
    context: QueueVisualRunContext,
    node_id: str,
    color: tuple[int, int, int],
) -> OutputSpec:
    """Build one callback specification from production-derived source metadata."""

    source = context.sources[node_id]
    return OutputSpec(
        source_key=source["sourceKey"],
        source_label=source["sourceLabel"],
        color=color,
        node_id=node_id,
    )


def _chained_cube_payload() -> dict[str, object]:
    """Return the four chained output stages from the brown-haired workflow."""

    payload: dict[str, object] = {}
    previous_output_id: str | None = None
    for sampler_id, output_id, label in (
        ("9", "8", "Text to Image"),
        ("11", "17", "Diffusion Upscale"),
        ("25", "29", "Automask Detailer"),
        ("32", "36", "Automask Detailer 2"),
    ):
        payload[sampler_id] = {
            "class_type": "KSampler",
            "inputs": (
                {} if previous_output_id is None else {"image": [previous_output_id, 0]}
            ),
            "_meta": {"title": f"{label}.KSampler"},
        }
        payload[output_id] = {
            "class_type": "SugarCubes.CubeOutput",
            "inputs": {"images": [sampler_id, 0]},
            "_meta": {"title": f"{label}.Output"},
        }
        previous_output_id = output_id
    return payload
