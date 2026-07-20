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

"""Contract tests for Cube Library management workflows."""

from __future__ import annotations

from typing import cast

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.cube_library import CubeLibraryManagementService
from substitute.application.ports import CubeLibraryClient
from substitute.domain.cube_library import (
    CubeCatalog,
    CubeCatalogEntry,
    CubeSourceMetadata,
)
from substitute.domain.onboarding import ComfyEndpoint


class _CatalogOnlyClient:
    """Provide catalog data for recipe drift diagnostics tests."""

    def __init__(self, catalog: CubeCatalog | None) -> None:
        """Store the catalog returned to the management service."""

        self.catalog = catalog

    def get_catalog(self) -> CubeCatalog | None:
        """Return the configured catalog."""

        return self.catalog


def test_recipe_drift_messages_report_missing_and_current_dirty_cubes() -> None:
    """Recipe diagnostics should report catalog-backed cube availability notices."""

    service = CubeLibraryManagementService(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        client=cast(
            CubeLibraryClient,
            _CatalogOnlyClient(
                CubeCatalog(
                    schema_version=1,
                    catalog_revision="sha256:catalog",
                    generated_at="2026-05-03T00:00:00Z",
                    cubes=(
                        CubeCatalogEntry(
                            cube_id="Owner/Repo/changed.cube",
                            version="1.0.0",
                            display_name="Changed",
                            description="",
                            source=CubeSourceMetadata(
                                kind="github",
                                repo_ref="Owner/Repo",
                                path="changed.cube",
                                dirty=True,
                            ),
                            content_hash="sha256:new",
                        ),
                    ),
                )
            ),
        ),
    )

    messages = service.recipe_drift_messages(
        {
            "Changed": {
                "cube_id": "Owner/Repo/changed.cube",
            },
            "Missing": {
                "cube_id": "Owner/Repo/missing.cube",
            },
        }
    )

    assert tuple(render_source_application_text(message) for message in messages) == (
        "Cube 'Changed' (Owner/Repo/changed.cube) currently has uncommitted Cube Library changes.",
        "Cube 'Missing' (Owner/Repo/missing.cube) is not available in the active Cube Library.",
    )


def test_recipe_drift_messages_return_empty_when_catalog_unavailable() -> None:
    """Recipe diagnostics should stay quiet when the target catalog cannot be fetched."""

    service = CubeLibraryManagementService(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        client=cast(CubeLibraryClient, _CatalogOnlyClient(None)),
    )

    assert (
        service.recipe_drift_messages(
            {
                "Cube": {
                    "cube_id": "Owner/Repo/cube.cube",
                }
            }
        )
        == ()
    )
