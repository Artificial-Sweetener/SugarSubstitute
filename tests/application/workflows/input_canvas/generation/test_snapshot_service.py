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

"""Prove exact image-and-mask external products at the generation barrier."""

import copy
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
from uuid import uuid4

from cutecanvas import EmbeddedImageExportSnapshot, MaskExportSnapshot
from PySide6.QtGui import QColor
import pytest

from substitute.application.workflows.generation_input_image_selection_service import (
    GenerationInputImageSelection,
)
from substitute.domain.workflow import WorkflowState
from substitute.presentation.canvas.input.input_generation_capture import (
    InputGenerationCapture,
)
from substitute.presentation.canvas.input.input_generation_image_materializer import (
    InputGenerationImageMaterializer,
)
from substitute.presentation.canvas.input.input_generation_mask_materializer import (
    InputGenerationMaskMaterializer,
)
from substitute.application.generation.input_generation_errors import (
    InputGenerationPreparationError,
    InputGenerationPreparationFailureKind,
)
from substitute.presentation.canvas.input.input_generation_snapshot_service import (
    InputGenerationSnapshotService,
)


from tests.application.workflows.input_canvas.generation.snapshot_service_support import (
    _Associations,
    _Io,
    _image,
    _mask,
    _nodes,
    _synthetic_workflow,
    _workflow,
)


def test_generation_without_input_canvas_captures_an_empty_document_bundle() -> None:
    """A workflow with no Input surfaces must remain directly generatable."""

    captured_requests: list[tuple[tuple[UUID, ...], tuple[UUID, ...]]] = []

    def capture_inputs(
        *,
        image_ids: tuple[UUID, ...],
        mask_ids: tuple[UUID, ...],
    ) -> InputGenerationCapture:
        """Record the empty capture boundary used by a text-only workflow."""

        captured_requests.append((image_ids, mask_ids))
        return InputGenerationCapture(images={}, masks={})

    copy_materializer = SimpleNamespace(
        prepare_workflow=lambda **kwargs: copy.deepcopy(kwargs["workflow"])
    )
    service = InputGenerationSnapshotService(
        capture_inputs=capture_inputs,
        select_generation_images=lambda _workflow: GenerationInputImageSelection(()),
        image_materializer=copy_materializer,
        mask_materializer=copy_materializer,
    )
    workflow = WorkflowState()

    prepared = service.prepare_workflow(workflow_id="text-only", workflow=workflow)

    assert isinstance(prepared, WorkflowState)
    assert prepared is not workflow
    assert captured_requests == [((), ())]


def test_generation_materializes_one_coherent_bundle_without_mutating_authoring(
    tmp_path: Path,
) -> None:
    """Later pixel edits cannot change either submitted execution product."""
    image_id = uuid4()
    mask_id = uuid4()
    image_pixels = _image(QColor("red"))
    mask_pixels = _mask(0)
    capture = InputGenerationCapture(
        images={
            image_id: EmbeddedImageExportSnapshot(
                image_id,
                uuid4(),
                8,
                image_pixels,
            )
        },
        masks={
            mask_id: MaskExportSnapshot(
                mask_id,
                image_id,
                13,
                mask_pixels,
            )
        },
    )
    workflow = _workflow(image_id, mask_id)
    io = _Io(tmp_path)
    associations = _Associations()
    service = InputGenerationSnapshotService(
        capture_inputs=lambda **_kwargs: capture,
        select_generation_images=lambda _workflow: GenerationInputImageSelection(
            (image_id,)
        ),
        image_materializer=InputGenerationImageMaterializer(
            canvas_io_service=io,
            association_service=associations,
            workflow_name_provider=lambda _workflow_id: "Recipe",
            projects_dir_provider=lambda: tmp_path,
        ),
        mask_materializer=InputGenerationMaskMaterializer(
            canvas_io_service=io,
            workflow_input_canvas_service=associations,
            workflow_name_provider=lambda _workflow_id: "Recipe",
            projects_dir_provider=lambda: tmp_path,
        ),
    )

    prepared = service.prepare_workflow(workflow_id="wf-a", workflow=workflow)
    image_pixels.fill(QColor("blue"))
    mask_pixels.fill(255)

    assert isinstance(prepared, WorkflowState)
    original_nodes = _nodes(workflow)
    prepared_nodes = _nodes(prepared)
    assert original_nodes["ImageNode"]["inputs"]["image"] == "authoring-image.png"
    assert original_nodes["MaskNode"]["inputs"]["image"] == "authoring-mask.png"
    prepared_image_value = prepared_nodes["ImageNode"]["inputs"]["image"]
    assert isinstance(prepared_image_value, str)
    assert prepared_image_value.startswith("input_images/.generation/")
    assert prepared_nodes["MaskNode"]["inputs"]["image"] == (
        f".generation/{mask_id}/13.png"
    )
    persisted_image = next(
        image for path, image in io.saved if "input_images" in path.parts
    )
    persisted_mask = next(image for path, image in io.saved if "masks" in path.parts)
    assert persisted_image.pixelColor(0, 0) == QColor("red")
    assert persisted_mask.pixelColor(0, 0) == QColor("black")


def test_generation_blocks_before_any_mask_write_when_image_product_fails(
    tmp_path: Path,
) -> None:
    """A failed image product must prevent partially prepared mask execution."""
    image_id = uuid4()
    mask_id = uuid4()
    workflow = _workflow(image_id, mask_id)
    capture = InputGenerationCapture(
        images={
            image_id: EmbeddedImageExportSnapshot(
                image_id,
                uuid4(),
                1,
                _image(QColor("red")),
            )
        },
        masks={
            mask_id: MaskExportSnapshot(mask_id, image_id, 1, _mask(255)),
        },
    )
    io = _Io(tmp_path, fail_images=True)
    associations = _Associations()
    service = InputGenerationSnapshotService(
        capture_inputs=lambda **_kwargs: capture,
        select_generation_images=lambda _workflow: GenerationInputImageSelection(
            (image_id,)
        ),
        image_materializer=InputGenerationImageMaterializer(
            canvas_io_service=io,
            association_service=associations,
            workflow_name_provider=lambda _workflow_id: "Recipe",
            projects_dir_provider=lambda: tmp_path,
        ),
        mask_materializer=InputGenerationMaskMaterializer(
            canvas_io_service=io,
            workflow_input_canvas_service=associations,
            workflow_name_provider=lambda _workflow_id: "Recipe",
            projects_dir_provider=lambda: tmp_path,
        ),
    )

    with pytest.raises(InputGenerationPreparationError) as error_info:
        service.prepare_workflow(workflow_id="wf-a", workflow=workflow)

    assert (
        error_info.value.kind
        is InputGenerationPreparationFailureKind.IMAGE_MATERIALIZATION
    )
    assert not any("masks" in path.parts for path, _image_value in io.saved)


def test_generation_materializes_synthetic_canvas_masks_without_backing_image(
    tmp_path: Path,
) -> None:
    """A synthetic canvas surface must remain canvas-only during generation."""

    image_id = uuid4()
    mask_id = uuid4()
    workflow = _synthetic_workflow(image_id, mask_id)
    capture = InputGenerationCapture(
        images={},
        masks={
            mask_id: MaskExportSnapshot(
                mask_id,
                image_id,
                5,
                _mask(255),
            )
        },
    )

    def capture_inputs(
        *,
        image_ids: tuple[UUID, ...],
        mask_ids: tuple[UUID, ...],
    ) -> InputGenerationCapture:
        """Require generation to request only the graph-owned mask product."""

        assert image_ids == ()
        assert mask_ids == (mask_id,)
        return capture

    io = _Io(tmp_path)
    associations = _Associations()
    service = InputGenerationSnapshotService(
        capture_inputs=capture_inputs,
        select_generation_images=lambda _workflow: GenerationInputImageSelection(()),
        image_materializer=InputGenerationImageMaterializer(
            canvas_io_service=io,
            association_service=associations,
            workflow_name_provider=lambda _workflow_id: "Regional",
            projects_dir_provider=lambda: tmp_path,
        ),
        mask_materializer=InputGenerationMaskMaterializer(
            canvas_io_service=io,
            workflow_input_canvas_service=associations,
            workflow_name_provider=lambda _workflow_id: "Regional",
            projects_dir_provider=lambda: tmp_path,
        ),
    )

    prepared = service.prepare_workflow(workflow_id="wf-region", workflow=workflow)

    assert isinstance(prepared, WorkflowState)
    assert not any("input_images" in path.parts for path, _image_value in io.saved)
    assert _nodes(prepared, "Region")["MaskNode"]["inputs"]["image"] == (
        f".generation/{mask_id}/5.png"
    )
    assert _nodes(prepared, "Region")["Latent"]["inputs"] == {
        "width": 960,
        "height": 1344,
        "batch_size": 1,
    }


def test_generation_fails_before_capture_when_canvas_surface_is_stale(
    tmp_path: Path,
) -> None:
    """Unresolved persisted canvas state must not become a partial request."""

    image_id = uuid4()
    mask_id = uuid4()
    workflow = _workflow(image_id, mask_id)
    io = _Io(tmp_path)
    associations = _Associations()

    def unexpected_capture(**_kwargs: object) -> InputGenerationCapture:
        """Reject capture after graph authority resolution has failed."""

        raise AssertionError("capture must not run")

    service = InputGenerationSnapshotService(
        capture_inputs=unexpected_capture,
        select_generation_images=lambda _workflow: GenerationInputImageSelection(
            (),
            unresolved_input_keys=("CubeA:RemovedImage",),
        ),
        image_materializer=InputGenerationImageMaterializer(
            canvas_io_service=io,
            association_service=associations,
            workflow_name_provider=lambda _workflow_id: "Recipe",
            projects_dir_provider=lambda: tmp_path,
        ),
        mask_materializer=InputGenerationMaskMaterializer(
            canvas_io_service=io,
            workflow_input_canvas_service=associations,
            workflow_name_provider=lambda _workflow_id: "Recipe",
            projects_dir_provider=lambda: tmp_path,
        ),
    )

    with pytest.raises(InputGenerationPreparationError) as error_info:
        service.prepare_workflow(workflow_id="wf-a", workflow=workflow)

    assert (
        error_info.value.kind
        is InputGenerationPreparationFailureKind.CANVAS_SURFACE_AUTHORITY
    )
