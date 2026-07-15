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

"""Tests for installed app layout and launcher-managed runtime integration."""

from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from substitute.app.bootstrap.app_layout import resolve_app_layout
from substitute.app.bootstrap.installation_context import (
    build_onboarding_service_bundle,
)
from substitute.domain.onboarding import (
    InstallationConfiguration,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.infrastructure.onboarding import (
    LauncherManagedRuntimeProvisioner,
    SubstituteRuntimeProvisioner,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingPageId,
    initial_onboarding_page,
)


def test_app_layout_resolves_installed_source_payload(tmp_path: Path) -> None:
    """Installed layouts use `<install_root>\\app` for entrypoint and requirements."""

    _write_file(tmp_path / "app" / "main.py", "print('installed')\n")
    _write_file(tmp_path / "app" / "requirements.txt", "PySide6\n")

    layout = resolve_app_layout(tmp_path)

    assert layout.installed_payload is True
    assert layout.app_dir == tmp_path.resolve() / "app"
    assert layout.entrypoint_path == tmp_path.resolve() / "app" / "main.py"
    assert layout.requirements_path == tmp_path.resolve() / "app" / "requirements.txt"


def test_app_layout_falls_back_to_source_checkout(tmp_path: Path) -> None:
    """Developer source checkout behavior remains available without app payload."""

    layout = resolve_app_layout(tmp_path)

    assert layout.installed_payload is False
    assert layout.entrypoint_path.name == "main.py"
    assert layout.requirements_path.name == "requirements.txt"
    assert layout.entrypoint_path.parent == layout.app_dir


def test_onboarding_bundle_uses_launcher_runtime_for_installed_payload(
    tmp_path: Path,
) -> None:
    """Installed app layouts validate launcher runtime instead of reinstalling deps."""

    _write_file(tmp_path / "app" / "main.py", "print('installed')\n")
    _write_file(tmp_path / "app" / "requirements.txt", "PySide6\n")

    bundle = build_onboarding_service_bundle(tmp_path)

    provisioner = bundle.runtime_service.provisioner
    assert isinstance(provisioner, LauncherManagedRuntimeProvisioner)
    assert provisioner.install_root == tmp_path.resolve()
    assert (
        provisioner.requirements_path == tmp_path.resolve() / "app" / "requirements.txt"
    )


def test_onboarding_bundle_keeps_source_checkout_runtime_provisioner(
    tmp_path: Path,
) -> None:
    """Source checkout execution keeps the developer runtime provisioner."""

    bundle = build_onboarding_service_bundle(tmp_path)

    assert isinstance(bundle.runtime_service.provisioner, SubstituteRuntimeProvisioner)


def test_launcher_runtime_provisioner_validates_without_installing_requirements(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Launcher-managed runtime validation runs no pip commands."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime_configuration = RuntimeConfiguration.create_default(installation)
    python_executable = runtime_configuration.python_executable
    assert python_executable is not None
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")
    requirements_path = tmp_path / "app" / "requirements.txt"
    _write_file(requirements_path, "PySide6\n")
    commands: list[list[str]] = []

    def _fake_run(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        stdout: object,
        stderr: object,
        stdin: object,
        startupinfo: object,
        creationflags: int,
        check: bool,
    ) -> SimpleNamespace:
        _ = stdout, stderr, stdin, startupinfo, creationflags, check
        assert cwd == requirements_path.parent
        assert env["PYTHONPATH"] == str(requirements_path.parent)
        commands.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = LauncherManagedRuntimeProvisioner(
        install_root=tmp_path,
        requirements_path=requirements_path,
    ).provision(runtime_configuration)

    assert result.bootstrap_status is RuntimeBootstrapStatus.READY
    assert result.python_executable == python_executable
    assert commands == [
        [
            str(python_executable),
            "-c",
            "import PySide6; import qfluentwidgets; import qpane; import substitute",
        ],
    ]


def test_launcher_runtime_provisioner_does_not_require_pip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Launcher-managed uv environments can be valid without `python -m pip`."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime_configuration = RuntimeConfiguration.create_default(installation)
    python_executable = runtime_configuration.python_executable
    assert python_executable is not None
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")
    requirements_path = tmp_path / "app" / "requirements.txt"
    _write_file(requirements_path, "PySide6\n")

    def _fake_run(
        command: list[str],
        **_kwargs: object,
    ) -> SimpleNamespace:
        if command[1:4] == ["-m", "pip", "--version"]:
            raise AssertionError("pip validation should not run")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = LauncherManagedRuntimeProvisioner(
        install_root=tmp_path,
        requirements_path=requirements_path,
    ).provision(runtime_configuration)

    assert result.bootstrap_status is RuntimeBootstrapStatus.READY


def test_launcher_runtime_launch_command_includes_install_root(tmp_path: Path) -> None:
    """Installed launch commands pass the authoritative install root to startup."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime_configuration = RuntimeConfiguration.create_default(installation)
    provisioner = LauncherManagedRuntimeProvisioner(
        install_root=tmp_path,
        requirements_path=tmp_path / "app" / "requirements.txt",
    )

    command = provisioner.build_launch_command(
        runtime_configuration,
        tmp_path / "app" / "main.py",
    )

    assert command == [
        str(runtime_configuration.python_executable),
        str(tmp_path / "app" / "main.py"),
        f"--install-root={tmp_path}",
    ]


def test_installed_onboarding_continues_after_launcher_owned_step_one() -> None:
    """Installed launcher mode continues with the next onboarding decision page."""

    assert (
        initial_onboarding_page(install_root_locked=True)
        is OnboardingPageId.TARGET_MODE
    )
    assert (
        initial_onboarding_page(install_root_locked=False) is OnboardingPageId.WELCOME
    )


def _write_file(path: Path, content: str) -> None:
    """Write one fixture file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
