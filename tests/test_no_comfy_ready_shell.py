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

"""Tests for no-Comfy ready-shell startup."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.app.bootstrap.no_comfy_ready_shell import (
    NoComfyReadyShellResult,
    launch_no_comfy_ready_shell,
    publish_no_comfy_ready_shell_result,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NO_COMFY_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "no_comfy_ready_shell.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
FORBIDDEN_NO_COMFY_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
)


def test_launch_no_comfy_ready_shell_closes_splash_and_shows_shell(
    tmp_path: Path,
) -> None:
    """No-Comfy launch should close splash, show shell, and attach reload."""

    calls: list[object] = []
    context = _context(tmp_path)
    splash = _Splash(calls)
    shell_frame = object()
    comfy_output_stream = object()
    shutdown_request = object()
    startup_timer = object()
    runtime_services = object()
    shell_placement = object()
    workspace = object()

    result = launch_no_comfy_ready_shell(
        context=context,
        splash=splash,
        comfy_output_stream=comfy_output_stream,
        shutdown_request=shutdown_request,
        startup_timer=startup_timer,
        runtime_services=runtime_services,
        initial_shell_placement=shell_placement,
        initial_workspace=workspace,
        show_main_window=lambda *args, **kwargs: _show_shell(
            calls,
            shell_frame,
            args,
            kwargs,
        ),
        attach_gui_reload_command=lambda frame: calls.append(("attach", frame)),
    )

    assert result == NoComfyReadyShellResult(
        shell_frame=shell_frame,
        splash=None,
    )
    assert calls == [
        "splash_close",
        (
            "show",
            (context,),
            {
                "comfy_output_stream": comfy_output_stream,
                "shutdown_request": shutdown_request,
                "startup_timer": startup_timer,
                "runtime_services": runtime_services,
                "initial_shell_placement": shell_placement,
                "initial_workspace": workspace,
            },
        ),
        ("attach", shell_frame),
    ]


def test_launch_no_comfy_ready_shell_tolerates_splash_close_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Splash close errors should be logged without blocking shell launch."""

    exception_logs: list[str] = []
    monkeypatch.setattr(
        "substitute.app.bootstrap.no_comfy_ready_shell.log_exception",
        lambda _logger, message: exception_logs.append(message),
    )
    shell_frame = object()
    attached_frames: list[object] = []

    result = launch_no_comfy_ready_shell(
        context=_context(tmp_path),
        splash=_FailingSplash(),
        comfy_output_stream=object(),
        shutdown_request=object(),
        startup_timer=object(),
        runtime_services=object(),
        initial_shell_placement=None,
        initial_workspace=None,
        show_main_window=lambda *_args, **_kwargs: shell_frame,
        attach_gui_reload_command=attached_frames.append,
    )

    assert result.shell_frame is shell_frame
    assert result.splash is None
    assert attached_frames == [shell_frame]
    assert exception_logs == ["Failed to close launch splash"]


def test_publish_no_comfy_ready_shell_result_updates_current_shell() -> None:
    """No-Comfy result handoff should publish the shown shell to reload state."""

    shell_frame = object()
    result = NoComfyReadyShellResult(shell_frame=shell_frame, splash=None)
    current_shells: list[object] = []

    published_result = publish_no_comfy_ready_shell_result(
        result,
        set_current_shell=current_shells.append,
    )

    assert published_result is result
    assert current_shells == [shell_frame]


def test_no_comfy_ready_shell_imports_no_forbidden_boundaries() -> None:
    """No-Comfy shell launch should stay free of Qt and process boundaries."""

    imported_modules = _imported_module_names(NO_COMFY_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_NO_COMFY_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_no_comfy_shell_launch() -> None:
    """Startup should delegate no-Comfy show/close/reload wiring."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "run_startup_shell_flow(" in source
    assert "create_ready_shell_launch_controller(" not in source
    assert "ReadyShellLaunchController(" not in source
    assert "launch_no_comfy_ready_shell(" not in source
    assert "publish_no_comfy_ready_shell_result(" not in source
    assert ".set_current_shell(shell_frame)" not in source
    assert "ready_shell.no_comfy.show_main_window" not in source
    assert "ready_shell.no_comfy.shown" not in source


class _Splash:
    """Splash test double."""

    def __init__(self, calls: list[object]) -> None:
        """Store shared call sink."""

        self._calls = calls

    def close(self) -> None:
        """Record splash close."""

        self._calls.append("splash_close")


class _FailingSplash:
    """Splash test double that fails on close."""

    def close(self) -> None:
        """Raise one close failure."""

        raise RuntimeError("close failed")


def _show_shell(
    calls: list[object],
    shell_frame: object,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> object:
    """Record one shell show call."""

    calls.append(("show", args, kwargs))
    return shell_frame


def _context(tmp_path: Path) -> InstallationContext:
    """Build one installation context for no-Comfy startup tests."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
    )


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
