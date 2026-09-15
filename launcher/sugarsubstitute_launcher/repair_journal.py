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

"""Own the persisted repair journal schema and atomic storage boundary."""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
from typing import TypedDict

from launcher.sugarsubstitute_launcher.application.repair.models import (
    RepairDisposition,
)
from launcher.sugarsubstitute_launcher.repair_errors import RepairTransactionError

REPAIR_JOURNAL_SCHEMA_VERSION = 1
PENDING_JOURNAL = Path(".repair") / "pending.json"


class RecoveryRecord(TypedDict):
    """Describe validated fields needed to roll back one destination."""

    destination: str
    disposition: str
    had_destination: bool
    relocated: bool
    promoted: bool


def read_repair_journal(root: Path) -> tuple[list[RecoveryRecord], Path] | None:
    """Read and validate every recovery destination before permitting mutation."""
    journal_path = root / PENDING_JOURNAL
    try:
        payload = json.loads(journal_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as error:
        raise RepairTransactionError(
            f"Pending repair journal is unreadable: {journal_path}"
        ) from error
    return _validate_journal(payload, root, journal_path)


def _validate_journal(
    payload: object,
    root: Path,
    journal_path: Path,
) -> tuple[list[RecoveryRecord], Path]:
    """Validate recovery data before mutating any path."""

    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != REPAIR_JOURNAL_SCHEMA_VERSION
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
    validated: list[RecoveryRecord] = []
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


def write_repair_journal(path: Path, payload: dict[str, object]) -> None:
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
