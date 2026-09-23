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

"""Verify direct Input image, mask, and picker presentation behavior."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from PySide6.QtGui import QColor
from cutecanvas import CuteCanvas
from substitute.application.errors import ErrorReport
from substitute.domain.workflow import WorkflowCanvasState
from substitute.presentation.canvas.input.input_image_materialization_presenter import (
    InputImageMaterializationPresenter,
)
from substitute.presentation.canvas.input.input_mask_picker_presenter import (
    InputMaskPickerPresenter,
)
from substitute.presentation.canvas.input.input_mask_selection_presenter import (
    InputMaskSelectionPresenter,
)
from substitute.presentation.canvas.input.input_materialization_presenter import (
    InputMaterializationPresenter,
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
    presenters = _presenters(
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

    assert presenters.images.materialize_selection(
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
    presenters = _presenters(
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

    presenters.masks.apply_selection("CubeA", "MaskNode", str(selected_path))

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
    presenters = _presenters(workflow=workflow, panel=panel, asset_path=asset_path)

    assert presenters.pickers.refresh("CubeA", "MaskNode") is True
    assert panel.refreshes == [("CubeA", "MaskNode", str(asset_path))]


@pytest.mark.parametrize(
    ("rejection_reason", "selected_dimensions", "required_dimensions"),
    [
        ("dimension_mismatch", (512, 768), (1024, 1024)),
        ("unverified_dimensions", None, (1024, 1024)),
        ("dimension_mismatch", None, (1024, 1024)),
    ],
)
def test_presenter_reports_rejected_mask_dimensions_without_projection(
    tmp_path: Path,
    rejection_reason: str,
    selected_dimensions: tuple[int, int] | None,
    required_dimensions: tuple[int, int] | None,
) -> None:
    """Dimension rejection should report context without refreshing the picker."""

    workflow = _workflow(image_id=uuid4(), mask_id=uuid4())
    panel = _Panel()
    reports: list[ErrorReport] = []
    changed: list[str] = []
    presenters = _presenters(
        workflow=workflow,
        panel=panel,
        asset_path=tmp_path / "asset.png",
        workflow_input_canvas_service=SimpleNamespace(
            apply_user_selected_input_mask=lambda **_kwargs: SimpleNamespace(
                applied=False,
                rejection_reason=rejection_reason,
                selected_dimensions=selected_dimensions,
                required_dimensions=required_dimensions,
                materialization_result=None,
            )
        ),
        error_presenter=SimpleNamespace(show_error_report=reports.append),
        mark_canvas_changed=changed.append,
    )

    accepted = presenters.masks.apply_selection(
        "CubeA",
        "MaskNode",
        str(tmp_path / "selected.png"),
    )

    assert accepted is False
    assert panel.refreshes == []
    assert changed == []
    assert len(reports) == 1
    report = reports[0]
    assert report.stage == "input_mask"
    assert report.workflow_id == "wf-a"
    assert report.operation_context is not None
    assert report.operation_context.operation == "load_input_mask"
    assert report.operation_context.cube_alias == "CubeA"
    assert report.operation_context.node_name == "MaskNode"


def test_presenter_skips_unresolved_loaded_image_identity(tmp_path: Path) -> None:
    """An unresolved document image should not enter graph reconciliation."""

    workflow = _workflow(image_id=uuid4(), mask_id=uuid4())
    reconciliations: list[dict[str, object]] = []
    changed: list[str] = []
    presenters = _presenters(
        workflow=workflow,
        panel=_Panel(),
        asset_path=tmp_path / "asset.png",
        workflow_input_canvas_service=SimpleNamespace(
            resolve_loaded_input_canvas_image_identity=lambda *_args: SimpleNamespace(
                accepted=False,
                input_key=None,
                rejection_reason="unmapped_image_id",
            ),
            reconcile_loaded_input_canvas_image=lambda **kwargs: reconciliations.append(
                kwargs
            ),
        ),
        mark_canvas_changed=changed.append,
    )

    presenters.images.handle_loaded_image(uuid4(), str(tmp_path / "loaded.png"))

    assert reconciliations == []
    assert changed == []


def test_image_presenter_materializes_active_loaded_section(tmp_path: Path) -> None:
    """Loaded-section presentation should project results and mark state changed."""

    workflow = _workflow(image_id=uuid4(), mask_id=uuid4())
    materializations: list[dict[str, object]] = []
    changed: list[str] = []
    result = SimpleNamespace(mask_results=(), first_mask_id=None)

    def materialize_loaded_section(**kwargs: object) -> tuple[object, ...]:
        """Record loaded-section application input and return one result."""

        materializations.append(kwargs)
        return (result,)

    presenters = _presenters(
        workflow=workflow,
        panel=_Panel(),
        asset_path=tmp_path / "asset.png",
        workflow_input_canvas_service=SimpleNamespace(
            materialize_loaded_section=materialize_loaded_section,
        ),
        mark_canvas_changed=changed.append,
    )

    presenters.images.materialize_loaded_section("wf-a", "CubeA")

    assert materializations[0]["workflow_id"] == "wf-a"
    assert materializations[0]["section_key"] == "CubeA"
    assert changed == ["wf-a"]


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


@dataclass(frozen=True)
class _Presenters:
    """Hold the three direct Input presentation owners under test."""

    images: InputImageMaterializationPresenter
    masks: InputMaskSelectionPresenter
    pickers: InputMaskPickerPresenter


def _presenters(
    *,
    workflow: SimpleNamespace,
    panel: _Panel,
    document: Any | None = None,
    asset_path: Path | None = None,
    current_image_id_provider: Callable[[], UUID | None] | None = None,
    input_canvas_state_service: Any | None = None,
    workflow_input_canvas_service: Any | None = None,
    error_presenter: Any | None = None,
    mark_canvas_changed: Callable[[str], None] | None = None,
) -> _Presenters:
    """Build the direct Input presentation owners with focused collaborators."""

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
    session = SimpleNamespace(
        active_workflow_id="wf-a",
        workflows={"wf-a": workflow},
    )
    pickers = InputMaskPickerPresenter(
        active_workflow=lambda: cast(Any, workflow),
        active_panel=lambda: panel,
        workflow_session=session,
        workflow_inputs=cast(Any, workflow_input_canvas_service),
        workflow_name=lambda _workflow_id: "Recipe",
        projects_dir=lambda: asset_path.parent,
    )
    regional_masks = RegionalMaskCollectionPresenter(
        input_document=document,
        active_panel=lambda: panel,
        mask_color=lambda index, total: QColor(index, total, 0),
    )
    materialization = InputMaterializationPresenter(
        input_document=document,
        active_workflow=lambda: cast(Any, workflow),
        active_panel=lambda: panel,
        mask_color=lambda index, total: f"color-{index}/{total}",
        refresh_scalar_mask=lambda cube_alias, node_name, projects_dir: pickers.refresh(
            cube_alias,
            node_name,
            projects_dir=projects_dir,
        ),
        refresh_ordered_mask=regional_masks.refresh,
        activate_mask=lambda active_workflow, mask_id: (
            input_canvas_state_service.set_active_workflow_mask(
                "wf-a",
                active_workflow,
                mask_id,
            )
        ),
    )
    return _Presenters(
        images=InputImageMaterializationPresenter(
            current_image_id=current_image_id_provider or (lambda: None),
            active_workflow=lambda: cast(Any, workflow),
            active_panel=lambda: panel,
            workflow_session=session,
            workflow_inputs=cast(Any, workflow_input_canvas_service),
            input_state=cast(Any, input_canvas_state_service),
            workflow_name=lambda _workflow_id: "Recipe",
            projects_dir=lambda: asset_path.parent,
            materialization=materialization,
            mark_changed=mark_canvas_changed,
        ),
        masks=InputMaskSelectionPresenter(
            active_workflow=lambda: cast(Any, workflow),
            workflow_session=session,
            workflow_inputs=cast(Any, workflow_input_canvas_service),
            workflow_name=lambda _workflow_id: "Recipe",
            projects_dir=lambda: asset_path.parent,
            materialization=materialization,
            mask_pickers=pickers,
            mark_changed=mark_canvas_changed,
            error_presenter=error_presenter,
        ),
        pickers=pickers,
    )
