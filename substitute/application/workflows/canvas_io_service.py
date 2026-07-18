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

"""Provide canvas-oriented path, metadata, and external-editor orchestration."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from substitute.application.cubes import cube_alias_body
from substitute.application.ports.image_repository import ImageRepository
from substitute.domain.workflow import ImageMeta
from substitute.shared.logging.logger import get_logger, log_exception
from substitute.shared.util.path_safety import (
    ensure_within_root,
    validate_top_level_name,
)

_LOGGER = get_logger("application.workflows.canvas_io_service")
_OUTPUT_IMAGE_NUMBER_RE = re.compile(r"^(\d{3})")
_UNSAFE_FILENAME_COMPONENT_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_FILENAME_SEPARATOR_RE = re.compile(r"_+")


class ExternalImageEditorGateway(Protocol):
    """Describe external-editor bridge behavior for canvas output images."""

    def open_image(self, *, image: object, image_meta: ImageMeta) -> bool:
        """Open one image in an external editor and return success state."""

    def open_images(self, *, images: Sequence[tuple[object, ImageMeta]]) -> bool:
        """Open multiple images in an external editor and return success state."""


class CanvasIoService:
    """Centralize filesystem and metadata behavior for canvas-related flows."""

    def __init__(
        self,
        *,
        image_repository: ImageRepository,
        external_image_gateway: ExternalImageEditorGateway | None = None,
    ) -> None:
        """Capture image IO repository and optional external-editor gateway."""

        self._image_repository = image_repository
        self._external_image_gateway = external_image_gateway

    def expected_bound_mask_path(
        self,
        *,
        workflow_name: str,
        associated_image_path: Path,
        cube_alias: str,
        mask_node_name: str,
        image_size: tuple[int, int] | None,
        projects_dir: Path,
    ) -> Path:
        """Return the deterministic mask artifact path for one image binding."""

        safe_workflow_name = validate_top_level_name(workflow_name, subject="Workflow")
        masks_dir = projects_dir / safe_workflow_name / "masks"
        resolved_masks_dir = ensure_within_root(
            masks_dir,
            root_path=projects_dir,
            subject="Masks directory",
        )
        resolved_masks_dir.mkdir(parents=True, exist_ok=True)

        filename = "__".join(
            (
                _safe_filename_component(associated_image_path.stem),
                _short_path_hash(associated_image_path),
                _image_size_component(image_size),
                _safe_identity_component(cube_alias),
                _safe_filename_component(mask_node_name),
            )
        )
        return ensure_within_root(
            resolved_masks_dir / f"{filename}.png",
            root_path=projects_dir,
            subject="Bound mask path",
        )

    def allocate_bound_mask_path(
        self,
        *,
        workflow_name: str,
        associated_image_path: Path,
        cube_alias: str,
        mask_node_name: str,
        image_size: tuple[int, int] | None,
        projects_dir: Path,
    ) -> Path:
        """Allocate a collision-safe bound mask path without overwriting artifacts."""

        preferred = self.expected_bound_mask_path(
            workflow_name=workflow_name,
            associated_image_path=associated_image_path,
            cube_alias=cube_alias,
            mask_node_name=mask_node_name,
            image_size=image_size,
            projects_dir=projects_dir,
        )
        if not preferred.exists():
            return preferred

        variant_number = 2
        while True:
            candidate = preferred.with_name(
                f"{preferred.stem}__v{variant_number:02d}{preferred.suffix}"
            )
            if not candidate.exists():
                return candidate
            variant_number += 1

    def create_blank_mask(self, *, destination: Path, size: object) -> bool:
        """Create transparent mask image file through image repository adapter."""

        return self._image_repository.save_blank_mask(destination, size=size)

    def synthetic_input_surface_path(
        self,
        *,
        workflow_name: str,
        section_key: str,
        surface_key: str,
        width: int,
        height: int,
        projects_dir: Path,
    ) -> Path:
        """Return a deterministic project path for one synthetic backing image."""

        safe_workflow_name = validate_top_level_name(workflow_name, subject="Workflow")
        surface_dir = ensure_within_root(
            projects_dir / safe_workflow_name / "input_surfaces",
            root_path=projects_dir,
            subject="Synthetic input surface directory",
        )
        filename = "__".join(
            (
                _safe_identity_component(section_key),
                _safe_identity_component(surface_key),
                _image_size_component((width, height)),
            )
        )
        return ensure_within_root(
            surface_dir / f"{filename}.png",
            root_path=projects_dir,
            subject="Synthetic input surface path",
        )

    def create_blank_input_surface(
        self,
        *,
        destination: Path,
        width: int,
        height: int,
    ) -> object | None:
        """Persist and load a neutral synthetic Input canvas backing image."""

        if destination.exists() and self.image_dimensions(destination) == (
            width,
            height,
        ):
            return self.load_input_image(destination)
        saved = self._image_repository.save_blank_image(
            destination,
            width=width,
            height=height,
        )
        return self.load_input_image(destination) if saved else None

    def save_mask_image(self, *, destination: Path, image: object) -> bool:
        """Persist existing mask image payload through image repository adapter."""

        return self._image_repository.save_image(destination, image=image)

    def resolve_mask_save_path(
        self,
        *,
        workflow_name: str,
        mask_filename: str,
        projects_dir: Path,
    ) -> Path:
        """Resolve canonical mask-save destination from workflow name and buffer path."""

        return self.resolve_mask_path(
            workflow_name=workflow_name,
            path_from_buffer=mask_filename,
            projects_dir=projects_dir,
        )

    def resolve_mask_path(
        self,
        *,
        workflow_name: str,
        path_from_buffer: str,
        projects_dir: Path,
    ) -> Path:
        """Resolve absolute/relative mask path from workflow buffer value safely."""

        raw_path = Path(path_from_buffer)
        if raw_path.is_absolute():
            return raw_path

        safe_workflow_name = validate_top_level_name(workflow_name, subject="Workflow")
        workflow_masks_dir = projects_dir / safe_workflow_name / "masks"
        candidate = workflow_masks_dir / raw_path
        return ensure_within_root(
            candidate,
            root_path=projects_dir,
            subject="Mask path",
        )

    def load_input_image(self, path: Path) -> object | None:
        """Load input image from filesystem for input-canvas materialization."""

        return self._image_repository.load_image(path)

    def image_dimensions(self, path: Path) -> tuple[int, int] | None:
        """Return filesystem image dimensions through the repository boundary."""

        return self._image_repository.image_dimensions(path)

    def load_output_image(self, path: Path) -> object | None:
        """Load output image from filesystem for output-canvas updates."""

        return self._image_repository.load_image(path)

    def load_recipe_preview_image(self, source_path: Path) -> object | None:
        """Load the preview image displayed when a PNG recipe is opened."""

        return self._image_repository.load_image(source_path)

    def build_output_image_metadata(
        self,
        *,
        workflow_name: str,
        node_meta_title: str,
        file_path: Path,
        source_key: str = "",
        source_label: str = "",
        node_id: str = "",
        generation_run_id: str | None = None,
        prompt_id: str | None = None,
        client_id: str | None = None,
        scene_run_id: str | None = None,
        scene_key: str | None = None,
        scene_title: str | None = None,
        scene_order: int | None = None,
        scene_count: int | None = None,
        width: int | None = None,
        height: int | None = None,
        list_index: int | None = None,
        batch_index: int | None = None,
        cube_execution_duration_ms: float | None = None,
    ) -> ImageMeta:
        """Build output metadata payload from workflow label, node title, and file path."""

        cube_name = (
            node_meta_title.split(".", 1)[0]
            if "." in node_meta_title
            else node_meta_title
        )
        stem = file_path.stem
        number_match = _OUTPUT_IMAGE_NUMBER_RE.match(stem)
        image_number = int(number_match.group(1)) if number_match else -1
        suffix = "_".join(stem.split("_")[1:]) if "_" in stem else ""
        return ImageMeta(
            workflow_name=workflow_name,
            cube_name=cube_name,
            image_number=image_number,
            suffix=suffix,
            path=file_path.as_posix(),
            source_key=source_key,
            source_label=source_label or cube_alias_body(cube_name),
            node_id=node_id,
            generation_run_id=generation_run_id or "",
            prompt_id=prompt_id or "",
            client_id=client_id or "",
            scene_run_id=scene_run_id or "",
            scene_key=scene_key or "",
            scene_title=scene_title or "",
            scene_order=scene_order,
            scene_count=scene_count,
            width=width,
            height=height,
            list_index=list_index,
            batch_index=batch_index,
            cube_execution_duration_ms=cube_execution_duration_ms,
        )

    def open_image_in_external_editor(
        self, *, image: object, image_meta: ImageMeta
    ) -> bool:
        """Attempt to open one image in external editor and fail closed on errors."""

        if self._external_image_gateway is None:
            return False
        try:
            return bool(
                self._external_image_gateway.open_image(
                    image=image,
                    image_meta=image_meta,
                )
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to open output image in external editor",
                workflow_name=image_meta.workflow_name,
                cube_name=image_meta.cube_name,
                path=image_meta.path,
                error=error,
            )
            return False

    def open_images_in_external_editor(
        self,
        *,
        images: Sequence[tuple[object, ImageMeta]],
    ) -> bool:
        """Attempt to open multiple images in external editor and fail closed."""

        if not images or self._external_image_gateway is None:
            return False
        try:
            return bool(self._external_image_gateway.open_images(images=images))
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to open output image set in external editor",
                image_count=len(images),
                error=error,
            )
            return False

    @staticmethod
    def resolve_workflow_label(workflow_metadata: object) -> str:
        """Resolve workflow label from metadata payload with fallback semantics."""

        if isinstance(workflow_metadata, dict):
            label = workflow_metadata.get("label")
            if isinstance(label, str) and label.strip():
                return label
        return "untitled_workflow"

    @staticmethod
    def resolve_node_meta_title(node_data: object) -> str:
        """Resolve node meta title text from workflow payload node data."""

        if not isinstance(node_data, dict):
            return ""
        maybe_meta = node_data.get("_meta")
        if not isinstance(maybe_meta, dict):
            return ""
        title = maybe_meta.get("title")
        if not isinstance(title, str):
            return ""
        return title


def _safe_filename_component(value: str) -> str:
    """Return a conservative filename component for generated mask artifacts."""

    replaced = _UNSAFE_FILENAME_COMPONENT_RE.sub("_", value.strip())
    replaced = re.sub(r"\s+", "_", replaced)
    collapsed = _FILENAME_SEPARATOR_RE.sub("_", replaced).strip(" ._")
    return collapsed or "unnamed"


def _safe_identity_component(value: str) -> str:
    """Return a filename component for graph identities that may contain paths."""

    normalized = value.strip()
    try:
        return _safe_filename_component(
            validate_top_level_name(normalized, subject="Graph identity")
        )
    except ValueError:
        safe_name = _safe_filename_component(normalized)
        identity_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
        return f"{safe_name}__{identity_hash}"


def _short_path_hash(path: Path) -> str:
    """Return a stable short hash for a normalized filesystem path."""

    try:
        normalized_path = path.expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        normalized_path = path.absolute()
    normalized = str(normalized_path).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]


def _image_size_component(image_size: tuple[int, int] | None) -> str:
    """Return deterministic dimensions text for bound mask filenames."""

    if image_size is None:
        return "unknown_size"
    width, height = image_size
    if width <= 0 or height <= 0:
        return "unknown_size"
    return f"{width}x{height}"


__all__ = [
    "CanvasIoService",
    "ExternalImageEditorGateway",
]
