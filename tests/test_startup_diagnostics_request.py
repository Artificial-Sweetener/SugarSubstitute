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

"""Tests for concrete startup diagnostics request resources."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from substitute.app.bootstrap import startup_diagnostics_request
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
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
REQUEST_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_diagnostics_request.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
MANAGED_READY_RUNTIME_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_runtime.py"
)
FORBIDDEN_REQUEST_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
)


def test_request_startup_diagnostics_titlebar_update_registers_resources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Concrete diagnostics requests should register bridge and executor resources."""

    bridge = object()
    submitter = object()
    registry = StartupResourceRegistry()
    events: list[object] = []

    def fake_prepare(**kwargs: Any) -> bool:
        """Record ports and invoke the resource registration callbacks."""

        bridge_factory = cast(Callable[[], object], kwargs["bridge_factory"])
        register_bridge = cast(Callable[[object], None], kwargs["register_bridge"])
        submitter_factory = cast(Callable[[], object], kwargs["submitter_factory"])
        register_submitter = cast(
            Callable[[object], None],
            kwargs["register_submitter"],
        )
        events.append(kwargs["metadata_providers"])
        created_bridge = bridge_factory()
        register_bridge(created_bridge)
        created_submitter = submitter_factory()
        register_submitter(created_submitter)
        return True

    monkeypatch.setattr(
        startup_diagnostics_request,
        "request_startup_diagnostics_titlebar_preparation",
        fake_prepare,
    )
    monkeypatch.setattr(
        startup_diagnostics_request,
        "startup_extension_metadata_providers",
        lambda _context: ("provider",),
    )
    monkeypatch.setattr(
        startup_diagnostics_request,
        "create_startup_diagnostics_bridge",
        lambda: bridge,
    )
    monkeypatch.setattr(
        startup_diagnostics_request,
        "create_startup_diagnostics_submitter",
        lambda **_kwargs: submitter,
    )

    started = startup_diagnostics_request.request_startup_diagnostics_titlebar_update(
        main_window=object(),
        incidents=(),
        transcript=(),
        ignore_repository=_Repository(),
        installation_context=_context(tmp_path),
        startup_resources=registry,
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
        startup_cancelled=lambda: False,
        shell_frame_available=lambda: True,
    )

    assert started is True
    assert events == [("provider",)]
    assert registry.startup_diagnostics_bridges == [bridge]
    assert len(registry.startup_diagnostics_tasks) == 1


def test_startup_diagnostics_request_imports_no_forbidden_boundaries() -> None:
    """Diagnostics request resources should avoid direct UI and process imports."""

    imported_modules = _imported_module_names(REQUEST_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_REQUEST_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_diagnostics_submitter_resource_closes_submitter() -> None:
    """Diagnostics task resources should release runtime submitter routes."""

    submitter = _CloseableSubmitter()
    resource = startup_diagnostics_request.StartupDiagnosticsSubmitterResource(
        cast(Any, submitter)
    )

    resource.shutdown()

    assert submitter.close_calls == 1


def test_startup_facade_delegates_diagnostics_request_resources() -> None:
    """Startup should not assemble diagnostics titlebar resources directly."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    runtime_source = MANAGED_READY_RUNTIME_SOURCE.read_text(encoding="utf-8")

    assert (
        "managed_ready_launch.create_startup_diagnostics_update_adapter"
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_startup_diagnostics_update_adapter" not in source
    )
    assert "create_ready_shell_startup_diagnostics_update_adapter(" not in source
    assert "create_ready_shell_startup_diagnostics_update_adapter(" in runtime_source
    assert "ReadyShellStartupDiagnosticsUpdateAdapter(" not in source
    assert "request_ready_shell_startup_diagnostics_update(" not in source
    assert "request_startup_diagnostics_titlebar_preparation(" not in source
    assert "startup_extension_metadata_providers(" not in source
    assert "StartupDiagnosticsTitlebarBridge" not in source
    assert 'thread_name_prefix="startup-diagnostics"' not in source


def _context(tmp_path: Path) -> InstallationContext:
    """Build one managed-local installation context."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            workspace_path=tmp_path / "ComfyUI",
            install_owned=True,
            launch_owned=True,
        ),
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


class _Repository:
    """No-op diagnostics ignore repository."""

    def load_ignored_fingerprints(self) -> frozenset[str]:
        """Return no ignored fingerprints."""

        return frozenset()

    def save_ignored_fingerprints(self, fingerprints: frozenset[str]) -> None:
        """Fail if the request persists ignored fingerprints."""

        pytest.fail(f"unexpected ignore persistence: {fingerprints}")


class _CloseableSubmitter:
    """Diagnostics submitter test double with close tracking."""

    def __init__(self) -> None:
        """Initialize close tracking."""

        self.close_calls = 0

    def close(self) -> None:
        """Record one close request."""

        self.close_calls += 1
