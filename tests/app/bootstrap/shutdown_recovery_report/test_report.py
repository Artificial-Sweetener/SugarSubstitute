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

"""Tests for actionable managed-shutdown recovery reports."""

from __future__ import annotations

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.app.bootstrap.lifecycle import (
    ManagedComfyCleanupOutcome,
    ManagedComfyCleanupResult,
)
from substitute.app.bootstrap.shutdown_recovery_report import (
    build_shutdown_recovery_report,
)


def test_report_classifies_native_exit_timeout_at_runtime_boundary() -> None:
    """A native wait timeout should not be presented as a Substitute UI crash."""

    report = render_source_application_text(
        build_shutdown_recovery_report(
            _cleanup_result(
                outcome=ManagedComfyCleanupOutcome.UNCERTAIN_SUCCESS,
                termination_attempted=True,
                verification_timeout=True,
                diagnostic_detail=(
                    "TimeoutError: A supervised job member has not completed native exit."
                ),
            )
        )
    )

    assert "Support code: SS-SHUTDOWN-NATIVE-EXIT-TIMEOUT" in report
    assert "Classification: Managed process native-exit verification timeout" in report
    assert (
        "Responsibility boundary: Managed runtime or operating-system process teardown"
        in report
    )
    assert "This does not indicate a crash in the Substitute interface." in report
    assert "Managed process detected before shutdown: Yes" in report
    assert "Termination requested: Yes" in report
    assert "Native exit verification timed out: Yes" in report
    assert "Managed process registry cleared: No" in report
    assert "Managed process ID: 53792" in report
    assert "Endpoint: 127.0.0.1:8188" in report
    assert (
        "Diagnostic evidence:\n"
        "TimeoutError: A supervised job member has not completed native exit." in report
    )


def test_report_classifies_pretermination_exception_as_internal_cleanup_error() -> None:
    """A failure before termination should identify Substitute orchestration as owner."""

    report = render_source_application_text(
        build_shutdown_recovery_report(
            _cleanup_result(
                outcome=ManagedComfyCleanupOutcome.FAILURE,
                termination_attempted=False,
                verification_timeout=False,
                diagnostic_detail=(
                    "Cleanup encountered an unexpected error before termination could be verified."
                ),
            )
        )
    )

    assert "Support code: SS-SHUTDOWN-INTERNAL-CLEANUP-ERROR" in report
    assert "Classification: Substitute shutdown cleanup error" in report
    assert "Responsibility boundary: Substitute shutdown orchestration" in report
    assert "Termination requested: No" in report


def _cleanup_result(
    *,
    outcome: ManagedComfyCleanupOutcome,
    termination_attempted: bool,
    verification_timeout: bool,
    diagnostic_detail: str,
) -> ManagedComfyCleanupResult:
    """Build one representative cleanup result with real support-relevant evidence."""

    return ManagedComfyCleanupResult(
        cleanup_ran=True,
        outcome=outcome,
        managed_resource_present=True,
        live_process_present=True,
        metadata_present=True,
        used_persisted_metadata=False,
        termination_attempted=termination_attempted,
        registry_cleared=False,
        pid=53792,
        host="127.0.0.1",
        port=8188,
        workspace=None,
        elapsed_ms=6734,
        taskkill_timeout=False,
        verification_timeout=verification_timeout,
        user_detail="Substitute could not confirm that shutdown finished.",
        technical_detail=(
            "Shutdown could not be confirmed before the verification timeout."
        ),
        diagnostic_detail=diagnostic_detail,
    )
