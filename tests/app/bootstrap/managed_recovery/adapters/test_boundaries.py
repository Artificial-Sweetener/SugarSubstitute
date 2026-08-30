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

"""Exercise one managed-recovery adapter behavior owner."""

from __future__ import annotations

from .support import (
    ADAPTER_SOURCE,
    FORBIDDEN_ADAPTER_IMPORT_PREFIXES,
    MANAGED_READY_RUNTIME_SOURCE,
    STARTUP_MANAGED_READY_LAUNCH_SOURCE,
    STARTUP_SOURCE,
    _imported_module_names,
)


def test_managed_recovery_adapters_import_no_forbidden_boundaries() -> None:
    """Concrete recovery adapters should avoid direct Qt/UI/process-shell imports."""

    imported_modules = _imported_module_names(ADAPTER_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_ADAPTER_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_managed_recovery_concrete_adapters() -> None:
    """Startup should delegate concrete managed recovery adapter details."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    managed_ready_runtime_source = MANAGED_READY_RUNTIME_SOURCE.read_text(
        encoding="utf-8"
    )

    assert "from concurrent.futures import" not in source
    assert "ensure_managed_comfy_setup" not in source
    assert 'thread_name_prefix="managed-compatibility-recovery"' not in source
    assert "def setup_managed_recovery_comfy" not in source
    assert "def cleanup_managed_recovery_state" not in source
    assert "def append_managed_recovery_message" not in source
    assert "def emit_managed_recovery_log" not in source
    assert "def handle_managed_recovery_failure" not in source
    assert "def relaunch_managed_recovery_comfy" not in source
    assert (
        "managed_ready_runtime.create_managed_recovery_startup_adapters(" not in source
    )
    assert (
        "from substitute.app.bootstrap.managed_recovery_adapters import" not in source
    )
    assert "create_managed_recovery_controller_adapters(" not in source
    assert (
        "create_managed_recovery_controller_adapters(" in managed_ready_runtime_source
    )
    assert "create_managed_recovery_startup_adapters(" in managed_ready_runtime_source
    assert "managed_ready_runtime.managed_recovery_controller_adapters" not in source
    assert (
        "managed_ready_launch.create_managed_compatibility_recovery_controller("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_managed_compatibility_recovery_controller("
        not in source
    )
    assert "startup_adapters=" not in source
    assert "ManagedRecoveryStartupAdapters(" not in source
    assert "ManagedRecoveryControllerAdapters(" not in source
    assert "create_managed_recovery_executor" not in source
    assert "register_managed_recovery_executor" not in source
    assert "cleanup_managed_recovery_state" not in source
    assert "setup_managed_recovery_comfy" not in source
    assert "confirmed_managed_recovery_termination_status()" not in source
