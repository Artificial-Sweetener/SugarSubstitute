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

"""Tests for version-first cube loading service behavior."""

from __future__ import annotations

from pathlib import Path

from substitute.application.cubes import CubeLoadService
from substitute.application.ports.cube_repository import (
    CubeCatalogRecord,
    CubeDefinitionRecord,
)
from substitute.domain.cube_library import CubeSourceMetadata


class _Repository:
    """Repository double that supports latest and versioned cube loads."""

    def __init__(self) -> None:
        """Initialize call tracking."""

        self.latest_loads: list[str] = []
        self.version_loads: list[tuple[str, str]] = []

    def load_cube(self, cube_id: str) -> CubeDefinitionRecord:
        """Return the latest cube definition."""

        self.latest_loads.append(cube_id)
        return _record(cube_id=cube_id, version="2.0")

    def load_cube_version(self, cube_id: str, version: str) -> CubeDefinitionRecord:
        """Return a versioned cube definition."""

        self.version_loads.append((cube_id, version))
        return _record(cube_id=cube_id, version=version)

    def list_cube_versions(self, cube_id: str) -> tuple[str, ...]:
        """Return available versions."""

        _ = cube_id
        return ("2.0", "1.0")

    def list_available_cubes(self) -> list[CubeCatalogRecord]:
        """Return picker records."""

        return [
            CubeCatalogRecord(
                cube_id="Owner/Repo/demo.cube",
                version="2.0",
                display_name="Demo",
            )
        ]


def test_load_cube_definition_version_uses_repository_version_loader() -> None:
    """Versioned loads should call the version repository port."""

    repository = _Repository()
    service = CubeLoadService(repository)

    loaded = service.load_cube_definition_version("Owner/Repo/demo.cube", "1.0")

    assert repository.version_loads == [("Owner/Repo/demo.cube", "1.0")]
    assert loaded.cube_id == "Owner/Repo/demo.cube"
    assert loaded.version == "1.0"
    assert loaded.ui_payload is not None
    assert "definition_ref" not in loaded.ui_payload


def test_load_cube_definition_version_reuses_latest_definition_cache() -> None:
    """A warmed latest definition should satisfy matching versioned restore loads."""

    repository = _Repository()
    service = CubeLoadService(repository)

    service.load_cube_definition("Owner/Repo/demo.cube")
    loaded = service.load_cube_definition_version("Owner/Repo/demo.cube", "2.0")

    assert repository.latest_loads == ["Owner/Repo/demo.cube"]
    assert repository.version_loads == []
    assert loaded.version == "2.0"


def test_load_cube_definition_version_writes_version_cache() -> None:
    """Repeated versioned loads should not repeat repository fetches."""

    repository = _Repository()
    service = CubeLoadService(repository)

    first = service.load_cube_definition_version("Owner/Repo/demo.cube", "1.0")
    second = service.load_cube_definition_version("Owner/Repo/demo.cube", "1.0")

    assert repository.version_loads == [("Owner/Repo/demo.cube", "1.0")]
    assert first.version == "1.0"
    assert second.version == "1.0"


def test_create_cube_state_persists_version_without_definition_ref() -> None:
    """Runtime cube state should carry cube id and version only."""

    service = CubeLoadService(_Repository())

    state = service.create_cube_state(
        cube_id="Owner/Repo/demo.cube",
        version="1.0",
        display_name="Demo",
        alias_name="Demo",
        cube_definition={"nodes": {}},
        cube_buffer={"nodes": {}},
        ui_payload={"catalog_revision": "rev"},
    )

    assert state.cube_id == "Owner/Repo/demo.cube"
    assert state.version == "1.0"
    assert state.ui == {"catalog_revision": "rev"}


def test_list_cube_versions_delegates_to_repository() -> None:
    """The service should expose version listing for the update modal."""

    service = CubeLoadService(_Repository())

    assert service.list_cube_versions("Owner/Repo/demo.cube") == ("2.0", "1.0")


def _record(*, cube_id: str, version: str) -> CubeDefinitionRecord:
    """Build a canonical cube definition record."""

    return CubeDefinitionRecord(
        cube_id=cube_id,
        version=version,
        display_name="Demo",
        graph={
            "cube_id": cube_id,
            "version": version,
            "implementation": {
                "nodes": {"noop": {"class_type": "NoOp", "inputs": {}}},
                "inputs": {},
                "outputs": {},
                "layout": {},
                "definitions": {},
                "subgraphs": [],
            },
            "surface": {"default_flavor_id": "default", "controls": []},
            "flavors": {
                "authored": [{"id": "default", "name": "Default", "values": {}}]
            },
        },
        content_hash="sha256:diagnostic",
        source=CubeSourceMetadata(kind="local", path="demo.cube"),
        artifact_label="demo",
        local_path=Path("E:/cubes/demo.cube"),
    )
