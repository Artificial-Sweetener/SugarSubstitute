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

"""Cover managed-recovery and startup-facade source boundaries."""

from __future__ import annotations


from .support import (
    FORBIDDEN_RECOVERY_IMPORT_PREFIXES,
    RECOVERY_SOURCE,
    STARTUP_MANAGED_READY_LAUNCH_SOURCE,
    STARTUP_SOURCE,
    _imported_module_names,
)


def test_managed_recovery_policy_imports_no_forbidden_boundaries() -> None:
    """Managed recovery policy should stay free of Qt, presentation, and infrastructure."""

    imported_modules = _imported_module_names(RECOVERY_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_RECOVERY_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_owns_managed_recovery_policy() -> None:
    """The startup facade should delegate managed recovery policy decisions."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    assert "def _core_nodepacks_for_compatibility_recovery" not in source
    assert "def _managed_compatibility_recovery_message" not in source
    assert "def _should_attempt_managed_core_refresh" not in source
    assert "class _ManagedCompatibilityRecoveryOutcome" not in source
    assert "_MANAGED_CORE_REFRESH_COMPATIBILITY_STATUSES" not in source
    assert "def start_managed_compatibility_recovery" not in source
    assert "def finish_managed_compatibility_recovery" not in source
    assert "def setup_managed_recovery_comfy" not in source
    assert "def cleanup_managed_recovery_state" not in source
    assert "setup_managed_recovery_comfy" not in source
    assert "cleanup_managed_recovery_state" not in source
    assert "create_managed_recovery_submitter" not in source
    assert "register_managed_recovery_submitter" not in source
    assert "confirmed_managed_recovery_termination_status()" not in source
    assert "ensure_managed_comfy_setup" not in source
    assert 'thread_name_prefix="managed-compatibility-recovery"' not in source
    assert "def mark_managed_recovery_comfy_not_ready" not in source
    assert "mark_comfy_not_ready=" not in source
    assert "def reset_managed_recovery_readiness_attempts" not in source
    assert "reset_readiness_attempts=" not in source
    assert "create_connected_managed_compatibility_recovery_controller(" not in source
    assert (
        "managed_ready_launch.create_managed_compatibility_recovery_controller("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_managed_compatibility_recovery_controller("
        not in source
    )
    assert (
        "from substitute.app.bootstrap.managed_compatibility_recovery import"
        not in source
    )
    assert "ManagedCompatibilityRecoveryController(" not in source
