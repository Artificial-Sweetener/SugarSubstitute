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

"""Adapt restored cube-picker records for update detection."""

from __future__ import annotations

from substitute.application.ports import CubeCatalogRecord, CubeCatalogSnapshot
from substitute.domain.cube_library import (
    CubeCatalog,
    CubeCatalogEntry,
    CubeSourceMetadata,
)


def catalog_from_picker_snapshot(snapshot: CubeCatalogSnapshot) -> CubeCatalog:
    """Convert picker cache records into the update-detection catalog model."""

    return CubeCatalog(
        schema_version=1,
        catalog_revision=snapshot.catalog_revision,
        generated_at="",
        cubes=tuple(_catalog_entry_from_record(record) for record in snapshot.entries),
    )


def _catalog_entry_from_record(record: CubeCatalogRecord) -> CubeCatalogEntry:
    """Convert one picker catalog record into a domain catalog entry."""

    return CubeCatalogEntry(
        cube_id=record.cube_id,
        version=record.version,
        display_name=record.display_name,
        description=record.description,
        source=record.source or CubeSourceMetadata(kind="", path=""),
        content_hash=record.content_hash,
        updated_at=record.updated_at,
        target_model=record.target_model,
        supported_models=record.supported_models,
        icon=record.icon,
    )
