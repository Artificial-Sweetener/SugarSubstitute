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

"""Build Output preview lifecycle test collaborators."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from substitute.application.workflows import OutputPreviewLaneKey
from substitute.application.workflows.output_preview_lifecycle_service import (
    OutputCanvasRevisionCache,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewLane,
    OutputPreviewLanePlacement,
)
from substitute.presentation.canvas.output.composition.preview import (
    output_preview_controller_for_host,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    activate_output_scene_overview,
)
from tests.support.output_canvas.projection_controller_factory import (
    output_canvas_projection_controller_for_test_host,
)


def output_preview_registry(output_mod: Any, fake: Any) -> Any:
    """Return the registry owner used by Output preview widget tests."""

    registry = getattr(fake, "_preview_registry", None)
    if not isinstance(registry, output_mod.OutputPreviewRegistry):
        registry = output_mod.OutputPreviewRegistry()
        fake._preview_registry = registry
    if not hasattr(fake, "_asset_lookup"):
        from .host_fakes import install_fake_output_asset_lookup  # noqa: PLC0415

        install_fake_output_asset_lookup(output_mod, fake)
    from .route_fakes import install_fake_output_qpane_presenter  # noqa: PLC0415

    install_fake_output_qpane_presenter(fake)
    install_fake_output_preview_controller(output_mod, fake)
    return output_mod.output_preview_registry(fake)


def output_preview_cache(output_mod: Any, fake: Any) -> Any:
    """Return registry-backed preview diagnostics for widget tests."""

    return output_mod.output_revision_cache(fake)


def apply_registry_preview(
    output_mod: Any,
    fake: Any,
    image: Any,
    *,
    source_key: str,
    source_label: str,
    generation_run_id: str = "run-1",
    prompt_id: str = "prompt-1",
    client_id: str = "client-1",
    scene_run_id: str | None = None,
    scene_key: str | None = None,
    scene_title: str | None = None,
    scene_order: int | None = None,
    scene_count: int | None = None,
    include_source: bool = True,
    include_scene: bool = False,
) -> tuple[Any, ...]:
    """Apply registry-owned accepted preview lanes to a lightweight Output fake."""

    registry = output_preview_registry(output_mod, fake)
    session = ensure_output_preview_session(
        output_mod,
        fake,
        source_key=source_key,
        scene_key=scene_key,
        scene_title=scene_title,
        scene_order=scene_order,
        scene_count=scene_count,
    )
    lanes = []
    if include_scene and scene_run_id is not None and scene_key is not None:
        lanes.append(
            registry_lane(
                output_mod,
                registry,
                key=OutputPreviewLaneKey.scene(
                    workflow_id="wf",
                    generation_run_id=generation_run_id,
                    prompt_id=prompt_id,
                    source_key=source_key,
                    scene_run_id=scene_run_id,
                    scene_key=scene_key,
                ),
                image=image,
                source_label=source_label,
                client_id=client_id,
                session_revision=session.revision,
                scene_title=scene_title,
                scene_order=scene_order,
                scene_count=scene_count,
                accepted_for_overview=True,
            )
        )
    if include_source:
        lanes.append(
            registry_lane(
                output_mod,
                registry,
                key=OutputPreviewLaneKey.source(
                    workflow_id="wf",
                    generation_run_id=generation_run_id,
                    prompt_id=prompt_id,
                    source_key=source_key,
                    scene_run_id=scene_run_id,
                    scene_key=scene_key,
                ),
                image=image,
                source_label=source_label,
                client_id=client_id,
                session_revision=session.revision,
                scene_title=scene_title,
                scene_order=scene_order,
                scene_count=scene_count,
            )
        )
    acceptance = output_mod.OutputPreviewAcceptance(
        accepted=bool(lanes), lanes=tuple(lanes)
    )
    fake._preview_controller.apply_preview_acceptance(acceptance)
    fake._revision_cache = OutputCanvasRevisionCache(registry, session)
    return tuple(lanes)


def ensure_output_preview_session(
    output_mod: Any,
    fake: Any,
    *,
    source_key: str,
    scene_key: str | None,
    scene_title: str | None,
    scene_order: int | None,
    scene_count: int | None,
) -> Any:
    """Install a lightweight Output session that authorizes preview lanes."""

    session = getattr(fake, "_output_session", None)
    if session is not None:
        return session
    from substitute.application.workflows import (  # noqa: PLC0415
        OutputCanvasProjection,
        OutputCanvasSceneGroup,
        OutputCanvasSourceGroup,
    )
    from substitute.application.workflows.output_canvas_session import (  # noqa: PLC0415
        bind_output_canvas_session,
    )
    from substitute.domain.workflow import CanvasSessionBoundary  # noqa: PLC0415
    from .host_fakes import (  # noqa: PLC0415
        install_fake_output_asset_lookup,
        install_fake_output_projection_chrome,
    )
    from .route_fakes import install_fake_output_qpane_presenter  # noqa: PLC0415

    source_group = OutputCanvasSourceGroup(
        source_key=source_key, label=source_key, images_by_set={}
    )
    scene_groups: tuple[Any, ...] = ()
    if scene_key is not None:
        scene_groups = (
            OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key=scene_key,
                title=scene_title or scene_key,
                order=scene_order or 0,
                sources=(source_group,),
            ),
        )
    projection = OutputCanvasProjection(
        sources=(source_group,),
        active_source_key=source_key,
        active_set_index=1,
        active_uuid=None,
        set_count=0,
        scene_groups=scene_groups,
        active_scene_key=scene_key,
        active_scene_overview=bool(scene_key and scene_count and scene_count > 1),
        scene_count=scene_count or 0,
    )
    boundary = getattr(fake, "_route_session_boundary", None) or CanvasSessionBoundary()
    session = bind_output_canvas_session(
        boundary, workflow_id="wf", projection=projection, image_metadata_lookup={}
    )
    fake._route_session_boundary = boundary
    fake._output_session = session
    fake._projection_workflow_id = "wf"
    fake._output_projection = projection
    install_fake_output_asset_lookup(output_mod, fake)
    install_fake_output_qpane_presenter(fake)
    install_fake_output_projection_chrome(fake)
    output_canvas_projection_controller_for_test_host(
        fake
    ).bind_projection_route_projector(session)
    return session


def registry_lane(
    output_mod: Any,
    registry: Any,
    *,
    key: Any,
    image: Any,
    source_label: str,
    client_id: str,
    session_revision: Any,
    scene_title: str | None,
    scene_order: int | None,
    scene_count: int | None,
    accepted_for_overview: bool = False,
) -> OutputPreviewLane:
    """Build and store one accepted registry lane with stable lane UUID reuse."""

    existing = next(
        (lane for lane in registry.lanes_for_session_like() if lane.key == key), None
    )
    lane = OutputPreviewLane(
        key=key,
        preview_id=existing.preview_id if existing is not None else uuid4(),
        image=image,
        source_label=source_label,
        client_id=client_id,
        session_revision=session_revision,
        scene_title=scene_title,
        scene_order=scene_order,
        scene_count=scene_count,
        accepted_for_overview=accepted_for_overview,
    )
    registry.store_accepted_lane(lane)
    return lane


def install_test_preview_lane(
    output_mod: Any,
    fake: Any,
    *,
    preview_id: UUID,
    image: object,
    source_key: str,
    source_label: str | None = None,
    generation_run_id: str = "run-1",
    prompt_id: str = "prompt-1",
    client_id: str = "client-1",
    scene_run_id: str | None = None,
    scene_key: str | None = None,
    scene_title: str | None = None,
    scene_order: int | None = None,
    scene_count: int | None = None,
    placement: Any | None = None,
    accepted_for_overview: bool = False,
) -> None:
    """Install one explicit registry-owned lane for lightweight widget fakes."""

    from substitute.domain.workflow import CanvasSessionRevision  # noqa: PLC0415

    registry = output_preview_registry(output_mod, fake)
    resolved_placement = placement or (
        OutputPreviewLanePlacement.SCENE
        if scene_run_id is not None and scene_key is not None
        else OutputPreviewLanePlacement.SOURCE
    )
    key = (
        OutputPreviewLaneKey.scene(
            workflow_id="wf",
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            source_key=source_key,
            scene_run_id=scene_run_id or "",
            scene_key=scene_key or "",
        )
        if resolved_placement is OutputPreviewLanePlacement.SCENE
        else OutputPreviewLaneKey.source(
            workflow_id="wf",
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            source_key=source_key,
            scene_run_id=scene_run_id,
            scene_key=scene_key,
        )
    )
    registry.store_accepted_lane(
        OutputPreviewLane(
            key=key,
            preview_id=preview_id,
            image=image,
            source_label=source_label or source_key,
            client_id=client_id,
            session_revision=CanvasSessionRevision(1),
            scene_title=scene_title,
            scene_order=scene_order,
            scene_count=scene_count,
            accepted_for_overview=accepted_for_overview,
        )
    )


def install_fake_output_preview_controller(output_mod: Any, fake: Any) -> None:
    """Install the composed preview controller expected by widget seams."""

    if hasattr(fake, "_preview_controller"):
        _install_preview_runtime(fake)
        return
    if not hasattr(fake, "_asset_lookup"):
        from .host_fakes import install_fake_output_asset_lookup  # noqa: PLC0415

        install_fake_output_asset_lookup(output_mod, fake)
        return
    from .route_fakes import install_fake_output_qpane_presenter  # noqa: PLC0415

    if not hasattr(fake, "_qpane_presenter"):
        install_fake_output_qpane_presenter(fake)
    set_current_image = getattr(getattr(fake, "pane", None), "setCurrentImageID", None)
    fake._preview_controller = output_preview_controller_for_host(
        fake,
        asset_lookup=fake._asset_lookup,
        qpane_presenter=fake._qpane_presenter,
        output_session=lambda: getattr(fake, "_output_session", None),
        set_current_output_image=(
            (lambda image_id: _set_pane_current_image(set_current_image, image_id))
            if callable(set_current_image)
            else lambda image_id: output_canvas_projection_controller_for_test_host(
                fake
            ).set_current_output_image(image_id)
        ),
        activate_scene_overview=lambda: _activate_scene_overview_for_preview(fake),
        mark_output_activity=lambda: None,
    )
    _install_preview_runtime(fake)


def _install_preview_runtime(fake: Any) -> None:
    """Expose the preview controller through the production-shaped runtime seam."""

    runtime = getattr(fake, "_runtime", None)
    if runtime is None:
        runtime = SimpleNamespace()
        fake._runtime = runtime
    runtime.preview = SimpleNamespace(controller=fake._preview_controller)


def _set_pane_current_image(set_current_image: Any, image_id: UUID) -> bool:
    """Call a fake pane image setter and report command success."""

    set_current_image(image_id)
    return True


def _activate_scene_overview_for_preview(fake: Any) -> None:
    """Activate scene overview for preview helpers and discard command result."""

    activate_output_scene_overview(
        fake, update_tabbar_container=fake._update_tabbar_container
    )


def preview_close_identity(
    output_mod: Any,
    *,
    image_id: UUID,
    source_key: str,
    source_label: str,
    generation_run_id: str = "",
    scene_run_id: str | None = None,
    scene_key: str | None = None,
    scene_title: str | None = None,
    scene_order: int | None = None,
    scene_count: int | None = None,
    list_index: int | None = 0,
) -> object:
    """Build the preview-close identity used by Output preview ownership tests."""

    return output_mod.OutputPreviewCloseIdentity(
        workflow_id="wf",
        image_id=image_id,
        source_key=source_key,
        source_label=source_label,
        generation_run_id=generation_run_id,
        prompt_id="prompt-1",
        client_id="client-1",
        node_id="node",
        list_index=list_index,
        scene_run_id=scene_run_id,
        scene_key=scene_key,
        scene_title=scene_title,
        scene_order=scene_order,
        scene_count=scene_count,
    )


__all__ = [
    "apply_registry_preview",
    "ensure_output_preview_session",
    "install_fake_output_preview_controller",
    "install_test_preview_lane",
    "output_preview_cache",
    "output_preview_registry",
    "preview_close_identity",
    "registry_lane",
]
