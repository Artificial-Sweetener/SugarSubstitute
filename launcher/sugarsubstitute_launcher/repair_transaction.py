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

"""Execute repair promotions with a durable journal and automatic rollback."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import json
import os
from pathlib import Path
import secrets
import shutil
from typing import TypedDict

from launcher.sugarsubstitute_launcher.application.repair.models import (
    RepairDisposition,
    RepairPlan,
    RepairReplacement,
)

_SCHEMA_VERSION = 1
_PENDING_JOURNAL = Path(".repair") / "pending.json"


class _RecoveryRecord(TypedDict):
    """Describe validated fields needed to roll back one destination."""

    destination: str
    disposition: str
    had_destination: bool
    relocated: bool
    promoted: bool


class RepairTransactionError(RuntimeError):
    """Report an invalid, failed, or unrecoverable repair transaction."""


class RepairTransaction:
    """Apply one prepared repair plan while retaining restorable prior content."""

    def __init__(
        self,
        *,
        after_move: Callable[[Path, Path], None] | None = None,
    ) -> None:
        """Store the optional fault-injection observer used after filesystem moves."""

        self._after_move = after_move or (lambda _source, _destination: None)

    def execute(
        self,
        *,
        plan: RepairPlan,
        replacements: Sequence[RepairReplacement],
        transaction_id: str | None = None,
        apply_repair: Callable[[], None] | None = None,
        validate_repair: Callable[[], None] | None = None,
    ) -> Path:
        """Quarantine existing targets, promote staged artifacts, and commit."""

        root = plan.install_root.resolve()
        journal_path = root / _PENDING_JOURNAL
        if journal_path.exists():
            raise RepairTransactionError(
                "A repair transaction is already pending and must be recovered first."
            )
        normalized = self._validate_replacements(plan, replacements)
        identifier = transaction_id or secrets.token_hex(8)
        quarantine_root = root / ".repair" / "quarantine" / identifier
        replacement_by_destination = {
            replacement.destination: replacement for replacement in normalized
        }
        transaction_operations = tuple(
            operation
            for operation in plan.operations
            if operation.disposition
            in {RepairDisposition.QUARANTINE, RepairDisposition.REPLACE}
        )
        records = [
            {
                "destination": str(operation.path.relative_to(root)),
                "disposition": operation.disposition.value,
                "staged_path": (
                    str(replacement_by_destination[operation.path].staged_path)
                    if operation.path in replacement_by_destination
                    else None
                ),
                "had_destination": operation.path.exists(),
                "relocated": False,
                "promoted": False,
            }
            for operation in transaction_operations
        ]
        payload: dict[str, object] = {
            "schema_version": _SCHEMA_VERSION,
            "scope": plan.scope.value,
            "transaction_id": identifier,
            "quarantine_root": str(quarantine_root.relative_to(root)),
            "records": records,
            "phase": "prepared",
        }
        _write_json_atomic(journal_path, payload)
        try:
            for operation, record in zip(transaction_operations, records, strict=True):
                destination = operation.path
                if destination.exists():
                    quarantined = quarantine_root / destination.relative_to(root)
                    quarantined.parent.mkdir(parents=True, exist_ok=True)
                    destination.replace(quarantined)
                    record["relocated"] = True
                    payload["phase"] = "relocating"
                    _write_json_atomic(journal_path, payload)
                    self._after_move(destination, quarantined)
                replacement = replacement_by_destination.get(destination)
                if replacement is None:
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                replacement.staged_path.replace(destination)
                record["promoted"] = True
                payload["phase"] = "promoting"
                _write_json_atomic(journal_path, payload)
                self._after_move(replacement.staged_path, destination)
            payload["phase"] = "applying"
            _write_json_atomic(journal_path, payload)
            if apply_repair is not None:
                apply_repair()
            payload["phase"] = "validating"
            _write_json_atomic(journal_path, payload)
            if validate_repair is not None:
                validate_repair()
        except BaseException as error:
            try:
                recover_interrupted_repair(root)
            except BaseException as recovery_error:
                raise RepairTransactionError(
                    "Repair failed and automatic rollback also failed."
                ) from recovery_error
            raise RepairTransactionError(
                "Repair failed and was rolled back."
            ) from error
        payload["phase"] = "committed"
        _write_json_atomic(journal_path, payload)
        journal_path.unlink()
        return quarantine_root

    @staticmethod
    def _validate_replacements(
        plan: RepairPlan,
        replacements: Sequence[RepairReplacement],
    ) -> tuple[RepairReplacement, ...]:
        """Normalize replacement bindings and reject ambiguous filesystem targets."""

        root = plan.install_root.resolve()
        normalized: list[RepairReplacement] = []
        destinations: set[Path] = set()
        for replacement in replacements:
            destination = replacement.destination.resolve()
            staged_path = replacement.staged_path.resolve()
            operation = next(
                (
                    candidate
                    for candidate in plan.operations
                    if candidate.path == destination
                ),
                None,
            )
            if (
                operation is None
                or operation.disposition is not RepairDisposition.REPLACE
            ):
                raise RepairTransactionError(
                    f"Replacement destination is not explicitly replaceable: {destination}"
                )
            if not destination.is_relative_to(root):
                raise RepairTransactionError(
                    f"Replacement destination escapes installation root: {destination}"
                )
            if not staged_path.exists():
                raise RepairTransactionError(
                    f"Staged replacement does not exist: {staged_path}"
                )
            if destination in destinations:
                raise RepairTransactionError(
                    f"Duplicate replacement destination: {destination}"
                )
            if destination.is_relative_to(staged_path) or staged_path.is_relative_to(
                destination
            ):
                raise RepairTransactionError(
                    f"Staged and destination paths overlap: {destination}"
                )
            destinations.add(destination)
            normalized.append(
                RepairReplacement(
                    destination=destination,
                    staged_path=staged_path,
                )
            )
        return tuple(normalized)


def recover_interrupted_repair(install_root: Path) -> bool:
    """Restore all relocated paths recorded by an interrupted repair journal."""

    root = install_root.resolve()
    journal_path = root / _PENDING_JOURNAL
    try:
        payload = json.loads(journal_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    except (OSError, json.JSONDecodeError) as error:
        raise RepairTransactionError(
            f"Pending repair journal is unreadable: {journal_path}"
        ) from error
    records, quarantine_root = _validate_journal(payload, root, journal_path)
    for record in reversed(records):
        destination = root / record["destination"]
        quarantined = quarantine_root / record["destination"]
        if record["relocated"]:
            if not quarantined.exists():
                raise RepairTransactionError(
                    f"Repair rollback source is missing: {quarantined}"
                )
            _remove_path(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            quarantined.replace(destination)
        elif (
            record["disposition"] == RepairDisposition.REPLACE.value
            and not record["had_destination"]
        ):
            _remove_path(destination)
    journal_path.unlink()
    return True


def _validate_journal(
    payload: object,
    root: Path,
    journal_path: Path,
) -> tuple[list[_RecoveryRecord], Path]:
    """Validate recovery data before mutating any path."""

    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != _SCHEMA_VERSION
    ):
        raise RepairTransactionError(
            f"Pending repair journal is invalid: {journal_path}"
        )
    records = payload.get("records")
    quarantine_value = payload.get("quarantine_root")
    if not isinstance(records, list) or not isinstance(quarantine_value, str):
        raise RepairTransactionError(
            f"Pending repair journal is invalid: {journal_path}"
        )
    quarantine_root = (root / quarantine_value).resolve()
    if not quarantine_root.is_relative_to(root / ".repair" / "quarantine"):
        raise RepairTransactionError(
            f"Pending repair quarantine path is unsafe: {journal_path}"
        )
    validated: list[_RecoveryRecord] = []
    for record in records:
        if not isinstance(record, dict):
            raise RepairTransactionError(
                f"Pending repair journal is invalid: {journal_path}"
            )
        destination_value = record.get("destination")
        disposition = record.get("disposition")
        had_destination = record.get("had_destination")
        relocated = record.get("relocated")
        promoted = record.get("promoted")
        if (
            not isinstance(destination_value, str)
            or disposition
            not in {
                RepairDisposition.QUARANTINE.value,
                RepairDisposition.REPLACE.value,
            }
            or not isinstance(had_destination, bool)
            or not isinstance(relocated, bool)
            or not isinstance(promoted, bool)
        ):
            raise RepairTransactionError(
                f"Pending repair journal is invalid: {journal_path}"
            )
        destination = (root / destination_value).resolve()
        if not destination.is_relative_to(root) or destination == root:
            raise RepairTransactionError(
                f"Pending repair destination is unsafe: {journal_path}"
            )
        validated.append(
            {
                "destination": destination_value,
                "disposition": disposition,
                "had_destination": had_destination,
                "relocated": relocated,
                "promoted": promoted,
            }
        )
    return validated, quarantine_root


def _remove_path(path: Path) -> None:
    """Remove one transaction-owned promoted path during rollback."""

    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    """Atomically persist a repair journal before filesystem transitions."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


__all__ = [
    "RepairTransaction",
    "RepairTransactionError",
    "recover_interrupted_repair",
]
