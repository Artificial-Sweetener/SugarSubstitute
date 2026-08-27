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

"""Test Cube Library command routing and failure presentation."""

from __future__ import annotations

from typing import Any

import pytest

from substitute.presentation.settings.cube_library_page import (
    CubeLibraryOperationResult,
    parse_github_cube_pack_url,
)
from tests.presentation.settings.cube_library.support import (
    FakeCubeLibraryService,
    build_page,
    pack,
)


def test_cube_library_page_invokes_pack_service_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Add, preflight, and sync operations should still call the service."""

    service = FakeCubeLibraryService()
    page = build_page(monkeypatch, service=service)
    pack_record = pack(owner="Owner", repo="Repo", branch="main")

    candidate = parse_github_cube_pack_url("Owner/Repo")
    assert candidate is not None
    page._validate_and_add_pack(candidate)
    page._sync_all()
    page._toggle_enabled(pack_record, False)
    page._sync_pack(pack_record)
    page._remove_pack(pack_record)

    assert service.preflight_calls == [("Owner", "Repo", "main")]
    assert service.add_calls == [("Owner", "Repo", "main", True)]
    assert service.sync_all_count == 1
    assert service.enabled_calls == [("Owner", "Repo", False)]
    assert service.sync_calls == [("Owner", "Repo")]
    assert service.remove_calls == [("Owner", "Repo")]
    page.close()


def test_cube_library_page_reports_exception_results_through_presenter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exception-backed operation results should open the unified error modal."""

    presented: list[dict[str, Any]] = []
    page = build_page(
        monkeypatch,
        error_presenter=type(
            "_Presenter",
            (),
            {"show_exception_report": lambda _self, **kwargs: presented.append(kwargs)},
        )(),
    )
    failure = RuntimeError("sync failed")

    page._apply_operation_result(
        CubeLibraryOperationResult(
            operation="sync",
            success=False,
            severity="error",
            title="Cube Pack sync failed",
            message="Could not sync Owner/Repo.",
            owner="Owner",
            repo="Repo",
            branch="main",
            error=failure,
        )
    )

    assert presented[0]["title"] == "Cube Pack sync failed"
    assert presented[0]["stage"] == "settings"
    assert presented[0]["error"] is failure
    context = presented[0]["context"]
    assert context.operation == "cube_library.sync"
    assert context.package_name == "Owner/Repo"
    assert context.values["branch"] == "main"
    assert page.notification_bar.severity() == "error"
    page.close()
