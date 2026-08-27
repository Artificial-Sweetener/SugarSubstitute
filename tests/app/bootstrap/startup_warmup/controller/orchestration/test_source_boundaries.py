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

"""Test startup-warmup behavior owners."""

from __future__ import annotations

from pathlib import Path


from .support import (
    _imported_module_names,
)

PROJECT_ROOT = Path(__file__).resolve().parents[6]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
STARTUP_WARMUP_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_warmup_controller.py"
)
FORBIDDEN_STARTUP_WARMUP_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_startup_warmup_controller_imports_no_forbidden_boundaries() -> None:
    """Warmup controller should not import concrete UI, IO, or subprocess owners."""

    imported_modules = _imported_module_names(STARTUP_WARMUP_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_STARTUP_WARMUP_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_direct_warmup_starts() -> None:
    """Startup should delegate direct warmup starts to the warmup controller."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    nonessential_warmup_source = launch_source[
        launch_source.index(
            "managed_ready_launch.create_nonessential_startup_warmup_runtime("
        ) : launch_source.index(
            "diagnostics_update_adapter =",
        )
    ]

    assert "def start_cube_icon_startup_warmup" not in source
    assert "def start_local_editor_startup_warmup" not in source
    assert "def start_backend_editor_startup_warmup" not in source
    assert "def schedule_nonessential_startup_warmups" not in source
    assert "def connect_restore_finalized_warmups" not in source
    assert "def start_nonessential_startup_warmups" not in source
    assert "def run_nonessential_startup_warmups" not in source
    assert (
        "managed_ready_launch.create_nonessential_startup_warmup_runtime("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_nonessential_startup_warmup_runtime("
        not in source
    )
    assert (
        "from substitute.app.bootstrap.startup_warmup_controller import" not in source
    )
    assert "create_nonessential_startup_warmup_launcher(" not in source
    assert "NonessentialStartupWarmupLauncher(" not in source
    assert "create_nonessential_startup_warmup_scheduler(" not in source
    assert "NonessentialStartupWarmupScheduler(" not in source
    assert "managed_ready_launch.create_managed_startup_prelude(" in launch_source
    assert "managed_ready_runtime.create_managed_startup_prelude(" not in source
    assert "managed_ready_runtime.start_cutecanvas_sam_startup_warmup" not in source
    assert "create_ready_shell_managed_startup_prelude(" not in source
    assert "managed_ready_launch.create_local_editor_warmup_adapter(" in launch_source
    assert "managed_ready_runtime.create_local_editor_warmup_adapter(" not in source
    assert "create_ready_shell_local_editor_warmup_adapter(" not in source
    assert "ReadyShellLocalEditorWarmupAdapter(" not in source
    assert (
        "readiness_state=readiness_controller_state" not in nonessential_warmup_source
    )
    assert "mark_pending_backend=lambda" not in source
    assert "schedule_nonessential_startup_warmups(" not in source
    assert "start_local_editor_startup_warmup(" not in source
    assert "StartupCubeIconWarmupHandle(" not in source
    assert "CuteCanvasSamStartupWarmupHandle(" not in source
    assert "LocalEditorStartupWarmupHandle(" not in source
    assert "BackendEditorStartupWarmupHandle(" not in source
