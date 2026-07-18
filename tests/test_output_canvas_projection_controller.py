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

"""Verify Output canvas projection binding outside the Qt widget."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from substitute.application.workflows.canvas_route_projector_port import (
    OutputRouteScope,
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
    OutputPreviewLane,
    OutputPreviewLaneKey,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareSelection,
    OutputCompareState,
)
from substitute.domain.workflow import (
    CanvasKind,
    CanvasRouteIdentity,
    CanvasSessionBoundary,
    CanvasSessionRevision,
    ImageMeta,
)
from substitute.presentation.canvas.output.output_canvas_projection_controller import (
    OutputCanvasProjectionController,
)
from substitute.presentation.canvas.output.output_compare_projection_presenter import (
    OutputCompareProjectionCallbacks,
    OutputCompareProjectionPresenter,
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
from substitute.presentation.canvas.output.output_compare_projection_presenter import (
    sync_output_compare_scene_button,
    sync_output_compare_set_button,
    sync_output_compare_source_button,
    sync_output_comparison_navigation_buttons,
)
from substitute.presentation.canvas.output.output_compare_controller import (
    OutputCompareProjectionPlan,
)


def test_bind_output_route_projector_reuses_preview_lane_session() -> None:
    """Preview-image routes should reuse the current session and include previews."""

    image_id = uuid4()
    preview_id = uuid4()
    session_boundary = CanvasSessionBoundary()
    session = _session(
        session_boundary=session_boundary,
        workflow_id="workflow-a",
        image_id=image_id,
        source_key="source-a",
        scene_key="scene-a",
    )
    preview_lane = _preview_lane(
        preview_id=preview_id,
        workflow_id="workflow-a",
        source_key="source-b",
        scene_key="scene-b",
        session_revision=session.revision,
    )
    route = CanvasRouteIdentity(
        route_kind="output_image",
        route_key=f"image:{preview_id}",
        primary_image_id=preview_id,
    )
    view = _view(
        session_boundary=session_boundary,
        output_session=session,
        preview_lanes=(preview_lane,),
    )

    _controller(view).bind_output_route_projector(route)

    assert view._output_session is session
    assert view.projector.bound_scopes[-1].session is session
    assert view.projector.bound_scopes[-1].allowed_image_ids == frozenset(
        {image_id, preview_id}
    )
    assert view.projector.bound_scopes[-1].allowed_source_keys == frozenset(
        {"source-a", "source-b"}
    )
    assert view.projector.bound_scopes[-1].allowed_scene_keys == frozenset({"scene-b"})


def test_bind_projection_route_projector_adopts_missing_boundary_session() -> None:
    """Binding an externally built session should seed an empty local boundary."""

    external_boundary = CanvasSessionBoundary()
    local_boundary = CanvasSessionBoundary()
    image_id = uuid4()
    session = _session(
        session_boundary=external_boundary,
        workflow_id="workflow-a",
        image_id=image_id,
        source_key="source-a",
        scene_key="scene-a",
    )
    view = _view(session_boundary=local_boundary)

    _controller(view).bind_projection_route_projector(session)

    assert local_boundary.current_session(CanvasKind.OUTPUT) == session.session
    assert view.projector.bound_scopes[-1] == OutputRouteScope(
        session=session,
        allowed_image_ids=session.allowed_image_ids,
        allowed_source_keys=session.allowed_source_keys,
        allowed_scene_keys=session.allowed_scene_keys,
        allowed_composition_ids=session.allowed_composition_ids,
    )


def test_set_current_output_image_binds_and_applies_route() -> None:
    """Concrete image selection should bind scope before commanding QPane."""

    image_id = uuid4()
    projection = _projection(
        image_id=image_id,
        source_key="source-a",
        scene_key="scene-a",
    )
    view = _view(
        projection=projection,
        projection_workflow_id="workflow-a",
    )

    assert _controller(view).set_current_output_image(image_id)

    assert view._output_session.allowed_image_ids == frozenset({image_id})
    assert view.projector.applied_routes == (
        CanvasRouteIdentity(
            route_kind="output_image",
            route_key=f"image:{image_id}",
            primary_image_id=image_id,
        ),
    )
    assert view.projector.applied_image_ids == (image_id,)


def test_set_current_output_image_none_binds_and_clears_route() -> None:
    """Clearing current image should bind an empty scope before clearing QPane."""

    view = _view(projection_workflow_id="workflow-a")

    assert _controller(view).set_current_output_image(None)

    assert view.projector.cleared_routes == (CanvasRouteIdentity.empty(),)
    assert view.projector.bound_scopes[-1].allowed_image_ids == frozenset()


def test_apply_projection_final_image_uses_session_active_route() -> None:
    """Projection final selection should use the bound session route identity."""

    image_id = uuid4()
    session = _session(
        session_boundary=CanvasSessionBoundary(),
        workflow_id="workflow-a",
        image_id=image_id,
        source_key="source-a",
        scene_key="scene-a",
    )
    view = _view(output_session=session)

    assert _controller(view).apply_projection_final_image(
        session,
        image_id,
    )

    assert view.projector.applied_routes == (session.active_route,)
    assert view.projector.applied_image_ids == (image_id,)


def test_bind_projection_session_applies_final_output_projection() -> None:
    """Projection session binding should apply normal final-output state."""

    image_id = uuid4()
    projection = _projection(
        image_id=image_id,
        source_key="source-a",
        scene_key="scene-a",
    )
    session_boundary = CanvasSessionBoundary()
    session = _session_for_projection(
        session_boundary=session_boundary,
        workflow_id="workflow-a",
        projection=projection,
    )
    view = _view(session_boundary=session_boundary)
    view._compare_presenter = _ComparePresenter()
    view._source_tabs_controller = _SourceTabsController()
    view._interaction_controller = _InteractionController()
    view._route_application_controller = _RouteApplicationController()
    retire_calls: list[tuple[object, str, str]] = []
    sync_calls: list[str] = []

    _controller(view, sync_calls=sync_calls).bind_projection_session(
        session,
        retire_completed_preview_slot=lambda slot_key, source_label, reason: (
            retire_calls.append((slot_key, source_label, reason))
        ),
    )

    assert view._output_session is session
    assert view._projection_workflow_id == "workflow-a"
    assert view._output_projection is projection
    assert view.scene_count == 1
    assert view.active_scene_key == "scene-a"
    assert view.active_scene_overview is False
    assert view.active_source_key == "source-a"
    assert view.active_set_index == 1
    assert view.last_real_set_index == 1
    assert view.set_count == 1
    assert view._source_tabs_controller.rebuilds == ["source-a"]
    assert view.projector.applied_routes == (session.active_route,)
    assert view.projector.applied_image_ids == (image_id,)
    assert view._interaction_controller.locked_values == [False]
    assert view._compare_presenter.presented[-1]["route_blocked"] is True
    assert retire_calls == []
    assert sync_calls == ["scene", "set", "scene", "source", "tabbar"]


def test_sync_compare_projection_applies_plan_to_widget_state() -> None:
    """Compare projection sync should live in the projection controller."""

    image_id = uuid4()
    projection = _projection(
        image_id=image_id,
        source_key="source-a",
        scene_key="scene-a",
        scene_count=2,
    )
    original_state = OutputCompareState(enabled=True)
    planned_state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection("scene-a", 2, "source-a"),
    )
    view = _view(projection=projection)
    view._compare_controller = _CompareController(
        OutputCompareProjectionPlan(
            state=planned_state,
            base=OutputCompareSelection("scene-a", 2, "source-a"),
            sources=projection.sources,
            set_count=4,
        )
    )
    view._source_tabs_controller = _SourceTabsController()
    view._interaction_controller = _InteractionController()
    view._compare_rendering_controller = _CompareRenderingController()
    sync_calls: list[str] = []
    _controller(view, sync_calls=sync_calls).sync_compare_projection(
        projection,
        original_state,
    )

    assert view._visible_compare_state == planned_state
    assert view.active_scene_overview is False
    assert view.active_scene_key == "scene-a"
    assert view.active_source_key == "source-a"
    assert view.active_set_index == 2
    assert view.last_real_set_index == 2
    assert view.set_count == 4
    assert view._source_tabs_controller.rebuilds == ["source-a"]
    assert sync_calls == ["scene", "set", "source", "comparison", "tabbar"]
    assert view._interaction_controller.locked_values == [False]
    assert view._compare_rendering_controller.sync_count == 1


def test_sync_compare_projection_disables_compare_without_base() -> None:
    """Missing base selection should delegate compare-mode shutdown."""

    image_id = uuid4()
    projection = _projection(
        image_id=image_id,
        source_key="source-a",
        scene_key="scene-a",
    )
    view = _view(projection=projection)
    view._compare_controller = _CompareController(
        OutputCompareProjectionPlan(
            state=OutputCompareState(enabled=True),
            base=None,
            sources=(),
            set_count=0,
        )
    )

    _controller(view).sync_compare_projection(
        projection,
        OutputCompareState(enabled=True),
    )

    assert view._compare_controller.enabled_values == [False]


def test_sync_output_comparison_navigation_buttons_uses_host_state() -> None:
    """Comparison navigation host adapter should sync visible comparison buttons."""

    selection = OutputCompareSelection(
        scene_key="scene-a",
        set_index=2,
        source_key="source-a",
    )
    scene_button = _SelectorButton()
    set_button = _SelectorButton()
    source_button = _SelectorButton()
    calls: list[tuple[str, object | None, object | None]] = []
    view = SimpleNamespace(
        _visible_compare_state=OutputCompareState(
            enabled=True,
            comparison=selection,
        ),
        comparison_nav_container=SimpleNamespace(
            hide=lambda: calls.append(("hide", None, None))
        ),
        comparison_scene_selector_button=scene_button,
        comparison_set_selector_button=set_button,
        comparison_source_selector_button=source_button,
        _output_projection=_projection(
            image_id=uuid4(),
            source_key="source-a",
            scene_key="scene-a",
            scene_count=2,
            scene_title="Scene",
        ),
        scene_count=2,
        _compare_controller=SimpleNamespace(
            compare_set_count=lambda _side: 4,
            compare_source_label=lambda _selection: "Source Label",
        ),
    )

    sync_output_comparison_navigation_buttons(view)

    assert calls == []
    assert scene_button.text == "Scene"
    assert scene_button.visible is True
    assert set_button.text == "2"
    assert set_button.visible is True
    assert source_button.text == "Source Label"
    assert source_button.visible is True


def test_sync_output_compare_set_button_applies_host_set_count() -> None:
    """Compare set host adapter should apply set index and count to the button."""

    selection = OutputCompareSelection(
        scene_key="scene-a",
        set_index=3,
        source_key="source-a",
    )
    button = _SelectorButton()
    view = SimpleNamespace(
        _compare_controller=SimpleNamespace(compare_set_count=lambda _side: 4)
    )

    sync_output_compare_set_button(view, button, selection)

    assert button.text == "3"
    assert button.visible is True


def test_sync_output_compare_source_button_applies_host_source_label() -> None:
    """Compare source host adapter should apply the resolved source label."""

    selection = OutputCompareSelection(
        scene_key="scene-a",
        set_index=3,
        source_key="source-a",
    )
    button = _SelectorButton()
    view = SimpleNamespace(
        _compare_controller=SimpleNamespace(
            compare_source_label=lambda _selection: "Preview Source"
        )
    )

    sync_output_compare_source_button(view, button, selection)

    assert button.text == "Preview Source"
    assert button.visible is True


def test_sync_output_compare_scene_button_applies_host_scene_label() -> None:
    """Compare scene host adapter should apply the selected scene label."""

    selection = OutputCompareSelection(
        scene_key="scene-a",
        set_index=3,
        source_key="source-a",
    )
    button = _SelectorButton()
    view = SimpleNamespace(
        _output_projection=_projection(
            image_id=uuid4(),
            source_key="source-a",
            scene_key="scene-a",
            scene_count=2,
            scene_title="Scene",
        ),
        scene_count=2,
    )

    sync_output_compare_scene_button(view, button, selection)

    assert button.text == "Scene"
    assert button.visible is True


class _SelectorButton:
    """Record selector button writes."""

    def __init__(self) -> None:
        """Create an unset button fake."""

        self.text = ""
        self.visible = False

    def setText(self, text: str) -> None:
        """Record button text."""

        self.text = text

    def setVisible(self, visible: bool) -> None:
        """Record button visibility."""

        self.visible = visible


def _controller(
    view: object,
    *,
    sync_calls: list[str] | None = None,
) -> OutputCanvasProjectionController:
    """Return a projection controller with explicit chrome callbacks."""

    calls = sync_calls if sync_calls is not None else []
    projector = cast(Any, getattr(view, "_route_projector"))
    boundary = cast(
        Any,
        getattr(view, "_route_session_boundary", None) or CanvasSessionBoundary(),
    )
    route_binding = OutputRouteBindingController(
        route_projector=projector,
        session_boundary=boundary,
        state=OutputRouteBindingState(
            workflow_id=lambda: str(getattr(view, "_projection_workflow_id", "") or ""),
            projection=lambda: cast(
                OutputCanvasProjection | None,
                getattr(view, "_output_projection", None),
            ),
            session=lambda: cast(
                OutputCanvasSession | None,
                getattr(view, "_output_session", None),
            ),
            store_session=lambda session: setattr(view, "_output_session", session),
            preview_registry=lambda: cast(Any, getattr(view, "preview_registry")),
            active_scene_overview=lambda: bool(
                getattr(view, "active_scene_overview", False)
            ),
            active_scene_key=lambda: cast(
                str | None, getattr(view, "active_scene_key", None)
            ),
        ),
    )
    image_routes = OutputImageRouteController(route_binding, projector)
    source_tabs = cast(Any, getattr(view, "_source_tabs_controller", object()))
    interaction = cast(Any, getattr(view, "_interaction_controller", object()))
    compare_projection = OutputCompareProjectionPresenter(
        view=view,
        compare_controller=cast(Any, getattr(view, "_compare_controller", object())),
        source_tabs=source_tabs,
        interaction=interaction,
        rendering=cast(Any, getattr(view, "_compare_rendering_controller", object())),
        callbacks=OutputCompareProjectionCallbacks(
            sync_scene_selector=lambda: calls.append("scene"),
            sync_set_selector=lambda: calls.append("set"),
            sync_source_selector=lambda: calls.append("source"),
            sync_comparison_navigation=lambda: calls.append("comparison"),
            update_tabbar=lambda: calls.append("tabbar"),
        ),
    )

    def present_grid() -> bool:
        """Record grid presentation through the installed route double."""

        controller = getattr(view, "_route_application_controller", None)
        if controller is None:
            return False
        if bool(getattr(view, "active_scene_overview", False)):
            controller.compose_scene_overview_grid(activate=True)
            return True
        source_key = getattr(view, "active_source_key", None)
        projection = getattr(view, "_output_projection", None)
        source = next(
            (
                item
                for item in getattr(projection, "sources", ())
                if item.source_key == source_key
            ),
            None,
        )
        if source is None:
            return False
        controller.compose_grid_scene_for_source(source, activate=True)
        return True

    presenter = OutputProjectionPresenter(
        view=view,
        route_binding=route_binding,
        image_routes=image_routes,
        compare_route_presenter=cast(
            Any, getattr(view, "_compare_presenter", object())
        ),
        compare_projection_presenter=compare_projection,
        source_tabs=source_tabs,
        interaction=interaction,
        present_current_grid=present_grid,
        cancel_grid=lambda: None,
        chrome=OutputProjectionChromeCallbacks(
            sync_scene_selector=lambda: calls.append("scene"),
            sync_set_selector=lambda: calls.append("set"),
            sync_source_selector=lambda: calls.append("source"),
            update_tabbar=lambda: calls.append("tabbar"),
        ),
    )
    return OutputCanvasProjectionController(
        route_binding=route_binding,
        image_routes=image_routes,
        presenter=presenter,
        compare_presenter=compare_projection,
    )


@dataclass(slots=True)
class _RouteProjector:
    """Record route projector commands issued by the controller."""

    bound_scopes: list[OutputRouteScope] = field(default_factory=list)
    applied_routes: tuple[CanvasRouteIdentity, ...] = ()
    applied_image_ids: tuple[UUID, ...] = ()
    cleared_routes: tuple[CanvasRouteIdentity, ...] = ()

    def bind(self, scope: OutputRouteScope) -> None:
        """Record one active Output route scope."""

        self.bound_scopes.append(scope)

    def apply_final_image_route(
        self,
        route: CanvasRouteIdentity,
        image_id: UUID,
    ) -> bool:
        """Record a final-image route command."""

        self.applied_routes = (*self.applied_routes, route)
        self.applied_image_ids = (*self.applied_image_ids, image_id)
        return True

    def clear_route(self, route: CanvasRouteIdentity) -> bool:
        """Record a route clear command."""

        self.cleared_routes = (*self.cleared_routes, route)
        return True


@dataclass(slots=True)
class _CompareController:
    """Return a fixed compare projection plan and record disable requests."""

    plan: OutputCompareProjectionPlan
    enabled_values: list[bool] = field(default_factory=list)

    def compare_projection_plan(
        self,
        projection: OutputCanvasProjection,
        state: OutputCompareState,
    ) -> OutputCompareProjectionPlan:
        """Return the configured compare projection plan."""

        _ = projection, state
        return self.plan

    def set_compare_mode_enabled(self, enabled: bool) -> None:
        """Record compare-mode enablement changes."""

        self.enabled_values.append(enabled)


@dataclass(slots=True)
class _SourceTabsController:
    """Record source-tab rebuild requests."""

    rebuilds: list[str | None] = field(default_factory=list)
    tooltip_refresh_count: int = 0

    def rebuild_source_tabs(self, *, active_source_key: str | None) -> None:
        """Record one source-tab rebuild."""

        self.rebuilds.append(active_source_key)

    def refresh_source_tab_tooltips(self) -> None:
        """Record source-tab tooltip refresh."""

        self.tooltip_refresh_count += 1


@dataclass(slots=True)
class _InteractionController:
    """Record grid-lock state changes."""

    locked_values: list[bool] = field(default_factory=list)

    def set_grid_interaction_locked(self, locked: bool) -> None:
        """Record whether grid interaction is locked."""

        self.locked_values.append(locked)


@dataclass(slots=True)
class _CompareRenderingController:
    """Record compare rendering refreshes."""

    sync_count: int = 0

    def sync_compare_rendering(self) -> None:
        """Record a compare rendering refresh."""

        self.sync_count += 1


@dataclass(slots=True)
class _ComparePresenter:
    """Record compare presenter calls."""

    presented: list[dict[str, object]] = field(default_factory=list)

    def present(self, **kwargs: object) -> None:
        """Record one compare presentation."""

        self.presented.append(kwargs)


@dataclass(slots=True)
class _RouteApplicationController:
    """Record projection route-application requests."""

    scene_overview_count: int = 0
    grid_sources: list[str] = field(default_factory=list)

    def compose_scene_overview_grid(self, *, activate: bool) -> None:
        """Record one scene-overview composition request."""

        if activate:
            self.scene_overview_count += 1

    def compose_grid_scene_for_source(
        self,
        source: OutputCanvasSourceGroup,
        *,
        activate: bool,
    ) -> None:
        """Record one source-grid composition request."""

        if activate:
            self.grid_sources.append(source.source_key)


@dataclass(frozen=True, slots=True)
class _PreviewRegistry:
    """Return fixed preview lanes for controller tests."""

    lanes: tuple[OutputPreviewLane, ...] = ()

    def lanes_for_session(
        self,
        session: OutputCanvasSession,
    ) -> tuple[OutputPreviewLane, ...]:
        """Return test preview lanes for any supplied session."""

        _ = session
        return self.lanes

    def preview_scene_groups(
        self,
        session: OutputCanvasSession | None,
    ) -> dict[str, OutputCanvasSceneGroup]:
        """Return no preview scene overlays for projection tests."""

        _ = session
        return {}


def _view(
    *,
    session_boundary: CanvasSessionBoundary | None = None,
    output_session: OutputCanvasSession | None = None,
    projection: OutputCanvasProjection | None = None,
    projection_workflow_id: str = "",
    preview_lanes: tuple[OutputPreviewLane, ...] = (),
) -> SimpleNamespace:
    """Return a minimal OutputCanvas-like object for controller tests."""

    projector = _RouteProjector()
    preview_registry = _PreviewRegistry(preview_lanes)
    view = SimpleNamespace(
        _output_session=output_session,
        _output_projection=projection,
        _projection_workflow_id=projection_workflow_id,
        _route_session_boundary=session_boundary,
        active_scene_overview=False,
        active_scene_key=None,
        projector=projector,
        preview_registry=preview_registry,
        _route_projector=projector,
    )
    view._preview_registry = preview_registry
    return view


def _session(
    *,
    session_boundary: CanvasSessionBoundary,
    workflow_id: str,
    image_id: UUID,
    source_key: str,
    scene_key: str,
) -> OutputCanvasSession:
    """Return one bound Output projection session."""

    projection = _projection(
        image_id=image_id,
        source_key=source_key,
        scene_key=scene_key,
    )
    return bind_output_canvas_session(
        session_boundary,
        workflow_id=workflow_id,
        projection=projection,
        image_metadata_lookup={
            image_id: _meta(source_key=source_key, scene_key=scene_key),
        },
    )


def _session_for_projection(
    *,
    session_boundary: CanvasSessionBoundary,
    workflow_id: str,
    projection: OutputCanvasProjection,
) -> OutputCanvasSession:
    """Return a session for one supplied projection."""

    return bind_output_canvas_session(
        session_boundary,
        workflow_id=workflow_id,
        projection=projection,
        image_metadata_lookup={
            item.image_id: item.image_meta
            for source in projection.sources
            for item in source.images_by_set.values()
        },
    )


def _projection(
    *,
    image_id: UUID,
    source_key: str,
    scene_key: str,
    scene_count: int = 1,
    scene_title: str | None = None,
) -> OutputCanvasProjection:
    """Return one source-backed Output projection."""

    image_item = OutputCanvasImageItem(
        image_id=image_id,
        image_meta=_meta(source_key=source_key, scene_key=scene_key),
        set_index=1,
    )
    source_group = OutputCanvasSourceGroup(
        source_key=source_key,
        label="Source",
        images_by_set={1: image_item},
    )
    scene_groups: tuple[OutputCanvasSceneGroup, ...] = ()
    if scene_title is not None:
        scene_groups = (
            OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key=scene_key,
                title=scene_title,
                order=0,
                sources=(source_group,),
            ),
        )
    return OutputCanvasProjection(
        sources=(source_group,),
        active_source_key=source_key,
        active_set_index=1,
        active_uuid=image_id,
        set_count=1,
        scene_groups=scene_groups,
        active_scene_key=scene_key,
        scene_count=scene_count,
    )


def _meta(*, source_key: str, scene_key: str) -> ImageMeta:
    """Return minimal output metadata for controller tests."""

    return ImageMeta(
        workflow_name="Workflow",
        cube_name="Output",
        image_number=1,
        suffix="",
        path="E:/out.png",
        source_key=source_key,
        source_label="Output",
        scene_key=scene_key,
    )


def _preview_lane(
    *,
    preview_id: UUID,
    workflow_id: str,
    source_key: str,
    scene_key: str | None,
    session_revision: CanvasSessionRevision,
) -> OutputPreviewLane:
    """Return one accepted Output preview lane."""

    return OutputPreviewLane(
        key=OutputPreviewLaneKey.source(
            workflow_id=workflow_id,
            generation_run_id="run-a",
            prompt_id="prompt-a",
            source_key=source_key,
            scene_key=scene_key,
        ),
        preview_id=preview_id,
        image=object(),
        source_label="Source",
        client_id="client-a",
        session_revision=session_revision,
    )
