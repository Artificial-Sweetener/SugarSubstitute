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

"""Test Cube Library dependency-repair restart coordination."""

from __future__ import annotations


import pytest

from substitute.presentation.settings.cube_library_page import (
    CubeLibraryOperationResult,
)
from tests.presentation.settings.cube_library.support import (
    application,
    build_page,
    readiness,
    readiness_button,
    repair_result,
    snapshot,
)


def test_cube_library_page_offers_restart_after_dependency_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dependency repair requiring restart should render a restart action."""

    app = application()
    restart_requests: list[object] = []
    restart_required_changes: list[bool] = []
    page = build_page(
        monkeypatch,
        restart_requested=lambda: restart_requests.append(object()),
        restart_required_changed=restart_required_changes.append,
    )
    page._apply_snapshot(
        snapshot(packs=(), readiness=readiness(missing_custom_nodes=()))
    )

    page._apply_operation_result(
        CubeLibraryOperationResult(
            operation="repair_dependencies",
            success=True,
            severity="success",
            title="Required nodes installed",
            message="Restart ComfyUI before using repaired cube dependencies.",
            payload=repair_result(restart_required=True),
        )
    )
    app.processEvents()

    restart_button = readiness_button(page, "Restart Comfy")
    restart_button.click()

    assert len(restart_requests) == 1
    assert restart_required_changes == [True]
    page._apply_snapshot(
        snapshot(packs=(), readiness=readiness(missing_custom_nodes=()))
    )
    assert restart_required_changes == [True]
    page.close()
