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

"""Provide deterministic fixtures for Cube Library Settings tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import PushButton  # type: ignore[import-untyped]

from substitute.application.cube_library import (
    CubeDependencyRepairProposal,
    CubeLibraryManagementService,
    CubeLibrarySnapshot,
)
from substitute.domain.cube_library import (
    CubeDependencyRepairResult,
    CubeLibraryReadiness,
    CubeLibraryStatus,
    CubePackPreflight,
    CubePackRecord,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.presentation.settings.cube_library_page import (
    ComfyRestartService,
    CubeLibrarySettingsPage,
)
from substitute.presentation.settings.settings_async import SettingsAsyncTaskRunner
from tests.support.execution import ImmediateTaskSubmitter


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


def immediate_task_runner_factory(
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


class FakeCubeLibraryService:
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

        return snapshot(packs=(), readiness=readiness(missing_custom_nodes=()))

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
        return pack(owner=owner, repo=repo, branch=branch)

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
        return pack(owner=owner, repo=repo, default_base_repo=False)

    def sync_pack(self, *, owner: str, repo: str) -> CubePackRecord:
        """Record one selected-pack sync."""

        self.sync_calls.append((owner, repo))
        return pack(owner=owner, repo=repo)

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


class FakeRestartService:
    """Record Comfy restart requests from Cube Library tests."""

    def __init__(self) -> None:
        """Initialize empty restart state."""

        self.restart_count = 0

    def restart_comfy(self) -> object:
        """Record and return one fake restart job."""

        self.restart_count += 1
        return object()


def snapshot(
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


def repair_result(*, restart_required: bool) -> CubeDependencyRepairResult:
    """Build one dependency repair result for page tests."""

    readiness_snapshot = readiness(missing_custom_nodes=())
    return CubeDependencyRepairResult(
        schema_version=1,
        readiness_before=readiness_snapshot,
        attempted_install_plan=(),
        installed_nodes=("node-a",),
        skipped_nodes=(),
        failed_nodes=(),
        readiness_after=readiness_snapshot,
        restart_required=restart_required,
    )


def pack(
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


def readiness(
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


def pack_button(
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


def header_button_texts(page: CubeLibrarySettingsPage, repo_ref: str) -> list[str]:
    """Return visible push-button texts from one pack expander header."""

    expander = page._pack_expanders[repo_ref]
    return [button.text() for button in expander.header_card.findChildren(PushButton)]


def pack_list_button(page: CubeLibrarySettingsPage, text: str) -> PushButton:
    """Return one button from the rendered pack list."""

    for button in page.pack_list.findChildren(PushButton):
        if button.text() == text:
            return button
    raise AssertionError(f"button {text!r} not found")


def readiness_button(page: CubeLibrarySettingsPage, text: str) -> PushButton:
    """Return one button from the readiness section."""

    for button in page.readiness_container.findChildren(PushButton):
        if button.text() == text:
            return button
    raise AssertionError(f"button {text!r} not found")


def description_label_texts(parent: QWidget) -> list[str]:
    """Return text from descendant widgets with description labels."""

    texts: list[str] = []
    for widget in parent.findChildren(QWidget):
        if hasattr(widget, "description_label"):
            owner = cast(_DescriptionLabelOwner, widget)
            texts.append(owner.description_label.text())
    return texts


def title_label_texts(parent: QWidget) -> list[str]:
    """Return text from descendant widgets with title labels."""

    texts: list[str] = []
    for widget in parent.findChildren(QWidget):
        if hasattr(widget, "title_label"):
            owner = cast(_TitleLabelOwner, widget)
            texts.append(owner.title_label.text())
    return texts


def application() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def build_page(
    monkeypatch: pytest.MonkeyPatch,
    *,
    service: FakeCubeLibraryService | None = None,
    restart_service: ComfyRestartService | None = None,
    restart_required_changed: Callable[[bool], None] | None = None,
    post_restart_refresh: Callable[[], None] | None = None,
    error_presenter: ErrorReportPresenterProtocol | None = None,
) -> CubeLibrarySettingsPage:
    """Create a page whose successful commands retain their rendered state."""

    application()
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    page_service = service or FakeCubeLibraryService()
    return CubeLibrarySettingsPage(
        cast(CubeLibraryManagementService, page_service),
        task_runner_factory=immediate_task_runner_factory,
        restart_service=restart_service,
        restart_required_changed=restart_required_changed,
        post_restart_refresh=post_restart_refresh,
        error_presenter=error_presenter,
    )


__all__ = [
    "FakeCubeLibraryService",
    "FakeRestartService",
    "application",
    "build_page",
    "description_label_texts",
    "header_button_texts",
    "pack",
    "pack_button",
    "pack_list_button",
    "readiness",
    "readiness_button",
    "repair_result",
    "snapshot",
    "title_label_texts",
]
