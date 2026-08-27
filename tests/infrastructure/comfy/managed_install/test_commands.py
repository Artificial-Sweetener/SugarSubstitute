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

"""Verify managed-install virtualenv and pip command behavior."""

from __future__ import annotations

from __future__ import annotations
from collections.abc import Callable
from pathlib import Path
import sys
import pytest
from substitute.infrastructure.comfy import managed_install_commands
from substitute.infrastructure.comfy import managed_install_failures
from substitute.infrastructure.comfy.managed_validation import (
    workspace_python_path,
)
from sugarsubstitute_shared.windows_long_paths import subprocess_path
from sugarsubstitute_shared.startup_remote_access import StartupConnectivityError


def test_ensure_workspace_virtualenv_creates_workspace_python(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed install should create the workspace-local virtualenv explicitly."""

    observed: list[list[str]] = []
    venv_python = workspace_python_path(tmp_path)

    def _fake_stream_command(
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        on_line: Callable[[str], None] | None = None,
        creationflags: int = 0,
    ) -> int:
        _ = cwd, env, on_line, creationflags
        observed.append(command)
        venv_python.parent.mkdir(parents=True, exist_ok=True)
        venv_python.write_text("", encoding="utf-8")
        return 0

    monkeypatch.setattr(
        managed_install_commands, "stream_command", _fake_stream_command
    )

    result = managed_install_commands.ensure_workspace_virtualenv(tmp_path)

    assert result == venv_python
    assert observed == [
        [sys.executable, "-m", "venv", subprocess_path(tmp_path / ".venv")]
    ]


def test_pip_install_raises_when_streamed_install_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Streamed pip installs should fail closed on non-zero exit codes."""

    monkeypatch.setattr(
        managed_install_commands,
        "stream_command",
        lambda *args, **kwargs: 1,
    )

    with pytest.raises(RuntimeError):
        managed_install_commands.pip_install(
            tmp_path / "python.exe",
            "comfy-cli",
            on_log=lambda message: None,
        )


def test_pip_install_promotes_connectivity_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pip transport evidence must reach the launch-scoped fallback as a type."""

    def fail_offline(
        _command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        on_line: Callable[[str], None] | None = None,
        creationflags: int = 0,
    ) -> int:
        """Emit the connection failure pip reports when its index is unreachable."""

        _ = cwd, env, creationflags
        assert on_line is not None
        on_line("NewConnectionError: getaddrinfo failed")
        return 1

    monkeypatch.setattr(managed_install_commands, "stream_command", fail_offline)

    with pytest.raises(StartupConnectivityError):
        managed_install_commands.pip_install(
            tmp_path / "python.exe",
            "comfy-cli",
            on_log=lambda _message: None,
        )


def test_pip_install_classifies_storage_failure_and_keeps_managed_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pip storage errors should not be reported as generic package failures."""

    observed_env: list[dict[str, str] | None] = []
    managed_env = {"TEMP": str(tmp_path / "temp")}

    def _fake_stream_command(
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        on_line: Callable[[str], None] | None = None,
        creationflags: int = 0,
    ) -> int:
        _ = command, cwd, creationflags
        observed_env.append(env)
        assert callable(on_line)
        on_line("OSError: [Errno 28] No space left on device")
        return 1

    monkeypatch.setattr(
        managed_install_commands, "stream_command", _fake_stream_command
    )

    with pytest.raises(managed_install_failures.ManagedInstallStorageError):
        managed_install_commands.pip_install(
            tmp_path / ".venv" / "Scripts" / "python.exe",
            "torch",
            on_log=lambda _message: None,
            env=managed_env,
        )

    assert observed_env == [managed_env]


def test_ensure_workspace_virtualenv_uses_managed_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Workspace venv creation should inherit install-root temp/cache routing."""

    observed_env: list[dict[str, str] | None] = []
    managed_env = {"TEMP": str(tmp_path / "temp")}
    venv_python = workspace_python_path(tmp_path)

    def _fake_stream_command(
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        on_line: Callable[[str], None] | None = None,
        creationflags: int = 0,
    ) -> int:
        _ = command, cwd, on_line, creationflags
        observed_env.append(env)
        venv_python.parent.mkdir(parents=True, exist_ok=True)
        venv_python.write_text("", encoding="utf-8")
        return 0

    monkeypatch.setattr(
        managed_install_commands, "stream_command", _fake_stream_command
    )

    result = managed_install_commands.ensure_workspace_virtualenv(
        tmp_path, env=managed_env
    )

    assert result == venv_python
    assert observed_env == [managed_env]
