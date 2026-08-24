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

"""Verify Input generation asset products through production shell wiring."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QColor, QImage

from substitute.application.generation import ComfyAssetStagingService
from substitute.application.generation.input_asset_staging_plan_service import (
    InputAssetStagingPlanService,
)
from substitute.application.ports.comfy_asset_stager import ComfyAssetStager
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.common import JsonObject
from substitute.domain.generation import ComfyStagedAsset
from substitute.presentation.canvas.input.input_node_preview_widget import (
    InputNodePreviewWidget,
)
from tests.support.real_input_editor.harness import (
    RealShellInputEditorHarness,
    make_source_image,
)
from tests.support.real_input_editor.generation import node_image_value


class _RecordingAssetStager(ComfyAssetStager):
    """Record exact generation product paths crossing the Comfy boundary."""

    def __init__(self) -> None:
        """Initialize an empty staging call record."""
        self.paths: list[Path] = []

    def stage_file_for_load_image(
        self,
        *,
        source_path: Path,
        target_subfolder: str,
        content_hash: str,
        node_class: str,
    ) -> ComfyStagedAsset:
        """Record one authorized source and return a deterministic execution value."""
        _ = content_hash, node_class
        self.paths.append(source_path)
        return ComfyStagedAsset(
            source_path=source_path,
            execution_value=f"{target_subfolder}/{source_path.name}",
            operation="authorized",
        )


def test_brand_new_inpaint_workflow_materializes_mask_for_long_source_name(
    tmp_path: Path,
) -> None:
    """Long legal source names must still produce a writable editable mask."""

    source_path = tmp_path / f"{'descriptive_source_' * 9}.png"
    make_source_image(source_path, QColor("cyan"), width=257, height=193)
    harness = RealShellInputEditorHarness(tmp_path)
    try:
        harness.select_image(source_path)

        mask_filename = node_image_value(harness.workflow, harness.MASK_NODE)
        mask_path = tmp_path / "projects" / "Input Editor" / "masks" / mask_filename
        assert mask_path.is_file()
        assert len(mask_path.name) <= 224
        assert harness.input_canvas.document.contains_mask(
            harness.image_id,
            harness.mask_id,
        )

        def drawn_mask_is_available() -> bool:
            """Return whether the production document has committed the brush dab."""

            exported = harness.input_canvas.document.export_mask_image(harness.mask_id)
            return (
                isinstance(exported, QImage)
                and nonzero_red_bounds(exported) is not None
            )

        harness.add_brush_dab(brush_size=80)
        harness.wait_until(drawn_mask_is_available)
        mask = harness.input_canvas.document.export_mask_image(harness.mask_id)
        assert isinstance(mask, QImage)
        content_bounds = nonzero_red_bounds(mask)
        assert content_bounds is not None
        assert abs(content_bounds.width() - content_bounds.height()) <= 1
    finally:
        harness.close()


def test_real_widgets_stage_exact_input_products_without_losing_live_preview(
    tmp_path: Path,
) -> None:
    """Real picker selection, capture, and staging must share project asset identity."""
    source_path = tmp_path / "source.png"
    make_source_image(source_path, QColor("cyan"), width=257, height=193)
    harness = RealShellInputEditorHarness(tmp_path)
    try:
        harness.select_image(source_path)
        image_preview = harness.image_picker.live_preview()
        mask_preview = harness.mask_picker.live_preview()
        assert isinstance(image_preview, InputNodePreviewWidget)
        assert isinstance(mask_preview, InputNodePreviewWidget)

        prepared = harness.prepare_generation()
        image_value = node_image_value(prepared, harness.IMAGE_NODE)
        mask_value = node_image_value(prepared, harness.MASK_NODE)
        payload: JsonObject = {
            "1": {
                "class_type": "LoadImage",
                "inputs": {"image": str(image_value)},
                "_meta": {"title": f"{harness.CUBE_ALIAS}.{harness.IMAGE_NODE}"},
            },
            "2": {
                "class_type": "LoadImageMask",
                "inputs": {"image": str(mask_value), "channel": "alpha"},
                "_meta": {"title": f"{harness.CUBE_ALIAS}.{harness.MASK_NODE}"},
            },
        }
        stager = _RecordingAssetStager()
        staging_plan = InputAssetStagingPlanService(
            InputAssetEndpointService(
                WorkflowNodeDefinitionService(harness.shell.node_definition_gateway)
            ),
            harness.shell.graph_section_service,
        )
        staged = ComfyAssetStagingService.with_projects_dir(
            stager=stager,
            projects_dir=tmp_path / "projects",
            input_asset_staging_plan_service=staging_plan,
        ).stage_payload(
            workflow_payload=payload,
            workflow_id=harness.WORKFLOW_ID,
            workflow_name="Input Editor",
            workflow=prepared,
        )

        assert staged.failures == ()
        assert stager.paths == [
            tmp_path / "projects" / "Input Editor" / image_value,
            tmp_path / "projects" / "Input Editor" / "masks" / mask_value,
        ]
        assert harness.image_picker.live_preview() is image_preview
        assert harness.mask_picker.live_preview() is mask_preview
    finally:
        harness.close()


def nonzero_red_bounds(image: QImage) -> QRect | None:
    """Return exact occupied red-channel bounds for one exported coverage image."""
    occupied = [
        QPoint(x, y)
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).red() > 0
    ]
    if not occupied:
        return None
    left = min(point.x() for point in occupied)
    top = min(point.y() for point in occupied)
    right = max(point.x() for point in occupied)
    bottom = max(point.y() for point in occupied)
    return QRect(left, top, right - left + 1, bottom - top + 1)
