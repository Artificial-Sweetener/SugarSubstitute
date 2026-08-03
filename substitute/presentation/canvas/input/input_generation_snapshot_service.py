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

"""Coordinate coherent Input capture and external generation products."""

from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from typing import Protocol
from uuid import UUID

from cutecanvas import EmbeddedImageExportSnapshot, MaskExportSnapshot

from substitute.domain.workflow import WorkflowState
from substitute.presentation.canvas.input.input_generation_capture import (
    InputGenerationCapture,
)
from substitute.presentation.canvas.input.input_mask_identity import (
    resolve_input_mask_id,
)
from substitute.shared.logging.logger import get_logger, log_error

_LOGGER = get_logger("presentation.canvas.input.input_generation_snapshot_service")


class InputCapturePort(Protocol):
    """Describe coherent document capture for generation."""

    def __call__(
        self,
        *,
        image_ids: tuple[UUID, ...],
        mask_ids: tuple[UUID, ...],
    ) -> InputGenerationCapture | None:
        """Capture one coherent set of detached Input products."""


class InputImageProductMaterializerPort(Protocol):
    """Describe exact image-product materialization."""

    def prepare_workflow(
        self,
        *,
        workflow_id: str,
        workflow: object,
        snapshots: Mapping[UUID, EmbeddedImageExportSnapshot],
    ) -> object | None:
        """Apply captured image products to a copied workflow."""


class InputMaskProductMaterializerPort(Protocol):
    """Describe exact mask-product materialization."""

    def prepare_workflow(
        self,
        *,
        workflow_id: str,
        workflow: object,
        snapshots: Mapping[UUID, MaskExportSnapshot],
    ) -> object | None:
        """Apply captured mask products to a copied workflow."""


class InputGenerationSnapshotService:
    """Capture once, then materialize exact image and mask products."""

    def __init__(
        self,
        *,
        capture_inputs: InputCapturePort,
        image_materializer: InputImageProductMaterializerPort,
        mask_materializer: InputMaskProductMaterializerPort,
    ) -> None:
        """Bind coherent capture and format-specific external product owners."""
        self._capture_inputs = capture_inputs
        self._image_materializer = image_materializer
        self._mask_materializer = mask_materializer

    def prepare_workflow(
        self,
        *,
        workflow_id: str,
        workflow: object,
    ) -> object | None:
        """Return an execution copy pinned to one coherent Input document state."""
        if not isinstance(workflow, WorkflowState):
            return copy.deepcopy(workflow)
        image_ids = self._identities(workflow.canvas.image_ids())
        mask_ids = self._identities(workflow.canvas.mask_ids())
        if image_ids is None or mask_ids is None:
            self._log_capture_failure(workflow_id, "invalid_workflow_identity")
            return None
        capture = self._capture_inputs(image_ids=image_ids, mask_ids=mask_ids)
        if capture is None:
            self._log_capture_failure(workflow_id, "incoherent_document_revision")
            return None
        prepared = self._image_materializer.prepare_workflow(
            workflow_id=workflow_id,
            workflow=workflow,
            snapshots=capture.images,
        )
        if prepared is None:
            return None
        return self._mask_materializer.prepare_workflow(
            workflow_id=workflow_id,
            workflow=prepared,
            snapshots=capture.masks,
        )

    @staticmethod
    def _identities(values: Iterable[object]) -> tuple[UUID, ...] | None:
        """Normalize one iterable of workflow UUID values without duplicates."""
        try:
            resolved = tuple(resolve_input_mask_id(value) for value in values)
        except TypeError:
            return None
        if any(value is None for value in resolved):
            return None
        return tuple(dict.fromkeys(value for value in resolved if value is not None))

    @staticmethod
    def _log_capture_failure(workflow_id: str, reason: str) -> None:
        """Record why generation could not pin one Input document state."""
        log_error(
            _LOGGER,
            "Failed to capture coherent Input document revision for generation",
            workflow_id=workflow_id,
            failure_reason=reason,
        )


__all__ = ["InputGenerationSnapshotService"]
