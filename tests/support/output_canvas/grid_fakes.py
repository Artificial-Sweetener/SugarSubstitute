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

"""Build Output grid and scene-overview interaction test collaborators."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from PySide6.QtCore import QEvent, QPoint, Qt

from substitute.domain.workflow import CanvasRouteIdentity, ImageMeta
from substitute.application.workflows.canvas_route_projector_port import (
    OutputRouteScope,
    create_canvas_session_boundary,
)
from substitute.presentation.canvas.output.composition.grid import (
    output_grid_event_controller_for_host,
)
from substitute.presentation.canvas.output.output_grid_scene_builder import (
    OutputGridSceneBuilder,
)
from substitute.presentation.canvas.shared.responsive_canvas_grid_policy import (
    CanvasViewportExtent,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    sync_output_set_selector_button,
)
from substitute.presentation.canvas.output.output_canvas_interaction_controller import (
    OutputCanvasInteractionController,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    activate_output_item,
    activate_output_scene_overview,
)
from substitute.presentation.canvas.output.output_scene_overview_composer import (
    OutputSceneOverviewComposer,
    scene_overview_preview_for_scene,
)

from .host_fakes import SignalStub, install_fake_navigation_chrome


class _GridMouseEventBase:
    """Identify lightweight mouse-event doubles without Qt construction."""


class PreparedGridRouteHarness:
    """Build and apply prepared grid plans for lightweight Output hosts."""

    def __init__(self, fake: Any) -> None:
        """Store one host with installed composers and route application."""

        self._fake = fake

    def present_scene_overview(self, *, activate: bool) -> UUID | None:
        """Build and apply the host's current scene-overview plan."""

        plan = self._fake._scene_overview_composer.compose_scene_overview(
            tuple(self._fake.scene_groups.values()),
            active_scene_key=getattr(self._fake, "active_scene_key", None),
        )
        if plan is None:
            return None
        result = self._fake._route_application_controller.apply(plan, activate=activate)
        return result.composition_id if result.accepted else None

    def present_source_grid(
        self,
        source: object,
        *,
        activate: bool,
    ) -> UUID | None:
        """Build and apply a source-grid plan for the host's active scene."""

        plan = self._fake._grid_composer.compose_source_grid(
            source,
            scene_key=getattr(self._fake, "active_scene_key", None),
        )
        if plan is None:
            return None
        result = self._fake._route_application_controller.apply(plan, activate=activate)
        return result.composition_id if result.accepted else None


def route_application_controller(
    output_mod: Any, fake: Any
) -> PreparedGridRouteHarness:
    """Return the prepared-grid harness for a lightweight fake."""

    if not hasattr(fake, "_route_application_controller"):
        from .host_fakes import install_fake_output_asset_lookup  # noqa: PLC0415

        install_fake_output_asset_lookup(output_mod, fake)
    harness = getattr(fake, "_prepared_grid_route_harness", None)
    if not isinstance(harness, PreparedGridRouteHarness):
        harness = PreparedGridRouteHarness(fake)
        fake._prepared_grid_route_harness = harness
    return harness


def attach_scene_overview_compose_helpers(fake: Any, output_mod: Any) -> None:
    """Attach OutputCanvas scene-overview compose methods to a fake."""

    from substitute.application.workflows import bind_output_canvas_session  # noqa: PLC0415
    from substitute.presentation.canvas.qpane.canvas_route_projector import (  # noqa: PLC0415
        OutputRouteProjector,
    )
    from substitute.presentation.canvas.qpane.output_pane_adapter import (  # noqa: PLC0415
        OutputQPaneRouteAdapter,
    )
    from .host_fakes import install_fake_output_asset_lookup  # noqa: PLC0415
    from .route_fakes import install_fake_output_qpane_presenter  # noqa: PLC0415

    attach_output_grid_layout_helpers(fake)
    scene_groups = tuple(getattr(fake, "scene_groups", {}).values())
    projection = output_mod.OutputCanvasProjection(
        sources=(),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=0,
        scene_groups=scene_groups,
        active_scene_key=None,
        active_scene_overview=True,
        scene_count=max(2, len(scene_groups)),
    )
    boundary = create_canvas_session_boundary()
    session = bind_output_canvas_session(
        boundary, workflow_id="wf", projection=projection, image_metadata_lookup={}
    )
    fake._projection_workflow_id = "wf"
    fake._output_projection = projection
    fake._output_session = session
    fake._route_session_boundary = boundary
    payloads = getattr(fake, "images_by_id", {})
    fake._final_output_payload = lambda image_id: payloads.get(image_id)
    fake._final_output_metadata = lambda _image_id: None
    install_fake_output_asset_lookup(output_mod, fake)
    install_fake_output_qpane_presenter(fake)
    if not hasattr(fake, "_route_projector"):
        route_projector = OutputRouteProjector(
            OutputQPaneRouteAdapter(fake.pane), session_boundary=boundary
        )
        route_projector.bind(
            OutputRouteScope(
                session=session,
                allowed_image_ids=session.allowed_image_ids,
                allowed_source_keys=session.allowed_source_keys,
                allowed_scene_keys=session.allowed_scene_keys,
                allowed_composition_ids=session.allowed_composition_ids,
            )
        )
        fake._route_projector = route_projector


def build_scene_preview_focus_fake(
    output_mod: Any,
    *,
    active_scene_key: str | None,
    active_scene_overview: bool,
    scene_count: int,
) -> tuple[SimpleNamespace, list[object], list[object], list[object]]:
    """Build an OutputCanvas double for scene preview focus tests."""

    added: list[object] = []
    current_ids: list[object] = []
    composed: list[object] = []

    def compose_scene(request: Any, activate: bool = True) -> Any:
        composed.append((request, activate))
        return request.composition_id

    pane = SimpleNamespace(
        addImage=lambda image_id, image, path: added.append((image_id, image, path)),
        setCurrentImageID=lambda image_id: current_ids.append(image_id),
        setControlMode=lambda _mode: None,
        composeScene=compose_scene,
    )
    fake = SimpleNamespace(
        pane=pane,
        images_by_id={},
        image_ids=[],
        preview_ids_by_source_key={},
        preview_labels_by_source_key={},
        preview_images_by_source_key={},
        preview_ids_by_source_slot={},
        preview_ids_by_scene_slot={},
        scene_preview_slots_by_key={},
        source_groups={},
        scene_groups={},
        active_scene_key=active_scene_key,
        active_scene_overview=active_scene_overview,
        scene_count=scene_count,
        scene_overview_scene_id=None,
        scene_grid_layer_ids_by_key={},
        active_source_key=None,
        active_set_index=1,
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
        set_count=0,
    )
    from .preview_fakes import install_fake_output_preview_controller  # noqa: PLC0415

    install_fake_output_preview_controller(output_mod, fake)
    fake._set_scene_preview_image = lambda image, **kwargs: (
        fake._preview_controller.set_scene_preview_image(image, **kwargs)
    )
    fake._activate_scene_overview = lambda: activate_output_scene_overview(
        fake, update_tabbar_container=fake._update_tabbar_container
    )
    fake._compose_scene_overview_grid = lambda *, activate: (
        route_application_controller(output_mod, fake).present_scene_overview(
            activate=activate
        )
    )
    attach_scene_overview_compose_helpers(fake, output_mod)
    fake._sync_scene_selector_button = lambda: None
    fake._sync_set_selector_button = lambda: None
    fake._update_tabbar_container = lambda: None
    return fake, added, current_ids, composed


def build_output_grid_click_fake(
    output_mod: Any, hit: object
) -> tuple[SimpleNamespace, UUID, list[object], list[str], list[object]]:
    """Build a lightweight OutputCanvas double for grid-click tests."""

    from substitute.application.workflows import (  # noqa: PLC0415
        OutputCanvasImageItem,
        OutputCanvasSourceGroup,
        bind_output_canvas_session,
    )
    from substitute.presentation.canvas.qpane.canvas_route_projector import (  # noqa: PLC0415
        OutputRouteProjector,
    )
    from substitute.presentation.canvas.qpane.output_pane_adapter import (  # noqa: PLC0415
        OutputQPaneRouteAdapter,
    )

    id_a = uuid4()
    id_b = uuid4()
    pane_calls: list[object] = []
    control_modes: list[str] = []
    hit_calls: list[object] = []

    def scene_hit_test(point: object) -> object:
        hit_calls.append(point)
        return hit

    tabbar = SimpleNamespace(
        items={"source-a": object()}, setCurrentItem=lambda _key: None
    )
    selector = SimpleNamespace(width=lambda: 44)
    selector.setText = lambda text: setattr(selector, "text", text)
    selector.setVisible = lambda visible: setattr(selector, "visible", visible)
    image_meta = ImageMeta("wf", "Source A", 1, "", "", source_key="source-a")
    source = OutputCanvasSourceGroup(
        source_key="source-a",
        label="Source A",
        images_by_set={
            1: OutputCanvasImageItem(id_a, image_meta, 1),
            2: OutputCanvasImageItem(id_b, image_meta, 2),
        },
    )
    projection = output_mod.OutputCanvasProjection(
        sources=(source,),
        active_source_key="source-a",
        active_set_index=0,
        active_uuid=None,
        set_count=2,
    )
    route = CanvasRouteIdentity(
        route_kind="source_grid", route_key="scene:;source:source-a;set:0"
    )
    boundary = create_canvas_session_boundary()
    session = bind_output_canvas_session(
        boundary,
        workflow_id="wf",
        projection=projection,
        image_metadata_lookup={id_a: source.images_by_set[1].image_meta},
    )
    projector = OutputRouteProjector(
        OutputQPaneRouteAdapter(SimpleNamespace()), session_boundary=boundary
    )
    route_scope = OutputRouteScope(
        session=session,
        allowed_image_ids=frozenset({id_a, id_b}),
        allowed_source_keys=frozenset({"source-a"}),
        allowed_scene_keys=frozenset(),
        allowed_composition_ids=session.allowed_composition_ids,
    )
    projector.bind(route_scope)
    composition_id = projector.route_composition_id(route)
    if hasattr(hit, "__dict__"):
        setattr(hit, "composition_id", composition_id)
    pane = SimpleNamespace(
        sceneHitTest=scene_hit_test,
        setCurrentImageID=lambda image_id: pane_calls.append(image_id),
        setControlMode=lambda mode: control_modes.append(mode),
        currentCompositionID=lambda: composition_id,
        getCompositionSnapshot=lambda: SimpleNamespace(
            current_composition_id=composition_id,
            compositions={
                composition_id: SimpleNamespace(
                    source_image_ids=(id_a, id_b),
                    current_image_id=None,
                    comparison=SimpleNamespace(enabled=False, source_id=None),
                )
            },
        ),
    )
    bound_projector = OutputRouteProjector(
        OutputQPaneRouteAdapter(pane), session_boundary=boundary
    )
    bound_projector.bind(route_scope)
    fake = SimpleNamespace(
        pane=pane,
        _route_session_boundary=boundary,
        _route_projector=bound_projector,
        _projection_workflow_id="wf",
        _output_projection=projection,
        activeOutputChanged=SignalStub(),
        activeOutputGridChanged=SignalStub(),
        active_source_key="source-a",
        active_set_index=0,
        last_real_set_index=1,
        source_groups={"source-a": source},
        tabbar=tabbar,
        _suppress_tab_change=False,
        _on_tab_changed=lambda _route: None,
        set_selector_button=selector,
        set_count=2,
        preview_ids_by_source_key={},
        preview_ids_by_source_slot={},
        preview_ids_by_scene_slot={},
        scene_preview_slots_by_key={},
        _grid_click_press_pos=None,
    )
    fake._activate_output_item = lambda source_key, item, **kwargs: (
        activate_output_item(
            fake,
            source_key,
            item,
            update_tabbar_container=fake._update_tabbar_container,
            **kwargs,
        )
    )
    fake._sync_set_selector_button = lambda: sync_output_set_selector_button(fake)
    install_fake_navigation_chrome(fake)
    install_fake_output_grid_event_controller(output_mod, fake)
    return fake, id_b, pane_calls, control_modes, hit_calls


def install_fake_output_interaction_controller(fake: Any) -> None:
    """Install the composed interaction controller expected by widget seams."""

    if hasattr(fake, "_interaction_controller"):
        return
    pane = getattr(fake, "pane", None)
    set_control_mode = getattr(pane, "setControlMode", None)
    fake._interaction_controller = OutputCanvasInteractionController(
        press_position=lambda: getattr(fake, "_grid_click_press_pos", None),
        set_press_position=lambda position: setattr(
            fake, "_grid_click_press_pos", position
        ),
        set_control_mode=(
            set_control_mode if callable(set_control_mode) else lambda _mode: None
        ),
        cursor_control_mode="cursor",
        panzoom_control_mode="panzoom",
    )


def install_fake_output_grid_event_controller(output_mod: Any, fake: Any) -> None:
    """Install the composed grid event controller expected by widget seams."""

    install_fake_output_interaction_controller(fake)
    if hasattr(fake, "_grid_event_controller"):
        return
    route_projector = getattr(
        fake,
        "_route_projector",
        SimpleNamespace(hit_test_scene=lambda _point: None),
    )
    fake._grid_event_controller = output_grid_event_controller_for_host(
        fake,
        route_projector=route_projector,
        interaction_controller=fake._interaction_controller,
        watched_is_pane=lambda watched: watched is fake.pane,
        is_mouse_event=lambda event: isinstance(event, _GridMouseEventBase),
        event_type=lambda event: cast(Any, event).type(),
        event_is_left_button=lambda event: (
            cast(Any, event).button() == Qt.MouseButton.LeftButton
        ),
        event_position=lambda event: cast(Any, event).position().toPoint(),
        drag_distance=lambda: 8,
        press_type=QEvent.Type.MouseButtonPress,
        release_type=QEvent.Type.MouseButtonRelease,
        update_tabbar_container=getattr(fake, "_update_tabbar_container", lambda: None),
    )


def attach_output_grid_layout_helpers(fake: Any) -> None:
    """Install the interaction collaborator needed by lightweight grid fakes."""

    install_fake_output_interaction_controller(fake)


def grid_mouse_event(output_mod: Any, event_type: object, x: int, y: int) -> object:
    """Build a QMouseEvent-like test double for output-grid event filters."""

    event_class = type(
        "GridMouseEvent",
        (_GridMouseEventBase,),
        {
            "type": lambda _self: event_type,
            "button": lambda _self: Qt.MouseButton.LeftButton,
            "position": lambda _self: SimpleNamespace(toPoint=lambda: QPoint(x, y)),
        },
    )
    return event_class()


def compose_scene_overview_route_request(output_mod: Any, fake: Any) -> Any | None:
    """Compose a scene-overview route request for an OutputCanvas fake."""

    composer = OutputSceneOverviewComposer(
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
    return composer.compose_scene_overview(
        tuple(
            output_mod.output_scene_groups_by_key(
                output_mod.output_route_state_snapshot(fake)
            ).values()
        ),
        active_scene_key=getattr(fake, "active_scene_key", None),
    )


__all__ = [
    "attach_output_grid_layout_helpers",
    "attach_scene_overview_compose_helpers",
    "build_output_grid_click_fake",
    "build_scene_preview_focus_fake",
    "compose_scene_overview_route_request",
    "grid_mouse_event",
    "install_fake_output_grid_event_controller",
    "install_fake_output_interaction_controller",
    "route_application_controller",
]
