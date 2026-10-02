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

"""Supervise a candidate application until its visible shell proves readiness."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
import json
import logging
from pathlib import Path
import secrets
import subprocess
import threading
import time

from launcher.sugarsubstitute_launcher.application_startup_contract import (
    CandidateProcess,
    DEFAULT_READINESS_TIMEOUT_SECONDS,
    ApplicationStartupCancelled,
    ApplicationStartupCompleted,
    ApplicationReadinessError,
)
from launcher.sugarsubstitute_launcher.application_readiness_qualification import (
    publish_qualification_receipt,
)
from launcher.sugarsubstitute_launcher.application_readiness_contract import (
    resolve_readiness_contract,
    publish_outer_receipt,
    extended_attestation_chain,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from sugarsubstitute_shared.application_readiness import (
    ApplicationReadinessReceipt,
    ApplicationReadinessSurface,
    READINESS_ACCEPTED_SCHEMA_VERSIONS_ENV,
    READINESS_DELEGATION_PATH_ENV,
    READINESS_DELEGATION_SCHEMA_ENV,
    READINESS_DELEGATION_TOKEN_ENV,
    READINESS_PATH_ENV,
    READINESS_SCHEMA_ENV,
    READINESS_SCHEMA_VERSION,
    READINESS_TOKEN_ENV,
    WRITABLE_READINESS_SCHEMA_VERSIONS,
)


_POLL_INTERVAL_SECONDS = 0.05
_RECEIPT_PUBLICATION_GRACE_SECONDS = 2.0
_TERMINATION_TIMEOUT_SECONDS = 5.0
_LOGGER = logging.getLogger(__name__)


def _unreadable_receipt_error(receipt_path: Path) -> ApplicationReadinessError:
    """Report a receipt that remained unreadable after publication settled."""

    return ApplicationReadinessError(
        f"SugarSubstitute wrote an invalid readiness receipt: {receipt_path}.",
        diagnostics={
            "readiness_failure_kind": "unreadable_receipt",
            "readiness_observed_schema": "unavailable",
        },
    )


class ApplicationReadinessSupervisor:
    """Start an application and require an accepted visible-surface receipt."""

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_READINESS_TIMEOUT_SECONDS,
        process_starter: Callable[
            [Sequence[str], Mapping[str, str]], tuple[CandidateProcess, Path]
        ]
        | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        wait: Callable[[float], object] | None = None,
        token_factory: Callable[[], str] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
        accepted_surfaces: Collection[ApplicationReadinessSurface] = (
            ApplicationReadinessSurface.MAIN_SHELL,
        ),
    ) -> None:
        """Store bounded process, clock, and surface-policy collaborators."""

        if timeout_seconds <= 0:
            raise ValueError("Application readiness timeout must be positive.")
        if not accepted_surfaces:
            raise ValueError("At least one application readiness surface is required.")
        self._timeout_seconds = timeout_seconds
        self._process_starter = process_starter or _start_candidate_process
        self._monotonic = monotonic
        self._wait = wait or threading.Event().wait
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self._accepted_surfaces = frozenset(accepted_surfaces)
        self._cancellation_requested = cancellation_requested

    def launch_until_ready(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
        expected_exit: Callable[[CandidateProcess], bool] | None = None,
    ) -> CandidateProcess:
        """Return the running process after an accepted surface is responsive."""

        self._check_cancellation()

        contract = resolve_readiness_contract(
            layout=layout, environment=environment, token_factory=self._token_factory
        )
        receipt_path = contract.child_receipt_path
        token = contract.child_token
        receipt_path.unlink(missing_ok=True)
        child_environment = dict(environment)
        child_environment[READINESS_PATH_ENV] = str(receipt_path)
        child_environment[READINESS_TOKEN_ENV] = token
        child_environment[READINESS_ACCEPTED_SCHEMA_VERSIONS_ENV] = ",".join(
            str(version) for version in WRITABLE_READINESS_SCHEMA_VERSIONS
        )
        child_environment[READINESS_SCHEMA_ENV] = str(READINESS_SCHEMA_VERSION)
        if contract.outer_receipts:
            delegated_receipt = contract.outer_receipts[-1]
            child_environment[READINESS_DELEGATION_PATH_ENV] = str(
                delegated_receipt.path
            )
            child_environment[READINESS_DELEGATION_TOKEN_ENV] = delegated_receipt.token
            child_environment[READINESS_DELEGATION_SCHEMA_ENV] = str(
                delegated_receipt.schema_version
            )
        process, startup_log_path = self._process_starter(
            command,
            child_environment,
        )
        started_at = self._monotonic()
        _LOGGER.info(
            "Started supervised application candidate | candidate_pid=%s | "
            "accepted_surfaces=%s | outer_contract=%s",
            process.pid,
            ",".join(sorted(surface.value for surface in self._accepted_surfaces)),
            bool(contract.outer_receipts),
        )
        try:
            deadline = started_at + self._timeout_seconds
            receipt_access_deadline: float | None = None
            receipt_access_error: OSError | None = None
            while self._monotonic() < deadline:
                self._check_cancellation(process)
                return_code = process.poll()
                if return_code is not None:
                    if expected_exit is not None and expected_exit(process):
                        _LOGGER.info(
                            "Accepted authenticated launcher startup completion | candidate_pid=%s | exit_code=%s",
                            process.pid,
                            return_code,
                        )
                        raise ApplicationStartupCompleted(process)
                    raise ApplicationReadinessError(
                        "SugarSubstitute exited before its main window became ready. "
                        f"Exit code: {return_code}. Startup log: {startup_log_path}.",
                        terminated_process=process,
                        diagnostics={"readiness_failure_kind": "process_exit"},
                    )
                if receipt_path.exists():
                    try:
                        receipt = self._validate_receipt(
                            receipt_path=receipt_path,
                            expected_token=token,
                            expected_pid=process.pid,
                        )
                    except (PermissionError, FileNotFoundError) as error:
                        receipt_access_error = error
                        observed_at = self._monotonic()
                        if receipt_access_deadline is None:
                            receipt_access_deadline = min(
                                deadline,
                                observed_at + _RECEIPT_PUBLICATION_GRACE_SECONDS,
                            )
                        if observed_at >= receipt_access_deadline:
                            raise _unreadable_receipt_error(receipt_path) from error
                        self._wait(_POLL_INTERVAL_SECONDS)
                        continue
                    self._require_accepted_surface(receipt)
                    publish_outer_receipt(contract=contract, receipt=receipt)
                    publish_qualification_receipt(
                        environment=environment,
                        receipt=receipt,
                        attester_pids=extended_attestation_chain(receipt),
                    )
                    _LOGGER.info(
                        "Accepted painted application surface | candidate_pid=%s | "
                        "surface_pid=%s | surface=%s | outer_contract=%s",
                        process.pid,
                        receipt.pid,
                        receipt.surface.value,
                        bool(contract.outer_receipts),
                    )
                    return process
                self._wait(_POLL_INTERVAL_SECONDS)
            if receipt_access_error is not None:
                raise _unreadable_receipt_error(receipt_path) from receipt_access_error
            raise ApplicationReadinessError(
                "SugarSubstitute did not reveal its main window before the startup "
                f"timeout. Startup log: {startup_log_path}.",
                diagnostics={"readiness_failure_kind": "timeout"},
            )
        except ApplicationStartupCompleted:
            raise
        except BaseException as error:
            termination_action = stop_candidate_process(process)
            if isinstance(error, ApplicationReadinessError):
                error.terminated_process = process
                error.add_diagnostics(
                    {
                        "readiness_candidate_pid": process.pid,
                        "readiness_elapsed_seconds": f"{max(0.0, self._monotonic() - started_at):.3f}",
                        "readiness_timeout_seconds": f"{self._timeout_seconds:.3f}",
                        "readiness_poll_interval_seconds": f"{_POLL_INTERVAL_SECONDS:.3f}",
                        "readiness_receipt_state": (
                            "present" if receipt_path.exists() else "missing"
                        ),
                        "readiness_outer_contract": (bool(contract.outer_receipts)),
                        "readiness_child_schema": READINESS_SCHEMA_VERSION,
                        "readiness_outer_schema": (
                            ",".join(
                                str(target.schema_version)
                                for target in contract.outer_receipts
                            )
                            or "none"
                        ),
                        "readiness_termination_action": termination_action,
                    }
                )
                _LOGGER.error(
                    "Application readiness supervision failed | candidate_pid=%s | "
                    "failure_kind=%s | elapsed_seconds=%s | timeout_seconds=%s | "
                    "receipt_state=%s | outer_contract=%s | outer_schema=%s | "
                    "termination_action=%s",
                    process.pid,
                    error.diagnostics.get("readiness_failure_kind", "unknown"),
                    error.diagnostics["readiness_elapsed_seconds"],
                    error.diagnostics["readiness_timeout_seconds"],
                    error.diagnostics["readiness_receipt_state"],
                    error.diagnostics["readiness_outer_contract"],
                    error.diagnostics["readiness_outer_schema"],
                    error.diagnostics["readiness_termination_action"],
                )
            raise
        finally:
            receipt_path.unlink(missing_ok=True)

    def _check_cancellation(self, process: CandidateProcess | None = None) -> None:
        """Distinguish the user's cancellation from an unresponsive or failed child."""
        if self._cancellation_requested is not None and self._cancellation_requested():
            raise ApplicationStartupCancelled(process)

    @staticmethod
    def _validate_receipt(
        *,
        receipt_path: Path,
        expected_token: str,
        expected_pid: int,
    ) -> ApplicationReadinessReceipt:
        """Return a valid receipt that belongs to the supervised process."""

        try:
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (PermissionError, FileNotFoundError):
            raise
        except (OSError, json.JSONDecodeError) as error:
            raise _unreadable_receipt_error(receipt_path) from error
        try:
            receipt = ApplicationReadinessReceipt.from_json(payload)
        except ValueError as error:
            raise ApplicationReadinessError(
                "Application readiness receipt is invalid.",
                diagnostics={
                    "readiness_failure_kind": "invalid_receipt",
                    "readiness_observed_schema": _observed_schema(payload),
                },
            ) from error
        token_matched = receipt.token == expected_token
        process_matched = expected_pid in {
            receipt.pid,
            receipt.parent_pid,
            *receipt.attester_pids,
        }
        if not token_matched or not process_matched:
            raise ApplicationReadinessError(
                "Application readiness receipt did not match the launched process. "
                f"Expected PID: {expected_pid}. Receipt PID: {receipt.pid}. "
                f"Receipt parent PID: {receipt.parent_pid}. "
                f"Receipt attester PIDs: {list(receipt.attester_pids)}. "
                f"Token matched: {token_matched}.",
                diagnostics={
                    "readiness_failure_kind": "identity_mismatch",
                    "readiness_observed_schema": _observed_schema(payload),
                    "readiness_token_matched": str(token_matched),
                    "readiness_process_matched": str(process_matched),
                },
            )
        return receipt

    def _require_accepted_surface(
        self,
        receipt: ApplicationReadinessReceipt,
    ) -> None:
        """Fail unless the reported painted surface satisfies this launch policy."""

        if receipt.surface in self._accepted_surfaces:
            return
        accepted = ", ".join(
            sorted(surface.value for surface in self._accepted_surfaces)
        )
        raise ApplicationReadinessError(
            "SugarSubstitute did not reveal an accepted visible surface. "
            f"Expected: {accepted}. Reported: {receipt.surface.value}.",
            diagnostics={
                "readiness_failure_kind": "unaccepted_surface",
                "readiness_reported_surface": receipt.surface.value,
                "readiness_accepted_surfaces": accepted,
            },
        )


def _start_candidate_process(
    command: Sequence[str],
    environment: Mapping[str, str],
) -> tuple[CandidateProcess, Path]:
    """Adapt the launcher process owner to the supervision port."""

    process, log_path = spawn_supervised_process(
        command, environment=environment, allow_handoff=True
    )
    return process, log_path


def stop_candidate_process(process: CandidateProcess) -> str:
    """Stop a failed candidate and return the exact supervisor action."""

    if process.poll() is not None:
        return "already_exited"
    process.terminate()
    try:
        process.wait(timeout=_TERMINATION_TIMEOUT_SECONDS)
        return "terminated"
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=_TERMINATION_TIMEOUT_SECONDS)
        return "killed"


def _observed_schema(payload: object) -> str:
    """Return a safe schema label from untrusted receipt data."""

    if not isinstance(payload, dict):
        return "unavailable"
    value = payload.get("schema_version")
    if not isinstance(value, int) or isinstance(value, bool):
        return "invalid"
    return str(value)


__all__ = [
    "ApplicationReadinessSupervisor",
    "stop_candidate_process",
]
