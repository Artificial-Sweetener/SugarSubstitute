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

"""Contract tests for guarded QPane canvas route projectors."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from uuid import UUID, uuid4

from _pytest.logging import LogCaptureFixture

from substitute.application.workflows.canvas_route_projector_port import (
    InputRouteScope,
    OutputCanvasHitKind,
    OutputRouteScope,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_session import (
    bind_output_canvas_session,
    deterministic_host_composition_id,
)
from substitute.domain.workflow import (
    CanvasKind,
    CanvasRouteIdentity,
    CanvasSessionBoundary,
    ImageMeta,
)
from substitute.presentation.canvas.qpane import (
    InputQPaneRouteAdapter,
    InputRouteProjector,
    OutputQPaneRouteAdapter,
    OutputRouteProjector,
)


class _InputPaneDouble:
    """Record Input QPane display calls."""

    def __init__(self) -> None:
        """Initialize active image state."""

        self.current_id: UUID | None = None
        self.active_mask_id: UUID | None = None
        self.calls: list[tuple[str, object]] = []

    def setCurrentImageID(self, image_id: UUID | None) -> None:  # noqa: N802
        """Record image selection."""

        self.current_id = image_id
        self.calls.append(("current", image_id))

    def currentImageID(self) -> UUID | None:  # noqa: N802
        """Return the active image selection."""

        return self.current_id

    def setActiveMaskID(self, mask_id: UUID) -> None:  # noqa: N802
        """Record mask selection."""

        self.active_mask_id = mask_id
        self.calls.append(("mask", mask_id))


class _OutputPaneDouble:
    """Record Output QPane display, composition, compare, and hit calls."""

    def __init__(self) -> None:
        """Initialize composition and call state."""

        self.current_id: UUID | None = None
        self.current_composition_id: UUID | None = None
        self.compositions: dict[UUID, SimpleNamespace] = {}
        self.calls: list[tuple[str, object]] = []
        self.hit: object | None = None

    def setCurrentImageID(self, image_id: UUID | None) -> None:  # noqa: N802
        """Record image selection and a default-image composition."""

        self.current_id = image_id
        self.calls.append(("current", image_id))
        if image_id is None:
            self.current_composition_id = None
            return
        composition_id = uuid4()
        self.current_composition_id = composition_id
        self.compositions[composition_id] = SimpleNamespace(
            composition_id=composition_id,
            kind="default-image",
            source_image_ids=(image_id,),
            current_image_id=image_id,
            comparison=SimpleNamespace(enabled=False, source_id=None),
        )

    def currentImageID(self) -> UUID | None:  # noqa: N802
        """Return active image selection."""

        return self.current_id

    def currentCompositionID(self) -> UUID | None:  # noqa: N802
        """Return active composition ID."""

        return self.current_composition_id

    def getCompositionSnapshot(self) -> object:  # noqa: N802
        """Return a QPane-like composition snapshot."""

        return SimpleNamespace(
            compositions=self.compositions,
            order=tuple(self.compositions),
            current_composition_id=self.current_composition_id,
        )

    def composeScene(self, request: object, *, activate: bool) -> UUID:  # noqa: N802
        """Record scene composition."""

        composition_id = getattr(request, "composition_id")
        assert isinstance(composition_id, UUID)
        image_ids = tuple(layer.image_id for layer in getattr(request, "layers", ()))
        self.compositions[composition_id] = SimpleNamespace(
            composition_id=composition_id,
            kind="layered-scene",
            source_image_ids=image_ids,
            current_image_id=None,
            comparison=SimpleNamespace(enabled=False, source_id=None),
        )
        if activate:
            self.current_composition_id = composition_id
        self.calls.append(("compose", (composition_id, activate)))
        return composition_id

    def openComposition(self, composition_id: UUID) -> None:  # noqa: N802
        """Record composition activation."""

        if composition_id not in self.compositions:
            raise KeyError(composition_id)
        self.current_composition_id = composition_id
        self.calls.append(("open", composition_id))

    def removeComposition(self, composition_id: UUID) -> None:  # noqa: N802
        """Record composition removal."""

        self.calls.append(("remove", composition_id))
        self.compositions.pop(composition_id, None)

    def setComparisonImageID(self, image_id: UUID) -> None:  # noqa: N802
        """Record comparison image selection."""

        if self.current_composition_id is not None:
            entry = self.compositions.get(self.current_composition_id)
            if entry is not None:
                entry.comparison = SimpleNamespace(
                    enabled=True,
                    source_kind="catalog",
                    source_id=image_id,
                )
        self.calls.append(("compare", image_id))

    def setComparisonSplit(self, position: float, orientation: object) -> None:  # noqa: N802
        """Record comparison split."""

        self.calls.append(("split", (position, orientation)))

    def clearComparisonImage(self) -> None:  # noqa: N802
        """Record comparison clear."""

        if self.current_composition_id is not None:
            entry = self.compositions.get(self.current_composition_id)
            if entry is not None:
                entry.comparison = SimpleNamespace(
                    enabled=False,
                    source_kind=None,
                    source_id=None,
                )
        self.calls.append(("clear_compare", None))

    def sceneHitTest(self, point: object) -> object | None:  # noqa: N802
        """Return the configured scene hit."""

        self.calls.append(("hit", point))
        return self.hit


def _output_projector(
    pane: _OutputPaneDouble,
    *,
    workflow_id: str = "wf",
    route: CanvasRouteIdentity | None = None,
    image_ids: frozenset[UUID] = frozenset(),
    source_keys: frozenset[str] = frozenset(),
    scene_keys: frozenset[str] = frozenset(),
    composition_ids: frozenset[UUID] | None = None,
) -> OutputRouteProjector:
    """Return one bound Output route projector."""

    boundary = CanvasSessionBoundary()
    active_route = route or CanvasRouteIdentity.empty()
    session = bind_output_canvas_session(
        boundary,
        workflow_id=workflow_id,
        projection=_projection_for_route(active_route),
        image_metadata_lookup={},
    )
    allowed_composition_ids = (
        composition_ids
        if composition_ids is not None
        else _allowed_composition_ids(workflow_id, active_route)
    )
    projector = OutputRouteProjector(
        OutputQPaneRouteAdapter(pane),
        session_boundary=boundary,
    )
    projector.bind(
        OutputRouteScope(
            session=session,
            allowed_image_ids=image_ids,
            allowed_source_keys=source_keys,
            allowed_scene_keys=scene_keys,
            allowed_composition_ids=allowed_composition_ids,
        )
    )
    return projector


def _allowed_composition_ids(
    workflow_id: str,
    route: CanvasRouteIdentity,
) -> frozenset[UUID]:
    """Return deterministic composition IDs for host-owned test routes."""

    if route.route_kind not in {"source_grid", "scene_overview"}:
        return frozenset()
    return frozenset(
        {
            deterministic_host_composition_id(
                canvas_kind=CanvasKind.OUTPUT,
                workflow_id=workflow_id,
                route=route,
            )
        }
    )


def _projection_for_route(route: CanvasRouteIdentity) -> OutputCanvasProjection:
    """Return a minimal projection whose active route matches route."""

    if route.route_kind == "source_grid":
        source_key, scene_key = _route_source_and_scene(route)
        return OutputCanvasProjection(
            sources=(),
            active_source_key=source_key,
            active_set_index=0,
            active_uuid=None,
            set_count=0,
            active_scene_key=scene_key or None,
        )
    if route.route_kind == "scene_overview":
        _source_key, scene_key = _route_source_and_scene(route)
        return OutputCanvasProjection(
            sources=(),
            active_source_key=None,
            active_set_index=1,
            active_uuid=None,
            set_count=0,
            active_scene_key=scene_key or None,
            active_scene_overview=True,
            scene_count=2,
        )
    if route.route_kind == "output_image" and route.primary_image_id is not None:
        source_key, scene_key = _route_source_and_scene(route)
        set_index = _route_set_index(route)
        source_key = source_key or ""
        image_item = OutputCanvasImageItem(
            image_id=route.primary_image_id,
            image_meta=ImageMeta(
                workflow_name="Workflow",
                cube_name="Output",
                image_number=1,
                suffix="",
                path="",
                source_key=source_key,
                scene_key=scene_key or "",
                list_index=set_index - 1,
            ),
            set_index=set_index,
        )
        return OutputCanvasProjection(
            sources=(
                OutputCanvasSourceGroup(
                    source_key=source_key,
                    label="Output",
                    images_by_set={set_index: image_item},
                ),
            ),
            active_source_key=source_key,
            active_set_index=set_index,
            active_uuid=route.primary_image_id,
            set_count=set_index,
            active_scene_key=scene_key or None,
        )
    return OutputCanvasProjection(
        sources=(),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=0,
    )


def _route_source_and_scene(
    route: CanvasRouteIdentity,
) -> tuple[str | None, str | None]:
    """Return source and scene route fields from one route identity."""

    source_key: str | None = None
    scene_key: str | None = None
    for segment in route.route_key.split(";"):
        if segment.startswith("source:"):
            source_key = segment.removeprefix("source:")
        elif segment.startswith("scene:"):
            scene_key = segment.removeprefix("scene:")
    return source_key, scene_key


def _route_set_index(route: CanvasRouteIdentity) -> int:
    """Return set index encoded in route, defaulting to the first set."""

    for segment in route.route_key.split(";"):
        if segment.startswith("set:"):
            try:
                return int(segment.removeprefix("set:"))
            except ValueError:
                return 1
    return 1


def test_input_route_projector_rejects_foreign_image(
    caplog: LogCaptureFixture,
) -> None:
    """Input projector should reject image IDs outside the bound route scope."""

    pane = _InputPaneDouble()
    boundary = CanvasSessionBoundary()
    owned_id = uuid4()
    session = boundary.bind_input_session(
        workflow_id="wf",
        active_route=CanvasRouteIdentity(
            route_kind="input_image",
            route_key=f"image:{owned_id}",
            primary_image_id=owned_id,
        ),
    )
    projector = InputRouteProjector(
        InputQPaneRouteAdapter(pane),
        session_boundary=boundary,
    )
    projector.bind(
        InputRouteScope(session=session, allowed_image_ids=frozenset({owned_id}))
    )

    with caplog.at_level(logging.WARNING):
        accepted = projector.show_image(uuid4())

    assert accepted is False
    assert pane.calls == []
    assert "rejection_reason=foreign_image" in caplog.text
    assert "workflow_id=wf" in caplog.text
    assert "canvas_kind=input" in caplog.text


def test_input_route_projector_applies_authorized_mask_route() -> None:
    """Input projector should activate masks only for their owning image."""

    pane = _InputPaneDouble()
    boundary = CanvasSessionBoundary()
    image_id = uuid4()
    mask_id = uuid4()
    session = boundary.bind_input_session(
        workflow_id="wf",
        active_route=CanvasRouteIdentity(
            route_kind="input_image",
            route_key=f"image:{image_id};mask:{mask_id}",
            primary_image_id=image_id,
        ),
    )
    projector = InputRouteProjector(
        InputQPaneRouteAdapter(pane),
        session_boundary=boundary,
    )
    projector.bind(
        InputRouteScope(
            session=session,
            allowed_image_ids=frozenset({image_id}),
            allowed_mask_image_ids={mask_id: image_id},
        )
    )

    accepted = projector.show_mask(image_id, mask_id)

    assert accepted is True
    assert pane.current_id == image_id
    assert pane.active_mask_id == mask_id
    assert pane.calls == [("current", image_id), ("mask", mask_id)]


def test_input_route_projector_rejects_mask_for_foreign_image(
    caplog: LogCaptureFixture,
) -> None:
    """Input projector should reject masks not mapped to the requested image."""

    pane = _InputPaneDouble()
    boundary = CanvasSessionBoundary()
    image_id = uuid4()
    foreign_image_id = uuid4()
    mask_id = uuid4()
    session = boundary.bind_input_session(
        workflow_id="wf",
        active_route=CanvasRouteIdentity(
            route_kind="input_image",
            route_key=f"image:{image_id};mask:{mask_id}",
            primary_image_id=image_id,
        ),
    )
    projector = InputRouteProjector(
        InputQPaneRouteAdapter(pane),
        session_boundary=boundary,
    )
    projector.bind(
        InputRouteScope(
            session=session,
            allowed_image_ids=frozenset({image_id}),
            allowed_mask_image_ids={mask_id: foreign_image_id},
        )
    )

    with caplog.at_level(logging.WARNING):
        accepted = projector.show_mask(image_id, mask_id)

    assert accepted is False
    assert pane.calls == []
    assert "rejection_reason=foreign_mask" in caplog.text


def test_input_route_projector_rejects_current_image_without_scope(
    caplog: LogCaptureFixture,
) -> None:
    """Input event reads should fail closed when no active scope is bound."""

    pane = _InputPaneDouble()
    pane.current_id = uuid4()
    projector = InputRouteProjector(
        InputQPaneRouteAdapter(pane),
        session_boundary=CanvasSessionBoundary(),
    )

    with caplog.at_level(logging.WARNING):
        image_id = projector.current_image_id_for_event()

    assert image_id is None
    assert "rejection_reason=missing_scope" in caplog.text


def test_input_route_projector_returns_loaded_image_without_membership() -> None:
    """QPane load events should expose the fresh UUID before workflow claim."""

    pane = _InputPaneDouble()
    boundary = CanvasSessionBoundary()
    owned_id = uuid4()
    loaded_id = uuid4()
    pane.current_id = loaded_id
    session = boundary.bind_input_session(
        workflow_id="wf",
        active_route=CanvasRouteIdentity(
            route_kind="input_image",
            route_key=f"image:{owned_id}",
            primary_image_id=owned_id,
        ),
    )
    projector = InputRouteProjector(
        InputQPaneRouteAdapter(pane),
        session_boundary=boundary,
    )
    projector.bind(
        InputRouteScope(session=session, allowed_image_ids=frozenset({owned_id}))
    )

    image_id = projector.loaded_image_id_for_event()

    assert image_id == loaded_id


def test_input_route_projector_rejects_loaded_image_for_stale_session(
    caplog: LogCaptureFixture,
) -> None:
    """QPane load event UUID reads still require the active Input session."""

    pane = _InputPaneDouble()
    boundary = CanvasSessionBoundary()
    loaded_id = uuid4()
    pane.current_id = loaded_id
    stale_session = boundary.bind_input_session(
        workflow_id="wf-stale",
        active_route=CanvasRouteIdentity.empty(),
    )
    projector = InputRouteProjector(
        InputQPaneRouteAdapter(pane),
        session_boundary=boundary,
    )
    projector.bind(
        InputRouteScope(session=stale_session, allowed_image_ids=frozenset())
    )
    boundary.bind_input_session(
        workflow_id="wf-active",
        active_route=CanvasRouteIdentity.empty(),
    )

    with caplog.at_level(logging.WARNING):
        image_id = projector.loaded_image_id_for_event()

    assert image_id is None
    assert "rejection_reason=workflow_mismatch" in caplog.text


def test_output_projector_rejects_foreign_image_route(
    caplog: LogCaptureFixture,
) -> None:
    """Output image route application should reject foreign image IDs."""

    pane = _OutputPaneDouble()
    owned_id = uuid4()
    foreign_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="output_image",
        route_key=f"image:{foreign_id};scene:;source:source-a;set:1",
        primary_image_id=foreign_id,
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({owned_id}),
        source_keys=frozenset({"source-a"}),
    )

    with caplog.at_level(logging.WARNING):
        accepted = projector.apply_final_image_route(route, foreign_id)

    assert accepted is False
    assert pane.calls == []
    assert "rejection_reason=foreign_image" in caplog.text


def test_output_projector_rejects_inactive_final_image_route(
    caplog: LogCaptureFixture,
) -> None:
    """Visible image activation must use the active projection route identity."""

    pane = _OutputPaneDouble()
    image_id = uuid4()
    active_route = CanvasRouteIdentity(
        route_kind="output_image",
        route_key=f"image:{image_id};scene:scene-a;source:source-a;set:1",
        primary_image_id=image_id,
    )
    inactive_route = CanvasRouteIdentity(
        route_kind="output_image",
        route_key=f"image:{image_id}",
        primary_image_id=image_id,
    )
    projector = _output_projector(
        pane,
        route=active_route,
        image_ids=frozenset({image_id}),
        source_keys=frozenset({"source-a"}),
        scene_keys=frozenset({"scene-a"}),
    )

    with caplog.at_level(logging.WARNING):
        accepted = projector.apply_final_image_route(inactive_route, image_id)

    assert accepted is False
    assert pane.calls == []
    assert "rejection_reason=inactive_route_activation" in caplog.text


def test_output_projector_allows_session_preview_image_route() -> None:
    """Session-owned preview lanes may activate without becoming durable routes."""

    pane = _OutputPaneDouble()
    preview_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="output_image",
        route_key=f"image:{preview_id}",
        primary_image_id=preview_id,
    )
    projector = _output_projector(
        pane,
        image_ids=frozenset({preview_id}),
    )

    accepted = projector.apply_final_image_route(route, preview_id)

    assert accepted is True
    assert pane.calls[0] == ("current", preview_id)
    assert pane.calls[1][0] == "open"
    assert pane.current_id == preview_id
    assert pane.current_composition_id is not None


def test_output_projector_uses_deterministic_composition_ids() -> None:
    """Host-owned scene routes should compose with stable deterministic IDs."""

    pane = _OutputPaneDouble()
    image_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:source-a;set:0",
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({image_id}),
        source_keys=frozenset({"source-a"}),
        scene_keys=frozenset({"scene-a"}),
    )
    expected_id = projector.route_composition_id(route)
    request = SimpleNamespace(
        composition_id=None,
        title="Grid",
        layers=(SimpleNamespace(image_id=image_id),),
    )

    accepted_first = projector.apply_source_grid_route(route, request, activate=True)
    accepted_second = projector.apply_source_grid_route(route, request, activate=True)

    assert accepted_first is True
    assert accepted_second is True
    assert pane.calls == [
        ("compose", (expected_id, True)),
        ("compose", (expected_id, True)),
    ]


def test_output_projector_rejects_inactive_layered_route_activation(
    caplog: LogCaptureFixture,
) -> None:
    """Legal cached scene routes cannot become visible unless session-active."""

    pane = _OutputPaneDouble()
    image_id = uuid4()
    active_route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:source-a;set:0",
    )
    inactive_route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:source-b;set:0",
    )
    composition_ids = frozenset(
        {
            deterministic_host_composition_id(
                canvas_kind=CanvasKind.OUTPUT,
                workflow_id="wf",
                route=active_route,
            ),
            deterministic_host_composition_id(
                canvas_kind=CanvasKind.OUTPUT,
                workflow_id="wf",
                route=inactive_route,
            ),
        }
    )
    projector = _output_projector(
        pane,
        route=active_route,
        image_ids=frozenset({image_id}),
        source_keys=frozenset({"source-a", "source-b"}),
        scene_keys=frozenset({"scene-a"}),
        composition_ids=composition_ids,
    )
    request = SimpleNamespace(
        composition_id=None,
        title="Grid",
        layers=(SimpleNamespace(image_id=image_id),),
    )

    prepared = projector.apply_source_grid_route(
        inactive_route,
        request,
        activate=False,
    )
    with caplog.at_level(logging.WARNING):
        activated = projector.apply_source_grid_route(
            inactive_route,
            request,
            activate=True,
        )

    assert prepared is True
    assert activated is False
    assert pane.calls == [
        ("compose", (projector.route_composition_id(inactive_route), False))
    ]
    assert "rejection_reason=inactive_route_activation" in caplog.text


def test_output_projector_rejects_foreign_scene_layer(
    caplog: LogCaptureFixture,
) -> None:
    """Scene composition should reject layers outside the active scope."""

    pane = _OutputPaneDouble()
    route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:source-a;set:0",
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({uuid4()}),
        source_keys=frozenset({"source-a"}),
        scene_keys=frozenset({"scene-a"}),
    )
    request = SimpleNamespace(
        composition_id=None,
        title="Grid",
        layers=(SimpleNamespace(image_id=uuid4()),),
    )

    with caplog.at_level(logging.WARNING):
        accepted = projector.apply_source_grid_route(route, request, activate=True)

    assert accepted is False
    assert pane.calls == []
    assert "rejection_reason=foreign_scene_layer" in caplog.text


def test_output_projector_rejects_source_grid_with_foreign_source(
    caplog: LogCaptureFixture,
) -> None:
    """Source-grid route application should reject source keys outside scope."""

    pane = _OutputPaneDouble()
    image_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:foreign;set:0",
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({image_id}),
        source_keys=frozenset({"source-a"}),
        scene_keys=frozenset({"scene-a"}),
    )
    request = SimpleNamespace(
        composition_id=None,
        title="Grid",
        layers=(SimpleNamespace(image_id=image_id),),
    )

    with caplog.at_level(logging.WARNING):
        accepted = projector.apply_source_grid_route(route, request, activate=True)

    assert accepted is False
    assert pane.calls == []
    assert "requested_source_key=foreign" in caplog.text
    assert "rejection_reason=foreign_source_route" in caplog.text


def test_output_projector_rejects_scene_route_without_allowed_composition(
    caplog: LogCaptureFixture,
) -> None:
    """Layered routes should require the session-owned deterministic composition ID."""

    pane = _OutputPaneDouble()
    image_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="scene_overview",
        route_key="scene:scene-a",
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({image_id}),
        scene_keys=frozenset({"scene-a"}),
        composition_ids=frozenset(),
    )
    request = SimpleNamespace(
        composition_id=None,
        title="Overview",
        layers=(SimpleNamespace(image_id=image_id),),
    )

    with caplog.at_level(logging.WARNING):
        accepted = projector.apply_scene_overview_route(route, request, activate=True)

    assert accepted is False
    assert pane.calls == []
    assert "rejection_reason=foreign_composition_id" in caplog.text


def test_output_projector_bind_clears_foreign_active_composition(
    caplog: LogCaptureFixture,
) -> None:
    """Binding a new Output scope should clear active composition foreign images."""

    pane = _OutputPaneDouble()
    owned_id = uuid4()
    foreign_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:source-a;set:0",
    )
    composition_id = deterministic_host_composition_id(
        canvas_kind=CanvasKind.OUTPUT,
        workflow_id="wf",
        route=route,
    )
    pane.current_composition_id = composition_id
    pane.current_id = foreign_id
    pane.compositions[composition_id] = SimpleNamespace(
        composition_id=composition_id,
        kind="layered-scene",
        source_image_ids=(foreign_id,),
        current_image_id=None,
        comparison=SimpleNamespace(
            enabled=True,
            source_kind="catalog",
            source_id=foreign_id,
        ),
    )

    with caplog.at_level(logging.WARNING):
        _output_projector(
            pane,
            route=route,
            image_ids=frozenset({owned_id}),
            source_keys=frozenset({"source-a"}),
            scene_keys=frozenset({"scene-a"}),
        )

    assert ("clear_compare", None) not in pane.calls
    assert ("remove", composition_id) in pane.calls
    assert ("current", None) in pane.calls
    assert composition_id not in pane.compositions
    assert "rejection_reason=foreign_active_composition" in caplog.text


def test_output_projector_bind_clears_foreign_current_image_without_composition(
    caplog: LogCaptureFixture,
) -> None:
    """Binding a new Output scope should clear a foreign default image route."""

    pane = _OutputPaneDouble()
    owned_id = uuid4()
    foreign_id = uuid4()
    pane.current_id = foreign_id
    pane.current_composition_id = None

    with caplog.at_level(logging.WARNING):
        _output_projector(pane, image_ids=frozenset({owned_id}))

    assert ("clear_compare", None) in pane.calls
    assert ("current", None) in pane.calls
    assert "rejection_reason=foreign_active_image" in caplog.text


def test_output_projector_rejects_mismatched_composed_id(
    caplog: LogCaptureFixture,
) -> None:
    """Scene composition should fail closed when QPane returns a different ID."""

    pane = _OutputPaneDouble()
    image_id = uuid4()
    wrong_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:source-a;set:0",
    )

    def compose_wrong_id(request: object, *, activate: bool) -> UUID:
        _OutputPaneDouble.composeScene(pane, request, activate=activate)
        return wrong_id

    pane.composeScene = compose_wrong_id  # type: ignore[method-assign]
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({image_id}),
        source_keys=frozenset({"source-a"}),
        scene_keys=frozenset({"scene-a"}),
    )
    request = SimpleNamespace(
        composition_id=None,
        title="Grid",
        layers=(SimpleNamespace(image_id=image_id),),
    )

    with caplog.at_level(logging.WARNING):
        accepted = projector.apply_source_grid_route(route, request, activate=True)

    assert accepted is False
    assert "rejection_reason=composition_failed" in caplog.text


def test_output_projector_validates_layered_scene_with_composition_snapshot() -> None:
    """Opening a scene should validate currentCompositionID and snapshot contents."""

    pane = _OutputPaneDouble()
    image_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="scene_overview",
        route_key="scene:scene-a",
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({image_id}),
        scene_keys=frozenset({"scene-a"}),
    )
    composition_id = projector.route_composition_id(route)
    pane.compositions[composition_id] = SimpleNamespace(
        composition_id=composition_id,
        kind="layered-scene",
        source_image_ids=(image_id,),
        current_image_id=None,
        comparison=SimpleNamespace(enabled=False, source_id=None),
    )

    request = SimpleNamespace(
        composition_id=None,
        title="Overview",
        layers=(SimpleNamespace(image_id=image_id),),
    )

    assert projector.apply_scene_overview_route(route, request, activate=True) is True
    assert pane.current_composition_id == composition_id


def test_output_projector_does_not_trust_matching_current_image_for_layered_scene(
    caplog: LogCaptureFixture,
) -> None:
    """A matching currentImageID should not prove a layered scene is valid."""

    pane = _OutputPaneDouble()
    image_id = uuid4()
    foreign_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:source-a;set:0",
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({image_id}),
        source_keys=frozenset({"source-a"}),
        scene_keys=frozenset({"scene-a"}),
    )
    composition_id = projector.route_composition_id(route)
    pane.current_id = image_id
    pane.current_composition_id = composition_id
    pane.compositions[composition_id] = SimpleNamespace(
        composition_id=composition_id,
        kind="layered-scene",
        source_image_ids=(foreign_id,),
        current_image_id=None,
        comparison=SimpleNamespace(enabled=False, source_id=None),
    )

    request = SimpleNamespace(
        composition_id=None,
        title="Grid",
        layers=(SimpleNamespace(image_id=image_id),),
    )

    accepted = projector.apply_source_grid_route(route, request, activate=True)

    assert accepted is True
    assert pane.compositions[composition_id].source_image_ids == (image_id,)
    assert ("compose", (composition_id, True)) in pane.calls


def test_output_projector_rejects_scene_hit_without_composition_state(
    caplog: LogCaptureFixture,
) -> None:
    """Scene hits should require currentCompositionID and composition snapshot proof."""

    pane = _OutputPaneDouble()
    image_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:source-a;set:0",
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({image_id}),
        source_keys=frozenset({"source-a"}),
        scene_keys=frozenset({"scene-a"}),
    )
    pane.getCompositionSnapshot = lambda: None  # type: ignore[method-assign]
    pane.currentCompositionID = lambda: None  # type: ignore[method-assign]
    pane.hit = SimpleNamespace(
        image_id=image_id,
        role="final-output",
        metadata={"source_key": "source-a", "scene_key": "scene-a", "set_index": 1},
    )

    with caplog.at_level(logging.WARNING):
        validation = projector.hit_test_scene(object())

    assert validation.accepted is False
    assert validation.rejection_reason == "composition_snapshot_invalid"
    assert "rejection_reason=composition_snapshot_invalid" in caplog.text


def test_output_projector_rejects_foreign_compare_route(
    caplog: LogCaptureFixture,
) -> None:
    """Comparison application should reject source routes outside the active scope."""

    pane = _OutputPaneDouble()
    base_id = uuid4()
    comparison_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="output_image",
        route_key=f"image:{base_id};scene:;source:foreign;set:1",
        primary_image_id=base_id,
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({base_id, comparison_id}),
        source_keys=frozenset({"source-a"}),
    )

    with caplog.at_level(logging.WARNING):
        accepted = projector.apply_compare(
            route=route,
            base_image_id=base_id,
            comparison_image_id=comparison_id,
            split_position=0.25,
            orientation="vertical",
        )

    assert accepted is False
    assert pane.calls == []
    assert "rejection_reason=foreign_route" in caplog.text


def test_output_projector_applies_compare_only_for_allowed_images() -> None:
    """Comparison route application should validate both image identities."""

    pane = _OutputPaneDouble()
    base_id = uuid4()
    comparison_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="output_image",
        route_key=f"image:{base_id};scene:;source:source-a;set:1",
        primary_image_id=base_id,
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({base_id, comparison_id}),
        source_keys=frozenset({"source-a"}),
    )

    accepted = projector.apply_compare(
        route=route,
        base_image_id=base_id,
        comparison_image_id=comparison_id,
        split_position=0.25,
        orientation="vertical",
    )

    assert accepted is True
    assert ("current", base_id) in pane.calls
    assert ("compare", comparison_id) in pane.calls
    assert ("split", (0.25, "vertical")) in pane.calls


def test_output_projector_rejects_foreign_compare_image(
    caplog: LogCaptureFixture,
) -> None:
    """Comparison route application should fail closed for foreign images."""

    pane = _OutputPaneDouble()
    base_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="output_image",
        route_key=f"image:{base_id};scene:;source:source-a;set:1",
        primary_image_id=base_id,
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({base_id}),
        source_keys=frozenset({"source-a"}),
    )

    with caplog.at_level(logging.WARNING):
        accepted = projector.apply_compare(
            route=route,
            base_image_id=base_id,
            comparison_image_id=uuid4(),
            split_position=0.25,
            orientation="vertical",
        )

    assert accepted is False
    assert ("current", base_id) not in pane.calls
    assert "rejection_reason=foreign_compare_image" in caplog.text


def test_output_projector_validates_final_output_scene_hit() -> None:
    """Scene-hit validation should return typed final-output intent."""

    pane = _OutputPaneDouble()
    image_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:source-a;set:0",
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({image_id}),
        source_keys=frozenset({"source-a"}),
        scene_keys=frozenset({"scene-a"}),
    )
    composition_id = projector.route_composition_id(route)
    pane.current_composition_id = composition_id
    pane.compositions[composition_id] = SimpleNamespace(
        composition_id=composition_id,
        kind="layered-scene",
        source_image_ids=(image_id,),
        current_image_id=None,
        comparison=SimpleNamespace(enabled=False, source_id=None),
    )
    pane.hit = SimpleNamespace(
        composition_id=composition_id,
        image_id=image_id,
        role="final-output",
        metadata={
            "source_key": "source-a",
            "scene_key": "scene-a",
            "set_index": 2,
            "image_id": str(image_id),
        },
    )

    validation = projector.hit_test_scene(object())

    assert validation.accepted is True
    assert validation.kind is OutputCanvasHitKind.FINAL_OUTPUT
    assert validation.image_id == image_id
    assert validation.source_key == "source-a"
    assert validation.scene_key == "scene-a"
    assert validation.set_index == 2


def test_output_projector_rejects_foreign_scene_hit_composition(
    caplog: LogCaptureFixture,
) -> None:
    """Scene-hit validation should reject hits from foreign compositions."""

    pane = _OutputPaneDouble()
    image_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:source-a;set:0",
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({image_id}),
        source_keys=frozenset({"source-a"}),
        scene_keys=frozenset({"scene-a"}),
    )
    expected_id = projector.route_composition_id(route)
    pane.current_composition_id = expected_id
    pane.compositions[expected_id] = SimpleNamespace(
        composition_id=expected_id,
        kind="layered-scene",
        source_image_ids=(image_id,),
        current_image_id=None,
        comparison=SimpleNamespace(enabled=False, source_id=None),
    )
    pane.hit = SimpleNamespace(
        composition_id=uuid4(),
        image_id=image_id,
        role="final-output",
        metadata={"source_key": "source-a", "set_index": 1},
    )

    with caplog.at_level(logging.WARNING):
        validation = projector.hit_test_scene(object())

    assert validation.accepted is False
    assert validation.rejection_reason == "hit_composition_mismatch"
    assert "rejection_reason=hit_composition_mismatch" in caplog.text


def test_output_projector_rejects_foreign_scene_hit_image(
    caplog: LogCaptureFixture,
) -> None:
    """Scene-hit validation should reject images outside the active scope."""

    pane = _OutputPaneDouble()
    owned_id = uuid4()
    foreign_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:source-a;set:0",
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({owned_id}),
        source_keys=frozenset({"source-a"}),
        scene_keys=frozenset({"scene-a"}),
    )
    composition_id = projector.route_composition_id(route)
    pane.current_composition_id = composition_id
    pane.compositions[composition_id] = SimpleNamespace(
        composition_id=composition_id,
        kind="layered-scene",
        source_image_ids=(owned_id,),
        current_image_id=None,
        comparison=SimpleNamespace(enabled=False, source_id=None),
    )
    pane.hit = SimpleNamespace(
        composition_id=composition_id,
        image_id=foreign_id,
        role="final-output",
        metadata={"source_key": "source-a", "scene_key": "scene-a", "set_index": 1},
    )

    with caplog.at_level(logging.WARNING):
        validation = projector.hit_test_scene(object())

    assert validation.accepted is False
    assert validation.rejection_reason == "foreign_hit_image"
    assert "rejection_reason=foreign_hit_image" in caplog.text


def test_output_projector_rejects_foreign_scene_hit_source(
    caplog: LogCaptureFixture,
) -> None:
    """Scene-hit validation should reject source keys outside the active scope."""

    pane = _OutputPaneDouble()
    image_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:source-a;set:0",
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({image_id}),
        source_keys=frozenset({"source-a"}),
        scene_keys=frozenset({"scene-a"}),
    )
    composition_id = projector.route_composition_id(route)
    pane.current_composition_id = composition_id
    pane.compositions[composition_id] = SimpleNamespace(
        composition_id=composition_id,
        kind="layered-scene",
        source_image_ids=(image_id,),
        current_image_id=None,
        comparison=SimpleNamespace(enabled=False, source_id=None),
    )
    pane.hit = SimpleNamespace(
        composition_id=composition_id,
        image_id=image_id,
        role="final-output",
        metadata={"source_key": "foreign", "scene_key": "scene-a", "set_index": 1},
    )

    with caplog.at_level(logging.WARNING):
        validation = projector.hit_test_scene(object())

    assert validation.accepted is False
    assert validation.rejection_reason == "foreign_hit_source"
    assert "rejection_reason=foreign_hit_source" in caplog.text


def test_output_projector_rejects_foreign_scene_hit_scene(
    caplog: LogCaptureFixture,
) -> None:
    """Scene-hit validation should reject scene keys outside the active scope."""

    pane = _OutputPaneDouble()
    image_id = uuid4()
    route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:source-a;set:0",
    )
    projector = _output_projector(
        pane,
        route=route,
        image_ids=frozenset({image_id}),
        source_keys=frozenset({"source-a"}),
        scene_keys=frozenset({"scene-a"}),
    )
    composition_id = projector.route_composition_id(route)
    pane.current_composition_id = composition_id
    pane.compositions[composition_id] = SimpleNamespace(
        composition_id=composition_id,
        kind="layered-scene",
        source_image_ids=(image_id,),
        current_image_id=None,
        comparison=SimpleNamespace(enabled=False, source_id=None),
    )
    pane.hit = SimpleNamespace(
        composition_id=composition_id,
        image_id=image_id,
        role="final-output",
        metadata={"source_key": "source-a", "scene_key": "foreign", "set_index": 1},
    )

    with caplog.at_level(logging.WARNING):
        validation = projector.hit_test_scene(object())

    assert validation.accepted is False
    assert validation.rejection_reason == "foreign_hit_scene"
    assert "rejection_reason=foreign_hit_scene" in caplog.text
