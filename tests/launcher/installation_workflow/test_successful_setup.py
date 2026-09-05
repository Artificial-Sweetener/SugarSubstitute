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

"""Verify successful first-run installation and setup handoff workflows."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from tests.launcher.installation_workflow.support import (
    advance_to_install_location,
    close_and_delete_launcher_window,
    release_source_for_test,
    wait_for_launcher_condition,
    workflow_factory,
)
from tests.launcher.support import launcher_test_application


def test_frozen_setup_installs_in_current_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Keep a downloaded frozen setup in its current installer window."""

    application = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    downloaded_exe = (
        tmp_path / "Downloads" / "SugarSubstitute-Installer-Windows-x64.exe"
    )
    downloaded_exe.parent.mkdir(parents=True)
    downloaded_exe.write_text("", encoding="utf-8")
    handoff_calls: list[tuple[Path, str | None, bool]] = []
    handoff_commands: list[list[str]] = []
    continue_calls = 0
    runtime_calls = 0
    runtime_initial_worker_states: list[bool] = []
    observed_release_sources: list[object] = []

    class _FakeFirstRunInstaller:
        """Record setup install requests."""

        def install_downloaded_launcher(
            self,
            *,
            install_root: Path,
            release_source: object,
            handoff_geometry: str | None,
            launch_installed: bool,
        ) -> object:
            """Return a fake copied-launcher result."""

            observed_release_sources.append(release_source)
            handoff_calls.append((install_root, handoff_geometry, launch_installed))
            return SimpleNamespace(layout=layout)

        def continue_install(
            self,
            *,
            layout: InstallLayout,
            release_source: object,
        ) -> object:
            """Record app payload installation."""

            nonlocal continue_calls
            observed_release_sources.append(release_source)
            continue_calls += 1
            return SimpleNamespace(
                layout=layout,
                app_version="0.4.0",
                app_command=["python.exe", "main.py", f"--install-root={layout.root}"],
            )

    class _FakeRuntimeInstaller:
        """Record managed runtime provisioning."""

        def provision(self, *, layout: InstallLayout) -> object:
            """Return a successful runtime result for the installed layout."""

            nonlocal runtime_calls
            runtime_calls += 1
            runtime_initial_worker_states.append(window.execution.initial_running)
            return SimpleNamespace(python_executable=layout.runtime_python)

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.ui.main_window._current_frozen_executable",
        lambda: downloaded_exe,
    )
    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.application.installation.release_source_policy.discover_local_release_root",
        lambda: tmp_path / ".local-release-channel",
    )
    initial_release_source = release_source_for_test()
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        initial_release_source=initial_release_source,
        workflow_factory=workflow_factory(
            artifact_installer=_FakeFirstRunInstaller(),
            runtime_provisioner=_FakeRuntimeInstaller(),
            process_starter=lambda command: handoff_commands.append(list(command)),
        ),
    )

    advance_to_install_location(window)
    window.view.primary_button.click()
    wait_for_launcher_condition(
        application,
        lambda: (
            window.view.primary_button.text() == "Setup started"
            and not window.execution.setup_running
        ),
    )

    assert len(handoff_calls) == 1
    assert handoff_calls[0][0] == layout.root
    assert handoff_calls[0][1] is not None
    assert handoff_calls[0][2] is False
    assert continue_calls == 1
    assert runtime_calls == 1
    assert runtime_initial_worker_states == [False]
    assert observed_release_sources == [
        initial_release_source,
        initial_release_source,
    ]
    assert len(handoff_commands) == 1
    assert handoff_commands[0][:3] == [
        "python.exe",
        "main.py",
        f"--install-root={layout.root}",
    ]
    assert handoff_commands[0][3].startswith("--handoff-geometry=")
    assert window.view.install_path_edit.isEnabled() is False
    assert window.view.browse_button is not None
    assert window.view.browse_button.isEnabled() is False
    assert "Installed launcher:" in window.view.progress_log.log_view.toPlainText()
    assert (
        "Starting installed launcher."
        not in window.view.progress_log.log_view.toPlainText()
    )
    close_and_delete_launcher_window(window)


def test_continue_install_auto_starts_runtime_and_setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Start runtime installation and setup automatically after launcher handoff."""

    application = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    continue_calls = 0
    runtime_calls = 0
    handoff_commands: list[list[str]] = []
    close_calls_ref = {"count": 0}

    class _FakeFirstRunInstaller:
        """Record app payload installation calls."""

        def continue_install(
            self, *, layout: InstallLayout, release_source: object
        ) -> object:
            """Return a fake continued install result."""

            nonlocal continue_calls
            _ = release_source
            continue_calls += 1
            return SimpleNamespace(
                layout=layout,
                app_version="0.4.0",
                app_command=["python.exe", "main.py", f"--install-root={layout.root}"],
            )

    class _FakeRuntimeInstaller:
        """Record runtime provisioning before setup handoff."""

        def provision(self, *, layout: InstallLayout) -> object:
            """Record that runtime provisioning ran."""

            nonlocal runtime_calls
            _ = layout
            runtime_calls += 1
            return SimpleNamespace(python_executable=layout.runtime_python)

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.application.installation.release_source_policy.discover_local_release_root",
        lambda: tmp_path / ".local-release-channel",
    )
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=True,
        repair=False,
        update_check_enabled=True,
        initial_release_source=release_source_for_test(),
        workflow_factory=workflow_factory(
            artifact_installer=_FakeFirstRunInstaller(),
            runtime_provisioner=_FakeRuntimeInstaller(),
            process_starter=lambda command: handoff_commands.append(list(command)),
        ),
    )
    window.handoff_completed.connect(lambda: _record_close_call(close_calls_ref))
    wait_for_launcher_condition(
        application,
        lambda: (
            window.view.primary_button.text() == "Setup started"
            and close_calls_ref["count"] == 1
        ),
    )

    assert continue_calls == 1
    assert runtime_calls == 1
    assert len(handoff_commands) == 1
    assert handoff_commands[0][:3] == [
        "python.exe",
        "main.py",
        f"--install-root={layout.root}",
    ]
    assert handoff_commands[0][3].startswith("--handoff-geometry=")
    assert close_calls_ref["count"] == 1
    close_and_delete_launcher_window(window)


def test_launcher_continue_installs_app_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Advance to app installation once instead of repeating layout preparation."""

    application = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    prepare_calls = 0
    continue_calls = 0
    runtime_calls = 0
    handoff_commands: list[list[str]] = []
    close_calls_ref = {"count": 0}

    class _FakeLayoutInstaller:
        """Record layout preparation calls."""

        def prepare(self, install_root: Path) -> object:
            """Return the prepared layout."""

            nonlocal prepare_calls
            prepare_calls += 1
            assert install_root == layout.root
            return SimpleNamespace(layout=layout)

    class _FakeFirstRunInstaller:
        """Record app payload install calls."""

        def continue_install(
            self, *, layout: InstallLayout, release_source: object
        ) -> object:
            """Return a fake continued install result."""

            nonlocal continue_calls
            _ = release_source
            continue_calls += 1
            return SimpleNamespace(
                layout=layout,
                app_version="0.4.0",
                app_command=["python.exe", "main.py", f"--install-root={layout.root}"],
            )

    class _FakeRuntimeInstaller:
        """Record runtime provisioning before setup handoff."""

        def provision(self, *, layout: InstallLayout) -> object:
            """Record that runtime provisioning ran."""

            nonlocal runtime_calls
            _ = layout
            runtime_calls += 1
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
            layout_preparer=_FakeLayoutInstaller(),
            artifact_installer=_FakeFirstRunInstaller(),
            runtime_provisioner=_FakeRuntimeInstaller(),
            process_starter=lambda command: handoff_commands.append(list(command)),
        ),
    )
    window.handoff_completed.connect(lambda: _record_close_call(close_calls_ref))

    advance_to_install_location(window)
    window.view.primary_button.click()
    window.view.primary_button.click()
    window.view.primary_button.click()
    wait_for_launcher_condition(
        application,
        lambda: (
            window.view.primary_button.text() == "Setup started"
            and close_calls_ref["count"] == 1
        ),
    )

    assert prepare_calls == 1
    assert continue_calls == 1
    assert runtime_calls == 1
    assert len(handoff_commands) == 1
    assert handoff_commands[0][:3] == [
        "python.exe",
        "main.py",
        f"--install-root={layout.root}",
    ]
    assert handoff_commands[0][3].startswith("--handoff-geometry=")
    assert window.view.primary_button.text() == "Setup started"
    assert window.view.primary_button.isEnabled() is False
    assert window.view.install_path_edit.isEnabled() is False
    assert window.view.browse_button is not None
    assert window.view.browse_button.isEnabled() is False
    assert close_calls_ref["count"] == 1
    close_and_delete_launcher_window(window)


def _record_close_call(close_calls_ref: dict[str, int]) -> None:
    """Record that the launcher requested its installer window to close."""

    close_calls_ref["count"] += 1
