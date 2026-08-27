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

#    SugarSubsti

from __future__ import annotations

from substitute.application.cubes import (
    CubePickerClassification,
    CubePickerModelRoleSection,
    CubePickerRole,
    CubePickerSection,
    CubeSearchTerm,
    CubeSearchTarget,
    build_cube_picker_entries,
    build_cube_picker_model_role_sections,
    build_cube_picker_sections,
    build_cube_search_targets,
    classify_cube_document,
)

from substitute.application.ports import CubeCatalogRecord

from substitute.domain.cube_library import CubeSourceMetadata


def _record(
    *,
    cube_id: str,
    display_name: str,
    description: str = "",
    source: CubeSourceMetadata | None = None,
    supported_models: tuple[str, ...] = (),
) -> CubeCatalogRecord:
    """Return one catalog record for picker model tests."""

    return CubeCatalogRecord(
        cube_id=cube_id,
        version="1.0.0",
        display_name=display_name,
        description=description,
        source=source,
        supported_models=supported_models,
    )


def _source(
    *,
    kind: str = "github",
    repo_ref: str = "",
    owner: str = "",
    repo: str = "",
    namespace: str = "",
    path: str = "",
) -> CubeSourceMetadata:
    """Return source metadata for picker model tests."""

    return CubeSourceMetadata(
        kind=kind,
        repo_ref=repo_ref,
        owner=owner,
        repo=repo,
        namespace=namespace,
        path=path,
    )


def _classification(
    role: CubePickerRole,
    inputs: int,
    outputs: int,
    supported_models: tuple[str, ...] = (),
    search_terms: tuple[str, ...] = (),
    search_targets: tuple[CubeSearchTerm, ...] = (),
) -> CubePickerClassification:
    """Return one picker classification for tests."""

    return CubePickerClassification(
        role=role,
        input_count=inputs,
        output_count=outputs,
        supported_models=supported_models,
        search_terms=search_terms,
        search_targets=search_targets,
    )


def _flatten_cube_ids(sections: tuple[CubePickerSection, ...]) -> tuple[str, ...]:
    """Return cube IDs from all section entries in display order."""

    return tuple(entry.cube_id for section in sections for entry in section.entries)


def _target_pairs(targets: tuple[CubeSearchTarget, ...]) -> set[tuple[str, str]]:
    """Return display text and kind pairs for search-target assertions."""

    return {(target.text, target.kind) for target in targets}


def _section_cube_ids_by_title(
    sections: tuple[CubePickerSection, ...],
) -> dict[str, tuple[str, ...]]:
    """Return section entries keyed by section title."""

    return {
        section.title: tuple(entry.cube_id for entry in section.entries)
        for section in sections
    }


def _flatten_model_role_cube_ids(
    sections: tuple[CubePickerModelRoleSection, ...],
) -> tuple[str, ...]:
    """Return cube IDs from nested model-role sections in display order."""

    return tuple(
        entry.cube_id
        for model_section in sections
        for role_section in model_section.role_sections
        for entry in role_section.entries
    )


def _model_role_cube_ids_by_title(
    sections: tuple[CubePickerModelRoleSection, ...],
) -> dict[str, tuple[str, ...]]:
    """Return nested section entries keyed by model section title."""

    return {
        section.title: tuple(
            entry.cube_id
            for role_section in section.role_sections
            for entry in role_section.entries
        )
        for section in sections
    }


__all__ = (
    "CubeCatalogRecord",
    "CubePickerClassification",
    "CubePickerModelRoleSection",
    "CubePickerRole",
    "CubePickerSection",
    "CubeSearchTarget",
    "CubeSearchTerm",
    "CubeSourceMetadata",
    "_classification",
    "_flatten_cube_ids",
    "_flatten_model_role_cube_ids",
    "_model_role_cube_ids_by_title",
    "_record",
    "_section_cube_ids_by_title",
    "_source",
    "_target_pairs",
    "annotations",
    "build_cube_picker_entries",
    "build_cube_picker_model_role_sections",
    "build_cube_picker_sections",
    "build_cube_search_targets",
    "classify_cube_document",
)
