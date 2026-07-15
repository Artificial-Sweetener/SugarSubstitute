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

"""Verify Output core and grid composition helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_canvas_session import (
    bind_output_canvas_session,
)
from substitute.application.workflows.canvas_route_projector_port import (
    OutputRouteProjectorPort,
    create_canvas_session_boundary,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewAcceptance,
    OutputPreviewLane,
    OutputPreviewLaneKey,
    OutputPreviewRegistry,
)
from substitute.presentation.canvas.output.composition.assets import (
    output_canvas_asset_lookup,
)
from substitute.presentation.canvas.output.composition.compare import (
    output_compare_material_gap_overlay,
    output_compare_presenter,
)
from substitute.presentation.canvas.output.composition.grid import (
    output_source_grid_composer,
    output_scene_overview_composer,
)
from substitute.presentation.canvas.output.composition.preview import (
    output_preview_controller_for_host,
)
from substitute.presentation.canvas.output.composition.qpane import (
    output_qpane_catalog,
    output_qpane_presenter,
    output_route_projector_for,
    output_route_presenter,
)
from substitute.presentation.canvas.output.output_compare_presenter import (
    OutputComparePresenter,
)
from substitute.presentation.canvas.output.output_compare_material_gap import (
    OutputCompareMaterialGapOverlay,
)
from substitute.presentation.canvas.output.output_canvas_asset_lookup import (
    OutputCanvasAssetLookup,
)
from substitute.presentation.canvas.output.output_canvas_route_presenter import (
    OutputCanvasRoutePresenter,
)
from substitute.presentation.canvas.output.output_source_grid_composer import (
    OutputSourceGridComposer,
)
from substitute.presentation.canvas.output.output_grid_scene_builder import (
    OutputGridSceneBuilder,
)
from substitute.presentation.canvas.shared.responsive_canvas_grid_policy import (
    CanvasViewportExtent,
)
from substitute.presentation.canvas.output.output_scene_overview_composer import (
    OutputSceneOverviewComposer,
)
from substitute.presentation.canvas.qpane.canvas_pane_catalog import CanvasPaneCatalog
from substitute.presentation.canvas.qpane.canvas_route_projector import (
    OutputRouteProjector,
)
from substitute.presentation.canvas.qpane.output_qpane_presenter import (
    OutputCanvasQPanePresenter,
)
from substitute.domain.workflow import CanvasSessionBoundary
from tests.support.output_canvas.composition_fakes import (
    _Catalog,
    _OverlayPane,
    _PreviewPresenter,
    _Registrar,
)


def test_output_canvas_composition_imports_no_qt_host_modules() -> None:
    """Output canvas composition should stay portable across Qt bindings."""

    composition_root = Path("substitute/presentation/canvas/output/composition")
    source = "\n".join(
        module.read_text(encoding="utf-8")
        for module in composition_root.glob("*.py")
        if "runtime" not in module.name and not module.name.startswith("qt_")
    )

    assert "PySide6" not in source
    assert "qfluentwidgets" not in source
    assert "qframelesswindow" not in source


def test_output_canvas_composition_builds_route_composers() -> None:
    """Composition helpers should build cached route composers for the widget."""

    payload = object()
    image_id = uuid4()

    grid_composer = output_source_grid_composer(
        lambda requested_id: payload if requested_id == image_id else None,
        scene_builder=OutputGridSceneBuilder(),
        viewport_extent=lambda: CanvasViewportExtent(1000.0, 1000.0),
    )
    overview_composer = output_scene_overview_composer(
        payload_lookup=lambda requested_id: (
            payload if requested_id == image_id else None
        ),
        preview_lookup=lambda _scene: None,
        scene_builder=OutputGridSceneBuilder(),
        viewport_extent=lambda: CanvasViewportExtent(1000.0, 1000.0),
    )

    assert isinstance(grid_composer, OutputSourceGridComposer)
    assert isinstance(overview_composer, OutputSceneOverviewComposer)


def test_output_canvas_composition_builds_asset_lookup() -> None:
    """Composition helper should wire final-output and preview asset callbacks."""

    image_id = uuid4()
    payload = object()
    preview_payload = object()

    lookup = output_canvas_asset_lookup(
        payload_lookup=lambda requested_id: (
            payload if requested_id == image_id else None
        ),
        metadata_lookup=None,
        preview_image_cache=lambda: {image_id: preview_payload},
    )

    assert isinstance(lookup, OutputCanvasAssetLookup)
    assert lookup.final_output_payload(image_id) is payload
    assert lookup.preview_images() == {image_id: preview_payload}


def test_output_canvas_composition_builds_compare_presenter() -> None:
    """Composition helper should build the compare presenter from the route port."""

    presenter = output_compare_presenter(cast(OutputRouteProjectorPort, object()))

    assert isinstance(presenter, OutputComparePresenter)


def test_output_canvas_composition_builds_compare_material_gap_overlay() -> None:
    """Composition helper should build compare gap overlay from pane callbacks."""

    pane = _OverlayPane()
    overlay = output_compare_material_gap_overlay(
        pane=pane,
        compare_enabled=lambda: False,
    )

    assert isinstance(overlay, OutputCompareMaterialGapOverlay)
    assert pane.registered_names == ("substitute-output-compare-material-gap",)


def test_output_canvas_composition_builds_qpane_collaborators() -> None:
    """Composition helpers should build QPane adapters from the host pane."""

    pane = object()
    catalog = output_qpane_catalog(pane)
    presenter = output_qpane_presenter(catalog)
    route_projector = output_route_projector_for(
        pane,
        session_boundary=create_canvas_session_boundary(),
    )

    assert isinstance(catalog, CanvasPaneCatalog)
    assert isinstance(presenter, OutputCanvasQPanePresenter)
    assert isinstance(route_projector, OutputRouteProjector)


def test_output_canvas_composition_builds_route_presenter() -> None:
    """Composition helper should build route presenter from explicit callbacks."""

    presenter = output_route_presenter(
        catalog=lambda: _Catalog(),
        image_registrar=lambda: _Registrar(),
        layer_payload=lambda _layer: None,
        layer_path=lambda _layer: None,
    )

    assert isinstance(presenter, OutputCanvasRoutePresenter)


def test_output_canvas_composition_builds_preview_controller_for_host() -> None:
    """Preview-controller composition should wire registry and host state adapters."""

    preview_id = uuid4()
    registry = OutputPreviewRegistry()
    presenter = _PreviewPresenter()
    activated: list[object] = []
    activity_marks: list[bool] = []
    session = bind_output_canvas_session(
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
    host = SimpleNamespace(
        _preview_registry=registry,
        _output_session=session,
        _qpane_presenter=presenter,
        _asset_lookup=output_canvas_asset_lookup(
            payload_lookup=None,
            metadata_lookup=None,
            preview_image_cache=lambda: {},
        ),
        scene_count=0,
        active_scene_key=None,
        active_scene_overview=False,
        _output_projection=None,
    )

    def activate_output_image(image_id: UUID) -> bool:
        """Record preview activation and report route command success."""

        activated.append(image_id)
        return True

    controller = output_preview_controller_for_host(
        host,
        asset_lookup=host._asset_lookup,
        qpane_presenter=presenter,
        output_session=lambda: session,
        set_current_output_image=activate_output_image,
        activate_scene_overview=lambda: None,
        mark_output_activity=lambda: activity_marks.append(True),
    )

    controller.apply_preview_acceptance(
        OutputPreviewAcceptance(
            accepted=True,
            lanes=(
                OutputPreviewLane(
                    key=OutputPreviewLaneKey.source(
                        workflow_id="wf",
                        generation_run_id="run-a",
                        prompt_id="prompt-a",
                        source_key="wf:source",
                    ),
                    preview_id=preview_id,
                    image=object(),
                    source_label="Source",
                    client_id="client-a",
                    session_revision=session.revision,
                ),
            ),
        )
    )

    assert presenter.registered_image_ids == (preview_id,)
    assert activated == [preview_id]
    assert activity_marks == [True]
