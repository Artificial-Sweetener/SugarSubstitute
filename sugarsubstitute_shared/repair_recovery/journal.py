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

"""Persist and validate repair transition journals before filesystem mutation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets

from sugarsubstitute_shared.repair_recovery.disposition import RepairDisposition
from sugarsubstitute_shared.repair_recovery.errors import RepairTransactionError
from sugarsubstitute_shared.repair_recovery.state import (
    RepairJournal,
    RepairPathRecord,
    RepairPathState,
    RepairPhase,
)

REPAIR_JOURNAL_SCHEMA_VERSION = 2
PENDING_JOURNAL = Path(".repair") / "pending.json"


def read_repair_journal(root: Path) -> RepairJournal | None:
    """Validate the entire persisted recovery boundary before allowing mutation."""
    path = root / PENDING_JOURNAL
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as error:
        raise RepairTransactionError(
            f"Pending repair journal is unreadable: {path}"
        ) from error
    if (
        not isinstance(payload, dict)
        or type(payload.get("schema_version")) is not int
        or payload.get("schema_version") not in {1, 2}
    ):
        raise RepairTransactionError(f"Pending repair journal is invalid: {path}")
    version = payload["schema_version"]
    values = payload.get("records")
    quarantine = _relative_path(payload.get("quarantine_root"), root)
    if not isinstance(values, list):
        raise RepairTransactionError(f"Pending repair records are invalid: {path}")
    try:
        phase = RepairPhase(payload.get("phase", "prepared" if version == 1 else None))
        records = [_read_record(value, root, version) for value in values]
    except (TypeError, ValueError) as error:
        raise RepairTransactionError(
            f"Pending repair transition state is invalid: {path}"
        ) from error
    journal = RepairJournal(quarantine, records, phase)
    validate_repair_journal_paths(root, journal)
    return journal


def validate_repair_journal_paths(root: Path, journal: RepairJournal) -> None:
    """Apply one path boundary to newly prepared and persisted transactions."""
    quarantine = _relative_path(str(journal.quarantine_root), root)
    if quarantine.parts[:2] != (".repair", "quarantine") or len(quarantine.parts) != 3:
        raise RepairTransactionError("Pending repair quarantine path is unsafe")
    destinations: list[Path] = []
    for record in journal.records:
        destination = _relative_path(str(record.destination), root)
        if destination.parts[0] == ".repair" or any(
            destination.is_relative_to(previous) or previous.is_relative_to(destination)
            for previous in destinations
        ):
            raise RepairTransactionError("Pending repair destinations are unsafe")
        _relative_path(str(quarantine / destination), root)
        destinations.append(destination)


def _read_record(value: object, root: Path, version: int) -> RepairPathRecord:
    """Decode current transitions or migrate a persisted first-generation record."""
    if not isinstance(value, dict) or not isinstance(
        value.get("had_destination"), bool
    ):
        raise RepairTransactionError("Pending repair record is invalid")
    disposition = RepairDisposition(value.get("disposition"))
    if disposition is RepairDisposition.PRESERVE:
        raise RepairTransactionError(
            "Pending repair record cannot replace preserved state"
        )
    destination = _relative_path(value.get("destination"), root)
    if version == 1:
        relocated, promoted = value.get("relocated"), value.get("promoted")
        if not isinstance(relocated, bool) or not isinstance(promoted, bool):
            raise RepairTransactionError("Pending legacy repair record is invalid")
        state = (
            RepairPathState.PROMOTED
            if promoted
            else RepairPathState.RELOCATED
            if relocated
            else RepairPathState.PREPARED
        )
    else:
        state = RepairPathState(value.get("state"))
    return RepairPathRecord(destination, disposition, value["had_destination"], state)


def _relative_path(value: object, root: Path) -> Path:
    """Reject escaped or redirected journal paths before interpreting state."""
    if not isinstance(value, str):
        raise RepairTransactionError("Pending repair path is invalid")
    path = Path(value)
    if path.is_absolute() or path.anchor or not path.parts or ".." in path.parts:
        raise RepairTransactionError(f"Pending repair path is unsafe: {value}")
    destination = root / path
    if not destination.resolve().is_relative_to(root.resolve()):
        raise RepairTransactionError(f"Pending repair path is unsafe: {value}")
    for candidate in (destination, *destination.parents):
        if candidate.is_symlink() or candidate.is_junction():
            raise RepairTransactionError(f"Pending repair path is unsafe: {value}")
        if candidate == root:
            break
    return path


def write_repair_journal(path: Path, journal: RepairJournal) -> None:
    """Flush transition intent before atomically replacing the previous journal."""
    payload = {
        "schema_version": REPAIR_JOURNAL_SCHEMA_VERSION,
        "quarantine_root": str(journal.quarantine_root),
        "phase": journal.phase.value,
        "records": [
            {
                "destination": str(record.destination),
                "disposition": record.disposition.value,
                "had_destination": record.had_destination,
                "state": record.state.value,
            }
            for record in journal.records
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
