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

"""Verify installed-launch startup-plan resolution and route selection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher import app as launcher_app
from launcher.sugarsubstitute_launcher.cli import parse_launcher_args
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import (
    InstallLayout,
    default_install_root,
)
from launcher.sugarsubstitute_launcher.startup_plan import (
    is_installed_app_launchable,
    resolve_install_root,
    resolve_startup_plan,
    should_launch_installed_app,
)
from sugarsubstitute_shared.installer_qualification import (
    INSTALLER_QUALIFICATION_PLAN_ENV,
    InstallerQualificationPlan,
)
from tests.launcher.support import write_launcher_executable


def test_launcher_resolves_installed_exe_parent_as_install_root(
    tmp_path: Path,
) -> None:
    """Resolve an installed executable's adjacent configuration root."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    write_launcher_executable(layout)

    resolved_root = resolve_install_root(
        explicit_install_root=None,
        executable_path=layout.executable_path,
    )

    assert resolved_root == layout.root


def test_launcher_resolves_install_root_from_frozen_support_bundle(
    tmp_path: Path,
) -> None:
    """Retain installed root through a symlink-resolved frozen support path."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    write_launcher_executable(layout)
    layout.launcher_support_path.mkdir(parents=True, exist_ok=True)
    resolved_executable = layout.launcher_support_path / layout.executable_path.name
    resolved_executable.write_text("", encoding="utf-8")

    startup_plan = resolve_startup_plan(
        explicit_install_root=None,
        executable_path=resolved_executable,
        frozen_support_path=layout.launcher_support_path,
    )

    assert startup_plan.layout == layout
    assert startup_plan.installed_config_found is True
    assert startup_plan.installed_config_valid is True


def test_launcher_resolves_install_root_from_frozen_invocation_path(
    tmp_path: Path,
) -> None:
    """Prefer the invoked bundle path over unrelated frozen runtime paths."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    write_launcher_executable(layout)
    unrelated_bundle = tmp_path / "frozen-runtime"
    unrelated_bundle.mkdir()
    resolved_executable = unrelated_bundle / layout.executable_path.name
    resolved_executable.write_text("", encoding="utf-8")

    startup_plan = resolve_startup_plan(
        explicit_install_root=None,
        executable_path=resolved_executable,
        frozen_support_path=unrelated_bundle,
        invocation_path=layout.executable_path,
    )

    assert startup_plan.layout == layout
    assert startup_plan.installed_config_found is True
    assert startup_plan.installed_config_valid is True


def test_launcher_resolves_install_root_from_nested_frozen_runtime_path(
    tmp_path: Path,
) -> None:
    """Find a validated installed ancestor from nested PyInstaller paths."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    write_launcher_executable(layout)
    nested_runtime = layout.launcher_support_path / "runtime" / "nested"
    nested_runtime.mkdir(parents=True)
    nested_executable = nested_runtime / layout.executable_path.name
    nested_executable.write_text("", encoding="utf-8")

    startup_plan = resolve_startup_plan(
        explicit_install_root=None,
        executable_path=nested_executable,
        frozen_support_path=nested_runtime,
        invocation_path=nested_executable,
        working_directory_path=tmp_path,
    )

    assert startup_plan.layout == layout
    assert startup_plan.installed_config_found is True
    assert startup_plan.installed_config_valid is True


def test_launcher_resolves_installed_root_from_validated_working_directory(
    tmp_path: Path,
) -> None:
    """Accept the configured installation working directory for process launches."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    write_launcher_executable(layout)
    unrelated_runtime = tmp_path / "runtime"
    unrelated_runtime.mkdir()
    runtime_executable = unrelated_runtime / layout.executable_path.name
    runtime_executable.write_text("", encoding="utf-8")

    startup_plan = resolve_startup_plan(
        explicit_install_root=None,
        executable_path=runtime_executable,
        frozen_support_path=unrelated_runtime,
        invocation_path=runtime_executable,
        working_directory_path=layout.root,
    )

    assert startup_plan.layout == layout
    assert startup_plan.installed_config_found is True
    assert startup_plan.installed_config_valid is True


def test_launcher_resolves_installed_root_from_native_process_image(
    tmp_path: Path,
) -> None:
    """Preserve installed identity through rewritten PyInstaller paths."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    write_launcher_executable(layout)
    unrelated_runtime = tmp_path / "runtime"
    unrelated_runtime.mkdir()
    runtime_executable = unrelated_runtime / layout.executable_path.name
    runtime_executable.write_text("", encoding="utf-8")

    startup_plan = resolve_startup_plan(
        explicit_install_root=None,
        executable_path=runtime_executable,
        frozen_support_path=unrelated_runtime,
        invocation_path=runtime_executable,
        native_executable_path=layout.executable_path,
        working_directory_path=tmp_path,
    )

    assert startup_plan.layout == layout
    assert startup_plan.installed_config_found is True
    assert startup_plan.installed_config_valid is True


@pytest.mark.platforms("linux", "macos")
def test_launcher_accepts_configured_runtime_python_symlink(tmp_path: Path) -> None:
    """Retain configured install identity through a POSIX venv Python symlink."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    write_launcher_executable(layout)
    managed_python = tmp_path / "uv-managed-python" / "python"
    managed_python.parent.mkdir(parents=True)
    managed_python.write_text("", encoding="utf-8")
    layout.runtime_python.parent.mkdir(parents=True)
    layout.runtime_python.symlink_to(managed_python)

    startup_plan = resolve_startup_plan(
        explicit_install_root=None,
        executable_path=layout.executable_path,
    )

    assert startup_plan.layout == layout
    assert startup_plan.installed_config_found is True
    assert startup_plan.installed_config_valid is True


def test_launcher_records_token_bound_startup_route(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Record the resolved route against release-qualification identity."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    write_launcher_executable(layout)
    startup_plan = resolve_startup_plan(
        explicit_install_root=None,
        executable_path=layout.executable_path,
    )
    event_log_path = tmp_path / "qualification.jsonl"
    qualification_plan = InstallerQualificationPlan(
        token="route-token",
        install_root=layout.root,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        event_log_path=event_log_path,
        timeout_seconds=30.0,
    )
    monkeypatch.setenv(
        INSTALLER_QUALIFICATION_PLAN_ENV,
        qualification_plan.to_json(),
    )

    launcher_app._record_qualification_startup_route(startup_plan)

    event = json.loads(event_log_path.read_text(encoding="utf-8"))
    assert event["event"] == "launcher.startup.resolved"
    assert event["token"] == "route-token"
    assert event["fields"]["installed_config_found"] is True
    assert event["fields"]["installed_config_valid"] is True
    assert event["fields"]["resolved_root"] == str(layout.root)


def test_setup_executable_does_not_adopt_ancestor_install_config(
    tmp_path: Path,
) -> None:
    """Keep a setup bundle inside an installation on the explicit setup route."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    setup_name = f"SugarSubstitute Setup{layout.executable_path.suffix}"
    setup_executable = layout.root / "downloads" / setup_name
    setup_executable.parent.mkdir(parents=True)
    setup_executable.write_text("", encoding="utf-8")

    startup_plan = resolve_startup_plan(
        explicit_install_root=None,
        executable_path=setup_executable,
        invocation_path=setup_executable,
        working_directory_path=layout.root,
    )

    assert startup_plan.installed_config_found is False
    assert startup_plan.layout.root == default_install_root(setup_executable)


def test_launcher_ignores_adjacent_app_without_launcher_config(
    tmp_path: Path,
) -> None:
    """Require adjacent launcher configuration before treating a launch as installed."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    layout.root.mkdir(parents=True)
    write_launcher_executable(layout)
    layout.app_entrypoint.parent.mkdir(parents=True, exist_ok=True)
    layout.app_entrypoint.write_text("", encoding="utf-8")

    startup_plan = resolve_startup_plan(
        explicit_install_root=None,
        executable_path=layout.executable_path,
    )

    assert startup_plan.installed_config_found is False
    assert startup_plan.layout.root == default_install_root(layout.executable_path)


def test_launcher_launches_installed_app_only_after_install_is_ready(
    tmp_path: Path,
) -> None:
    """Bypass setup only when an installed layout is complete and launchable."""

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
    """Keep continue-install and repair invocations on the setup route."""

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
