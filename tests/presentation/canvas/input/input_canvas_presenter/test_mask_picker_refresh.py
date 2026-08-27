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

"""Verify presenter-owned Input mask picker refresh behavior."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from PySide6.QtGui import QColor
from cutecanvas import CuteCanvas
from substitute.domain.workflow import WorkflowCanvasState
from substitute.presentation.canvas.input import (
    InputCanvasPresenter,
)
from substitute.presentation.regional.mask_collection_presenter import (
    RegionalMaskCollectionPresenter,
)


class _Panel:
    """Record mask picker refreshes and reject widget-local path reads."""

    def __init__(self) -> None:
        """Initialize empty refresh history."""

        self.refreshes: list[tuple[str, str, str]] = []

    def refresh_mask_picker(
        self, cube_alias: str, node_name: str, new_path: str
    ) -> None:
        """Record one authoritative refresh."""

        self.refreshes.append((cube_alias, node_name, new_path))

    def current_file_path(self) -> str:
        """Fail if presenter code reads widget-local path memory."""

        raise AssertionError("widget-local path memory must not be read")


def test_presenter_refreshes_materialized_picker_from_asset_state(
    tmp_path: Path,
) -> None:
    """Materialization picker refresh should ignore result-local paths."""

    image_id = uuid4()
    mask_id = uuid4()
    stale_result_path = tmp_path / "stale-widget.png"
    asset_path = tmp_path / "Recipe" / "masks" / "asset.png"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"asset")
    panel = _Panel()
    workflow = _workflow(image_id=image_id, mask_id=mask_id)
    presenter = _presenter(
        workflow=workflow,
        panel=panel,
        asset_path=asset_path,
        workflow_input_canvas_service=SimpleNamespace(
            materialize_input_image=lambda **_kwargs: SimpleNamespace(
                image_id=image_id,
                mask_results=(
                    SimpleNamespace(
                        association_key=("CubeA", "MaskNode"),
                        mask_id=mask_id,
                        resolved_path=stale_result_path,
                    ),
                ),
                first_mask_id=mask_id,
            ),
            resolve_input_mask_path=lambda *_args, **_kwargs: asset_path,
        ),
    )

    assert presenter.materialize_image_selection(
        "CubeA",
        "ImageNode",
        str(tmp_path / "chosen.png"),
    )

    assert panel.refreshes == [("CubeA", "MaskNode", str(asset_path))]


def test_presenter_refreshes_user_selected_mask_from_asset_state(
    tmp_path: Path,
) -> None:
    """User-selected mask refresh should use asset state, not selected path."""

    image_id = uuid4()
    mask_id = uuid4()
    selected_path = tmp_path / "selected-but-not-authority.png"
    asset_path = tmp_path / "Recipe" / "masks" / "asset.png"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"asset")
    panel = _Panel()
    workflow = _workflow(image_id=image_id, mask_id=mask_id)
    presenter = _presenter(
        workflow=workflow,
        panel=panel,
        asset_path=asset_path,
        workflow_input_canvas_service=SimpleNamespace(
            apply_user_selected_input_mask=lambda **_kwargs: SimpleNamespace(
                applied=True,
                rejection_reason="",
                selected_dimensions=None,
                required_dimensions=None,
                materialization_result=None,
            ),
            resolve_input_mask_path=lambda *_args, **_kwargs: asset_path,
        ),
    )

    presenter.apply_mask_selection("CubeA", "MaskNode", str(selected_path))

    assert panel.refreshes == [("CubeA", "MaskNode", str(asset_path))]


def test_presenter_rejects_widget_local_path_memory_as_refresh_authority(
    tmp_path: Path,
) -> None:
    """Picker refresh should never consult widget-local current_file_path."""

    image_id = uuid4()
    mask_id = uuid4()
    asset_path = tmp_path / "Recipe" / "masks" / "asset.png"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"asset")
    panel = _Panel()
    workflow = _workflow(image_id=image_id, mask_id=mask_id)
    presenter = _presenter(workflow=workflow, panel=panel, asset_path=asset_path)

    assert presenter.refresh_mask_picker_from_asset_state("CubeA", "MaskNode") is True
    assert panel.refreshes == [("CubeA", "MaskNode", str(asset_path))]


def _workflow(*, image_id: UUID, mask_id: UUID) -> SimpleNamespace:
    """Return workflow state with one graph-bound image and mask."""

    canvas = WorkflowCanvasState()
    canvas.bind_image("CubeA:ImageNode", image_id)
    canvas.bind_mask(("CubeA", "MaskNode"), mask_id, image_id)
    return SimpleNamespace(
        canvas=canvas,
        cubes={
            "CubeA": SimpleNamespace(
                buffer={
                    "nodes": {
                        "MaskNode": {
                            "class_type": "LoadImageMask",
                            "inputs": {"image": "stale-buffer.png"},
                        }
                    }
                }
            )
        },
    )


def _presenter(
    *,
    workflow: SimpleNamespace,
    panel: _Panel,
    document: Any | None = None,
    asset_path: Path | None = None,
    current_image_id_provider: Callable[[], UUID | None] | None = None,
    input_canvas_state_service: Any | None = None,
    workflow_input_canvas_service: Any | None = None,
) -> InputCanvasPresenter:
    """Build an InputCanvasPresenter with focused test collaborators."""

    document = document or SimpleNamespace(
        set_mask_properties=lambda *_args, **_kwargs: None,
        image_has_masks=lambda _image_id: False,
        active_image_has_mask_target=lambda _image_id: False,
        smart_segmentation_ready=lambda: False,
        current_canvas_operation=lambda: CuteCanvas.CONTROL_MODE_PANZOOM,
        set_canvas_operation=lambda _operation_id: True,
    )
    asset_path = asset_path or Path(__file__).resolve()
    workflow_input_canvas_service = workflow_input_canvas_service or SimpleNamespace(
        binding_for_mask=lambda *_args: SimpleNamespace(
            section_key="CubeA",
            surface_key="ImageNode",
            association_key=("CubeA", "MaskNode"),
        ),
        bindings_for_image=lambda *_args: (
            SimpleNamespace(association_key=("CubeA", "MaskNode")),
        ),
        resolve_input_mask_path=lambda *_args, **_kwargs: asset_path,
    )
    input_canvas_state_service = input_canvas_state_service or SimpleNamespace(
        set_active_input_image=lambda *_args: True,
        set_active_workflow_mask=lambda *_args: True,
        input_image_path=lambda _image_id: None,
    )
    return InputCanvasPresenter(
        input_document=document,
        current_image_id_provider=current_image_id_provider or (lambda: None),
        active_workflow_provider=lambda: cast(Any, workflow),
        active_editor_panel_provider=lambda: panel,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": workflow},
        ),
        workflow_input_canvas_service=cast(Any, workflow_input_canvas_service),
        input_canvas_state_service=cast(Any, input_canvas_state_service),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: asset_path.parent,
        mask_color_provider=lambda index, total: f"color-{index}/{total}",
        regional_mask_presenter=RegionalMaskCollectionPresenter(
            input_document=document,
            active_workflow=lambda: cast(Any, workflow),
            active_panel=lambda: panel,
            mask_color=lambda index, total: QColor(index, total, 0),
        ),
    )
