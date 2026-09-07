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

"""Support observable three-scene Automatic Output canvas stories."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import (
    GenerationRunHandle,
    OutputSpec,
    SceneSpec,
)

TEXT_SOURCE = "alpha:text"
UPSCALE_SOURCE = "alpha:upscale"


@dataclass(frozen=True, slots=True)
class ObservedAutoState:
    """Capture durable and mounted Output ownership for one timeline step."""

    durable_route: tuple[str | None, bool, str | None, int, UUID | None]
    visible_route: tuple[str | None, bool, str | None, int]
    preview_lanes: tuple[tuple[str, str | None, str, UUID], ...]
    presented_ids: tuple[UUID, ...]
    mounted_grid_ids: tuple[UUID, ...]


def start_scene_test(
    harness: RealShellOutputCanvasHarness,
) -> tuple[SceneSpec, ...]:
    """Mount the three-scene workflow and register its scene-run manifest."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    scene_run_id = "scene-test-run-1"
    scenes = tuple(
        SceneSpec(
            run_id=scene_run_id,
            key=f"scene-{index}",
            title=f"Scene {index}",
            order=index - 1,
            count=3,
        )
        for index in range(1, 4)
    )
    harness.shell.output_scene_run_service.start_scene_run(
        scene_run_id=scene_run_id,
        workflow_id="workflow-alpha",
        workflow_name="Scene Test",
        scenes=tuple((scene.key, scene.title, scene.order) for scene in scenes),
    )
    return scenes


def emit_tensor_batch_and_ids(
    harness: RealShellOutputCanvasHarness,
    run: GenerationRunHandle,
    *,
    scene: SceneSpec,
    source_key: str,
    source_label: str,
    colors: tuple[tuple[int, int, int], tuple[int, int, int]],
    expected_output_count: int,
) -> tuple[UUID, UUID]:
    """Emit one same-run tensor batch and return its projected IDs."""

    emit_tensor_batch(
        harness,
        run,
        scene=scene,
        source_key=source_key,
        source_label=source_label,
        colors=colors,
        expected_output_count=expected_output_count,
    )
    harness.shell.output_image_pipeline.flush_visible_output_projection()
    harness.process_events()
    output_ids = harness.output_ids_for_scene_source(
        scene_key=scene.key,
        source_key=source_key,
    )
    assert len(output_ids) == 2
    return output_ids[0], output_ids[1]


def emit_single_output(
    harness: RealShellOutputCanvasHarness,
    run: GenerationRunHandle,
    *,
    scene: SceneSpec,
    source_key: str,
    source_label: str,
    color: tuple[int, int, int],
    batch_index: int,
    expected_output_count: int,
) -> tuple[int, UUID]:
    """Emit one indexed final and return its projected image identifier."""

    harness.emit_output(
        run,
        OutputSpec(
            source_key,
            source_label,
            color,
            batch_index=batch_index,
            scene=scene,
        ),
    )
    expected_output_count += 1
    harness.wait_for_output_count("alpha", expected_output_count)
    harness.shell.output_image_pipeline.flush_visible_output_projection()
    harness.process_events()
    output_ids = harness.output_ids_for_scene_source(
        scene_key=scene.key,
        source_key=source_key,
    )
    image_id = output_ids[batch_index]
    return expected_output_count, image_id


def source_preview_id(
    harness: RealShellOutputCanvasHarness,
    source_key: str,
) -> UUID:
    """Return the active source-level preview ID for one CubeOutput."""

    return next(
        lane.preview_id
        for lane in harness.shell.output_preview_registry.lanes_for_session_like()
        if lane.key.source_key == source_key and lane.key.placement.value == "source"
    )


def observe_auto_state(
    harness: RealShellOutputCanvasHarness,
) -> ObservedAutoState:
    """Capture authoritative workflow, host, registry, and mounted document state."""

    canvas = harness.shell.output_canvas
    fingerprint = harness.fingerprint()
    lanes = tuple(
        sorted(
            (
                (
                    lane.key.placement.value,
                    lane.key.scene_key,
                    lane.key.source_key,
                    lane.preview_id,
                )
                for lane in harness.shell.output_preview_registry.lanes_for_session_like()
            ),
            key=lambda item: (item[0], item[1] or "", item[2], str(item[3])),
        )
    )
    return ObservedAutoState(
        durable_route=fingerprint.workflow_output_routes["workflow-alpha"],
        visible_route=(
            canvas.active_scene_key,
            canvas.active_scene_overview,
            canvas.active_source_key,
            canvas.active_set_index,
        ),
        preview_lanes=lanes,
        presented_ids=fingerprint.presented_image_ids,
        mounted_grid_ids=tuple(frame[1] for frame in fingerprint.grid_target_frames),
    )


def emit_preview(
    harness: RealShellOutputCanvasHarness,
    run: GenerationRunHandle,
    *,
    scene: SceneSpec,
    source_key: str,
    source_label: str,
    color: tuple[int, int, int],
) -> None:
    """Emit and flush one preview for a source in the current scene run."""

    harness.emit_preview(
        run,
        OutputSpec(source_key, source_label, color, scene=scene),
    )
    flush_preview(harness)


def emit_tensor_batch(
    harness: RealShellOutputCanvasHarness,
    run: GenerationRunHandle,
    *,
    scene: SceneSpec,
    source_key: str,
    source_label: str,
    colors: tuple[tuple[int, int, int], ...],
    expected_output_count: int,
) -> int:
    """Emit every member of one diffusion batch from the same generation run."""

    for batch_index, color in enumerate(colors):
        harness.emit_output(
            run,
            OutputSpec(
                source_key,
                source_label,
                color,
                batch_index=batch_index,
                scene=scene,
            ),
        )
    expected_output_count += len(colors)
    harness.wait_for_output_count("alpha", expected_output_count)
    harness.wait_until(
        lambda: (
            scene_source_count(
                harness,
                scene_key=scene.key,
                source_key=source_key,
            )
            == len(colors)
        )
    )
    return expected_output_count


def scene_source_count(
    harness: RealShellOutputCanvasHarness,
    *,
    scene_key: str,
    source_key: str,
) -> int:
    """Return a projected source count while projection work is queued."""

    try:
        return len(
            harness.output_ids_for_scene_source(
                scene_key=scene_key,
                source_key=source_key,
            )
        )
    except AssertionError:
        return 0


def scene_preview_id(
    harness: RealShellOutputCanvasHarness,
    scene_key: str,
) -> UUID:
    """Return the current scene-overview preview identifier."""

    return next(
        lane.preview_id
        for lane in harness.shell.output_preview_registry.lanes_for_session_like()
        if lane.key.scene_key == scene_key and lane.key.placement.value == "scene"
    )


def assert_single_preview(
    harness: RealShellOutputCanvasHarness,
    *,
    source_key: str,
) -> None:
    """Assert Automatic presents the only available preview by itself."""

    harness.wait_until(
        lambda: (
            not harness.shell.output_canvas.active_scene_overview
            and harness.shell.output_canvas.active_source_key == source_key
            and harness.shell.output_canvas.active_set_index == 1
            and len(harness.fingerprint().presented_image_ids) == 1
        )
    )
    assert (
        harness.fingerprint().workflow_output_focus_modes["workflow-alpha"]
        == "automatic"
    )


def assert_collapsed_all(
    harness: RealShellOutputCanvasHarness,
    *,
    visible_ids: tuple[UUID, ...],
) -> None:
    """Assert a preview-only source remains represented once in All."""

    harness.wait_until(
        lambda: (
            harness.shell.output_canvas.active_scene_overview
            and harness.shell.output_canvas.active_source_key is None
            and harness.shell.output_canvas.active_set_index == 1
            and harness.fingerprint().presented_image_ids == visible_ids
            and harness.fingerprint().set_selector_hidden
            and harness.fingerprint().source_selector_hidden
            and not harness.shell.output_canvas.tabbar.items
        )
    )
    canvas = harness.shell.output_canvas
    state = harness.fingerprint()
    assert canvas.scene_selector_button.text() == "All", state
    assert not state.scene_selector_hidden, state
    assert state.workflow_output_focus_modes["workflow-alpha"] == "automatic", state


def flush_preview(harness: RealShellOutputCanvasHarness) -> None:
    """Drain coalesced preview and deferred navigation work deterministically."""

    harness.process_events()
    harness.shell.generation_feedback_dispatcher.flush_now()
    harness.process_events()
    harness.process_events()


__all__ = [
    "TEXT_SOURCE",
    "UPSCALE_SOURCE",
    "ObservedAutoState",
    "assert_collapsed_all",
    "assert_single_preview",
    "emit_preview",
    "emit_single_output",
    "emit_tensor_batch",
    "emit_tensor_batch_and_ids",
    "flush_preview",
    "observe_auto_state",
    "scene_preview_id",
    "scene_source_count",
    "source_preview_id",
    "start_scene_test",
]
