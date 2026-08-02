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

"""Exercise the mounted inpaint image, mask, activation, and brush workflow."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication
from cutecanvas import CuteCanvas

from substitute.application.workflows import (
    CanvasIoService,
    InputCanvasPlanService,
    InputCanvasStateService,
    WorkflowAssetService,
    WorkflowInputCanvasService,
)
from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.infrastructure.persistence import QtImageStore
from substitute.presentation.canvas.input.input_canvas_presenter import (
    InputCanvasPresenter,
)
from substitute.presentation.canvas.input.input_document import InputCanvasDocument
from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
    create_input_canvas_tool_system,
)
from substitute.presentation.canvas.input.input_canvas_tool_controller import (
    InputCanvasToolController,
)
from substitute.presentation.canvas.input.input_route_projector import (
    InputRouteProjector,
)


class _DefinitionGateway:
    """Provide exact inpaint-node definitions without a live Comfy connection."""

    def __init__(self, definitions: Mapping[str, JsonObject]) -> None:
        """Store definitions by class type."""

        self._definitions = definitions

    def get_node_definition(self, node_class: str) -> JsonObject:
        """Return one available definition."""

        return self._definitions.get(node_class, {})

    def get_required_node_definition(self, node_class: str) -> JsonObject:
        """Return one required definition."""

        return self.get_node_definition(node_class)


class _EditorPanel:
    """Record authoritative mask-picker refreshes."""

    def __init__(self) -> None:
        """Initialize the refresh record."""

        self.refreshes: list[tuple[str, str, str]] = []

    def refresh_mask_picker(
        self,
        cube_alias: str,
        node_name: str,
        new_path: str,
    ) -> None:
        """Record one refreshed mask thumbnail."""

        self.refreshes.append((cube_alias, node_name, new_path))


class _CanvasHost:
    """Record the canvas selected by presentation intent."""

    def __init__(self, input_canvas: object) -> None:
        """Store the Input canvas used by the integration fixture."""

        self.input_canvas = input_canvas
        self.focused: list[str] = []

    def focus_attached_canvas(self, label: str) -> None:
        """Record one requested canvas focus."""

        self.focused.append(label)


def _app() -> QApplication:
    """Return a QApplication for the mounted CuteCanvas integration."""

    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def _inpaint_workflow() -> WorkflowState:
    """Build the graph shape used by the SDXL inpaint cube."""

    graph: JsonObject = {
        "nodes": {
            "load_image": {
                "class_type": "LoadImage",
                "inputs": {},
            },
            "load_image_as_mask": {
                "class_type": "LoadImageMask",
                "inputs": {"channel": "alpha"},
            },
            "inpaint_with_mask": {
                "class_type": "InpaintWithMask",
                "inputs": {
                    "pixels": ["load_image", 0],
                    "mask": ["load_image_as_mask", 0],
                },
            },
        }
    }
    workflow = WorkflowState(
        cubes={
            "SDXL/Inpaint": CubeState(
                cube_id="Artificial-Sweetener/Base-Cubes/SDXL/Inpaint.cube",
                version="1.1.0",
                alias="SDXL/Inpaint",
                original_cube=graph,
                buffer=graph,
            )
        },
        stack_order=["SDXL/Inpaint"],
    )
    return workflow


def _plan_service() -> InputCanvasPlanService:
    """Build the graph-semantic plan service for the inpaint fixture."""

    definitions: dict[str, JsonObject] = {
        "LoadImage": {
            "input": {"required": {"image": [["input.png"], {"image_upload": True}]}},
            "output": ["IMAGE", "MASK"],
        },
        "LoadImageMask": {
            "input": {
                "required": {
                    "image": [["mask.png"], {"image_upload": True}],
                    "channel": [["alpha", "red"], {}],
                }
            },
            "output": ["MASK"],
        },
        "InpaintWithMask": {
            "input": {
                "required": {
                    "pixels": ["IMAGE", {}],
                    "mask": ["MASK", {}],
                }
            },
            "output": ["IMAGE"],
        },
    }
    definition_service = WorkflowNodeDefinitionService(_DefinitionGateway(definitions))
    return InputCanvasPlanService(
        node_definition_service=definition_service,
        endpoint_service=InputAssetEndpointService(definition_service),
    )


def test_image_selection_creates_blank_mask_and_mask_click_activates_brush(
    tmp_path: Path,
) -> None:
    """The production inpaint path should create and activate an editable mask."""

    app = _app()
    image_path = tmp_path / "source.png"
    image = QImage(83, 61, QImage.Format.Format_ARGB32)
    image.fill(QColor("magenta"))
    assert image.save(str(image_path))

    workflow_id = "workflow-inpaint"
    workflow_name = "Inpaint Recipe"
    workflow = _inpaint_workflow()
    document = InputCanvasDocument(features=("mask",))
    boundary = create_canvas_session_boundary()
    route_projector = InputRouteProjector(document, session_boundary=boundary)
    state_service = InputCanvasStateService(
        input_document=document,
        input_route_projector=route_projector,
        canvas_session_boundary=boundary,
    )
    graph_section_service = WorkflowGraphSectionService()
    asset_service = WorkflowAssetService(graph_section_service)
    workflow_service = WorkflowInputCanvasService(
        input_canvas_plan_service=_plan_service(),
        input_canvas_state_service=state_service,
        canvas_io_service=CanvasIoService(image_repository=QtImageStore()),
        workflow_asset_service=asset_service,
        graph_section_service=graph_section_service,
    )
    panel = _EditorPanel()
    canvas_host = _CanvasHost(document.canvas)
    runtime = create_input_canvas_tool_system()
    tool_controller = InputCanvasToolController(
        input_document=document,
        operation_setter=document.set_canvas_operation,
        current_image_id_provider=route_projector.current_image_id_for_event,
        runtime=runtime,
    )
    presenter = InputCanvasPresenter(
        input_document=document,
        current_image_id_provider=route_projector.current_image_id_for_event,
        active_workflow_provider=lambda: workflow,
        active_editor_panel_provider=lambda: panel,
        workflow_session_service=cast(
            Any,
            SimpleNamespace(
                active_workflow_id=workflow_id,
                workflows={workflow_id: workflow},
            ),
        ),
        workflow_input_canvas_service=workflow_service,
        input_canvas_state_service=state_service,
        canvas_host_provider=cast(Callable[[], Any], lambda: canvas_host),
        workflow_name_provider=lambda _workflow_id: workflow_name,
        projects_dir_provider=lambda: tmp_path,
        mask_color_provider=lambda _index, _total: QColor("red"),
        tool_controller=tool_controller,
    )

    presenter.handle_input_image_changed(
        "SDXL/Inpaint",
        "load_image",
        str(image_path),
    )
    app.processEvents()

    image_id = workflow.canvas.input_key_map["SDXL/Inpaint:load_image"]
    mask_id = workflow.canvas.mask_associations[("SDXL/Inpaint", "load_image_as_mask")]
    mask_path = asset_service.resolve_input_mask_path(
        workflow,
        workflow_name=workflow_name,
        section_key="SDXL/Inpaint",
        node_name="load_image_as_mask",
        field_key="image",
        projects_dir=tmp_path,
    )
    assert mask_path is not None and mask_path.exists()
    persisted_mask = QImage(str(mask_path))
    assert persisted_mask.size() == image.size()
    assert {
        persisted_mask.pixelColor(x, y).rgba()
        for y in range(persisted_mask.height())
        for x in range(persisted_mask.width())
    } == {0}
    assert document.image_has_masks(image_id)
    assert document.canvas.activeMaskID() == mask_id

    document.set_canvas_operation(CuteCanvas.CONTROL_MODE_PANZOOM)
    presenter.handle_input_mask_clicked(
        "SDXL/Inpaint",
        "load_image_as_mask",
        str(mask_path),
    )
    app.processEvents()

    assert document.current_image_id() == image_id
    assert document.canvas.activeMaskID() == mask_id
    assert route_projector.current_image_id_for_event() == image_id
    tool_controller.refresh_tool_context()
    brush = tool_controller.palette.presentation_for(InputCanvasToolId.BRUSH)
    assert brush is not None and brush.enabled is True
    assert document.canvas.getControlMode() == document.canvas.CONTROL_MODE_DRAW_BRUSH
    assert canvas_host.focused == ["Input"]
    assert panel.refreshes
