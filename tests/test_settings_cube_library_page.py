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

"""Widget contract tests for the Cube Library Settings page."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any, Protocol, cast

import pytest
from PySide6.QtCore import QObject
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import LineEdit, PushButton  # type: ignore[import-untyped]

from substitute.application.cube_library import (
    CubeDependencyRepairProposal,
    CubeLibraryManagementService,
    CubeLibrarySnapshot,
)
from tests.execution_testing import ImmediateTaskSubmitter
from substitute.domain.cube_library import (
    CubeDependencyRepairResult,
    CubeLibraryReadiness,
    CubeLibraryStatus,
    CubePackPreflight,
    CubePackRecord,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.presentation.settings.cube_library_page import (
    CubeLibraryOperationResult,
    CubeLibrarySettingsPage,
    parse_github_cube_pack_url,
)
from substitute.presentation.settings.settings_async import SettingsAsyncTaskRunner


class _TextLabel(Protocol):
    """Describe the label text surface used by SettingsCard tests."""

    def text(self) -> str:
        """Return the label text."""


class _DescriptionLabelOwner(Protocol):
    """Describe widgets that expose a SettingsCard description label."""

    description_label: _TextLabel


class _TitleLabelOwner(Protocol):
    """Describe widgets that expose a SettingsCard title label."""

    title_label: _TextLabel


if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "settings Qt contract tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _task_runner_factory(
    parent: QObject,
    *,
    owner_id: str,
) -> SettingsAsyncTaskRunner:
    """Create an immediate Settings task runner for Cube Library tests."""

    return SettingsAsyncTaskRunner(
        parent,
        submitter=ImmediateTaskSubmitter(),
        owner_id=owner_id,
    )


def test_cube_library_page_renders_packs_and_selection_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pack rows and direct actions should render without table selection."""

    app = _app()
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    page = CubeLibrarySettingsPage(
        cast(CubeLibraryManagementService, _Service()),
        task_runner_factory=_task_runner_factory,
    )
    snapshot = _snapshot(
        packs=(
            _pack(owner="Owner", repo="Editable", default_base_repo=False),
            _pack(owner="Base", repo="Default", default_base_repo=True),
        ),
        readiness=_readiness(missing_custom_nodes=()),
    )

    page._apply_snapshot(snapshot)
    app.processEvents()

    assert page.rendered_pack_refs() == ("Owner/Editable", "Base/Default")
    assert tuple(page._pack_expanders) == ("Owner/Editable", "Base/Default")
    assert not hasattr(page, "pack_table")
    assert page.readiness_container.findChildren(PushButton) == []
    assert "Required custom nodes are installed." in _description_label_texts(
        page.readiness_container
    )

    editable_remove = _pack_button(page, "Owner/Editable", "Remove")
    default_remove = _pack_button(page, "Base/Default", "Remove")

    assert editable_remove.isEnabled() is True
    assert default_remove.isEnabled() is False
    assert "demo.cube" in _description_label_texts(
        page._pack_expanders["Owner/Editable"].content_widget()
    )
    assert _header_button_texts(page, "Owner/Editable") == []
    page.close()


def test_cube_library_page_renders_missing_readiness_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing readiness should list custom-node names in the page."""

    app = _app()
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    page = CubeLibrarySettingsPage(
        cast(CubeLibraryManagementService, _Service()),
        task_runner_factory=_task_runner_factory,
    )

    page._apply_snapshot(
        _snapshot(
            packs=(),
            readiness=_readiness(missing_custom_nodes=("Impact Pack",)),
        )
    )
    app.processEvents()

    labels = _description_label_texts(page.readiness_container)

    assert "Missing custom nodes: 1" in labels
    assert "Impact Pack" in labels
    page.close()


def test_cube_library_page_renders_empty_state_and_add_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty pack state should offer a focused add-pack action."""

    app = _app()
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    page = CubeLibrarySettingsPage(
        cast(CubeLibraryManagementService, _Service()),
        task_runner_factory=_task_runner_factory,
    )

    page._apply_snapshot(
        _snapshot(packs=(), readiness=_readiness(missing_custom_nodes=()))
    )
    app.processEvents()

    empty_titles = _title_label_texts(page.pack_list)
    assert "No Cube Packs tracked" in empty_titles
    assert page.add_pack_expander.is_expanded() is False

    _pack_list_button(page, "Add Cube Pack").click()
    app.processEvents()

    assert page.add_pack_expander.is_expanded() is False
    assert page.add_pack_expander.has_content_available() is False
    page.close()


def test_cube_library_page_validates_and_adds_github_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adding should parse, validate, sync, and render validation details."""

    app = _app()
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    service = _Service()
    page = CubeLibrarySettingsPage(
        cast(CubeLibraryManagementService, service),
        task_runner_factory=_task_runner_factory,
    )
    page.github_url_edit.setText("https://github.com/Owner/Repo")
    candidate = page._add_pack_candidate()
    assert candidate is not None

    page._validate_and_add_pack(candidate)
    app.processEvents()

    assert page.notification_bar.severity() == "success"
    assert service.preflight_calls == [("Owner", "Repo", "main")]
    assert service.add_calls == [("Owner", "Repo", "main", True)]
    assert page.validation_result_row.isHidden() is False
    assert page.add_pack_expander.has_content_available() is True
    assert page.add_pack_expander.is_expanded() is True
    assert "Owner/Repo" in page.validation_result_row.description_label.text()
    assert "demo.cube" in page.validation_result_row.description_label.text()
    page.close()


def test_cube_library_page_unavailable_snapshot_clears_packs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unavailable snapshots should clear pack rows and show unavailable status."""

    app = _app()
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    page = CubeLibrarySettingsPage(
        cast(CubeLibraryManagementService, _Service()),
        task_runner_factory=_task_runner_factory,
    )

    page._apply_snapshot(None)
    app.processEvents()

    assert page.rendered_pack_refs() == ()
    assert page.status_row.description_label.text() == (
        "Cube Library unavailable on the active target."
    )
    assert page.notification_bar.severity() == "error"
    page.close()


def test_cube_library_page_add_url_enablement_and_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Add controls should require a parseable GitHub repository URL."""

    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    page = CubeLibrarySettingsPage(
        cast(CubeLibraryManagementService, _Service()),
        task_runner_factory=_task_runner_factory,
    )

    page.github_url_edit.setText("")

    assert page.add_button.isEnabled() is False
    assert page.add_pack_expander.has_content_available() is False
    assert page.add_pack_expander.is_expanded() is False

    page.github_url_edit.setText("https://github.com/Owner/Repo")

    assert page._add_pack_candidate() == parse_github_cube_pack_url(
        "https://github.com/Owner/Repo"
    )
    assert page.add_button.isEnabled() is True
    assert page.add_button.text() == "Add"
    assert page.add_pack_expander.header_card.findChildren(LineEdit) == [
        page.github_url_edit
    ]
    page.add_pack_expander.header_card.activated.emit()
    assert page.add_pack_expander.is_expanded() is False
    assert "GitHub URL" not in _title_label_texts(
        page.add_pack_expander.content_widget()
    )
    assert "Add pack" not in _title_label_texts(page.add_pack_expander.content_widget())
    page.close()


def test_cube_library_page_ready_readiness_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready readiness should keep the existing success copy."""

    app = _app()
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    page = CubeLibrarySettingsPage(
        cast(CubeLibraryManagementService, _Service()),
        task_runner_factory=_task_runner_factory,
    )

    page._apply_snapshot(
        _snapshot(packs=(), readiness=_readiness(missing_custom_nodes=()))
    )
    app.processEvents()

    labels = _description_label_texts(page.readiness_container)
    assert "Required custom nodes are installed." in labels
    page.close()


def test_cube_library_page_invokes_pack_service_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Add, preflight, and sync operations should still call the service."""

    _app()
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    service = _Service()
    page = CubeLibrarySettingsPage(
        cast(CubeLibraryManagementService, service),
        task_runner_factory=_task_runner_factory,
    )
    pack = _pack(owner="Owner", repo="Repo", branch="main")

    candidate = parse_github_cube_pack_url("Owner/Repo")
    assert candidate is not None
    page._validate_and_add_pack(candidate)
    page._sync_all()
    page._toggle_enabled(pack, False)
    page._sync_pack(pack)
    page._remove_pack(pack)

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

    _app()
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    presented: list[dict[str, Any]] = []
    page = CubeLibrarySettingsPage(
        cast(CubeLibraryManagementService, _Service()),
        task_runner_factory=_task_runner_factory,
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


def test_cube_library_page_offers_restart_after_dependency_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dependency repair requiring restart should render a restart action."""

    app = _app()
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    restart_service = _RestartService()
    restart_required_changes: list[bool] = []
    post_restart_refreshes: list[object] = []
    page = CubeLibrarySettingsPage(
        cast(CubeLibraryManagementService, _Service()),
        task_runner_factory=_task_runner_factory,
        restart_service=restart_service,
        restart_required_changed=restart_required_changes.append,
        post_restart_refresh=lambda: post_restart_refreshes.append(object()),
    )
    page._apply_snapshot(
        _snapshot(packs=(), readiness=_readiness(missing_custom_nodes=()))
    )

    page._apply_operation_result(
        CubeLibraryOperationResult(
            operation="repair_dependencies",
            success=True,
            severity="success",
            title="Required nodes installed",
            message="Restart ComfyUI before using repaired cube dependencies.",
            payload=_repair_result(restart_required=True),
        )
    )
    app.processEvents()

    restart_button = _readiness_button(page, "Restart Comfy")
    restart_button.click()
    _process_events_until(app, lambda: restart_service.restart_count == 1)

    assert restart_service.restart_count == 1
    assert page.notification_bar.title_label.text() == "Comfy restart requested"
    assert len(post_restart_refreshes) == 1
    assert restart_required_changes == [True]
    page._apply_snapshot(
        _snapshot(packs=(), readiness=_readiness(missing_custom_nodes=()))
    )
    assert restart_required_changes == [True, False]
    page.close()


def test_parse_github_cube_pack_url_accepts_github_urls_and_shorthand() -> None:
    """GitHub pack parser should accept pasted URLs and owner/repo shorthand."""

    assert parse_github_cube_pack_url("https://github.com/Owner/Repo") is not None
    assert parse_github_cube_pack_url("github.com/Owner/Repo.git") is not None
    assert parse_github_cube_pack_url("Owner/Repo") is not None
    assert parse_github_cube_pack_url("https://example.com/Owner/Repo") is None
    assert parse_github_cube_pack_url("https://github.com/Owner") is None


class _Service:
    """Record Cube Library page service calls for widget tests."""

    def __init__(self) -> None:
        """Initialize empty call records."""

        self.preflight_calls: list[tuple[str, str, str]] = []
        self.add_calls: list[tuple[str, str, str, bool]] = []
        self.sync_all_count = 0
        self.enabled_calls: list[tuple[str, str, bool]] = []
        self.sync_calls: list[tuple[str, str]] = []
        self.remove_calls: list[tuple[str, str]] = []
        self.repair_proposals: list[CubeDependencyRepairProposal] = []

    def load_snapshot(self) -> CubeLibrarySnapshot:
        """Return an available empty snapshot."""

        return _snapshot(packs=(), readiness=_readiness(missing_custom_nodes=()))

    def preflight_pack(
        self,
        *,
        owner: str,
        repo: str,
        branch: str = "main",
    ) -> CubePackPreflight:
        """Record one preflight request."""

        self.preflight_calls.append((owner, repo, branch))
        return CubePackPreflight(
            owner=owner,
            repo=repo,
            branch=branch,
            contains_cubes=True,
            cube_count=1,
            cube_paths=("demo.cube",),
            truncated=False,
            checked_via="test",
        )

    def add_pack(
        self,
        *,
        owner: str,
        repo: str,
        branch: str = "main",
        sync_immediately: bool = True,
    ) -> CubePackRecord:
        """Record one add-pack request."""

        self.add_calls.append((owner, repo, branch, sync_immediately))
        return _pack(owner=owner, repo=repo, branch=branch)

    def sync_all_packs(self) -> tuple[CubePackRecord, ...]:
        """Record one sync-all request."""

        self.sync_all_count += 1
        return ()

    def set_pack_enabled(
        self,
        *,
        owner: str,
        repo: str,
        enabled: bool,
    ) -> CubePackRecord:
        """Record one enabled-state update."""

        self.enabled_calls.append((owner, repo, enabled))
        return _pack(owner=owner, repo=repo, default_base_repo=False)

    def sync_pack(self, *, owner: str, repo: str) -> CubePackRecord:
        """Record one selected-pack sync."""

        self.sync_calls.append((owner, repo))
        return _pack(owner=owner, repo=repo)

    def remove_pack(self, *, owner: str, repo: str) -> bool:
        """Record one selected-pack removal."""

        self.remove_calls.append((owner, repo))
        return True

    def dependency_repair_proposal(
        self,
        readiness: object,
    ) -> CubeDependencyRepairProposal | None:
        """Return no repair proposal for basic page tests."""

        _ = readiness
        return None

    def repair_dependency_proposal(
        self,
        proposal: CubeDependencyRepairProposal,
    ) -> None:
        """Record one dependency repair request."""

        self.repair_proposals.append(proposal)


class _RestartService:
    """Record Comfy restart requests from Cube Library tests."""

    def __init__(self) -> None:
        """Initialize empty restart state."""

        self.restart_count = 0

    def restart_comfy(self) -> object:
        """Record and return one fake restart job."""

        self.restart_count += 1
        return object()


class _InlineThread:
    """Run background work synchronously in widget tests."""

    def __init__(self, *, target: Any, daemon: bool = False) -> None:
        """Capture a thread target."""

        _ = daemon
        self._target = target

    def start(self) -> None:
        """Run the target immediately."""

        self._target()


def _snapshot(
    *,
    packs: tuple[CubePackRecord, ...],
    readiness: CubeLibraryReadiness | None,
) -> CubeLibrarySnapshot:
    """Build a Cube Library snapshot for page rendering tests."""

    return CubeLibrarySnapshot(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        status=CubeLibraryStatus(
            schema_version=1,
            available=True,
            source="test",
            catalog_revision="sha256:test",
            pack_management_supported=True,
            local_authoring_supported=False,
            readiness_supported=True,
            errors=(),
        ),
        packs=packs,
        readiness=readiness,
        cube_paths_by_pack={pack.repo_ref: ("demo.cube",) for pack in packs},
    )


def _repair_result(*, restart_required: bool) -> CubeDependencyRepairResult:
    """Build one dependency repair result for page tests."""

    readiness = _readiness(missing_custom_nodes=())
    return CubeDependencyRepairResult(
        schema_version=1,
        readiness_before=readiness,
        attempted_install_plan=(),
        installed_nodes=("node-a",),
        skipped_nodes=(),
        failed_nodes=(),
        readiness_after=readiness,
        restart_required=restart_required,
    )


def _pack(
    *,
    owner: str,
    repo: str,
    branch: str = "main",
    default_base_repo: bool = False,
) -> CubePackRecord:
    """Build a tracked Cube Pack record for page tests."""

    return CubePackRecord(
        repo_ref=f"{owner}/{repo}",
        owner=owner,
        repo=repo,
        branch=branch,
        enabled=True,
        default_base_repo=default_base_repo,
        auto_update=False,
        local_head_sha="local",
        remote_head_sha="remote",
        update_available=False,
        last_sync_at="",
        last_sync_status="clean",
        last_sync_error="",
        last_checked_at="",
        last_check_status="clean",
        last_check_error="",
        cube_count=1,
    )


def _readiness(
    *,
    missing_custom_nodes: tuple[str, ...],
) -> CubeLibraryReadiness:
    """Build target custom-node readiness for page rendering tests."""

    return CubeLibraryReadiness(
        schema_version=1,
        ready=not missing_custom_nodes,
        required_custom_nodes=("node-a",),
        missing_custom_nodes=missing_custom_nodes,
        installed_custom_nodes=(),
        can_install=False,
        install_supported=False,
        catalog_revision="sha256:test",
        errors=(),
    )


def _pack_button(
    page: CubeLibrarySettingsPage,
    repo_ref: str,
    text: str,
) -> PushButton:
    """Return one button from a rendered pack expander."""

    expander = page._pack_expanders[repo_ref]
    for button in expander.content_widget().findChildren(PushButton):
        if button.text() == text:
            return button
    raise AssertionError(f"button {text!r} not found for {repo_ref}")


def _header_button_texts(page: CubeLibrarySettingsPage, repo_ref: str) -> list[str]:
    """Return visible push-button texts from one pack expander header."""

    expander = page._pack_expanders[repo_ref]
    return [button.text() for button in expander.header_card.findChildren(PushButton)]


def _pack_list_button(page: CubeLibrarySettingsPage, text: str) -> PushButton:
    """Return one button from the rendered pack list."""

    for button in page.pack_list.findChildren(PushButton):
        if button.text() == text:
            return button
    raise AssertionError(f"button {text!r} not found")


def _readiness_button(page: CubeLibrarySettingsPage, text: str) -> PushButton:
    """Return one button from the readiness section."""

    for button in page.readiness_container.findChildren(PushButton):
        if button.text() == text:
            return button
    raise AssertionError(f"button {text!r} not found")


def _description_label_texts(parent: QWidget) -> list[str]:
    """Return text from descendant widgets with description labels."""

    texts: list[str] = []
    for widget in parent.findChildren(QWidget):
        if hasattr(widget, "description_label"):
            owner = cast(_DescriptionLabelOwner, widget)
            texts.append(owner.description_label.text())
    return texts


def _title_label_texts(parent: QWidget) -> list[str]:
    """Return text from descendant widgets with title labels."""

    texts: list[str] = []
    for widget in parent.findChildren(QWidget):
        if hasattr(widget, "title_label"):
            owner = cast(_TitleLabelOwner, widget)
            texts.append(owner.title_label.text())
    return texts


def _app() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _process_events_until(
    app: QApplication,
    condition: Callable[[], bool],
    *,
    timeout_ms: int = 1000,
) -> None:
    """Process Qt events until one asynchronous widget condition is true."""

    deadline = time.perf_counter() + (timeout_ms / 1000.0)
    while time.perf_counter() < deadline:
        app.processEvents()
        if condition():
            return
        QTest.qWait(10)
    app.processEvents()
    assert condition()
