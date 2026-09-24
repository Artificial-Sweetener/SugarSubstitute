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

"""Provide focused Prompt by Region integration boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from substitute.application.ports.cube_repository import (
    CubeCatalogRecord,
    CubeDefinitionRecord,
)
from substitute.domain.common import JsonObject
from substitute.domain.generation import ComfyStagedAsset

CUBE_ID = "Artificial-Sweetener/Base-Cubes/Anima/Prompt by Region.cube"
CUBE_ALIAS = "Anima/Prompt by Region"


class CubeRepository:
    """Return one canonical Prompt by Region cube document."""

    def __init__(self, record: CubeDefinitionRecord) -> None:
        """Store the only available cube definition."""

        self._record = record

    def load_cube(self, cube_id: str) -> CubeDefinitionRecord:
        """Return the requested current cube definition."""

        assert cube_id == CUBE_ID
        return self._record

    def load_cube_version(self, cube_id: str, version: str) -> CubeDefinitionRecord:
        """Return the requested persisted cube version."""

        assert (cube_id, version) == (CUBE_ID, "3.2.0")
        return self._record

    def list_cube_versions(self, cube_id: str) -> tuple[str, ...]:
        """Return the single fixture version."""

        assert cube_id == CUBE_ID
        return ("3.2.0",)

    def prewarm_cube_version(self, cube_id: str, version: str) -> bool:
        """Accept best-effort warming for the available fixture version."""

        return (cube_id, version) == (CUBE_ID, "3.2.0")

    def list_available_cubes(self) -> list[CubeCatalogRecord]:
        """Return the single fixture catalog entry."""

        return [
            CubeCatalogRecord(
                cube_id=CUBE_ID,
                version="3.2.0",
                display_name="Prompt by Region",
            )
        ]


class DefinitionGateway:
    """Expose exact cube-owned node definitions to graph services."""

    def __init__(self, definitions: Mapping[str, JsonObject]) -> None:
        """Store node definitions by class type."""

        self._definitions = definitions

    def get_node_definition(self, node_class: str) -> JsonObject:
        """Return a definition or an empty mapping for unknown classes."""

        return self._definitions.get(node_class, {})

    def get_required_node_definition(self, node_class: str) -> JsonObject:
        """Return a required definition through the same fixture boundary."""

        return self.get_node_definition(node_class)


class Stager:
    """Record exact ordered files crossing the Comfy upload boundary."""

    def __init__(self) -> None:
        """Initialize empty staging history."""

        self.paths: list[Path] = []

    def stage_file_for_load_image(
        self,
        *,
        source_path: Path,
        target_subfolder: str,
        content_hash: str,
        node_class: str,
    ) -> ComfyStagedAsset:
        """Return one deterministic execution value for an existing mask file."""

        assert content_hash
        assert node_class == "SimpleSyrup.LoadMaskBatch"
        self.paths.append(source_path)
        return ComfyStagedAsset(
            source_path=source_path,
            execution_value=f"{target_subfolder}/{source_path.name}",
            operation="uploaded",
        )


__all__ = ["CUBE_ALIAS", "CUBE_ID", "CubeRepository", "DefinitionGateway", "Stager"]
