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

"""Prove closing the installer stops safely without destroying active workers."""

from __future__ import annotations

from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from tests.launcher.installation_workflow.support import (
    advance_to_install_location,
    release_source_for_test,
    wait_for_launcher_condition,
    workflow_factory,
)
from tests.launcher.support import launcher_test_application


def test_close_during_initial_install_waits_for_its_safe_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Keep the surface alive, then stop before runtime or setup begins."""

    application = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    install_started = threading.Event()
    release_install = threading.Event()
    runtime_calls: list[Path] = []
    setup_commands: list[list[str]] = []

    class _LayoutPreparer:
        """Return the selected layout without touching unrelated storage."""

        def prepare(self, _install_root: Path) -> object:
            """Return one prepared layout."""

            return SimpleNamespace(layout=layout)

    class _BlockingArtifactInstaller:
        """Hold payload installation at a deterministic worker boundary."""

        def continue_install(
            self, *, layout: InstallLayout, release_source: object
        ) -> object:
            """Wait for the test before publishing installed application state."""

            _ = release_source
            install_started.set()
            assert release_install.wait(5)
            return SimpleNamespace(
                layout=layout,
                app_version="qualification",
                app_command=["python.exe", "main.py"],
            )

    class _RuntimeProvisioner:
        """Record any forbidden continuation beyond the requested close."""

        def provision(self, *, layout: InstallLayout) -> object:
            """Record and return runtime state."""

            runtime_calls.append(layout.root)
            return SimpleNamespace(python_executable=layout.runtime_python)

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.application.installation.release_source_policy.discover_local_release_root",
        lambda: tmp_path / ".local-release-channel",
    )
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        initial_release_source=release_source_for_test(),
        workflow_factory=workflow_factory(
            layout_preparer=_LayoutPreparer(),
            artifact_installer=_BlockingArtifactInstaller(),
            runtime_provisioner=_RuntimeProvisioner(),
            process_starter=lambda command: setup_commands.append(list(command)),
        ),
    )
    window.show()
    advance_to_install_location(window)
    window.view.primary_button.click()
    assert install_started.wait(5)

    window.close()
    application.processEvents()

    assert window.isVisible()
    assert "Finishing the current setup step before closing." in (
        window.view.status_panel.progress_log.log_view.toPlainText()
    )
    release_install.set()
    wait_for_launcher_condition(
        application,
        lambda: not window.isVisible() and not window.execution.initial_running,
    )
    assert runtime_calls == []
    assert setup_commands == []
    window.deleteLater()
    application.processEvents()


def test_close_during_runtime_prevents_setup_process_handoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Finish runtime transactionally but do not start another process after close."""

    application = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    runtime_started = threading.Event()
    release_runtime = threading.Event()
    setup_commands: list[list[str]] = []

    class _LayoutPreparer:
        """Return the selected layout immediately."""

        def prepare(self, _install_root: Path) -> object:
            """Return one prepared layout."""

            return SimpleNamespace(layout=layout)

    class _ArtifactInstaller:
        """Publish a synthetic installed application immediately."""

        def continue_install(
            self, *, layout: InstallLayout, release_source: object
        ) -> object:
            """Return an application ready for runtime provisioning."""

            _ = release_source
            return SimpleNamespace(
                layout=layout,
                app_version="qualification",
                app_command=["python.exe", "main.py"],
            )

    class _BlockingRuntimeProvisioner:
        """Hold runtime completion until close has been requested."""

        def provision(self, *, layout: InstallLayout) -> object:
            """Wait at the active runtime boundary."""

            runtime_started.set()
            assert release_runtime.wait(5)
            return SimpleNamespace(python_executable=layout.runtime_python)

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.application.installation.release_source_policy.discover_local_release_root",
        lambda: tmp_path / ".local-release-channel",
    )
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        initial_release_source=release_source_for_test(),
        workflow_factory=workflow_factory(
            layout_preparer=_LayoutPreparer(),
            artifact_installer=_ArtifactInstaller(),
            runtime_provisioner=_BlockingRuntimeProvisioner(),
            process_starter=lambda command: setup_commands.append(list(command)),
        ),
    )
    window.show()
    advance_to_install_location(window)
    window.view.primary_button.click()
    wait_for_launcher_condition(application, runtime_started.is_set)

    window.close()
    application.processEvents()
    assert window.isVisible()

    release_runtime.set()
    wait_for_launcher_condition(
        application,
        lambda: not window.isVisible() and not window.execution.setup_running,
    )
    assert setup_commands == []
    window.deleteLater()
    application.processEvents()


def test_close_during_repair_staging_prevents_repair_handoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Leave active files untouched when close wins before staged repair handoff."""

    application = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    staging_started = threading.Event()
    release_staging = threading.Event()
    handoff_paths: list[Path] = []

    def prepare_repair(_service: object, **_arguments: object) -> object:
        """Hold immutable staging until close has been observed."""

        staging_started.set()
        assert release_staging.wait(5)
        return object()

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.ui.repair_preparation_execution.RepairPreparationService.prepare_bound_application_repair",
        prepare_repair,
    )
    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.ui.main_window.launch_prepared_repair_helper",
        lambda *, request_path: handoff_paths.append(request_path),
    )
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=True,
        update_check_enabled=True,
        initial_release_source=release_source_for_test(),
        workflow_factory=workflow_factory(),
    )
    window.show()
    window.view.repair_page.primary_button.click()
    wait_for_launcher_condition(application, staging_started.is_set)

    window.close()
    application.processEvents()
    assert window.isVisible()

    release_staging.set()
    wait_for_launcher_condition(
        application,
        lambda: not window.isVisible() and not window.repair_execution.running,
    )
    assert handoff_paths == []
    window.deleteLater()
    application.processEvents()
