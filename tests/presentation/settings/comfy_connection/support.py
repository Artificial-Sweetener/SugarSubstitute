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

"""Provide deterministic fixtures for Comfy connection settings tests."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap.settings_execution import (
    create_settings_task_runner_factory,
)
from substitute.application.onboarding import (
    ComfyConnectionSaveResult,
    ComfyConnectionSettingsDraft,
    ComfyConnectionSettingsService,
    ComfyConnectionSettingsSnapshot,
)
from substitute.application.restart_requirements import (
    RestartRequirementItem,
    RestartRequirementSnapshot,
    RestartScope,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
)
from substitute.presentation.settings.comfy_connection_page import (
    ComfyConnectionSettingsPage,
)
from substitute.presentation.settings.settings_async import (
    SettingsAsyncTaskRunner,
    SettingsAsyncTaskRunnerFactory,
)
from substitute.presentation.shell.shell_resource_lifecycle import (
    ShellResourceLifecycle,
)
from tests.support.execution.runtime_support import ExecutionRuntimeStub
from tests.support.execution import ImmediateTaskSubmitter


class FakeComfyConnectionService:
    """Record service calls and return configurable deterministic results."""

    def __init__(
        self,
        target: ComfyTargetConfiguration,
        *,
        block_load: bool = False,
    ) -> None:
        """Store the snapshot target and optional load barrier."""

        self.target = target
        self.saved_drafts: list[ComfyConnectionSettingsDraft] = []
        self.test_calls: list[tuple[str, int]] = []
        self.save_succeeds = True
        self.test_succeeds = True
        self.load_started = threading.Event()
        self.load_release = threading.Event() if block_load else None
        self.load_finished = False

    def load_snapshot(self) -> ComfyConnectionSettingsSnapshot:
        """Return the current snapshot after an optional explicit release."""

        self.load_started.set()
        if self.load_release is not None:
            if not self.load_release.wait(timeout=5.0):
                raise TimeoutError("Comfy connection snapshot load was not released.")
        self.load_finished = True
        workspace = self.target.workspace_path
        managed_model_root = (
            str(workspace / "models") if workspace is not None else "/srv/comfy/models"
        )
        return ComfyConnectionSettingsSnapshot(
            target=self.target,
            persisted_exists=True,
            status_message=(
                "Substitute is configured to use test ComfyUI at "
                f"{self.target.endpoint.host}:{self.target.endpoint.port}."
            ),
            can_test_endpoint=True,
            managed_model_root=managed_model_root,
            active_managed_model_root=managed_model_root,
            default_managed_model_root=managed_model_root,
            model_root_management_available=True,
        )

    def save_draft(
        self,
        draft: ComfyConnectionSettingsDraft,
    ) -> ComfyConnectionSaveResult:
        """Record one save and optionally update the snapshot target."""

        self.saved_drafts.append(draft)
        if not self.save_succeeds:
            return ComfyConnectionSaveResult(
                target=None,
                succeeded=False,
                message="Save failed.",
                restart_required=False,
            )
        self.target = target_from_draft(draft)
        return ComfyConnectionSaveResult(
            target=self.target,
            succeeded=True,
            message="Saved. Restart Substitute to use the new ComfyUI connection.",
            restart_required=True,
            restart_snapshot=RestartRequirementSnapshot(
                items=(
                    RestartRequirementItem(
                        key="comfy.connection",
                        label="ComfyUI connection",
                        active_value="A",
                        saved_value="B",
                        scope=RestartScope.FULL_APP,
                    ),
                ),
                required_scope=RestartScope.FULL_APP,
            ),
        )

    def test_endpoint(self, host: str, port: int) -> ComfyConnectionSaveResult:
        """Record one endpoint test without changing saved state."""

        self.test_calls.append((host, port))
        if not self.test_succeeds:
            return ComfyConnectionSaveResult(
                target=None,
                succeeded=False,
                message=f"ComfyUI did not respond at {host.strip()}:{port}.",
                restart_required=False,
            )
        return ComfyConnectionSaveResult(
            target=None,
            succeeded=True,
            message=f"ComfyUI responded at {host.strip()}:{port}.",
            restart_required=False,
        )


class ThreadedRunnerFactory:
    """Create and retain one runtime-backed runner for signal observation."""

    def __init__(self) -> None:
        """Prepare an isolated runtime and lifecycle for one page."""

        self._runtime = ExecutionRuntimeStub()
        self._lifecycle = ShellResourceLifecycle()
        self._factory = create_settings_task_runner_factory(
            self._runtime,
            resource_lifecycle=self._lifecycle,
        )
        self.runner: SettingsAsyncTaskRunner | None = None

    def __call__(
        self,
        parent: QObject,
        *,
        owner_id: str,
    ) -> SettingsAsyncTaskRunner:
        """Create and retain the page-owned runner."""

        self.runner = self._factory(parent, owner_id=owner_id)
        return self.runner

    def shutdown(self) -> None:
        """Release the isolated execution lane."""

        self._lifecycle.shutdown_or_raise()


def application() -> QApplication:
    """Return the active QApplication instance."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def immediate_task_runner_factory(
    parent: QObject,
    *,
    owner_id: str,
) -> SettingsAsyncTaskRunner:
    """Create an immediate Settings task runner for page tests."""

    return SettingsAsyncTaskRunner(
        parent,
        submitter=ImmediateTaskSubmitter(),
        owner_id=owner_id,
    )


def build_page(
    tmp_path: Path,
    *,
    open_reconfigure_window: Callable[[], object] | None = None,
    service: FakeComfyConnectionService | None = None,
    task_runner_factory: SettingsAsyncTaskRunnerFactory = immediate_task_runner_factory,
    show_restart_requirements: Callable[[], None] | None = None,
) -> ComfyConnectionSettingsPage:
    """Create a loaded Comfy connection page with explicit collaborators."""

    application()
    callback = open_reconfigure_window or (lambda: object())
    page_service = service or FakeComfyConnectionService(managed_target(tmp_path))
    return ComfyConnectionSettingsPage(
        service=cast(ComfyConnectionSettingsService, page_service),
        open_reconfigure_window=callback,
        task_runner_factory=task_runner_factory,
        show_restart_requirements=show_restart_requirements,
    )


def managed_target(tmp_path: Path) -> ComfyTargetConfiguration:
    """Build a managed-local target for page tests."""

    return ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=tmp_path / "comfyui",
        install_owned=True,
        launch_owned=True,
    )


def target_from_draft(
    draft: ComfyConnectionSettingsDraft,
) -> ComfyTargetConfiguration:
    """Build a target from a saved test draft."""

    endpoint = ComfyEndpoint(host=draft.host.strip(), port=draft.port)
    if draft.mode is ComfyTargetMode.MANAGED_LOCAL:
        return ComfyTargetConfiguration(
            mode=draft.mode,
            endpoint=endpoint,
            workspace_path=draft.managed_workspace_path,
            install_owned=True,
            launch_owned=True,
        )
    if draft.mode is ComfyTargetMode.ATTACHED_LOCAL:
        return ComfyTargetConfiguration(
            mode=draft.mode,
            endpoint=endpoint,
            workspace_path=draft.attached_workspace_path,
            install_owned=False,
            launch_owned=True,
        )
    return ComfyTargetConfiguration(
        mode=draft.mode,
        endpoint=endpoint,
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )


__all__ = [
    "FakeComfyConnectionService",
    "ThreadedRunnerFactory",
    "application",
    "build_page",
    "immediate_task_runner_factory",
    "managed_target",
]
