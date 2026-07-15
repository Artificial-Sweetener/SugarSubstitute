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

"""Tests for ready-shell startup trace field ownership."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from substitute.app.bootstrap.ready_shell_trace_fields import (
    ReadyShellTraceFieldsProvider,
    create_ready_shell_trace_fields_provider,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRACE_FIELDS_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "ready_shell_trace_fields.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
FORBIDDEN_TRACE_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_ready_shell_trace_fields_provider_reads_current_startup_state() -> None:
    """Ready-shell trace fields should reflect current gate and recovery state."""

    startup = _MutableFlag(value=False)
    shell = _MutableFlag(value=False)
    provisional = _MutableFlag(value=True)
    ready_state = SimpleNamespace(
        minimum_shell_ready=False,
        comfy_http_ready=True,
        main_window_shown=False,
        prehydration_attempted=True,
        prehydration_succeeded=False,
        hydration_started=False,
    )
    readiness_state = SimpleNamespace(
        readiness_attempts=3,
        nonessential_startup_warmups_pending_backend=True,
    )
    recovery_state = SimpleNamespace(
        recovery_attempted=True,
        recovery_running=False,
    )
    projection_state = SimpleNamespace(pending=True)
    provider = ReadyShellTraceFieldsProvider(
        startup_cancelled=lambda: startup.value,
        shell_frame_present=lambda: shell.value,
        ready_state=ready_state,
        readiness_state=readiness_state,
        recovery_state=recovery_state,
        pre_show_restore_projection_state=projection_state,
        provisional_restore_projection_present=lambda: provisional.value,
    )

    fields = provider()

    assert fields == {
        "startup_cancelled": False,
        "shell_frame_present": False,
        "minimum_shell_ready": False,
        "comfy_http_ready": True,
        "main_window_shown": False,
        "prehydration_attempted": True,
        "prehydration_succeeded": False,
        "hydration_started": False,
        "readiness_attempts": 3,
        "managed_compatibility_recovery_attempted": True,
        "managed_compatibility_recovery_running": False,
        "pre_show_restore_projection_pending": True,
        "nonessential_startup_warmups_pending_backend": True,
        "provisional_restore_projection_present": True,
    }

    startup.value = True
    shell.value = True
    provisional.value = False
    ready_state.minimum_shell_ready = True
    readiness_state.readiness_attempts = 4
    recovery_state.recovery_running = True
    projection_state.pending = False

    updated_fields = provider()

    assert updated_fields["startup_cancelled"] is True
    assert updated_fields["shell_frame_present"] is True
    assert updated_fields["minimum_shell_ready"] is True
    assert updated_fields["readiness_attempts"] == 4
    assert updated_fields["managed_compatibility_recovery_running"] is True
    assert updated_fields["pre_show_restore_projection_pending"] is False
    assert updated_fields["provisional_restore_projection_present"] is False


def test_ready_shell_trace_fields_factory_creates_provider() -> None:
    """Trace-field factory should expose the provider as the owner entry point."""

    ready_state = SimpleNamespace(
        minimum_shell_ready=True,
        comfy_http_ready=False,
        main_window_shown=True,
        prehydration_attempted=False,
        prehydration_succeeded=False,
        hydration_started=True,
    )
    readiness_state = SimpleNamespace(
        readiness_attempts=2,
        nonessential_startup_warmups_pending_backend=False,
    )
    recovery_state = SimpleNamespace(
        recovery_attempted=False,
        recovery_running=False,
    )
    projection_state = SimpleNamespace(pending=False)

    provider = create_ready_shell_trace_fields_provider(
        startup_cancelled=lambda: False,
        shell_frame_present=lambda: True,
        ready_state=ready_state,
        readiness_state=readiness_state,
        recovery_state=recovery_state,
        pre_show_restore_projection_state=projection_state,
        provisional_restore_projection_present=lambda: False,
    )

    assert isinstance(provider, ReadyShellTraceFieldsProvider)
    assert provider()["shell_frame_present"] is True
    assert provider()["hydration_started"] is True


def test_ready_shell_trace_fields_imports_no_forbidden_boundaries() -> None:
    """Ready-shell trace fields should remain pure bootstrap observability."""

    imported_modules = _imported_module_names(TRACE_FIELDS_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_TRACE_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_ready_shell_trace_field_assembly() -> None:
    """Startup should delegate ready-shell trace field assembly."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    assert "managed_ready_launch.create_ready_trace_fields(" in launch_source
    assert (
        "managed_ready_runtime.create_ready_shell_trace_fields_provider(" not in source
    )
    assert "from substitute.app.bootstrap.ready_shell_trace_fields import" not in source
    assert "ReadyShellTraceFieldsProvider(" not in source
    assert "def ready_trace_fields" not in source
    assert '"managed_compatibility_recovery_attempted"' not in source


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


class _MutableFlag:
    """Expose mutable boolean state through callables."""

    def __init__(self, *, value: bool) -> None:
        """Store the initial value."""

        self.value = value
