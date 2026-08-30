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
    FakeRestartService,
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
    restart_service = FakeRestartService()
    restart_required_changes: list[bool] = []
    post_restart_refreshes: list[object] = []
    page = build_page(
        monkeypatch,
        restart_service=restart_service,
        restart_required_changed=restart_required_changes.append,
        post_restart_refresh=lambda: post_restart_refreshes.append(object()),
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

    assert restart_service.restart_count == 1
    assert page.notification_bar.title_label.text() == "Comfy restart requested"
    assert len(post_restart_refreshes) == 1
    assert restart_required_changes == [True]
    page._apply_snapshot(
        snapshot(packs=(), readiness=readiness(missing_custom_nodes=()))
    )
    assert restart_required_changes == [True, False]
    page.close()
