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

"""Provide deterministic launcher-window workflow test boundaries."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from launcher.sugarsubstitute_launcher.application.installation.workflow import (
    InstallationWorkflow,
)
from launcher.sugarsubstitute_launcher.first_run import FirstRunInstaller
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.installer import LayoutInstaller
from launcher.sugarsubstitute_launcher.release_sources import GitHubReleaseSource
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from tests.support.qt.semantic_wait import wait_for_qt_condition, wait_for_qt_signal


def wait_for_launcher_condition(
    application: QApplication,
    predicate: Callable[[], bool],
    *,
    timeout_seconds: float = 5.0,
) -> None:
    """Wait until observable launcher state proves background work completed."""

    _ = application
    wait_for_qt_condition(predicate, timeout_ms=round(timeout_seconds * 1000))


def close_and_delete_launcher_window(window: LauncherMainWindow) -> None:
    """Close one launcher window after its workers finish and confirm deletion."""

    wait_for_qt_condition(
        lambda: (
            not window.execution.initial_running and not window.execution.setup_running
        )
    )
    destroyed = QSignalSpy(window.destroyed)
    window.close()
    window.deleteLater()
    wait_for_qt_signal(destroyed)


def release_source_for_test() -> GitHubReleaseSource:
    """Return a non-networking source identity for launcher window tests."""

    return GitHubReleaseSource("https://example.invalid/manifest.json")


class _UnusedRuntimeProvisioner:
    """Provide a runtime result for tests that do not exercise provisioning."""

    def provision(self, *, layout: InstallLayout) -> object:
        """Return the runtime path without performing installation work."""

        return SimpleNamespace(python_executable=layout.runtime_python)


def workflow_factory(
    *,
    layout_preparer: object | None = None,
    artifact_installer: object | None = None,
    runtime_provisioner: object | None = None,
    process_starter: Callable[[Sequence[str]], None] = lambda _command: None,
) -> Callable[[Callable[[str], None]], InstallationWorkflow]:
    """Build test workflows from explicit installer boundary doubles."""

    resolved_layout_preparer = layout_preparer or LayoutInstaller()
    resolved_artifact_installer = artifact_installer or FirstRunInstaller(
        process_starter=lambda _command: None
    )
    resolved_runtime_provisioner = runtime_provisioner or _UnusedRuntimeProvisioner()

    def create_workflow(
        _output_callback: Callable[[str], None],
    ) -> InstallationWorkflow:
        """Return one workflow using the configured test boundaries."""

        return InstallationWorkflow(
            layout_preparer=cast(Any, resolved_layout_preparer),
            artifact_installer=cast(Any, resolved_artifact_installer),
            runtime_provisioner=cast(Any, resolved_runtime_provisioner),
            process_starter=process_starter,
        )

    return create_workflow
