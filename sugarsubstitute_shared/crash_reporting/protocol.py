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

"""Authenticate crash-supervisor lifecycle messages exchanged through files."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from enum import Enum
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
from typing import Self

from sugarsubstitute_shared.crash_reporting.store import _write_json_atomically


CRASH_PROTOCOL_SCHEMA_VERSION = 1
CRASH_RUN_ID_ENV = "SUGAR_SUBSTITUTE_CRASH_RUN_ID"
CRASH_RUN_TOKEN_ENV = "SUGAR_SUBSTITUTE_CRASH_RUN_TOKEN"
CRASH_INCIDENT_ROOT_ENV = "SUGAR_SUBSTITUTE_CRASH_INCIDENT_ROOT"
CRASH_EXIT_INTENT_PATH_ENV = "SUGAR_SUBSTITUTE_CRASH_EXIT_INTENT_PATH"
CRASH_EXIT_RECEIPT_PATH_ENV = "SUGAR_SUBSTITUTE_CRASH_EXIT_RECEIPT_PATH"
CRASHPAD_DATABASE_ENV = "SUGAR_SUBSTITUTE_CRASHPAD_DATABASE"
CRASHPAD_HANDLER_ENV = "SUGAR_SUBSTITUTE_CRASHPAD_HANDLER"
CRASHPAD_CLIENT_LIBRARY_ENV = "SUGAR_SUBSTITUTE_CRASHPAD_CLIENT_LIBRARY"
_CRASH_SUPERVISION_ENVIRONMENT_NAMES = (
    CRASH_RUN_ID_ENV,
    CRASH_RUN_TOKEN_ENV,
    CRASH_INCIDENT_ROOT_ENV,
    CRASH_EXIT_INTENT_PATH_ENV,
    CRASH_EXIT_RECEIPT_PATH_ENV,
    CRASHPAD_DATABASE_ENV,
    CRASHPAD_HANDLER_ENV,
    CRASHPAD_CLIENT_LIBRARY_ENV,
)


class CleanExitOutcome(Enum):
    """Classify an application-controlled terminal lifecycle transition."""

    CLOSED = "closed"
    RESTART = "restart"
    UPDATE_HANDOFF = "update_handoff"


@dataclass(frozen=True, slots=True)
class CrashRunContext:
    """Carry one supervisor-owned run contract into the application process."""

    run_id: str
    token: str
    incident_root: Path
    exit_intent_path: Path
    exit_receipt_path: Path
    crashpad_database: Path
    crashpad_handler: Path | None = None
    crashpad_client_library: Path | None = None

    @classmethod
    def create(
        cls,
        diagnostics_root: Path,
        *,
        crashpad_handler: Path | None = None,
        crashpad_client_library: Path | None = None,
    ) -> Self:
        """Create one unpredictable run contract below a diagnostics root."""

        if bool(crashpad_handler) != bool(crashpad_client_library):
            raise ValueError("Crashpad handler and client library must be paired.")

        run_id = secrets.token_urlsafe(24)
        lifecycle_root = diagnostics_root / "lifecycle" / run_id
        return cls(
            run_id=run_id,
            token=secrets.token_urlsafe(32),
            incident_root=diagnostics_root / "crashes",
            exit_intent_path=lifecycle_root / "exit-intent.json",
            exit_receipt_path=lifecycle_root / "exit-receipt.json",
            crashpad_database=diagnostics_root / "crashpad",
            crashpad_handler=crashpad_handler,
            crashpad_client_library=crashpad_client_library,
        )

    def environment(self, source: Mapping[str, str] | None = None) -> dict[str, str]:
        """Return a child environment containing the complete crash contract."""

        environment = dict(os.environ if source is None else source)
        environment.update(
            {
                CRASH_RUN_ID_ENV: self.run_id,
                CRASH_RUN_TOKEN_ENV: self.token,
                CRASH_INCIDENT_ROOT_ENV: str(self.incident_root),
                CRASH_EXIT_INTENT_PATH_ENV: str(self.exit_intent_path),
                CRASH_EXIT_RECEIPT_PATH_ENV: str(self.exit_receipt_path),
                CRASHPAD_DATABASE_ENV: str(self.crashpad_database),
            }
        )
        if (
            self.crashpad_handler is not None
            and self.crashpad_client_library is not None
        ):
            environment[CRASHPAD_HANDLER_ENV] = str(self.crashpad_handler)
            environment[CRASHPAD_CLIENT_LIBRARY_ENV] = str(self.crashpad_client_library)
        else:
            environment.pop(CRASHPAD_HANDLER_ENV, None)
            environment.pop(CRASHPAD_CLIENT_LIBRARY_ENV, None)
        return environment

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> Self | None:
        """Parse a complete inherited contract or reject partial supervision."""

        source = os.environ if environment is None else environment
        required_names = (
            CRASH_RUN_ID_ENV,
            CRASH_RUN_TOKEN_ENV,
            CRASH_INCIDENT_ROOT_ENV,
            CRASH_EXIT_INTENT_PATH_ENV,
            CRASH_EXIT_RECEIPT_PATH_ENV,
            CRASHPAD_DATABASE_ENV,
        )
        values = {name: source.get(name) for name in required_names}
        if all(value is None for value in values.values()):
            return None
        if any(not value for value in values.values()):
            raise ValueError("Crash supervision environment is incomplete.")
        run_id = values[CRASH_RUN_ID_ENV]
        token = values[CRASH_RUN_TOKEN_ENV]
        if run_id is None or token is None:
            raise ValueError("Crash supervision identity is incomplete.")
        handler = source.get(CRASHPAD_HANDLER_ENV)
        client_library = source.get(CRASHPAD_CLIENT_LIBRARY_ENV)
        if bool(handler) != bool(client_library):
            raise ValueError("Crashpad native runtime environment is incomplete.")
        return cls(
            run_id=run_id,
            token=token,
            incident_root=Path(_present(values, CRASH_INCIDENT_ROOT_ENV)),
            exit_intent_path=Path(_present(values, CRASH_EXIT_INTENT_PATH_ENV)),
            exit_receipt_path=Path(_present(values, CRASH_EXIT_RECEIPT_PATH_ENV)),
            crashpad_database=Path(_present(values, CRASHPAD_DATABASE_ENV)),
            crashpad_handler=Path(handler) if handler else None,
            crashpad_client_library=(Path(client_library) if client_library else None),
        )

    def clear_secret_environment(
        self,
        environment: MutableMapping[str, str] | None = None,
    ) -> None:
        """Remove the authentication token before unrelated children are launched."""

        target = os.environ if environment is None else environment
        target.pop(CRASH_RUN_TOKEN_ENV, None)

    def write_exit_intent(self, outcome: CleanExitOutcome, *, process_id: int) -> None:
        """Record the application-requested outcome before final cleanup begins."""

        _write_lifecycle_message(
            self.exit_intent_path,
            run_id=self.run_id,
            token=self.token,
            process_id=process_id,
            outcome=outcome,
            phase="intent",
        )

    def write_exit_receipt(self, outcome: CleanExitOutcome, *, process_id: int) -> None:
        """Record successful cleanup at the final controlled application boundary."""

        _write_lifecycle_message(
            self.exit_receipt_path,
            run_id=self.run_id,
            token=self.token,
            process_id=process_id,
            outcome=outcome,
            phase="complete",
        )

    def validates_clean_exit(self, *, process_id: int | None = None) -> bool:
        """Return whether matching signed intent and completion messages exist."""

        intent = _read_lifecycle_message(
            self.exit_intent_path,
            run_id=self.run_id,
            token=self.token,
            expected_process_id=process_id,
            phase="intent",
        )
        receipt = _read_lifecycle_message(
            self.exit_receipt_path,
            run_id=self.run_id,
            token=self.token,
            expected_process_id=process_id,
            phase="complete",
        )
        return intent is not None and receipt == intent


def without_crash_supervision_environment(
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return an environment detached from the current crash-supervised run."""

    detached = dict(os.environ if environment is None else environment)
    for name in _CRASH_SUPERVISION_ENVIRONMENT_NAMES:
        detached.pop(name, None)
    return detached


def _present(values: Mapping[str, str | None], key: str) -> str:
    """Return a field already proven present while satisfying static typing."""

    value = values[key]
    if value is None:
        raise ValueError("Crash supervision environment is incomplete.")
    return value


def _write_lifecycle_message(
    path: Path,
    *,
    run_id: str,
    token: str,
    process_id: int,
    outcome: CleanExitOutcome,
    phase: str,
) -> None:
    """Write one signed lifecycle message atomically."""

    signature = _message_signature(
        run_id=run_id,
        token=token,
        process_id=process_id,
        outcome=outcome,
        phase=phase,
    )
    _write_json_atomically(
        path,
        {
            "schema_version": CRASH_PROTOCOL_SCHEMA_VERSION,
            "run_id": run_id,
            "process_id": process_id,
            "outcome": outcome.value,
            "phase": phase,
            "signature": signature,
        },
    )


def _read_lifecycle_message(
    path: Path,
    *,
    run_id: str,
    token: str,
    expected_process_id: int | None,
    phase: str,
) -> tuple[CleanExitOutcome, int] | None:
    """Return one verified lifecycle outcome or reject malformed evidence."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            return None
        if payload.get("schema_version") != CRASH_PROTOCOL_SCHEMA_VERSION:
            return None
        if payload.get("run_id") != run_id:
            return None
        process_id = payload.get("process_id")
        if not isinstance(process_id, int) or isinstance(process_id, bool):
            return None
        if process_id <= 0:
            return None
        if expected_process_id is not None and process_id != expected_process_id:
            return None
        if payload.get("phase") != phase:
            return None
        raw_outcome = payload.get("outcome")
        signature = payload.get("signature")
        if not isinstance(raw_outcome, str) or not isinstance(signature, str):
            return None
        outcome = CleanExitOutcome(raw_outcome)
        expected = _message_signature(
            run_id=run_id,
            token=token,
            process_id=process_id,
            outcome=outcome,
            phase=phase,
        )
        return (
            (outcome, process_id) if hmac.compare_digest(signature, expected) else None
        )
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _message_signature(
    *,
    run_id: str,
    token: str,
    process_id: int,
    outcome: CleanExitOutcome,
    phase: str,
) -> str:
    """Authenticate one lifecycle message with the supervisor-only run token."""

    message = f"{CRASH_PROTOCOL_SCHEMA_VERSION}\0{run_id}\0{process_id}\0{outcome.value}\0{phase}"
    return hmac.new(token.encode(), message.encode(), hashlib.sha256).hexdigest()


__all__ = [
    "CRASHPAD_DATABASE_ENV",
    "CRASHPAD_CLIENT_LIBRARY_ENV",
    "CRASHPAD_HANDLER_ENV",
    "CRASH_EXIT_INTENT_PATH_ENV",
    "CRASH_EXIT_RECEIPT_PATH_ENV",
    "CRASH_INCIDENT_ROOT_ENV",
    "CRASH_RUN_ID_ENV",
    "CRASH_RUN_TOKEN_ENV",
    "CleanExitOutcome",
    "CrashRunContext",
    "without_crash_supervision_environment",
]
