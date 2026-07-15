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

"""Compose projection controllers for lightweight Output test hosts."""

from __future__ import annotations

from collections.abc import MutableMapping
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_canvas_route_scope import (
    scene_overview_route_identity,
    source_grid_route_identity,
)
from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
    OutputRouteProjectorPort,
    create_canvas_session_boundary,
)
from substitute.presentation.canvas.output.composition.qpane import (
    output_route_projector_for,
)
from substitute.presentation.canvas.output.output_canvas_projection_controller import (
    OutputCanvasProjectionController,
)
from substitute.presentation.canvas.output.output_compare_projection_presenter import (
    OutputCompareProjectionCallbacks,
    OutputCompareProjectionPresenter,
    sync_output_comparison_navigation_buttons,
)
from substitute.presentation.canvas.output.output_image_route_controller import (
    OutputImageRouteController,
)
from substitute.presentation.canvas.output.output_projection_presenter import (
    OutputProjectionChromeCallbacks,
    OutputProjectionPresenter,
)
from substitute.presentation.canvas.output.output_route_binding_controller import (
    OutputRouteBindingController,
    OutputRouteBindingState,
)
from substitute.presentation.canvas.output.output_canvas_preview_state import (
    output_preview_registry,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    sync_output_scene_selector_button,
    sync_output_set_selector_button,
    sync_output_source_selector_button,
)
from substitute.presentation.canvas.output.output_canvas_navigation_chrome import (
    update_output_tabbar_container,
)


def _output_projection_for(host: object) -> OutputCanvasProjection | None:
    """Return the host projection when it has the expected DTO type."""

    projection = getattr(host, "_output_projection", None)
    return projection if isinstance(projection, OutputCanvasProjection) else None


def _output_session_for(host: object) -> OutputCanvasSession | None:
    """Return the host Output session when bound."""

    session = getattr(host, "_output_session", None)
    return session if isinstance(session, OutputCanvasSession) else None


def _compare_clear_route_identity(host: object) -> CanvasRouteIdentity:
    """Return the Output route whose compare rendering should be cleared."""

    if bool(getattr(host, "active_scene_overview", False)):
        return scene_overview_route_identity(
            active_scene_key=getattr(host, "active_scene_key", None),
        )
    active_source_key = getattr(host, "active_source_key", None)
    if active_source_key is not None and int(getattr(host, "active_set_index", 0)) == 0:
        return source_grid_route_identity(
            source_key=str(active_source_key),
            active_scene_key=getattr(host, "active_scene_key", None),
        )
    return CanvasRouteIdentity.empty()


def _allowed_output_image_ids_for(host: object) -> frozenset[UUID]:
    """Return authorized final-output image ids for a bound Output host."""

    session = _output_session_for(host)
    return session.allowed_image_ids if session is not None else frozenset()


def _active_scene_key_for(host: object) -> str | None:
    """Return the active scene key when it is a concrete route key."""

    scene_key = getattr(host, "active_scene_key", None)
    return scene_key if isinstance(scene_key, str) else None


def _active_source_key_for(host: object) -> str | None:
    """Return the active source key when it is a concrete route key."""

    source_key = getattr(host, "active_source_key", None)
    return source_key if isinstance(source_key, str) else None


def _source_tab_cache_signature_for(
    host: object,
) -> tuple[tuple[str, str], ...] | None:
    """Return cached source-tab identity when the host has one."""

    signature = getattr(host, "_source_tab_cache_signature", None)
    return signature if isinstance(signature, tuple) else None


def _source_tab_tooltip_filters_for(host: object) -> MutableMapping[str, object]:
    """Return mutable source-tab tooltip filter storage for the host."""

    filters = getattr(host, "_source_tab_tooltip_filters", None)
    if isinstance(filters, dict):
        return filters
    filters = {}
    setattr(host, "_source_tab_tooltip_filters", filters)
    return filters


def _host_width_for(host: object) -> int | None:
    """Return the host widget width when it can be measured."""

    width = getattr(host, "width", None)
    return int(width()) if callable(width) else None


def output_canvas_projection_controller_for_test_host(
    view: Any,
) -> OutputCanvasProjectionController:
    """Compose the projection facade for a lightweight non-production host."""

    existing = getattr(view, "_output_projection_controller", None)
    if isinstance(existing, OutputCanvasProjectionController):
        return existing
    boundary = getattr(view, "_route_session_boundary", None)
    if boundary is None:
        boundary = create_canvas_session_boundary()
        view._route_session_boundary = boundary
    projector = getattr(view, "_route_projector", None)
    if projector is None:
        projector = output_route_projector_for(
            getattr(view, "pane", object()),
            session_boundary=boundary,
        )
        view._route_projector = projector

    def preview_registry() -> Any:
        """Return the explicitly installed lightweight-host preview registry."""

        registry = getattr(view, "_preview_registry", None)
        return registry() if callable(registry) else output_preview_registry(view)

    route_binding = OutputRouteBindingController(
        route_projector=cast(OutputRouteProjectorPort, projector),
        session_boundary=cast(CanvasRouteSessionBoundaryPort, boundary),
        state=OutputRouteBindingState(
            workflow_id=lambda: str(getattr(view, "_projection_workflow_id", "") or ""),
            projection=lambda: _output_projection_for(view),
            session=lambda: _output_session_for(view),
            store_session=lambda session: setattr(view, "_output_session", session),
            preview_registry=preview_registry,
            active_scene_overview=lambda: bool(
                getattr(view, "active_scene_overview", False)
            ),
            active_scene_key=lambda: _active_scene_key_for(view),
        ),
    )
    image_routes = OutputImageRouteController(route_binding, cast(Any, projector))
    source_tabs = cast(
        Any,
        getattr(
            view,
            "_source_tabs_controller",
            SimpleNamespace(
                rebuild_source_tabs=lambda **_kwargs: None,
                refresh_source_tab_tooltips=lambda: None,
            ),
        ),
    )
    interaction = cast(
        Any,
        getattr(
            view,
            "_interaction_controller",
            SimpleNamespace(set_grid_interaction_locked=lambda _locked: None),
        ),
    )
    compare_controller = cast(
        Any, getattr(view, "_compare_controller", SimpleNamespace())
    )
    compare_rendering = cast(
        Any,
        getattr(
            view,
            "_compare_rendering_controller",
            SimpleNamespace(sync_compare_rendering=lambda: None),
        ),
    )
    compare_projection = OutputCompareProjectionPresenter(
        view=view,
        compare_controller=compare_controller,
        source_tabs=source_tabs,
        interaction=interaction,
        rendering=compare_rendering,
        callbacks=OutputCompareProjectionCallbacks(
            sync_scene_selector=lambda: sync_output_scene_selector_button(view),
            sync_set_selector=lambda: sync_output_set_selector_button(view),
            sync_source_selector=lambda: sync_output_source_selector_button(view),
            sync_comparison_navigation=lambda: (
                sync_output_comparison_navigation_buttons(view)
            ),
            update_tabbar=lambda: update_output_tabbar_container(view),
        ),
    )

    def present_grid() -> bool:
        """Present a grid through an explicitly installed test collaborator."""

        controller = getattr(view, "_route_application_controller", None)
        if controller is None:
            return False
        if bool(getattr(view, "active_scene_overview", False)):
            composer = getattr(view, "_scene_overview_composer", None)
            scenes = getattr(view, "scene_groups", {})
            plan = (
                composer.compose_scene_overview(
                    tuple(scenes.values()),
                    active_scene_key=_active_scene_key_for(view),
                )
                if composer is not None
                else None
            )
            return bool(
                plan is not None and controller.apply(plan, activate=True).accepted
            )
        source_key = _active_source_key_for(view)
        projection = _output_projection_for(view)
        source = (
            next(
                (item for item in projection.sources if item.source_key == source_key),
                None,
            )
            if projection is not None
            else None
        )
        composer = getattr(view, "_grid_composer", None)
        plan = (
            composer.compose_source_grid(
                source,
                scene_key=_active_scene_key_for(view),
            )
            if source is not None and composer is not None
            else None
        )
        return bool(plan is not None and controller.apply(plan, activate=True).accepted)

    presenter = OutputProjectionPresenter(
        view=view,
        route_binding=route_binding,
        image_routes=image_routes,
        compare_route_presenter=cast(
            Any,
            getattr(
                view,
                "_compare_presenter",
                SimpleNamespace(present=lambda **_kwargs: None),
            ),
        ),
        compare_projection_presenter=compare_projection,
        source_tabs=source_tabs,
        interaction=interaction,
        present_current_grid=present_grid,
        cancel_grid=lambda: None,
        chrome=OutputProjectionChromeCallbacks(
            sync_scene_selector=lambda: sync_output_scene_selector_button(view),
            sync_set_selector=lambda: sync_output_set_selector_button(view),
            sync_source_selector=lambda: sync_output_source_selector_button(view),
            update_tabbar=lambda: update_output_tabbar_container(view),
        ),
    )
    controller = OutputCanvasProjectionController(
        route_binding=route_binding,
        image_routes=image_routes,
        presenter=presenter,
        compare_presenter=compare_projection,
    )
    view._output_projection_controller = controller
    return controller
