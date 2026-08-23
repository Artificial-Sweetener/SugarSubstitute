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

"""Drive the complete Input editor slice through the real shell scaffold."""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch
from uuid import UUID

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from cutecanvas import PixelSelectionMode, VectorShapeKind

from substitute.application.workflows import (
    CanvasIoService,
    InputCanvasPlanService,
    WorkflowAssetService,
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
from substitute.presentation.canvas.input.input_canvas_view import InputCanvas
from substitute.presentation.editor.panel.widgets.fields.load_image import ImagePicker
from substitute.presentation.editor.panel.widgets.fields.load_mask import MaskPicker
from substitute.presentation.shell.input_canvas_composition import (
    compose_input_canvas_controllers,
)
from substitute.presentation.shell.main_window_dependencies import (
    InstallationPathBundle,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


class RealShellInputEditorHarness:
    """Mount one inpaint workflow through production shell Input composition."""

    WORKFLOW_ID = "workflow-input-editor"
    CUBE_ALIAS = "SDXL/Inpaint"
    IMAGE_NODE = "load_image"
    MASK_NODE = "load_image_as_mask"

    def __init__(
        self,
        root: Path,
        *,
        workflow: WorkflowState | None = None,
    ) -> None:
        """Build a deterministic shell, project boundary, and inpaint editor panel."""
        self.root = Path(root)
        self._closed = False
        with patch.dict(
            "os.environ",
            {
                "SUGAR_SUBSTITUTE_STARTUP_HARNESS": "1",
                "SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM": "1",
            },
        ):
            self._base = PromptEditorRealShellScenario(
                artifact_root=self.root / "prompt-editor-artifacts"
            )
        self.shell = cast(Any, self._base.shell)
        self.shell.path_bundle = self._path_bundle(self.root)
        self.shell.node_definition_gateway.install_recorded_definitions(
            self._node_definitions()
        )
        definition_service = WorkflowNodeDefinitionService(
            self.shell.node_definition_gateway
        )
        self.shell.input_asset_endpoint_service = InputAssetEndpointService(
            definition_service
        )
        self.shell.input_canvas_plan_service = InputCanvasPlanService(
            node_definition_service=definition_service,
            endpoint_service=self.shell.input_asset_endpoint_service,
        )
        self.shell.graph_section_service = WorkflowGraphSectionService()
        self.shell.workflow_asset_service = WorkflowAssetService(
            self.shell.graph_section_service
        )
        self.shell.canvas_io_service = CanvasIoService(image_repository=QtImageStore())
        compose_input_canvas_controllers(self.shell)
        self.workflow = workflow or self._workflow()
        self._mount_workflow(self.workflow)

    @property
    def input_canvas(self) -> InputCanvas:
        """Return the production Input canvas mounted by the shell."""
        return cast(InputCanvas, self.shell.canvas_host.canvas_for("Input"))

    @property
    def image_picker(self) -> ImagePicker:
        """Return the production Load Image picker."""
        return cast(ImagePicker, self._picker(ImagePicker, self.IMAGE_NODE))

    @property
    def mask_picker(self) -> MaskPicker:
        """Return the production Load Image Mask picker."""
        return cast(MaskPicker, self._picker(MaskPicker, self.MASK_NODE))

    @property
    def image_id(self) -> UUID:
        """Return the workflow's authoritative Input image identity."""
        entry = self.workflow.canvas.image_entry(f"{self.CUBE_ALIAS}:{self.IMAGE_NODE}")
        if entry is None:
            raise RuntimeError("Production workflow has no Input image entry")
        return entry.image_id

    @property
    def mask_id(self) -> UUID:
        """Return the workflow's authoritative Input mask identity."""
        entry = self.workflow.canvas.mask_entry((self.CUBE_ALIAS, self.MASK_NODE))
        if entry is None:
            raise RuntimeError("Production workflow has no Input mask entry")
        return entry.mask_id

    def select_image(self, path: Path) -> None:
        """Route one selected image through the production picker signals."""
        self.select_image_for(self.CUBE_ALIAS, path)

    def select_image_for(self, cube_alias: str, path: Path) -> None:
        """Route one graph-identified image through production picker signals."""

        picker = cast(
            ImagePicker, self.picker(ImagePicker, cube_alias, self.IMAGE_NODE)
        )
        picker.set_thumbnail(str(path))
        picker.imageSelected.emit(str(path))
        self.process_events(8)

    def picker(
        self,
        picker_type: type[Any],
        cube_alias: str,
        node_name: str,
    ) -> Any:
        """Return one production picker by exact graph identity."""

        picker = self._find_picker(picker_type, node_name, cube_alias=cube_alias)
        if picker is not None:
            return picker
        panel = self.shell.editor_panels[self.WORKFLOW_ID]
        panel.reveal_loaded_cube(cube_alias)
        self.process_events(10)
        self.wait_until(
            lambda: (
                self._find_picker(
                    picker_type,
                    node_name,
                    cube_alias=cube_alias,
                )
                is not None
            )
        )
        picker = self._find_picker(picker_type, node_name, cube_alias=cube_alias)
        if picker is not None:
            return picker
        raise RuntimeError(
            f"Production editor panel did not mount {cube_alias}:{node_name}"
        )

    def add_rectangle(self, bounds: QRectF) -> None:
        """Commit one retained mask shape through CuteCanvas's public facade."""
        assert self.input_canvas.document.set_active_mask_id(self.mask_id)
        item_id = self.input_canvas.document.canvas.addCoverageShape(
            VectorShapeKind.RECTANGLE,
            bounds,
            PixelSelectionMode.ADD,
        )
        if item_id is None:
            raise RuntimeError("Production Input canvas rejected retained rectangle")
        self.process_events(12)

    def add_brush_dab(self, point: QPoint, *, brush_size: int) -> None:
        """Commit one brush dab after the mounted canvas receives its press delivery."""

        input_canvas = self.input_canvas
        input_canvas.resize(400, 300)
        input_canvas.show()
        assert input_canvas.document.set_active_mask_id(self.mask_id)
        input_canvas.canvas.setBrushSize(brush_size)
        input_canvas.canvas.setControlMode(input_canvas.canvas.CONTROL_MODE_DRAW_BRUSH)
        self.wait_until(
            lambda: (
                input_canvas.canvas.isVisible()
                and input_canvas.canvas.isEnabled()
                and input_canvas.canvas.size() == input_canvas.size()
                and input_canvas.canvas.rect().contains(point)
                and input_canvas.canvas.getControlMode()
                == input_canvas.canvas.CONTROL_MODE_DRAW_BRUSH
            )
        )
        QTest.mousePress(
            input_canvas.canvas,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            point,
        )
        self.process_events()
        QTest.mouseRelease(
            input_canvas.canvas,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            point,
        )

    def prepare_generation(self) -> WorkflowState:
        """Capture and materialize one execution-only workflow revision."""
        prepared = self.shell.input_generation_snapshot_service.prepare_workflow(
            workflow_id=self.WORKFLOW_ID,
            workflow=self.workflow,
        )
        if not isinstance(prepared, WorkflowState):
            raise RuntimeError("Production generation barrier rejected Input products")
        return prepared

    def save_editable_document(self) -> Path:
        """Persist the complete editable Input document through shell lifecycle."""
        lifecycle = self.shell.input_editable_document_lifecycle
        lifecycle.prepare_session_persistence().persist()
        if not lifecycle.archive_path.is_file():
            raise RuntimeError(
                "Production Input document persistence produced no archive"
            )
        return cast(Path, lifecycle.archive_path)

    def process_events(self, cycles: int = 4) -> None:
        """Drain bounded queued shell and renderer work."""
        _ = cycles
        self._base.wait_for_queued_delivery()

    def wait_until(self, predicate: Callable[[], bool]) -> None:
        """Wait for one observable production-shell condition with a bound."""
        self._base.wait_until(predicate)

    def close(self) -> None:
        """Release every real shell widget and document runtime."""

        if self._closed:
            return
        self._closed = True
        input_document = self.input_canvas.document
        output_document = self.shell.output_canvas.document
        input_document.close()
        output_document.close()
        self._base.close()

    def _mount_workflow(self, workflow: WorkflowState) -> None:
        """Install one workflow and its real editor-panel surface."""
        self.shell.workflow_session_service.replace_workflows(
            {self.WORKFLOW_ID: workflow},
            active_workflow_id=self.WORKFLOW_ID,
        )
        self.shell.workflow_tabbar.addTab(self.WORKFLOW_ID, "Input Editor")
        self.shell.install_workflow_surface(self.WORKFLOW_ID)
        panel = self.shell.editor_panels[self.WORKFLOW_ID]
        panel.load_all_cubes(
            [
                (cube_alias, workflow.cubes[cube_alias])
                for cube_alias in workflow.stack_order
            ],
            cube_states=workflow.cubes,
            stack_order=list(workflow.stack_order),
        )
        self.shell.editor_panel_container.setCurrentWidget(panel)
        self.shell.editor_panel = panel
        panel.show()
        panel.reveal_loaded_cube(self.CUBE_ALIAS)
        self.process_events(10)
        self._base.wait_until(
            lambda: (
                self._find_picker(ImagePicker, self.IMAGE_NODE) is not None
                and self._find_picker(MaskPicker, self.MASK_NODE) is not None
            ),
        )

    def _picker(self, picker_type: type[Any], node_name: str) -> Any:
        """Resolve one picker by its production graph metadata."""
        picker = self._find_picker(picker_type, node_name)
        if picker is not None:
            return picker
        raise RuntimeError(f"Production editor panel did not mount {node_name}")

    def _find_picker(
        self,
        picker_type: type[Any],
        node_name: str,
        *,
        cube_alias: str | None = None,
    ) -> Any | None:
        """Find one picker without introducing a timing assertion."""
        panel = cast(QWidget, self.shell.active_editor_panel)
        for picker in panel.findChildren(picker_type):
            metadata = picker.property("input_metadata")
            if (
                isinstance(metadata, dict)
                and metadata.get("cube_alias") == (cube_alias or self.CUBE_ALIAS)
                and metadata.get("node_name") == node_name
            ):
                return picker
        return None

    @staticmethod
    def _workflow() -> WorkflowState:
        """Build the graph shape used by the Input editor abuse fixture."""
        graph: JsonObject = {
            "nodes": {
                "load_image": {
                    "class_type": "LoadImage",
                    "_meta": {"title": "Load Image"},
                    "inputs": {"image": ""},
                },
                "load_image_as_mask": {
                    "class_type": "LoadImageMask",
                    "_meta": {"title": "Load Image as Mask"},
                    "inputs": {"image": "", "channel": "alpha"},
                },
                "inpaint_with_mask": {
                    "class_type": "InpaintWithMask",
                    "_meta": {"title": "Inpaint"},
                    "inputs": {
                        "pixels": ["load_image", 0],
                        "mask": ["load_image_as_mask", 0],
                    },
                },
            }
        }
        cube = CubeState(
            cube_id="InputEditorHarness.cube",
            version="1.0",
            alias=RealShellInputEditorHarness.CUBE_ALIAS,
            original_cube=copy.deepcopy(graph),
            buffer=copy.deepcopy(graph),
        )
        return WorkflowState(
            cubes={RealShellInputEditorHarness.CUBE_ALIAS: cube},
            stack_order=[RealShellInputEditorHarness.CUBE_ALIAS],
            metadata={"name": "Input Editor"},
        )

    @staticmethod
    def two_pair_workflow() -> WorkflowState:
        """Build two independent image/mask graph pairs for routing tests."""

        workflow = RealShellInputEditorHarness._workflow()
        second_alias = "Face/Inpaint"
        first_cube = workflow.cubes[RealShellInputEditorHarness.CUBE_ALIAS]
        workflow.cubes[second_alias] = CubeState(
            cube_id="InputEditorHarness.second-cube",
            version="1.0",
            alias=second_alias,
            original_cube=copy.deepcopy(first_cube.original_cube),
            buffer=copy.deepcopy(first_cube.buffer),
        )
        workflow.stack_order.append(second_alias)
        return workflow

    @staticmethod
    def _node_definitions() -> dict[str, dict[str, object]]:
        """Return deterministic Comfy definitions for Input graph semantics."""
        return {
            "LoadImage": {
                "input": {
                    "required": {"image": [["input.png"], {"image_upload": True}]}
                },
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

    @staticmethod
    def _path_bundle(root: Path) -> InstallationPathBundle:
        """Build isolated project paths for one harness lifetime."""
        return InstallationPathBundle(
            install_root=root,
            user_dir=root / "user",
            projects_dir=root / "projects",
            outputs_dir=root / "outputs",
            sugar_scripts_dir=root / "scripts",
            wildcards_dir=root / "wildcards",
            managed_comfy_dir=root / "comfy",
            session_dir=root / "session",
        )


def make_source_image(path: Path, color: QColor, *, width: int, height: int) -> QImage:
    """Create one deterministic opaque source image for harness use."""
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    if not image.save(str(path)):
        raise RuntimeError(f"Could not create Input harness image at {path}")
    return image


__all__ = ["RealShellInputEditorHarness", "make_source_image"]
