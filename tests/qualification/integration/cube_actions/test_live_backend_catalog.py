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

"""Qualify cube-picker catalog presentation against a live local backend."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from substitute.application.cubes import CubeLoadService
from substitute.application.ports import CubeCatalogRecord
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.cubes import BackendCubeRepository
from substitute.infrastructure.external import SubstituteBackendCubeLibraryClient
from tests.presentation.shell.cube_actions.support import _CubeStack, _import_module


def test_show_cube_picker_live_backend_catalog_opens_with_records() -> None:
    """Present records supplied by a ready live Substitute BackEnd catalog."""
    mod = _import_module()
    stack = _CubeStack()
    endpoint = ComfyEndpoint(host="127.0.0.1", port=8188)
    client = SubstituteBackendCubeLibraryClient(endpoint, timeout_seconds=10.0)
    catalog = client.get_catalog()
    if catalog is None or not catalog.cubes:
        pytest.skip("Substitute BackEnd has not published a cube catalog on port 8188.")
    cube_load_service = CubeLoadService(BackendCubeRepository(client=client))
    presented: list[dict[str, Any]] = []
    view = SimpleNamespace(
        active_cube_stack=stack,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-live"),
        cube_icon_factory=object(),
        cube_load_service=cube_load_service,
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
        error_presenter=SimpleNamespace(
            show_exception_report=lambda **kwargs: presented.append(kwargs)
        ),
    )

    class _Picker:
        """Capture records passed into the live catalog picker."""

        records: list[CubeCatalogRecord] = []

        @staticmethod
        def select_cube(**kwargs: object) -> CubeCatalogRecord | None:
            """Capture the available records without selecting one."""
            records = kwargs["records"]
            assert isinstance(records, list)
            _Picker.records = records
            return None

    actions.show_cube_picker(cube_picker=_Picker)

    assert presented == []
    assert _Picker.records
    assert any(record.cube_id for record in _Picker.records)
