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
    READINESS_DELEGATION_PATH_ENV,
    READINESS_DELEGATION_TOKEN_ENV,
    READINESS_PATH_ENV,
    READINESS_TOKEN_ENV,
    publish_application_readiness_receipt,
)


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
    ) -> None:
        """Retain terminated-process and durable-incident recovery context."""

        super().__init__(message)
        self.terminated_process = terminated_process
        self.incident_id = incident_id


@dataclass(frozen=True, slots=True)
class _ReadinessContract:
    """Separate one child proof from an optional caller-owned outer proof."""

    child_receipt_path: Path
    child_token: str
    outer_receipt_path: Path | None
    outer_token: str | None


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
        if contract.outer_receipt_path is not None and contract.outer_token is not None:
            child_environment[READINESS_DELEGATION_PATH_ENV] = str(
                contract.outer_receipt_path
            )
            child_environment[READINESS_DELEGATION_TOKEN_ENV] = contract.outer_token
        process, startup_log_path = self._process_starter(
            command,
            child_environment,
        )
        _LOGGER.info(
            "Started supervised application candidate | candidate_pid=%s | "
            "accepted_surfaces=%s | outer_contract=%s",
            process.pid,
            ",".join(sorted(surface.value for surface in self._accepted_surfaces)),
            contract.outer_receipt_path is not None,
        )
        try:
            deadline = self._monotonic() + self._timeout_seconds
            while self._monotonic() < deadline:
                self._check_cancellation(process)
                return_code = process.poll()
                if return_code is not None:
                    raise ApplicationReadinessError(
                        "SugarSubstitute exited before its main window became ready. "
                        f"Exit code: {return_code}. Startup log: {startup_log_path}.",
                        terminated_process=process,
                    )
                if receipt_path.exists():
                    receipt = self._validate_receipt(
                        receipt_path=receipt_path,
                        expected_token=token,
                        expected_pid=process.pid,
                    )
                    self._require_accepted_surface(receipt)
                    self._publish_outer_receipt(contract=contract, receipt=receipt)
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
                f"timeout. Startup log: {startup_log_path}."
            )
        except BaseException as error:
            stop_candidate_process(process)
            if isinstance(error, ApplicationReadinessError):
                error.terminated_process = process
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
        delegated_path = environment.get(READINESS_DELEGATION_PATH_ENV)
        delegated_token = environment.get(READINESS_DELEGATION_TOKEN_ENV)
        if bool(external_path) != bool(external_token):
            raise ApplicationReadinessError(
                "Application readiness path and token must be supplied together."
            )
        if bool(delegated_path) != bool(delegated_token):
            raise ApplicationReadinessError(
                "Application readiness delegation path and token must be supplied "
                "together."
            )
        outer_path = delegated_path or external_path
        outer_token = delegated_token or external_token
        if outer_path and outer_token:
            return _ReadinessContract(
                child_receipt_path=(
                    layout.launcher_dir
                    / "readiness"
                    / f"candidate-{secrets.token_hex(16)}.json"
                ),
                child_token=self._token_factory(),
                outer_receipt_path=Path(outer_path).expanduser().resolve(),
                outer_token=outer_token,
            )
        return _ReadinessContract(
            child_receipt_path=layout.launcher_dir / "readiness" / "candidate.json",
            child_token=self._token_factory(),
            outer_receipt_path=None,
            outer_token=None,
        )

    @staticmethod
    def _publish_outer_receipt(
        *,
        contract: _ReadinessContract,
        receipt: ApplicationReadinessReceipt,
    ) -> None:
        """Preserve the painted process while attesting through this process hop."""

        if contract.outer_receipt_path is None or contract.outer_token is None:
            return
        publish_application_readiness_receipt(
            receipt_path=contract.outer_receipt_path,
            receipt=ApplicationReadinessReceipt(
                pid=receipt.pid,
                token=contract.outer_token,
                surface=receipt.surface,
                parent_pid=receipt.parent_pid,
                milestones=receipt.milestones,
                attester_pids=_extended_attestation_chain(receipt),
            ),
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
                f"SugarSubstitute wrote an invalid readiness receipt: {receipt_path}."
            ) from error
        try:
            receipt = ApplicationReadinessReceipt.from_json(payload)
        except ValueError as error:
            raise ApplicationReadinessError(
                "Application readiness receipt is invalid."
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
                f"Token matched: {token_matched}."
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
            f"Expected: {accepted}. Reported: {receipt.surface.value}."
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


def _extended_attestation_chain(
    receipt: ApplicationReadinessReceipt,
) -> tuple[int, ...]:
    """Append this supervisor and its OS parent without duplicating prior hops."""

    process_ids = (*receipt.attester_pids, os.getpid(), os.getppid())
    return tuple(
        dict.fromkeys(process_id for process_id in process_ids if process_id > 0)
    )


def stop_candidate_process(process: CandidateProcess) -> None:
    """Ensure a timed-out candidate no longer holds app or runtime files."""

    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=_TERMINATION_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=_TERMINATION_TIMEOUT_SECONDS)


__all__ = [
    "ApplicationReadinessError",
    "ApplicationReadinessSupervisor",
    "DEFAULT_READINESS_TIMEOUT_SECONDS",
    "stop_candidate_process",
]
