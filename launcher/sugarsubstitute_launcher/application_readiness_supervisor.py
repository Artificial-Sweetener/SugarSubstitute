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
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import secrets
import subprocess
import threading
import time

from launcher.sugarsubstitute_launcher.application_startup_contract import (
    CandidateProcess,
    ApplicationStartupCancelled,
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
    READINESS_LEGACY_DELEGATION_SCHEMA_VERSION,
    READINESS_SCHEMA_ENV,
    READINESS_SCHEMA_VERSION,
    READINESS_TOKEN_ENV,
    WRITABLE_READINESS_SCHEMA_VERSIONS,
    publish_application_readiness_receipt,
)
from sugarsubstitute_shared.installer_qualification import InstallerQualificationPlan


DEFAULT_READINESS_TIMEOUT_SECONDS = 3600.0
_POLL_INTERVAL_SECONDS = 0.05
_TERMINATION_TIMEOUT_SECONDS = 5.0
_LOGGER = logging.getLogger(__name__)


class ApplicationReadinessError(RuntimeError):
    """Report a candidate that exits or stalls before its shell is ready."""

    def __init__(
        self,
        message: str,
        *,
        terminated_process: CandidateProcess | None = None,
        incident_id: str | None = None,
        diagnostics: Mapping[str, str] | None = None,
    ) -> None:
        """Retain terminated-process and durable-incident recovery context."""

        super().__init__(message)
        self.terminated_process = terminated_process
        self.incident_id = incident_id
        self.diagnostics = dict(diagnostics or {})

    def add_diagnostics(self, values: Mapping[str, object]) -> None:
        """Add non-secret supervisor facts without replacing specific evidence."""

        for key, value in values.items():
            self.diagnostics.setdefault(key, str(value))


@dataclass(frozen=True, slots=True)
class _ReadinessContract:
    """Separate one child proof from an optional caller-owned outer proof."""

    child_receipt_path: Path
    child_token: str
    outer_receipt_path: Path | None
    outer_token: str | None
    outer_schema_version: int | None


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
    ) -> CandidateProcess:
        """Return the running process after an accepted surface is responsive."""

        self._check_cancellation()

        contract = self._readiness_contract(layout=layout, environment=environment)
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
        if contract.outer_receipt_path is not None and contract.outer_token is not None:
            child_environment[READINESS_DELEGATION_PATH_ENV] = str(
                contract.outer_receipt_path
            )
            child_environment[READINESS_DELEGATION_TOKEN_ENV] = contract.outer_token
            if contract.outer_schema_version is None:
                raise RuntimeError("Outer readiness schema was not resolved.")
            child_environment[READINESS_DELEGATION_SCHEMA_ENV] = str(
                contract.outer_schema_version
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
            contract.outer_receipt_path is not None,
        )
        try:
            deadline = started_at + self._timeout_seconds
            while self._monotonic() < deadline:
                self._check_cancellation(process)
                return_code = process.poll()
                if return_code is not None:
                    raise ApplicationReadinessError(
                        "SugarSubstitute exited before its main window became ready. "
                        f"Exit code: {return_code}. Startup log: {startup_log_path}.",
                        terminated_process=process,
                        diagnostics={"readiness_failure_kind": "process_exit"},
                    )
                if receipt_path.exists():
                    receipt = self._validate_receipt(
                        receipt_path=receipt_path,
                        expected_token=token,
                        expected_pid=process.pid,
                    )
                    self._require_accepted_surface(receipt)
                    self._publish_outer_receipt(contract=contract, receipt=receipt)
                    self._publish_qualification_receipt(
                        environment=environment,
                        receipt=receipt,
                    )
                    _LOGGER.info(
                        "Accepted painted application surface | candidate_pid=%s | "
                        "surface_pid=%s | surface=%s | outer_contract=%s",
                        process.pid,
                        receipt.pid,
                        receipt.surface.value,
                        contract.outer_receipt_path is not None,
                    )
                    return process
                self._wait(_POLL_INTERVAL_SECONDS)
            raise ApplicationReadinessError(
                "SugarSubstitute did not reveal its main window before the startup "
                f"timeout. Startup log: {startup_log_path}.",
                diagnostics={"readiness_failure_kind": "timeout"},
            )
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
                        "readiness_outer_contract": (
                            contract.outer_receipt_path is not None
                        ),
                        "readiness_child_schema": READINESS_SCHEMA_VERSION,
                        "readiness_outer_schema": (
                            contract.outer_schema_version
                            if contract.outer_schema_version is not None
                            else "none"
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

    def _readiness_contract(
        self,
        *,
        layout: InstallLayout,
        environment: Mapping[str, str],
    ) -> _ReadinessContract:
        """Adopt a complete outer proof contract or create a private one."""

        external_path = environment.get(READINESS_PATH_ENV)
        external_token = environment.get(READINESS_TOKEN_ENV)
        external_schema = environment.get(READINESS_SCHEMA_ENV)
        delegated_path = environment.get(READINESS_DELEGATION_PATH_ENV)
        delegated_token = environment.get(READINESS_DELEGATION_TOKEN_ENV)
        delegated_schema = environment.get(READINESS_DELEGATION_SCHEMA_ENV)
        if bool(external_path) != bool(external_token):
            raise ApplicationReadinessError(
                "Application readiness path and token must be supplied together."
            )
        if bool(delegated_path) != bool(delegated_token):
            raise ApplicationReadinessError(
                "Application readiness delegation path and token must be supplied "
                "together."
            )
        if external_schema and not (external_path and external_token):
            raise ApplicationReadinessError(
                "Application readiness schema requires a path and token."
            )
        if delegated_schema and not (delegated_path and delegated_token):
            raise ApplicationReadinessError(
                "Application readiness delegation schema requires a path and token."
            )
        outer_path = delegated_path or external_path
        outer_token = delegated_token or external_token
        outer_schema = delegated_schema or external_schema
        if outer_path and outer_token:
            outer_schema_version = _resolve_outer_schema_version(
                declared_schema=outer_schema,
                advertised_versions=environment.get(
                    READINESS_ACCEPTED_SCHEMA_VERSIONS_ENV
                ),
            )
            return _ReadinessContract(
                child_receipt_path=(
                    layout.launcher_dir
                    / "readiness"
                    / f"candidate-{secrets.token_hex(16)}.json"
                ),
                child_token=self._token_factory(),
                outer_receipt_path=Path(outer_path).expanduser().resolve(),
                outer_token=outer_token,
                outer_schema_version=outer_schema_version,
            )
        return _ReadinessContract(
            child_receipt_path=layout.launcher_dir / "readiness" / "candidate.json",
            child_token=self._token_factory(),
            outer_receipt_path=None,
            outer_token=None,
            outer_schema_version=None,
        )

    @staticmethod
    def _publish_outer_receipt(
        *,
        contract: _ReadinessContract,
        receipt: ApplicationReadinessReceipt,
    ) -> None:
        """Preserve the painted process while attesting through this process hop."""

        if (
            contract.outer_receipt_path is None
            or contract.outer_token is None
            or contract.outer_schema_version is None
        ):
            return
        publish_application_readiness_receipt(
            receipt_path=contract.outer_receipt_path,
            receipt=ApplicationReadinessReceipt(
                pid=receipt.pid,
                token=contract.outer_token,
                surface=receipt.surface,
                parent_pid=(
                    receipt.parent_pid
                    if contract.outer_schema_version >= READINESS_SCHEMA_VERSION
                    else os.getpid()
                ),
                milestones=receipt.milestones,
                attester_pids=_extended_attestation_chain(receipt),
            ),
            schema_version=contract.outer_schema_version,
        )

    @staticmethod
    def _publish_qualification_receipt(
        *,
        environment: Mapping[str, str],
        receipt: ApplicationReadinessReceipt,
    ) -> None:
        """Mirror validated readiness across legacy detached update handoffs."""

        try:
            plan = InstallerQualificationPlan.from_environment(environment)
            if plan is None:
                return
            publish_application_readiness_receipt(
                receipt_path=plan.readiness_receipt_path,
                receipt=ApplicationReadinessReceipt(
                    pid=receipt.pid,
                    token=plan.token,
                    surface=receipt.surface,
                    parent_pid=receipt.parent_pid,
                    milestones=receipt.milestones,
                    attester_pids=_extended_attestation_chain(receipt),
                ),
            )
        except (OSError, ValueError) as error:
            _LOGGER.warning(
                "Could not publish installer qualification readiness | "
                "error_type=%s | error=%s",
                type(error).__name__,
                error,
            )

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
        except (OSError, json.JSONDecodeError) as error:
            raise ApplicationReadinessError(
                f"SugarSubstitute wrote an invalid readiness receipt: {receipt_path}.",
                diagnostics={
                    "readiness_failure_kind": "unreadable_receipt",
                    "readiness_observed_schema": "unavailable",
                },
            ) from error
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


def _resolve_outer_schema_version(
    *,
    declared_schema: str | None,
    advertised_versions: str | None,
) -> int:
    """Resolve an explicit schema, negotiated capability, or legacy fallback."""

    if declared_schema is not None:
        return _compatible_outer_schema(declared_schema)
    if advertised_versions is None:
        return READINESS_LEGACY_DELEGATION_SCHEMA_VERSION
    raw_versions = advertised_versions.split(",")
    if not raw_versions or any(
        not raw_version or not raw_version.isdecimal() for raw_version in raw_versions
    ):
        raise ApplicationReadinessError(
            "Application readiness schema capabilities are invalid."
        )
    compatible_versions = {
        int(raw_version)
        for raw_version in raw_versions
        if int(raw_version) in WRITABLE_READINESS_SCHEMA_VERSIONS
    }
    if not compatible_versions:
        raise ApplicationReadinessError(
            "Application readiness schema capabilities are incompatible."
        )
    return max(compatible_versions)


def _extended_attestation_chain(
    receipt: ApplicationReadinessReceipt,
) -> tuple[int, ...]:
    """Append this supervisor and its OS parent without duplicating prior hops."""

    process_ids = (*receipt.attester_pids, os.getpid(), os.getppid())
    return tuple(
        dict.fromkeys(process_id for process_id in process_ids if process_id > 0)
    )


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


def _compatible_outer_schema(raw_schema: str | None) -> int:
    """Return the richest schema a declared or pre-negotiation outer accepts."""

    if raw_schema is None:
        return READINESS_LEGACY_DELEGATION_SCHEMA_VERSION
    try:
        requested = int(raw_schema)
    except ValueError as error:
        raise ApplicationReadinessError(
            "Application readiness schema must be an integer."
        ) from error
    if requested <= 0:
        raise ApplicationReadinessError(
            "Application readiness schema must be positive."
        )
    return min(requested, READINESS_SCHEMA_VERSION)


def _observed_schema(payload: object) -> str:
    """Return a safe schema label from untrusted receipt data."""

    if not isinstance(payload, dict):
        return "unavailable"
    value = payload.get("schema_version")
    if not isinstance(value, int) or isinstance(value, bool):
        return "invalid"
    return str(value)


__all__ = [
    "ApplicationReadinessError",
    "ApplicationReadinessSupervisor",
    "DEFAULT_READINESS_TIMEOUT_SECONDS",
    "stop_candidate_process",
]
