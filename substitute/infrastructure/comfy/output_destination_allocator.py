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

"""Allocate collision-free generated output destinations."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from substitute.application.generation.output_path_template_renderer import (
    OutputPathTemplateRenderer,
)
from substitute.application.ports.comfy_gateway import OutputSavePlan
from substitute.domain.generation import OutputPathRenderContext
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
    cube_number_for_source_identity,
)
from substitute.infrastructure.persistence.image_naming import (
    get_next_bucket_run_number,
    get_next_folder_image_number,
)


class OutputDestinationAllocator:
    """Own shared output numbering, path rendering, and collision policy."""

    def __init__(
        self,
        *,
        output_save_plan: OutputSavePlan,
        cube_numbers_by_alias: Mapping[str, int],
        output_path_renderer: OutputPathTemplateRenderer | None = None,
    ) -> None:
        """Initialize one listener-run destination namespace."""

        self._plan = output_save_plan
        self._cube_numbers_by_alias = dict(cube_numbers_by_alias)
        self._renderer = output_path_renderer or OutputPathTemplateRenderer()
        self._run_number = output_save_plan.output_run_number
        self._source_counts: dict[str, int] = {}

    def allocate(
        self,
        *,
        source_identity: OutputSourceIdentity,
        width: int,
        height: int,
        suffix: str,
        companion_suffixes: tuple[str, ...] = (),
    ) -> Path | None:
        """Return one reserved durable path or ``None`` for transient policy."""

        source_index = self._next_source_index(source_identity.source_key)
        cube_alias = source_identity.cube_alias or source_identity.source_label
        if not self._plan.persists_cube(cube_alias):
            return None
        cube_number = cube_number_for_source_identity(
            source_identity,
            self._cube_numbers_by_alias,
        )
        if self._run_number is None:
            bucket = self._renderer.resolve_run_bucket(
                output_root=self._plan.output_root,
                path_pattern=self._plan.path_pattern,
                context=self._context(
                    source_identity=source_identity,
                    output_run_number=None,
                    cube_number=cube_number,
                    folder_image_number=None,
                    width=width,
                    height=height,
                    source_index=source_index,
                ),
            )
            self._run_number = get_next_bucket_run_number(bucket.directory)
        folder_image_number = self._folder_image_number(
            source_identity=source_identity,
            cube_number=cube_number,
            width=width,
            height=height,
            source_index=source_index,
        )
        rendered = self._renderer.render_path(
            output_root=self._plan.output_root,
            path_pattern=self._plan.path_pattern,
            context=self._context(
                source_identity=source_identity,
                output_run_number=self._run_number,
                cube_number=cube_number,
                folder_image_number=folder_image_number,
                width=width,
                height=height,
                source_index=source_index,
            ),
        ).path
        destination = _reserve_path(
            rendered.with_suffix(suffix),
            companion_suffixes=companion_suffixes,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        return destination

    def _folder_image_number(
        self,
        *,
        source_identity: OutputSourceIdentity,
        cube_number: int | None,
        width: int,
        height: int,
        source_index: int,
    ) -> int | None:
        """Allocate the legacy folder ordinal when requested by the template."""

        if "{image#}" not in self._plan.path_pattern:
            return None
        unnumbered_path = self._renderer.render_path(
            output_root=self._plan.output_root,
            path_pattern=self._plan.path_pattern,
            context=self._context(
                source_identity=source_identity,
                output_run_number=self._run_number,
                cube_number=cube_number,
                folder_image_number=None,
                width=width,
                height=height,
                source_index=source_index,
            ),
            avoid_collisions=False,
        ).path
        return get_next_folder_image_number(
            unnumbered_path.parent,
            self._plan.path_pattern,
        )

    def _context(
        self,
        *,
        source_identity: OutputSourceIdentity,
        output_run_number: int | None,
        cube_number: int | None,
        folder_image_number: int | None,
        width: int,
        height: int,
        source_index: int,
    ) -> OutputPathRenderContext:
        """Build one render context from authoritative save-plan state."""

        source_label = source_identity.source_label
        return OutputPathRenderContext(
            workflow_name=self._plan.workflow_name,
            source=source_label,
            cube=source_identity.cube_alias or source_label,
            output_run_number=output_run_number,
            cube_number=cube_number,
            folder_image_number=folder_image_number,
            job_started_at=self._plan.job_started_at,
            width=width,
            height=height,
            index=source_index,
            set_index=source_index,
            seed=self._plan.seed,
        )

    def _next_source_index(self, source_key: str) -> int:
        """Increment and return one source-local output ordinal."""

        next_index = self._source_counts.get(source_key, 0) + 1
        self._source_counts[source_key] = next_index
        return next_index


def _reserve_path(
    path: Path,
    *,
    companion_suffixes: tuple[str, ...],
) -> Path:
    """Return a collision-free path whose companion stems are also free."""

    candidate = path
    ordinal = 2
    while candidate.exists() or any(
        candidate.with_suffix(suffix).exists() for suffix in companion_suffixes
    ):
        candidate = path.with_name(f"{path.stem}_{ordinal}")
        ordinal += 1
    return candidate


__all__ = ["OutputDestinationAllocator"]
