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

"""Tests for the managed-Comfy process lifetime lease."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.app.bootstrap.lifecycle import (
    ManagedComfyCleanupOutcome,
    ManagedComfyCleanupResult,
)
from substitute.app.bootstrap.startup_shutdown import (
    ManagedComfyLease,
    ManagedComfyLeaseError,
)


def test_managed_comfy_lease_allows_one_active_gui_reload() -> None:
    """A GUI reload lease should mark only the active transaction as sanctioned."""

    lease = ManagedComfyLease(lambda: _cleanup_result())

    with lease.begin_gui_reload():
        assert lease.gui_reload_active is True
        with pytest.raises(ManagedComfyLeaseError):
            lease.begin_gui_reload()

    assert lease.gui_reload_active is False


def test_managed_comfy_lease_cleanup_still_runs_during_gui_reload() -> None:
    """Process exit during reload must still invoke managed Comfy cleanup."""

    calls: list[str] = []

    def cleanup() -> ManagedComfyCleanupResult:
        """Record one cleanup invocation."""

        calls.append("cleanup")
        return _cleanup_result()

    lease = ManagedComfyLease(cleanup)

    with lease.begin_gui_reload():
        result = lease.cleanup()

    assert result.outcome is ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS
    assert calls == ["cleanup"]
    assert lease.cleanup_finished is True


def test_managed_comfy_lease_blocks_reload_after_terminal_cleanup() -> None:
    """A GUI reload cannot begin after managed cleanup has finished."""

    lease = ManagedComfyLease(lambda: _cleanup_result())

    lease.cleanup()

    with pytest.raises(ManagedComfyLeaseError):
        lease.begin_gui_reload()


def test_managed_comfy_lease_allows_retry_after_failed_cleanup() -> None:
    """Failed cleanup attempts should not close the lease against retry."""

    lease = ManagedComfyLease(
        lambda: _cleanup_result(ManagedComfyCleanupOutcome.FAILURE)
    )

    result = lease.cleanup()

    assert result.outcome is ManagedComfyCleanupOutcome.FAILURE
    assert lease.cleanup_finished is False
    with lease.begin_gui_reload():
        assert lease.gui_reload_active is True


def _cleanup_result(
    outcome: ManagedComfyCleanupOutcome = ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS,
) -> ManagedComfyCleanupResult:
    """Build one deterministic managed-Comfy cleanup result."""

    return ManagedComfyCleanupResult(
        cleanup_ran=True,
        outcome=outcome,
        managed_resource_present=outcome
        is not ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED,
        live_process_present=False,
        metadata_present=outcome is not ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED,
        used_persisted_metadata=False,
        termination_attempted=outcome
        is not ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED,
        registry_cleared=outcome is ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS,
        pid=1234,
        host="127.0.0.1",
        port=8188,
        workspace=Path("E:/ComfyUI"),
        elapsed_ms=10,
        taskkill_timeout=False,
        verification_timeout=False,
        user_detail="done",
        technical_detail="done",
        diagnostic_detail="done",
    )
