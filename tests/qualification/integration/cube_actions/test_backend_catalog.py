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

"""Qualify backend catalog translation through cube-picker presentation."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from substitute.application.cubes import CubeLoadService
from substitute.application.ports import CubeCatalogRecord
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.cubes import BackendCubeRepository
from substitute.infrastructure.external import SubstituteBackendCubeLibraryClient
from tests.presentation.shell.cube_actions.support import _CubeStack, _import_module


@dataclass(frozen=True, slots=True)
class _CatalogResponse:
    """Return one representative successful backend catalog response."""

    payload: dict[str, object]

    def raise_for_status(self) -> None:
        """Accept the configured successful response."""

    def json(self) -> object:
        """Return the configured catalog payload."""

        return self.payload


def test_backend_catalog_opens_cube_picker_with_translated_records() -> None:
    """Translate a backend payload through the real client and repository owners."""

    requested_urls: list[str] = []

    def get_catalog(url: str, **_kwargs: object) -> _CatalogResponse:
        """Capture the client route and return deterministic catalog metadata."""

        requested_urls.append(url)
        payload = _artifact_payload() if "/cubes/load?" in url else _catalog_payload()
        return _CatalogResponse(payload)

    client = SubstituteBackendCubeLibraryClient(
        ComfyEndpoint(host="127.0.0.1", port=8188),
        http_get=get_catalog,
        timeout_seconds=1.0,
    )
    cube_load_service = CubeLoadService(BackendCubeRepository(client=client))
    presented: list[dict[str, Any]] = []
    view = SimpleNamespace(
        active_cube_stack=_CubeStack(),
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-catalog"),
        cube_icon_factory=object(),
        cube_load_service=cube_load_service,
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )
    actions = _import_module().WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
        error_presenter=SimpleNamespace(
            show_exception_report=lambda **kwargs: presented.append(kwargs)
        ),
    )

    class _Picker:
        """Capture the records presented by the integrated catalog path."""

        records: list[CubeCatalogRecord] = []

        @staticmethod
        def select_cube(**kwargs: object) -> CubeCatalogRecord | None:
            """Capture catalog records without selecting a cube."""

            records = kwargs["records"]
            assert isinstance(records, list)
            _Picker.records = records
            return None

    actions.show_cube_picker(cube_picker=_Picker)

    assert presented == []
    assert [(record.cube_id, record.display_name) for record in _Picker.records] == [
        ("Artificial-Sweetener/Base/demo.cube", "Demo Cube")
    ]
    assert requested_urls == [
        "http://127.0.0.1:8188/substitute/v1/cube-library/catalog",
        "http://127.0.0.1:8188/substitute/v1/cube-library/cubes/load?"
        "cubeId=Artificial-Sweetener%2FBase%2Fdemo.cube",
    ]


def _catalog_payload() -> dict[str, object]:
    """Return representative Cube Library catalog JSON."""

    return {
        "schemaVersion": 1,
        "catalogRevision": "sha256:catalog",
        "generatedAt": "2026-08-24T00:00:00Z",
        "cubes": [
            {
                "cubeId": "Artificial-Sweetener/Base/demo.cube",
                "version": "1.0.0",
                "displayName": "Demo Cube",
                "description": "Representative picker qualification cube.",
                "source": {
                    "kind": "git",
                    "owner": "Artificial-Sweetener",
                    "repo": "Base",
                    "branch": "main",
                    "path": "demo.cube",
                },
                "contentHash": "sha256:cube",
                "updatedAt": "2026-08-24T00:00:00Z",
                "supportedModels": ["sdxl"],
            }
        ],
    }


def _artifact_payload() -> dict[str, object]:
    """Return the catalog entry's loadable cube artifact JSON."""

    return {
        "schemaVersion": 1,
        "cubeId": "Artificial-Sweetener/Base/demo.cube",
        "version": "1.0.0",
        "displayName": "Demo Cube",
        "contentHash": "sha256:cube",
        "source": {
            "kind": "git",
            "owner": "Artificial-Sweetener",
            "repo": "Base",
            "branch": "main",
            "path": "demo.cube",
        },
        "cube": {
            "schema_version": 1,
            "cube_id": "Artificial-Sweetener/Base/demo.cube",
            "version": "1.0.0",
            "nodes": {},
        },
    }
