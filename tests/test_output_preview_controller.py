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

"""Verify Output preview controller QPane removal commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from substitute.application.workflows.output_canvas_state_service import (
    OutputPreviewCloseIdentity,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_session import (
    OutputCanvasSession,
    bind_output_canvas_session,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewAcceptance,
    OutputPreviewLane,
    OutputPreviewLaneKey,
    OutputPreviewRegistry,
)
from substitute.domain.workflow import (
    CanvasSessionBoundary,
    CanvasSessionRevision,
    ImageMeta,
)
from substitute.application.workflows.output_preview_lifecycle_service import (
    ScenePreviewSlot,
)
from substitute.presentation.canvas.output.output_preview_controller import (
    OutputPreviewController,
)


def test_close_final_output_preview_lane_removes_closed_preview() -> None:
    """Final-output close commands should remove only matching preview images."""

    preview_id = uuid4()
    other_preview_id = uuid4()
    registry = OutputPreviewRegistry()
    registry.store_accepted_lane(
        _lane(
            preview_id=preview_id,
            source_key="wf:upscale",
            scene_key="portrait",
        )
    )
    registry.store_accepted_lane(
        _lane(
            preview_id=other_preview_id,
            source_key="wf:text",
            scene_key="portrait",
        )
    )
    presenter = _Presenter()
    controller = OutputPreviewController(
        preview_registry=lambda: registry,
        qpane_presenter=lambda: presenter,
    )

    controller.close_final_output_preview_lane(
        OutputPreviewCloseIdentity(
            workflow_id="wf",
            image_id=uuid4(),
            source_key="wf:upscale",
            source_label="Upscale",
            generation_run_id="run-a",
            prompt_id="prompt-a",
            client_id="client-a",
            node_id="wf:upscale",
            list_index=1,
            scene_run_id=None,
            scene_key="portrait",
            scene_title=None,
            scene_order=None,
            scene_count=None,
        )
    )

    assert presenter.removed_image_ids == (preview_id,)


def test_clear_previews_removes_registry_cleared_images() -> None:
    """Clear commands should remove every preview image returned by the registry."""

    source_preview_id = uuid4()
    other_preview_id = uuid4()
    registry = OutputPreviewRegistry()
    registry.store_accepted_lane(
        _lane(
            preview_id=source_preview_id,
            source_key="wf:upscale",
            scene_key=None,
        )
    )
    registry.store_accepted_lane(
        _lane(
            preview_id=other_preview_id,
            source_key="wf:text",
            scene_key=None,
        )
    )
    presenter = _Presenter()
    controller = OutputPreviewController(
        preview_registry=lambda: registry,
        qpane_presenter=lambda: presenter,
    )

    controller.clear_previews(source_key="wf:upscale")

    assert presenter.removed_image_ids == (source_preview_id,)


def test_apply_preview_acceptance_registers_and_activates_source_lane() -> None:
    """Accepted source previews should register with QPane and activate the route."""

    preview_id = uuid4()
    session = _session()
    presenter = _Presenter()
    activated: list[UUID] = []
    activity_marks: list[bool] = []

    def activate_output_image(image_id: UUID) -> bool:
        """Record preview activation and report route command success."""

        activated.append(image_id)
        return True

    controller = OutputPreviewController(
        preview_registry=OutputPreviewRegistry,
        qpane_presenter=lambda: presenter,
        output_session=lambda: session,
        set_current_output_image=activate_output_image,
        mark_output_activity=lambda: activity_marks.append(True),
    )

    controller.apply_preview_acceptance(
        OutputPreviewAcceptance(
            accepted=True,
            lanes=(
                _lane(
                    preview_id=preview_id,
                    source_key="wf:upscale",
                    scene_key=None,
                    session_revision=session.revision,
                ),
            ),
        )
    )

    assert presenter.registered_image_ids == (preview_id,)
    assert activated == [preview_id]
    assert activity_marks == [True]


def test_apply_preview_acceptance_updates_scene_overview_state() -> None:
    """Accepted scene previews should update scene overview state without activation."""

    preview_id = uuid4()
    session = _session()
    presenter = _Presenter()
    scene_count = 1
    active_scene_key: str | None = None
    active_scene_overview = False
    overview_activations: list[bool] = []

    def set_scene_count(next_scene_count: int) -> None:
        nonlocal scene_count
        scene_count = next_scene_count

    def set_active_scene_key(scene_key: str | None) -> None:
        nonlocal active_scene_key
        active_scene_key = scene_key

    def set_active_scene_overview(active: bool) -> None:
        nonlocal active_scene_overview
        active_scene_overview = active

    controller = OutputPreviewController(
        preview_registry=OutputPreviewRegistry,
        qpane_presenter=lambda: presenter,
        output_session=lambda: session,
        scene_count=lambda: scene_count,
        set_scene_count=set_scene_count,
        active_scene_key=lambda: active_scene_key,
        set_active_scene_key=set_active_scene_key,
        active_scene_overview=lambda: active_scene_overview,
        set_active_scene_overview=set_active_scene_overview,
        activate_scene_overview=lambda: overview_activations.append(True),
    )

    controller.apply_preview_acceptance(
        OutputPreviewAcceptance(
            accepted=True,
            lanes=(
                _scene_lane(
                    preview_id=preview_id,
                    source_key="wf:upscale",
                    scene_key="portrait",
                    session_revision=session.revision,
                    scene_count=2,
                ),
            ),
        )
    )

    assert presenter.registered_image_ids == (preview_id,)
    assert scene_count == 2
    assert active_scene_key == "portrait"
    assert active_scene_overview is True
    assert overview_activations == [True]


def test_set_scene_preview_image_registers_new_preview_scene() -> None:
    """Scene preview mutation should cache image, slot, group, and overview state."""

    preview_id = uuid4()
    presenter = _Presenter()
    scene_preview_slots: dict[str, ScenePreviewSlot] = {}
    preview_image_cache: dict[UUID, object] = {}
    preview_scene_groups: dict[str, OutputCanvasSceneGroup] = {}
    scene_count = 0
    active_scene_key: str | None = None
    active_scene_overview = False
    overview_activations: list[bool] = []

    def set_scene_count(next_scene_count: int) -> None:
        nonlocal scene_count
        scene_count = next_scene_count

    def set_active_scene_key(scene_key: str | None) -> None:
        nonlocal active_scene_key
        active_scene_key = scene_key

    def set_active_scene_overview(active: bool) -> None:
        nonlocal active_scene_overview
        active_scene_overview = active

    image = object()
    controller = OutputPreviewController(
        preview_registry=OutputPreviewRegistry,
        qpane_presenter=lambda: presenter,
        scene_count=lambda: scene_count,
        set_scene_count=set_scene_count,
        active_scene_key=lambda: active_scene_key,
        set_active_scene_key=set_active_scene_key,
        active_scene_overview=lambda: active_scene_overview,
        set_active_scene_overview=set_active_scene_overview,
        activate_scene_overview=lambda: overview_activations.append(True),
        scene_preview_id_for_source=lambda **_kwargs: preview_id,
        scene_groups_by_key=lambda: {},
        scene_preview_matches_representative=lambda **_kwargs: True,
        scene_preview_slots=lambda: scene_preview_slots,
        preview_image_cache=lambda: preview_image_cache,
        preview_scene_groups_by_key=lambda: preview_scene_groups,
    )

    controller.set_scene_preview_image(
        image,
        scene_key="portrait",
        scene_title="Portrait",
        scene_order=2,
        scene_count=3,
        generation_run_id="run-a",
        scene_run_id="scene-run-a",
        source_key="wf:upscale",
        source_label="Upscale",
    )

    assert presenter.registered_image_ids == (preview_id,)
    assert preview_image_cache == {preview_id: image}
    assert scene_preview_slots["portrait"].preview_id == preview_id
    assert preview_scene_groups["portrait"].preview_image_id == preview_id
    assert scene_count == 3
    assert active_scene_key == "portrait"
    assert active_scene_overview is True
    assert overview_activations == [True]


def test_set_scene_preview_image_skips_completed_final_source() -> None:
    """Scene preview mutation should ignore previews superseded by final output."""

    preview_id = uuid4()
    presenter = _Presenter()
    scene = _scene(
        sources=(
            _source(
                source_key="wf:upscale",
                label="Upscale",
                image_id=uuid4(),
            ),
        )
    )
    controller = OutputPreviewController(
        preview_registry=OutputPreviewRegistry,
        qpane_presenter=lambda: presenter,
        scene_preview_id_for_source=lambda **_kwargs: preview_id,
        scene_groups_by_key=lambda: {"portrait": scene},
    )

    controller.set_scene_preview_image(
        object(),
        scene_key="portrait",
        scene_title="Portrait",
        scene_order=0,
        scene_count=1,
        generation_run_id="run-a",
        scene_run_id="scene-run-a",
        source_key="wf:upscale",
        source_label="Upscale",
    )

    assert presenter.registered_image_ids == ()


@dataclass(slots=True)
class _Presenter:
    """Record preview image removals."""

    removed_image_ids: tuple[UUID, ...] = ()
    registered_image_ids: tuple[UUID, ...] = ()

    def register_image(
        self,
        image_id: UUID,
        image: object,
        path: Path | None,
    ) -> None:
        """Record one registered preview image."""

        _ = image, path
        self.registered_image_ids = (*self.registered_image_ids, image_id)

    def remove_image(self, image_id: UUID) -> None:
        """Record one removed preview image."""

        self.removed_image_ids = (*self.removed_image_ids, image_id)


def _lane(
    *,
    preview_id: UUID,
    source_key: str,
    scene_key: str | None,
    session_revision: CanvasSessionRevision | None = None,
) -> OutputPreviewLane:
    """Return one accepted preview lane."""

    return OutputPreviewLane(
        key=OutputPreviewLaneKey.source(
            workflow_id="wf",
            generation_run_id="run-a",
            prompt_id="prompt-a",
            source_key=source_key,
            scene_key=scene_key,
        ),
        preview_id=preview_id,
        image=object(),
        source_label=source_key.rsplit(":", maxsplit=1)[-1].title(),
        client_id="client-a",
        session_revision=session_revision or CanvasSessionRevision(1),
    )


def _scene_lane(
    *,
    preview_id: UUID,
    source_key: str,
    scene_key: str,
    session_revision: CanvasSessionRevision,
    scene_count: int,
) -> OutputPreviewLane:
    """Return one accepted scene preview lane."""

    return OutputPreviewLane(
        key=OutputPreviewLaneKey.scene(
            workflow_id="wf",
            generation_run_id="run-a",
            prompt_id="prompt-a",
            source_key=source_key,
            scene_run_id="scene-run-a",
            scene_key=scene_key,
        ),
        preview_id=preview_id,
        image=object(),
        source_label=source_key.rsplit(":", maxsplit=1)[-1].title(),
        client_id="client-a",
        session_revision=session_revision,
        scene_title="Portrait",
        scene_order=0,
        scene_count=scene_count,
        accepted_for_overview=True,
    )


def _session() -> OutputCanvasSession:
    """Return one Output preview session for controller tests."""

    return bind_output_canvas_session(
        CanvasSessionBoundary(),
        workflow_id="wf",
        projection=OutputCanvasProjection(
            sources=(),
            active_source_key=None,
            active_set_index=1,
            active_uuid=None,
            set_count=0,
        ),
        image_metadata_lookup={},
    )


def _scene(
    *,
    sources: tuple[OutputCanvasSourceGroup, ...],
) -> OutputCanvasSceneGroup:
    """Return one scene group for preview controller tests."""

    return OutputCanvasSceneGroup(
        scene_run_id="scene-run-a",
        scene_key="portrait",
        title="Portrait",
        order=0,
        sources=sources,
    )


def _source(
    *,
    source_key: str,
    label: str,
    image_id: UUID,
) -> OutputCanvasSourceGroup:
    """Return one completed source group for preview controller tests."""

    return OutputCanvasSourceGroup(
        source_key=source_key,
        label=label,
        images_by_set={
            1: OutputCanvasImageItem(
                image_id=image_id,
                image_meta=_meta(),
                set_index=1,
            )
        },
    )


def _meta() -> ImageMeta:
    """Return minimal image metadata for preview controller tests."""

    return ImageMeta(
        workflow_name="Workflow",
        cube_name="Output",
        image_number=1,
        suffix="",
        path="E:/out.png",
    )
