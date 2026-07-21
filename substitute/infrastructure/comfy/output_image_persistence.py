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

"""Persist final Comfy output images with Substitute metadata and naming."""

from __future__ import annotations

import io
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, PngImagePlugin

from substitute.application.generation.output_path_template_renderer import (
    OutputPathTemplateRenderer,
)
from substitute.application.ports.comfy_gateway import OutputSavePlan
from substitute.domain.generation import OutputPathRenderContext
from substitute.infrastructure.comfy.comfy_payload_fields import positive_int_or_zero
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
    cube_number_for_source_identity,
)
from substitute.infrastructure.persistence.image_naming import (
    get_next_bucket_run_number,
    get_next_folder_image_number,
)
from substitute.infrastructure.comfy.jpeg_companion_encoder import (
    JpegCompanionEncoder,
)
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("infrastructure.comfy.output_image_persistence")


@dataclass(frozen=True)
class PersistedOutputImage:
    """Describe materialized output facts and optional durable PNG path."""

    file_path: Path | None
    width: int
    height: int


class OutputImagePersistence:
    """Own output image file persistence, naming state, and PNG metadata."""

    def __init__(
        self,
        *,
        output_save_plan: OutputSavePlan,
        workflow_payload: Mapping[str, object],
        sugar_script: str,
        cube_numbers_by_alias: Mapping[str, int],
        output_path_renderer: OutputPathTemplateRenderer | None = None,
        jpeg_encoder: JpegCompanionEncoder | None = None,
    ) -> None:
        """Initialize one listener-run persistence owner."""

        self._output_save_plan = output_save_plan
        self._workflow_payload = workflow_payload
        self._sugar_script = sugar_script
        self._cube_numbers_by_alias = dict(cube_numbers_by_alias)
        self._output_path_renderer = (
            output_path_renderer or OutputPathTemplateRenderer()
        )
        self._image_run_counter: int | None = output_save_plan.output_run_number
        self._source_output_counts: dict[str, int] = {}
        self._jpeg_encoder = jpeg_encoder or JpegCompanionEncoder()

    def persist_output_image(
        self,
        *,
        image_bytes: bytes,
        source_identity: OutputSourceIdentity,
    ) -> PersistedOutputImage:
        """Materialize optional durable files and always return decoded dimensions."""

        workflow_name = self._output_save_plan.workflow_name
        source_label = source_identity.source_label
        source_index = self._next_source_output_index(source_identity.source_key)
        cube_number = cube_number_for_source_identity(
            source_identity,
            self._cube_numbers_by_alias,
        )

        with Image.open(io.BytesIO(image_bytes)) as image:
            width = positive_int_or_zero(getattr(image, "width", 0))
            height = positive_int_or_zero(getattr(image, "height", 0))
            if not self._output_save_plan.persists_cube(
                source_identity.cube_alias or source_identity.source_label
            ):
                return PersistedOutputImage(
                    file_path=None,
                    width=width,
                    height=height,
                )
            cube_label = source_identity.cube_alias or source_label
            if self._image_run_counter is None:
                bucket = self._output_path_renderer.resolve_run_bucket(
                    output_root=self._output_save_plan.output_root,
                    path_pattern=self._output_save_plan.path_pattern,
                    context=self._output_path_context(
                        workflow_name=workflow_name,
                        source=source_label,
                        cube=cube_label,
                        output_run_number=None,
                        cube_number=cube_number,
                        folder_image_number=None,
                        width=width,
                        height=height,
                        index=source_index,
                        set_index=source_index,
                    ),
                )
                self._image_run_counter = get_next_bucket_run_number(bucket.directory)
            folder_image_number = self._next_folder_image_number(
                workflow_name=workflow_name,
                source=source_label,
                cube=cube_label,
                output_run_number=self._image_run_counter,
                cube_number=cube_number,
                width=width,
                height=height,
                source_index=source_index,
            )
            file_path = self._output_path_renderer.render_path(
                output_root=self._output_save_plan.output_root,
                path_pattern=self._output_save_plan.path_pattern,
                context=self._output_path_context(
                    workflow_name=workflow_name,
                    source=source_label,
                    cube=cube_label,
                    output_run_number=self._image_run_counter,
                    cube_number=cube_number,
                    folder_image_number=folder_image_number,
                    width=width,
                    height=height,
                    index=source_index,
                    set_index=source_index,
                ),
            ).path
            file_path = _reserve_png_jpeg_pair(
                file_path,
                include_jpeg=self._output_save_plan.jpeg.enabled,
            )
            file_path.parent.mkdir(parents=True, exist_ok=True)

            png_metadata = PngImagePlugin.PngInfo()
            headered_script = f"# Project: {workflow_name}\n\n{self._sugar_script}"
            png_metadata.add_text("sugar_script", headered_script)
            workflow_metadata = workflow_metadata_json(self._workflow_payload)
            if workflow_metadata is not None:
                png_metadata.add_text("workflow", workflow_metadata)
            image.save(file_path, pnginfo=png_metadata)
            if self._output_save_plan.jpeg.enabled:
                try:
                    jpeg_bytes = self._jpeg_encoder.encode(
                        image, self._output_save_plan.jpeg
                    )
                    file_path.with_suffix(".jpg").write_bytes(jpeg_bytes)
                except Exception as error:
                    log_exception(
                        _LOGGER,
                        "Failed to write optional JPEG companion",
                        png_path=file_path,
                        error=error,
                    )
        return PersistedOutputImage(file_path=file_path, width=width, height=height)

    def _next_folder_image_number(
        self,
        *,
        workflow_name: str,
        source: str,
        cube: str,
        output_run_number: int | None,
        cube_number: int | None,
        width: int,
        height: int,
        source_index: int,
    ) -> int | None:
        """Allocate a folder-local image number when `{image#}` is configured."""

        if "{image#}" not in self._output_save_plan.path_pattern:
            return None
        unnumbered_path = self._output_path_renderer.render_path(
            output_root=self._output_save_plan.output_root,
            path_pattern=self._output_save_plan.path_pattern,
            context=self._output_path_context(
                workflow_name=workflow_name,
                source=source,
                cube=cube,
                output_run_number=output_run_number,
                cube_number=cube_number,
                folder_image_number=None,
                width=width,
                height=height,
                index=source_index,
                set_index=source_index,
            ),
            avoid_collisions=False,
        ).path
        return get_next_folder_image_number(
            unnumbered_path.parent,
            self._output_save_plan.path_pattern,
        )

    def _output_path_context(
        self,
        *,
        workflow_name: str,
        source: str,
        cube: str,
        output_run_number: int | None,
        cube_number: int | None,
        folder_image_number: int | None,
        width: int,
        height: int,
        index: int,
        set_index: int,
    ) -> OutputPathRenderContext:
        """Build the renderer context shared by bucket and path rendering."""

        return OutputPathRenderContext(
            workflow_name=workflow_name,
            source=source,
            cube=cube,
            output_run_number=output_run_number,
            cube_number=cube_number,
            folder_image_number=folder_image_number,
            job_started_at=self._output_save_plan.job_started_at,
            width=width,
            height=height,
            index=index,
            set_index=set_index,
            seed=self._output_save_plan.seed,
        )

    def _next_source_output_index(self, source_key: str) -> int:
        """Increment and return the per-source output ordinal for this listener."""

        next_index = self._source_output_counts.get(source_key, 0) + 1
        self._source_output_counts[source_key] = next_index
        return next_index


def workflow_metadata_json(workflow_payload: Mapping[str, object]) -> str | None:
    """Return Comfy UI workflow metadata JSON from a wrapped Sugar payload."""

    workflow = workflow_payload.get("workflow")
    if not isinstance(workflow, Mapping):
        return None
    return json.dumps(workflow, separators=(",", ":"))


def _reserve_png_jpeg_pair(path: Path, *, include_jpeg: bool) -> Path:
    """Return a collision-free PNG path whose optional JPEG stem is also free."""

    candidate = path.with_suffix(".png")
    ordinal = 2
    while candidate.exists() or (
        include_jpeg and candidate.with_suffix(".jpg").exists()
    ):
        candidate = path.with_name(f"{path.stem}_{ordinal}").with_suffix(".png")
        ordinal += 1
    return candidate


__all__ = [
    "OutputImagePersistence",
    "PersistedOutputImage",
    "workflow_metadata_json",
]
