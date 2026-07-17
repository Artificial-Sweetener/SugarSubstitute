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

"""Tests for the standalone launcher skeleton."""

from __future__ import annotations

import ast
import json
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import ANY

from PySide6.QtWidgets import QApplication, QWidget
import pytest

from launcher.sugarsubstitute_launcher import app as launcher_app
from launcher.sugarsubstitute_launcher.app import (
    is_installed_app_launchable,
    resolve_install_root,
    resolve_startup_plan,
    should_launch_installed_app,
)
from launcher.sugarsubstitute_launcher.cli import parse_launcher_args
from launcher.sugarsubstitute_launcher.config import (
    DEFAULT_RELEASE_MANIFEST_URL,
    LauncherConfig,
    ReleaseSourceConfig,
    UpdateCheckConfig,
)
from launcher.sugarsubstitute_launcher.install_layout import (
    InstallLayout,
    default_install_root,
)
from launcher.sugarsubstitute_launcher.installer import LayoutInstaller
from launcher.sugarsubstitute_launcher.logging_setup import configure_launcher_logging
from launcher.sugarsubstitute_launcher.release_sources import GitHubReleaseSource
from launcher.sugarsubstitute_launcher.ui.main_window import (
    LauncherMainWindow,
    resolve_initial_install_release_source,
)
from launcher.sugarsubstitute_launcher.release_sources import LocalFolderReleaseSource
from sugarsubstitute_shared.presentation.terminal import TerminalOutputView


REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_PACKAGE_ROOT = REPO_ROOT / "launcher" / "sugarsubstitute_launcher"


@pytest.fixture()
def qt_application() -> QApplication:
    """Return a QApplication for launcher widget tests."""

    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return cast(QApplication, application)


def _pump_events_until(
    application: QApplication,
    predicate: Callable[[], bool],
    *,
    timeout_seconds: float = 5.0,
) -> None:
    """Process Qt events until a background launcher condition is satisfied."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        application.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for launcher background work.")


def test_launcher_args_parse_internal_flags() -> None:
    """The launcher accepts setup, repair, update, and install-root flags."""

    args = parse_launcher_args(
        [
            "--continue-install",
            "--repair",
            "--no-update-check",
            "--install-root",
            "E:\\Programs\\SugarSubstitute",
            "--handoff-geometry",
            "10,20,1260,800",
        ]
    )

    assert args.continue_install is True
    assert args.repair is True
    assert args.no_update_check is True
    assert args.handoff_geometry == "10,20,1260,800"
    assert args.install_root == Path("E:\\Programs\\SugarSubstitute")


def test_install_layout_resolves_target_paths(tmp_path: Path) -> None:
    """The install layout matches the planned launcher-owned directory shape."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")

    assert layout.executable_path == layout.root / "SugarSubstitute.exe"
    assert layout.config_path == layout.root / "launcher" / "config.json"
    assert layout.state_path == layout.root / "launcher" / "state.json"
    assert layout.logs_dir == layout.root / "launcher" / "logs"
    assert layout.cache_dir == layout.root / "launcher" / "cache"
    assert layout.downloads_dir == layout.root / "launcher" / "downloads"
    assert layout.locks_dir == layout.root / "launcher" / "locks"
    assert (
        layout.runtime_python
        == layout.root / "runtime" / ".venv" / "Scripts" / "python.exe"
    )
    assert (
        layout.runtime_gui_python
        == layout.root / "runtime" / ".venv" / "Scripts" / "pythonw.exe"
    )
    assert layout.app_entrypoint == layout.root / "app" / "main.py"
    assert layout.user_dir == layout.root / "user"
    assert layout.appdata_dir == layout.root / "appdata"


def test_default_install_root_uses_setup_executable_drive(tmp_path: Path) -> None:
    """Setup mode should default to SugarSubstitute on the setup exe drive."""

    executable_path = (
        tmp_path / "Downloads" / "SugarSubstitute-Installer-Windows-x64.exe"
    )

    assert default_install_root(executable_path) == Path(
        f"{executable_path.drive}\\SugarSubstitute"
    )


def test_layout_installer_creates_base_directories_and_config(tmp_path: Path) -> None:
    """Preparing an install root creates launcher state without app payload data."""

    result = LayoutInstaller().prepare(tmp_path / "SugarSubstitute")

    assert result.layout.root.is_dir()
    assert result.layout.launcher_dir.is_dir()
    assert result.layout.logs_dir.is_dir()
    assert result.layout.cache_dir.is_dir()
    assert result.layout.downloads_dir.is_dir()
    assert result.layout.locks_dir.is_dir()
    assert result.layout.runtime_dir.is_dir()
    assert result.layout.user_dir.is_dir()
    assert result.layout.appdata_dir.is_dir()
    assert not result.layout.app_dir.exists()
    assert result.layout.config_path.is_file()
    assert LauncherConfig.load(result.layout.config_path) == result.config


def test_launcher_config_round_trips_schema_json(tmp_path: Path) -> None:
    """Launcher config persists and reloads the planned schema."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    config = LauncherConfig.from_layout(
        layout=layout,
        channel="stable",
        update_check=UpdateCheckConfig(enabled=False, frequency="manual"),
    )

    config.save(layout.config_path)
    loaded = LauncherConfig.load(layout.config_path)

    assert loaded == config
    raw_payload = json.loads(layout.config_path.read_text(encoding="utf-8"))
    assert raw_payload["schema_version"] == 1
    assert raw_payload["install_root"] == str(layout.root)
    assert raw_payload["app_dir"] == str(layout.app_dir)
    assert raw_payload["runtime_python"] == str(layout.runtime_python)
    assert raw_payload["update_check"] == {"enabled": False, "frequency": "manual"}
    assert raw_payload["release_source"] == {
        "kind": "github_release_manifest",
        "manifest_url": DEFAULT_RELEASE_MANIFEST_URL,
    }


def test_launcher_config_can_disable_persisted_release_source(
    tmp_path: Path,
) -> None:
    """Dev-only local installs can explicitly avoid a persisted production source."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    config = LauncherConfig.from_layout(layout=layout, release_source=None)

    config.save(layout.config_path)
    loaded = LauncherConfig.load(layout.config_path)

    assert loaded.release_source is None
    raw_payload = json.loads(layout.config_path.read_text(encoding="utf-8"))
    assert raw_payload["release_source"] is None


def test_frozen_local_test_installer_prefers_embedded_release_channel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A packaged local-test installer must not resolve the GitHub channel."""

    release_root = tmp_path / "launcher_local_release"
    release_root.mkdir()
    (release_root / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    source = resolve_initial_install_release_source(frozen_setup=True)

    assert source == LocalFolderReleaseSource(release_root.resolve())


def test_launcher_config_upgrades_missing_release_source_to_github(
    tmp_path: Path,
) -> None:
    """Existing schema-one configs without source data should use GitHub updates."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    payload = LauncherConfig.from_layout(layout=layout).to_json()
    payload.pop("release_source")
    layout.config_path.parent.mkdir(parents=True, exist_ok=True)
    layout.config_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = LauncherConfig.load(layout.config_path)

    assert loaded.release_source == ReleaseSourceConfig.default()


def test_launcher_logging_writes_under_launcher_logs(tmp_path: Path) -> None:
    """Launcher logging config creates its log file under launcher state."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")

    log_path = configure_launcher_logging(layout=layout)

    assert log_path == layout.logs_dir / "launcher.log"
    assert log_path.parent.is_dir()


def test_launcher_resolves_installed_exe_parent_as_install_root(
    tmp_path: Path,
) -> None:
    """An installed exe should use its own root when adjacent config matches."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    layout.executable_path.write_text("", encoding="utf-8")

    resolved_root = resolve_install_root(
        explicit_install_root=None,
        executable_path=layout.executable_path,
    )

    assert resolved_root == layout.root


def test_launcher_ignores_adjacent_app_without_launcher_config(
    tmp_path: Path,
) -> None:
    """Only launcher config beside the exe marks an installed launcher."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    layout.root.mkdir(parents=True)
    layout.executable_path.write_text("", encoding="utf-8")
    layout.app_entrypoint.parent.mkdir(parents=True, exist_ok=True)
    layout.app_entrypoint.write_text("", encoding="utf-8")

    startup_plan = resolve_startup_plan(
        explicit_install_root=None,
        executable_path=layout.executable_path,
    )

    assert startup_plan.installed_config_found is False
    assert startup_plan.layout.root == Path(
        f"{layout.executable_path.drive}\\SugarSubstitute"
    )


def test_launcher_launches_installed_app_only_after_install_is_ready(
    tmp_path: Path,
) -> None:
    """Normal installed launches should bypass setup only for complete layouts."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    layout.app_entrypoint.parent.mkdir(parents=True, exist_ok=True)
    layout.app_entrypoint.write_text("", encoding="utf-8")
    runtime_python = layout.runtime_python
    runtime_python.parent.mkdir(parents=True, exist_ok=True)
    runtime_python.write_text("", encoding="utf-8")
    args = parse_launcher_args([])

    assert is_installed_app_launchable(layout) is True
    assert (
        should_launch_installed_app(
            args=args,
            startup_plan=resolve_startup_plan(
                explicit_install_root=None,
                executable_path=layout.executable_path,
            ),
        )
        is True
    )


def test_launcher_setup_flags_do_not_bypass_to_normal_launch(tmp_path: Path) -> None:
    """Continue-install and repair invocations must keep showing setup UI."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    layout.app_entrypoint.parent.mkdir(parents=True, exist_ok=True)
    layout.app_entrypoint.write_text("", encoding="utf-8")
    layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
    layout.runtime_python.write_text("", encoding="utf-8")

    assert (
        should_launch_installed_app(
            args=parse_launcher_args(["--continue-install"]),
            startup_plan=resolve_startup_plan(
                explicit_install_root=None,
                executable_path=layout.executable_path,
            ),
        )
        is False
    )
    assert (
        should_launch_installed_app(
            args=parse_launcher_args(["--repair"]),
            startup_plan=resolve_startup_plan(
                explicit_install_root=None,
                executable_path=layout.executable_path,
            ),
        )
        is False
    )


def test_launcher_initial_screen_matches_onboarding_step_one_shell(
    qt_application: QApplication,
    tmp_path: Path,
) -> None:
    """The downloaded setup UI should present itself as onboarding step one."""

    _ = qt_application
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")

    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        process_starter=lambda _command: None,
        runtime_installer=cast(Any, object()),
    )

    assert window.width() == 1260
    assert window.height() == 800
    assert window.titleBar.minBtn.isHidden() is True
    assert window.titleBar.maxBtn.isHidden() is True
    assert window.progress_count_label.text() == "Step 1 of 4"
    assert window.progress_title_label.text() == "Choose a folder"
    assert len(window.step_items) == 4
    assert window.step_items[0].property("stepState") == "active"
    assert window.step_items[1].property("stepState") == "inactive"
    assert window._path_edit.text() == str(layout.root)  # noqa: SLF001
    assert window._path_edit.isEnabled() is True  # noqa: SLF001
    assert window._browse_button is not None  # noqa: SLF001
    assert window._browse_button.isEnabled() is True  # noqa: SLF001
    assert window._primary_button.text() == "Install"  # noqa: SLF001
    assert isinstance(window._progress_log, TerminalOutputView)  # noqa: SLF001
    assert window._progress_log.log_view.minimumHeight() == 260  # noqa: SLF001
    assert window._progress_log.log_view.maximumHeight() == 340  # noqa: SLF001
    assert "Avoid Program Files" in window._install_location_guidance_label.text()  # noqa: SLF001
    assert "Ready." in window._progress_log.log_view.toPlainText()  # noqa: SLF001
    assert window._status_panel is not None  # noqa: SLF001
    assert window._status_panel.isHidden() is True  # noqa: SLF001
    assert "OnboardingIdentityRail" in window.styleSheet()
    assert "OnboardingSectionPanel" in window.styleSheet()
    window.close()


def test_launcher_page_fits_fixed_window_with_live_output_visible(
    qt_application: QApplication,
    tmp_path: Path,
) -> None:
    """The downloaded installer page should fit before and during install work."""

    window = LauncherMainWindow(
        initial_layout=InstallLayout.from_root(tmp_path / "SugarSubstitute"),
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        process_starter=lambda _command: None,
        runtime_installer=cast(Any, object()),
    )
    window.show()
    qt_application.processEvents()

    try:
        page_stage = window.findChild(QWidget, "OnboardingPageStage")
        page_stack = window.findChild(QWidget, "OnboardingPageStack")
        page = window.findChild(QWidget, "OnboardingPageFrame")
        assert page_stage is not None
        assert page_stack is not None
        assert page is not None

        for live_output_visible in (False, True):
            if live_output_visible:
                window._show_status_output()
                qt_application.processEvents()

            assert page.sizeHint().height() <= page_stage.contentsRect().height()
            assert page_stage.contentsRect().contains(page_stack.geometry())
            assert page_stack.contentsRect().contains(page.geometry())
    finally:
        window.close()
        window.deleteLater()
        qt_application.processEvents()


def test_launcher_main_repairs_moved_installed_exe_config(
    monkeypatch: pytest.MonkeyPatch,
    qt_application: QApplication,
    tmp_path: Path,
) -> None:
    """An adjacent config pointing elsewhere should be repair, not setup mode."""

    _ = qt_application
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    other_layout = InstallLayout.from_root(tmp_path / "OtherSugarSubstitute")
    LauncherConfig.from_layout(layout=other_layout).save(layout.config_path)
    layout.executable_path.write_text("", encoding="utf-8")
    windows: list[dict[str, object]] = []

    class _FakeWindow:
        """Record launcher window construction without showing real UI."""

        def __init__(self, **kwargs: object) -> None:
            """Capture construction keyword arguments."""

            windows.append(kwargs)

        def show(self) -> None:
            """Record that the window would be shown."""

    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setattr(launcher_app, "LauncherMainWindow", _FakeWindow)
    monkeypatch.setattr(
        launcher_app,
        "start_detached",
        lambda _command: pytest.fail("Invalid installed config must not launch app."),
    )

    assert launcher_app.main([]) == 0
    assert windows
    assert windows[0]["initial_layout"] == layout
    assert windows[0]["repair"] is True
    assert windows[0]["continue_install"] is False


def test_launcher_main_starts_app_from_installed_exe_parent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The installed executable should launch the app instead of setup UI."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    layout.executable_path.write_text("", encoding="utf-8")
    layout.app_entrypoint.parent.mkdir(parents=True, exist_ok=True)
    layout.app_entrypoint.write_text("", encoding="utf-8")
    layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
    layout.runtime_python.write_text("", encoding="utf-8")
    started_commands: list[list[str]] = []

    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setattr(
        launcher_app,
        "start_launcher_splash_session",
        lambda *, layout: None,
    )
    monkeypatch.setattr(
        launcher_app,
        "start_detached",
        lambda command: started_commands.append(list(command)),
    )
    monkeypatch.setattr(
        launcher_app,
        "LauncherMainWindow",
        lambda **_kwargs: pytest.fail("Installed launch must not show setup UI."),
    )

    assert launcher_app.main([]) == 0
    assert started_commands == [
        [
            str(layout.runtime_python),
            str(layout.app_entrypoint),
            f"--install-root={layout.root}",
        ]
    ]


def test_launcher_main_runs_pre_launch_update_before_app_handoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Installed launches should run launcher update orchestration before handoff."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    layout.executable_path.write_text("", encoding="utf-8")
    layout.app_entrypoint.parent.mkdir(parents=True, exist_ok=True)
    layout.app_entrypoint.write_text("", encoding="utf-8")
    layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
    layout.runtime_python.write_text("", encoding="utf-8")
    calls: list[str] = []
    progress_client = object()
    splash_session = SimpleNamespace(
        client=progress_client,
        app_arguments=("--splash-session-endpoint=127.0.0.1:49152",),
    )

    class _FakeUpdateOrchestrator:
        """Record pre-launch update orchestration."""

        def run(self, **kwargs: object) -> object:
            """Record update arguments before app launch."""

            calls.append("update")
            assert kwargs["layout"] == layout
            assert isinstance(kwargs["config"], LauncherConfig)
            assert isinstance(kwargs["release_source"], GitHubReleaseSource)
            assert kwargs["release_source"].manifest_url == DEFAULT_RELEASE_MANIFEST_URL
            assert kwargs["no_update_check"] is False
            assert kwargs["progress"] is progress_client
            from launcher.sugarsubstitute_launcher.update_orchestrator import (
                PreLaunchUpdateResult,
            )

            return PreLaunchUpdateResult(
                checked_manifest=True,
                installed_update=False,
            )

    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setattr(
        launcher_app,
        "LauncherUpdateOrchestrator",
        _FakeUpdateOrchestrator,
    )
    monkeypatch.setattr(
        launcher_app,
        "start_launcher_splash_session",
        lambda *, layout: splash_session,
    )
    monkeypatch.setattr(
        launcher_app,
        "start_detached",
        lambda command: calls.extend(["launch", *command]),
    )
    monkeypatch.setattr(
        launcher_app,
        "LauncherMainWindow",
        lambda **_kwargs: pytest.fail("Installed launch must not show setup UI."),
    )

    assert launcher_app.main([]) == 0
    assert calls == [
        "update",
        "launch",
        str(layout.runtime_python),
        str(layout.app_entrypoint),
        f"--install-root={layout.root}",
        "--splash-session-endpoint=127.0.0.1:49152",
    ]


def test_launcher_main_hands_off_pending_launcher_update_instead_of_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A staged launcher update should replace, relaunch, then start the app."""

    from launcher.sugarsubstitute_launcher.update_orchestrator import (
        PreLaunchUpdateResult,
    )

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    layout.executable_path.write_text("", encoding="utf-8")
    layout.app_entrypoint.parent.mkdir(parents=True, exist_ok=True)
    layout.app_entrypoint.write_text("", encoding="utf-8")
    layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
    layout.runtime_python.write_text("", encoding="utf-8")
    closed: list[bool] = []
    splash_session = SimpleNamespace(
        client=SimpleNamespace(close=lambda: closed.append(True)),
        app_arguments=(),
    )
    scheduled: list[dict[str, object]] = []

    def schedule_update(**kwargs: object) -> int:
        """Record the detached launcher update handoff."""

        scheduled.append(kwargs)
        return 1234

    class _FakeUpdateOrchestrator:
        """Return one pending launcher request."""

        def run(self, **_kwargs: object) -> PreLaunchUpdateResult:
            """Return the staged update result."""

            return PreLaunchUpdateResult(
                checked_manifest=True,
                installed_update=True,
                launcher_update_request_path=str(layout.launcher_update_request_path),
            )

    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setattr(
        launcher_app,
        "LauncherUpdateOrchestrator",
        _FakeUpdateOrchestrator,
    )
    monkeypatch.setattr(
        launcher_app,
        "start_launcher_splash_session",
        lambda *, layout: splash_session,
    )
    monkeypatch.setattr(
        launcher_app,
        "schedule_launcher_update",
        schedule_update,
    )
    monkeypatch.setattr(
        launcher_app,
        "start_detached",
        lambda _command: pytest.fail("The old launcher must not start the app."),
    )

    assert launcher_app.main([]) == 0
    assert closed == [True]
    assert scheduled == [
        {
            "request_path": layout.launcher_update_request_path,
            "runtime_python": layout.runtime_python,
            "app_dir": layout.app_dir,
            "relaunch": True,
            "wait_pid": ANY,
        }
    ]


def test_frozen_setup_installs_in_current_window(
    monkeypatch: pytest.MonkeyPatch,
    qt_application: QApplication,
    tmp_path: Path,
) -> None:
    """A downloaded frozen setup should not open a second installer window."""

    application = qt_application
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    downloaded_exe = (
        tmp_path / "Downloads" / "SugarSubstitute-Installer-Windows-x64.exe"
    )
    downloaded_exe.parent.mkdir(parents=True)
    downloaded_exe.write_text("", encoding="utf-8")
    handoff_calls: list[tuple[Path, str | None, bool]] = []
    continue_calls = 0
    setup_started = 0

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

            _ = release_source
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
            _ = release_source
            continue_calls += 1
            return SimpleNamespace(
                app_version="0.4.0",
                app_command=["python.exe", "main.py", f"--install-root={layout.root}"],
            )

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.ui.main_window._current_frozen_executable",
        lambda: downloaded_exe,
    )
    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.ui.main_window.discover_local_release_root",
        lambda: tmp_path / ".local-release-channel",
    )
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        process_starter=lambda _command: None,
        runtime_installer=cast(Any, object()),
    )
    window._first_run_installer = cast(Any, _FakeFirstRunInstaller())  # noqa: SLF001
    monkeypatch.setattr(
        window,
        "_start_setup_worker",
        lambda: nonlocal_setup_started(),
    )

    def nonlocal_setup_started() -> None:
        """Record that setup would continue into runtime provisioning."""

        nonlocal setup_started
        setup_started += 1

    window._primary_button.click()  # noqa: SLF001
    _pump_events_until(application, lambda: setup_started == 1)

    assert len(handoff_calls) == 1
    assert handoff_calls[0][0] == layout.root
    assert handoff_calls[0][1] is not None
    assert handoff_calls[0][2] is False
    assert continue_calls == 1
    assert window._prepared_layout == layout  # noqa: SLF001
    assert window._setup_command is not None  # noqa: SLF001
    assert window._setup_command[:3] == [  # noqa: SLF001
        "python.exe",
        "main.py",
        f"--install-root={layout.root}",
    ]
    assert window._setup_command[3].startswith("--handoff-geometry=")  # noqa: SLF001
    assert window._path_edit.isEnabled() is False  # noqa: SLF001
    assert window._browse_button is not None  # noqa: SLF001
    assert window._browse_button.isEnabled() is False  # noqa: SLF001
    assert "Installed launcher:" in window._progress_log.log_view.toPlainText()  # noqa: SLF001
    assert (  # noqa: SLF001
        "Starting installed launcher."
        not in window._progress_log.log_view.toPlainText()
    )
    window.close()


def test_continue_install_auto_starts_runtime_and_setup(
    monkeypatch: pytest.MonkeyPatch,
    qt_application: QApplication,
    tmp_path: Path,
) -> None:
    """The installed --continue-install launcher should not wait for another click."""

    _ = qt_application
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
            return object()

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.ui.main_window.discover_local_release_root",
        lambda: tmp_path / ".local-release-channel",
    )
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=True,
        repair=False,
        update_check_enabled=True,
        process_starter=lambda command: handoff_commands.append(list(command)),
        runtime_installer=_FakeRuntimeInstaller(),
    )
    window._first_run_installer = cast(Any, _FakeFirstRunInstaller())  # noqa: SLF001
    window._close_after_successful_handoff = lambda: _record_close_call(  # type: ignore[method-assign]  # noqa: SLF001
        close_calls_ref
    )
    _pump_events_until(
        qt_application,
        lambda: (
            window._primary_button.text() == "Setup started"  # noqa: SLF001
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
    window.close()


def test_setup_handoff_closes_only_after_worker_thread_stops(
    qt_application: QApplication,
    tmp_path: Path,
) -> None:
    """Successful handoff must keep Qt alive until its worker thread has stopped."""

    _ = qt_application
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    close_calls_ref = {"count": 0}
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        process_starter=lambda _command: None,
        runtime_installer=cast(Any, object()),
    )
    window._setup_thread = cast(Any, object())  # noqa: SLF001
    window._setup_worker = cast(Any, object())  # noqa: SLF001
    window._close_after_successful_handoff = lambda: _record_close_call(  # type: ignore[method-assign]  # noqa: SLF001
        close_calls_ref
    )

    window._handle_setup_worker_succeeded()  # noqa: SLF001

    assert window._primary_button.text() == "Setup started"  # noqa: SLF001
    assert close_calls_ref["count"] == 0

    window._forget_setup_worker()  # noqa: SLF001

    assert close_calls_ref["count"] == 1
    assert window._setup_thread is None  # noqa: SLF001
    assert window._setup_worker is None  # noqa: SLF001
    window.close()


def test_launcher_continue_installs_app_once(
    monkeypatch: pytest.MonkeyPatch,
    qt_application: QApplication,
    tmp_path: Path,
) -> None:
    """Continue should advance to app install instead of repeating layout prep."""

    _ = qt_application
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
            return object()

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.ui.main_window.discover_local_release_root",
        lambda: tmp_path / ".local-release-channel",
    )
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        process_starter=lambda command: handoff_commands.append(list(command)),
        runtime_installer=_FakeRuntimeInstaller(),
    )
    window._layout_installer = cast(Any, _FakeLayoutInstaller())  # noqa: SLF001
    window._first_run_installer = cast(Any, _FakeFirstRunInstaller())  # noqa: SLF001
    window._close_after_successful_handoff = lambda: _record_close_call(  # type: ignore[method-assign]  # noqa: SLF001
        close_calls_ref
    )

    window._primary_button.click()  # noqa: SLF001
    window._primary_button.click()  # noqa: SLF001
    window._primary_button.click()  # noqa: SLF001
    _pump_events_until(
        qt_application,
        lambda: (
            window._primary_button.text() == "Setup started"  # noqa: SLF001
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
    assert window._primary_button.text() == "Setup started"  # noqa: SLF001
    assert window._primary_button.isEnabled() is False  # noqa: SLF001
    assert window._path_edit.isEnabled() is False  # noqa: SLF001
    assert window._browse_button is not None  # noqa: SLF001
    assert window._browse_button.isEnabled() is False  # noqa: SLF001
    assert close_calls_ref["count"] == 1
    window.close()


def test_launcher_handoff_failure_keeps_open_setup_enabled(
    monkeypatch: pytest.MonkeyPatch,
    qt_application: QApplication,
    tmp_path: Path,
) -> None:
    """A failed setup handoff should leave a retry action instead of a dead end."""

    _ = qt_application
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")

    class _FakeLayoutInstaller:
        """Return a prepared install layout."""

        def prepare(self, install_root: Path) -> object:
            """Return the prepared layout."""

            assert install_root == layout.root
            return SimpleNamespace(layout=layout)

    class _FakeFirstRunInstaller:
        """Return an app command that the process starter will reject."""

        def continue_install(
            self, *, layout: InstallLayout, release_source: object
        ) -> object:
            """Return a fake continued install result."""

            _ = release_source
            return SimpleNamespace(
                app_version="0.4.0",
                app_command=["missing-python.exe", str(layout.app_entrypoint)],
            )

    class _FakeRuntimeInstaller:
        """Succeed runtime provisioning for handoff failure coverage."""

        def provision(self, *, layout: InstallLayout) -> object:
            """Return a successful runtime provisioning marker."""

            _ = layout
            return object()

    def _fail_handoff(_command: Sequence[str]) -> None:
        """Raise the same broad failure class as subprocess startup."""

        raise OSError("missing-python.exe was not found")

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.ui.main_window.discover_local_release_root",
        lambda: tmp_path / ".local-release-channel",
    )
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        process_starter=_fail_handoff,
        runtime_installer=_FakeRuntimeInstaller(),
    )
    window._layout_installer = cast(Any, _FakeLayoutInstaller())  # noqa: SLF001
    window._first_run_installer = cast(Any, _FakeFirstRunInstaller())  # noqa: SLF001

    window._primary_button.click()  # noqa: SLF001
    window._primary_button.click()  # noqa: SLF001
    _pump_events_until(
        qt_application,
        lambda: window._primary_button.text() == "Open setup",  # noqa: SLF001
    )

    assert window._primary_button.text() == "Open setup"  # noqa: SLF001
    assert window._primary_button.isEnabled() is True  # noqa: SLF001
    assert (
        "Could not start SugarSubstitute setup."
        in window._progress_log.log_view.toPlainText()
    )  # noqa: SLF001
    window.close()


def test_launcher_runtime_failure_keeps_runtime_retry_enabled(
    monkeypatch: pytest.MonkeyPatch,
    qt_application: QApplication,
    tmp_path: Path,
) -> None:
    """Runtime provisioning failure should not advance to setup handoff."""

    _ = qt_application
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    handoff_commands: list[list[str]] = []

    class _FakeLayoutInstaller:
        """Return a prepared install layout."""

        def prepare(self, install_root: Path) -> object:
            """Return the prepared layout."""

            assert install_root == layout.root
            return SimpleNamespace(layout=layout)

    class _FakeFirstRunInstaller:
        """Return a successful app payload install result."""

        def continue_install(
            self, *, layout: InstallLayout, release_source: object
        ) -> object:
            """Return a fake continued install result."""

            _ = release_source
            return SimpleNamespace(
                app_version="0.4.0",
                app_command=["python.exe", str(layout.app_entrypoint)],
            )

    class _FailingRuntimeInstaller:
        """Fail runtime provisioning."""

        def provision(self, *, layout: InstallLayout) -> object:
            """Raise a runtime setup failure."""

            _ = layout
            raise RuntimeError("uv.exe is missing")

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.ui.main_window.discover_local_release_root",
        lambda: tmp_path / ".local-release-channel",
    )
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        process_starter=lambda command: handoff_commands.append(list(command)),
        runtime_installer=_FailingRuntimeInstaller(),
    )
    window._layout_installer = cast(Any, _FakeLayoutInstaller())  # noqa: SLF001
    window._first_run_installer = cast(Any, _FakeFirstRunInstaller())  # noqa: SLF001

    window._primary_button.click()  # noqa: SLF001
    window._primary_button.click()  # noqa: SLF001
    _pump_events_until(
        qt_application,
        lambda: window._primary_button.text() == "Install runtime",  # noqa: SLF001
    )

    assert handoff_commands == []
    assert window._primary_button.text() == "Install runtime"  # noqa: SLF001
    assert window._primary_button.isEnabled() is True  # noqa: SLF001
    assert (  # noqa: SLF001
        "Could not install the Python runtime."
        in window._progress_log.log_view.toPlainText()
    )
    window.close()


def test_launcher_package_does_not_import_app_payload() -> None:
    """The standalone launcher package stays independent from substitute code."""

    import_names: set[str] = set()
    for path in LAUNCHER_PACKAGE_ROOT.rglob("*.py"):
        module = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                import_names.update(
                    alias.name.split(".", maxsplit=1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                import_names.add(node.module.split(".", maxsplit=1)[0])

    assert "substitute" not in import_names


def _record_close_call(close_calls_ref: dict[str, int]) -> None:
    """Record that the launcher requested its installer window to close."""

    close_calls_ref["count"] += 1
