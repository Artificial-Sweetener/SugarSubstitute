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

"""Build copyable support evidence for managed shutdown recovery."""

from __future__ import annotations

from dataclasses import dataclass

from sugarsubstitute_shared.localization import (
    ApplicationText,
    app_text,
    opaque_text,
)

from substitute.app.bootstrap.lifecycle import (
    ManagedComfyCleanupOutcome,
    ManagedComfyCleanupResult,
)


@dataclass(frozen=True)
class _ShutdownClassification:
    """Describe the stable support classification for one recovery outcome."""

    support_code: str
    label: ApplicationText
    responsibility_boundary: ApplicationText
    explanation: ApplicationText


def build_shutdown_recovery_report(
    result: ManagedComfyCleanupResult,
) -> ApplicationText:
    """Render structured, localized evidence suitable for direct support sharing."""

    classification = _classify_shutdown(result)
    return app_text(
        "Support code: %1\n"
        "Classification: %2\n"
        "Responsibility boundary: %3\n\n"
        "What happened:\n%4\n\n"
        "Observed shutdown facts:\n"
        "- Cleanup outcome: %5\n"
        "- Managed process detected before shutdown: %6\n"
        "- Ownership metadata available: %7\n"
        "- Persisted ownership metadata used: %8\n"
        "- Termination requested: %9\n"
        "- Native exit verification timed out: %10\n"
        "- Termination command timed out: %11\n"
        "- Managed process registry cleared: %12\n"
        "- Managed process ID: %13\n"
        "- Endpoint: %14\n"
        "- Cleanup elapsed: %15 milliseconds\n\n"
        "User-safe detail:\n%16\n\n"
        "Diagnostic evidence:\n%17",
        opaque_text(classification.support_code),
        classification.label,
        classification.responsibility_boundary,
        classification.explanation,
        opaque_text(result.outcome.value),
        _yes_no(result.live_process_present),
        _yes_no(result.metadata_present),
        _yes_no(result.used_persisted_metadata),
        _yes_no(result.termination_attempted),
        _yes_no(result.verification_timeout),
        _yes_no(result.taskkill_timeout),
        _yes_no(result.registry_cleared),
        _optional_number(result.pid),
        _endpoint(result.host, result.port),
        opaque_text(str(result.elapsed_ms)),
        result.technical_detail,
        opaque_text(result.diagnostic_detail or "Unavailable"),
    )


def shutdown_support_code(result: ManagedComfyCleanupResult) -> str:
    """Return the stable support code used by the visible report and logs."""

    return _classify_shutdown(result).support_code


def _classify_shutdown(result: ManagedComfyCleanupResult) -> _ShutdownClassification:
    """Attribute one failure to the narrowest boundary supported by evidence."""

    if result.verification_timeout and result.pid is not None:
        return _ShutdownClassification(
            support_code="SS-SHUTDOWN-NATIVE-EXIT-TIMEOUT",
            label=app_text("Managed process native-exit verification timeout"),
            responsibility_boundary=app_text(
                "Managed runtime or operating-system process teardown"
            ),
            explanation=app_text(
                "SugarSubstitute sent the termination request, but the operating system "
                "did not confirm that every managed process exited before the verification "
                "deadline. This does not indicate a crash in the Substitute interface."
            ),
        )
    if result.taskkill_timeout:
        return _ShutdownClassification(
            support_code="SS-SHUTDOWN-TERMINATION-COMMAND-TIMEOUT",
            label=app_text("Managed process termination command timeout"),
            responsibility_boundary=app_text(
                "Operating-system process termination command"
            ),
            explanation=app_text(
                "SugarSubstitute requested managed-process termination, but the operating "
                "system command did not finish before its deadline."
            ),
        )
    if not result.termination_attempted:
        return _ShutdownClassification(
            support_code="SS-SHUTDOWN-INTERNAL-CLEANUP-ERROR",
            label=app_text("Substitute shutdown cleanup error"),
            responsibility_boundary=app_text("Substitute shutdown orchestration"),
            explanation=app_text(
                "Substitute encountered an internal cleanup error before it could request "
                "managed-process termination."
            ),
        )
    if result.verification_timeout:
        return _ShutdownClassification(
            support_code="SS-SHUTDOWN-COORDINATOR-TIMEOUT",
            label=app_text("Substitute shutdown coordinator timeout"),
            responsibility_boundary=app_text("Substitute shutdown orchestration"),
            explanation=app_text(
                "Substitute's cleanup task did not return before the shutdown coordinator "
                "deadline, so process exit could not be verified."
            ),
        )
    if result.outcome is ManagedComfyCleanupOutcome.UNCERTAIN_SUCCESS:
        return _ShutdownClassification(
            support_code="SS-SHUTDOWN-EXIT-UNCONFIRMED",
            label=app_text("Managed process exit was not confirmed"),
            responsibility_boundary=app_text(
                "Managed runtime or operating-system process teardown"
            ),
            explanation=app_text(
                "SugarSubstitute requested termination but could not prove that the managed "
                "process family completed exit."
            ),
        )
    return _ShutdownClassification(
        support_code="SS-SHUTDOWN-TERMINATION-FAILED",
        label=app_text("Managed process termination failed"),
        responsibility_boundary=app_text("Managed process termination boundary"),
        explanation=app_text(
            "SugarSubstitute reached the managed-process termination boundary, but the "
            "termination attempt did not complete successfully."
        ),
    )


def _yes_no(value: bool) -> ApplicationText:
    """Return one localized boolean label."""

    return app_text("Yes") if value else app_text("No")


def _optional_number(value: int | None) -> ApplicationText:
    """Render one optional numeric diagnostic value without translating its digits."""

    return opaque_text(str(value)) if value is not None else app_text("Unavailable")


def _endpoint(host: str | None, port: int | None) -> ApplicationText:
    """Render one endpoint without inventing missing identity."""

    if host is None or port is None:
        return app_text("Unavailable")
    return opaque_text(f"{host}:{port}")


__all__ = ["build_shutdown_recovery_report", "shutdown_support_code"]
