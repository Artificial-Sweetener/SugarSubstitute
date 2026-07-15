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

"""Build Output route projection and application test collaborators."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID

from substitute.domain.workflow import CanvasRouteIdentity
from substitute.presentation.canvas.output.output_scene_overview_composer import (
    scene_overview_preview_for_scene,
)
from substitute.application.workflows.canvas_route_projector_port import (
    OutputRouteScope,
    create_canvas_session_boundary,
)
from substitute.presentation.canvas.output.composition.grid import (
    output_scene_overview_composer,
    output_source_grid_composer,
)
from substitute.presentation.canvas.output.output_grid_route_application_controller import (
    OutputGridRouteApplicationController,
)
from substitute.presentation.canvas.output.composition.qpane import (
    output_route_presenter,
    output_route_projector_for,
)
from substitute.presentation.canvas.output.output_grid_scene_builder import (
    OutputGridSceneBuilder,
)
from substitute.presentation.canvas.shared.responsive_canvas_grid_policy import (
    CanvasViewportExtent,
)


class RecordingOutputRouteProjector:
    """Record Output route projector calls made by widget helper tests."""

    def __init__(self) -> None:
        """Create empty source-grid and scene-overview call logs."""

        self.source_grid_calls: list[tuple[object, bool]] = []
        self.scene_overview_calls: list[tuple[object, bool]] = []

    def bind(self, _scope: object) -> None:
        """Accept route scope binding from projection helpers."""

    def apply_source_grid_route(
        self, _route: object, request: object, *, activate: bool
    ) -> bool:
        """Record a source-grid route request."""

        self.source_grid_calls.append((request, activate))
        return True

    def apply_scene_overview_route(
        self, _route: object, request: object, *, activate: bool
    ) -> bool:
        """Record a scene-overview route request."""

        self.scene_overview_calls.append((request, activate))
        return True

    def route_composition_id(self, route: CanvasRouteIdentity) -> UUID:
        """Return the deterministic host composition ID for a route."""

        from substitute.application.workflows.output_canvas_session import (  # noqa: PLC0415
            deterministic_host_composition_id,
        )
        from substitute.domain.workflow import CanvasKind  # noqa: PLC0415

        return deterministic_host_composition_id(
            canvas_kind=CanvasKind.OUTPUT, workflow_id="wf", route=route
        )


def install_fake_output_qpane_presenter(fake: Any) -> None:
    """Install the composed QPane presenter expected by widget seams."""

    pane = getattr(fake, "pane", None)
    if pane is not None and not hasattr(pane, "setControlMode"):
        pane.setControlMode = lambda _mode: None
    from .grid_fakes import install_fake_output_interaction_controller  # noqa: PLC0415

    install_fake_output_interaction_controller(fake)
    if not hasattr(fake, "_qpane_presenter"):
        add_image = getattr(pane, "addImage", None)
        remove_image = getattr(pane, "removeImageByID", None)
        fake._qpane_presenter = SimpleNamespace(
            register_image=(
                (lambda image_id, image, path: add_image(image_id, image, path))
                if callable(add_image)
                else (lambda *_args: None)
            ),
            remove_image=(
                (lambda image_id: remove_image(image_id))
                if callable(remove_image)
                else (lambda _image_id: None)
            ),
        )


def install_fake_output_route_presenter(output_mod: Any, fake: Any) -> None:
    """Install the composed route presenter expected by route-application seams."""

    if not hasattr(fake, "_qpane_catalog"):
        pane = getattr(fake, "pane", None)
        image_ids = getattr(pane, "imageIDs", None)
        fake._qpane_catalog = SimpleNamespace(
            contains=(
                (lambda image_id: image_id in image_ids())
                if callable(image_ids)
                else (lambda _image_id: False)
            )
        )
    if not hasattr(fake, "_route_presenter"):
        fake._route_presenter = output_route_presenter(
            catalog=lambda: fake._qpane_catalog,
            image_registrar=lambda: fake._qpane_presenter,
            layer_payload=fake._asset_lookup.scene_request_layer_payload,
            layer_path=fake._asset_lookup.scene_request_layer_path,
        )


def install_fake_output_route_composers(output_mod: Any, fake: Any) -> None:
    """Install composed route composers expected by route-application seams."""

    if not hasattr(fake, "_grid_composer"):
        fake._grid_composer = output_source_grid_composer(
            fake._asset_lookup.final_output_payload,
            scene_builder=OutputGridSceneBuilder(),
            viewport_extent=lambda: CanvasViewportExtent(1000.0, 1000.0),
        )
    if not hasattr(fake, "_scene_overview_composer"):
        fake._scene_overview_composer = output_scene_overview_composer(
            payload_lookup=fake._asset_lookup.final_output_payload,
            scene_builder=OutputGridSceneBuilder(),
            viewport_extent=lambda: CanvasViewportExtent(1000.0, 1000.0),
            preview_lookup=lambda scene: scene_overview_preview_for_scene(
                scene,
                preview_image_cache=fake._asset_lookup.preview_images(),
                scene_preview_slots=output_mod.output_revision_cache(
                    fake
                ).scene_preview_slots_by_key,
                completed_preview_slots=output_mod.output_revision_cache(
                    fake
                ).completed_preview_slots,
            ),
        )
    install_fake_output_route_projector(output_mod, fake)
    install_fake_output_route_application_controller(output_mod, fake)


def install_fake_output_route_projector(output_mod: Any, fake: Any) -> None:
    """Install the composed route projector expected by route-application seams."""

    route_projector = getattr(fake, "_route_projector", None)
    if route_projector is not None:
        bind_fake_output_route_projector_scope(output_mod, fake)
        return
    boundary = getattr(fake, "_route_session_boundary", None)
    if boundary is None:
        boundary = create_canvas_session_boundary()
        fake._route_session_boundary = boundary
    fake._route_projector = output_route_projector_for(
        getattr(fake, "pane", object()), session_boundary=boundary
    )
    bind_fake_output_route_projector_scope(output_mod, fake)


def bind_fake_output_route_projector_scope(output_mod: Any, fake: Any) -> None:
    """Bind fake route projector scope when a projection session is installed."""

    session = getattr(fake, "_output_session", None)
    route_projector = getattr(fake, "_route_projector", None)
    bind = getattr(route_projector, "bind", None)
    if session is None or not callable(bind):
        return
    bind(
        OutputRouteScope(
            session=session,
            allowed_image_ids=session.allowed_image_ids,
            allowed_source_keys=session.allowed_source_keys,
            allowed_scene_keys=session.allowed_scene_keys,
            allowed_composition_ids=session.allowed_composition_ids,
        )
    )


def install_fake_output_route_application_controller(
    output_mod: Any, fake: Any
) -> None:
    """Install the composed route application controller expected by widget seams."""

    if not hasattr(fake, "_route_application_controller"):
        fake._route_application_controller = OutputGridRouteApplicationController(
            route_projector=fake._route_projector,
            ensure_scene_request_images_cached=(
                fake._route_presenter.ensure_scene_request_images_cached
            ),
        )


__all__ = [
    "RecordingOutputRouteProjector",
    "bind_fake_output_route_projector_scope",
    "install_fake_output_qpane_presenter",
    "install_fake_output_route_application_controller",
    "install_fake_output_route_composers",
    "install_fake_output_route_presenter",
    "install_fake_output_route_projector",
]
