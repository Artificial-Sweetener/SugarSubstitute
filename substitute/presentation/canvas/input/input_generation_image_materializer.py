#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
"""Materialize exact captured Input image products for generation."""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol
from uuid import UUID

from cutecanvas import EmbeddedImageExportSnapshot

from substitute.domain.workflow import WorkflowState
from substitute.presentation.canvas.input.input_mask_identity import (
    resolve_input_mask_id,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_error,
    log_exception,
    log_info,
)

_LOGGER = get_logger("presentation.canvas.input.input_generation_image_materializer")
_GENERATION_DIRECTORY = ".generation"


class GenerationImageCanvasIoPort(Protocol):
    """Describe exact Input image product persistence."""

    def resolve_input_image_save_path(
        self,
        *,
        workflow_name: str,
        image_filename: str,
        projects_dir: Path,
    ) -> Path:
        """Resolve one project-owned generation image path."""

    def save_input_image(self, *, destination: Path, image: object) -> bool:
        """Persist one detached image product."""


class GenerationImageAssociationPort(Protocol):
    """Describe execution-copy image association."""

    def associate_project_input_image(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        relative_path: Path | str,
    ) -> bool:
        """Associate one copied image node with a project product."""


class InputGenerationImageMaterializer:
    """Apply captured embedded image revisions to an execution workflow copy."""

    def __init__(
        self,
        *,
        canvas_io_service: GenerationImageCanvasIoPort,
        association_service: GenerationImageAssociationPort,
        workflow_name_provider: Callable[[str], str],
        projects_dir_provider: Callable[[], Path],
    ) -> None:
        """Bind product I/O, graph association, and project path owners."""
        self._canvas_io_service = canvas_io_service
        self._association_service = association_service
        self._workflow_name_provider = workflow_name_provider
        self._projects_dir_provider = projects_dir_provider

    def prepare_workflow(
        self,
        *,
        workflow_id: str,
        workflow: object,
        snapshots: Mapping[UUID, EmbeddedImageExportSnapshot],
    ) -> object | None:
        """Return a copied workflow that references every exact image product."""
        if not isinstance(workflow, WorkflowState):
            return copy.deepcopy(workflow)
        execution_workflow = copy.deepcopy(workflow)
        workflow_name = self._workflow_name_provider(workflow_id)
        projects_dir = self._projects_dir_provider()
        for input_key, raw_image_id in sorted(
            workflow.canvas.input_key_map.items(),
            key=lambda item: str(item[0]),
        ):
            identity = self._resolve_input_key(input_key)
            image_id = resolve_input_mask_id(raw_image_id)
            snapshot = None if image_id is None else snapshots.get(image_id)
            if (
                identity is None
                or image_id is None
                or snapshot is None
                or snapshot.composition_id != image_id
            ):
                self._log_failure(
                    workflow_id=workflow_id,
                    input_key=input_key,
                    image_id=raw_image_id,
                    reason="invalid_or_missing_image_snapshot",
                )
                return None
            relative_path = self._relative_snapshot_path(image_id, snapshot)
            try:
                destination = self._canvas_io_service.resolve_input_image_save_path(
                    workflow_name=workflow_name,
                    image_filename=relative_path.as_posix(),
                    projects_dir=projects_dir,
                )
                saved = self._canvas_io_service.save_input_image(
                    destination=destination,
                    image=snapshot.image,
                )
            except (
                AttributeError,
                OSError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as error:
                log_exception(
                    _LOGGER,
                    "Exact Input image revision persistence raised",
                    workflow_id=workflow_id,
                    input_key=str(input_key),
                    image_id=str(image_id),
                    image_revision=snapshot.revision,
                    error=error,
                )
                saved = False
            if not saved:
                self._log_failure(
                    workflow_id=workflow_id,
                    input_key=input_key,
                    image_id=image_id,
                    reason="snapshot_persistence_failed",
                )
                return None
            section_key, node_name = identity
            try:
                associated = self._association_service.associate_project_input_image(
                    execution_workflow,
                    section_key=section_key,
                    node_name=node_name,
                    relative_path=relative_path,
                )
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                log_exception(
                    _LOGGER,
                    "Exact Input image revision association raised",
                    workflow_id=workflow_id,
                    input_key=str(input_key),
                    image_id=str(image_id),
                    image_revision=snapshot.revision,
                    error=error,
                )
                associated = False
            if not associated:
                self._log_failure(
                    workflow_id=workflow_id,
                    input_key=input_key,
                    image_id=image_id,
                    reason="execution_association_failed",
                )
                return None
            log_info(
                _LOGGER,
                "Materialized exact Input image revision for generation",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                section_key=section_key,
                node_name=node_name,
                image_id=str(image_id),
                resource_id=str(snapshot.resource_id),
                image_revision=snapshot.revision,
                destination=str(destination),
            )
        return execution_workflow

    @staticmethod
    def _relative_snapshot_path(
        image_id: UUID,
        snapshot: EmbeddedImageExportSnapshot,
    ) -> Path:
        """Return one stable resource-revision-relative image path."""
        return (
            Path(_GENERATION_DIRECTORY)
            / str(image_id)
            / f"{snapshot.resource_id}-{snapshot.revision}.png"
        )

    @staticmethod
    def _resolve_input_key(key: object) -> tuple[str, str] | None:
        """Parse one non-empty section and image-node identity."""
        if not isinstance(key, str):
            return None
        section_key, separator, node_name = key.partition(":")
        if separator and section_key and node_name:
            return section_key, node_name
        return None

    @staticmethod
    def _log_failure(
        *,
        workflow_id: str,
        input_key: object,
        image_id: object,
        reason: str,
    ) -> None:
        """Record a generation-blocking image product failure."""
        log_error(
            _LOGGER,
            "Failed to materialize exact Input image revision for generation",
            workflow_id=workflow_id,
            input_key=str(input_key),
            image_id=str(image_id),
            failure_reason=reason,
        )


__all__ = ["InputGenerationImageMaterializer"]
