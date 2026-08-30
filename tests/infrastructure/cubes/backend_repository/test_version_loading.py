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

"""Verify selected-version loading through the backend Cube repository."""

from __future__ import annotations

from typing import cast

from substitute.application.ports import CubeLibraryClient
from substitute.domain.common import JsonObject
from substitute.domain.cube_library import CubeSourceMetadata, LoadedCubeArtifact
from substitute.infrastructure.cubes.backend_cube_repository import (
    BackendCubeRepository,
)


class _VersionLoadingClient:
    """Provide the selected-version boundary required by this repository test."""

    def __init__(self) -> None:
        """Initialize selected-version call tracking."""

        self.version_loads: list[tuple[str, str]] = []

    def load_cube_version(
        self,
        cube_id: str,
        version: str,
    ) -> LoadedCubeArtifact:
        """Return one artifact for the requested version."""

        self.version_loads.append((cube_id, version))
        return LoadedCubeArtifact(
            cube_id=cube_id,
            version=version,
            display_name="Demo",
            content_hash="sha256:diagnostic",
            source=CubeSourceMetadata(kind="local", path="demo.cube"),
            cube=cast(
                JsonObject,
                {"cube_id": cube_id, "version": version, "nodes": {}},
            ),
        )


def test_backend_repository_loads_versioned_record() -> None:
    """Expose selected-version loading through the application repository port."""

    client = _VersionLoadingClient()
    repository = BackendCubeRepository(client=cast(CubeLibraryClient, client))

    record = repository.load_cube_version("Owner/Repo/demo.cube", "2.0")

    assert client.version_loads == [("Owner/Repo/demo.cube", "2.0")]
    assert record.cube_id == "Owner/Repo/demo.cube"
    assert record.version == "2.0"
    assert record.graph["cube_id"] == "Owner/Repo/demo.cube"
