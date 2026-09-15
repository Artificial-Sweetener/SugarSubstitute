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
from pathlib import Path
import secrets

from launcher.sugarsubstitute_launcher.application.repair.models import (
    RepairDisposition,
    RepairPlan,
    RepairReplacement,
)
from launcher.sugarsubstitute_launcher.repair_errors import RepairTransactionError
from launcher.sugarsubstitute_launcher.repair_journal import (
    PENDING_JOURNAL,
    write_repair_journal,
    validate_repair_journal_paths,
)
from launcher.sugarsubstitute_launcher.repair_journal_state import (
    RepairJournal,
    RepairPathRecord,
    RepairPathState,
    RepairPhase,
)
from launcher.sugarsubstitute_launcher.repair_recovery import recover_interrupted_repair
from launcher.sugarsubstitute_launcher.repair_preserved_state import (
    PreservedRepairState,
)


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
        journal_path = root / PENDING_JOURNAL
        if journal_path.exists():
            raise RepairTransactionError(
                "A repair transaction is already pending and must be recovered first."
            )
        normalized = self._validate_replacements(plan, replacements)
        preserved_state = PreservedRepairState(plan)
        identifier = transaction_id or secrets.token_hex(8)
        if not identifier or any(
            character
            not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for character in identifier
        ):
            raise RepairTransactionError("Repair transaction identifier is invalid.")
        quarantine_root = root / ".repair" / "quarantine" / identifier
        if quarantine_root.exists():
            raise RepairTransactionError("Repair quarantine already exists.")
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
            RepairPathRecord(
                destination=operation.path.relative_to(root),
                disposition=operation.disposition,
                had_destination=operation.path.exists(),
            )
            for operation in transaction_operations
        ]
        journal = RepairJournal(quarantine_root.relative_to(root), records)
        validate_repair_journal_paths(root, journal)
        write_repair_journal(journal_path, journal)
        try:
            for operation, record in zip(transaction_operations, records, strict=True):
                destination = operation.path
                if destination.exists():
                    quarantined = quarantine_root / destination.relative_to(root)
                    quarantined.parent.mkdir(parents=True, exist_ok=True)
                    record.state = RepairPathState.RELOCATING
                    journal.phase = RepairPhase.RELOCATING
                    write_repair_journal(journal_path, journal)
                    destination.replace(quarantined)
                    record.state = RepairPathState.RELOCATED
                    write_repair_journal(journal_path, journal)
                    self._after_move(destination, quarantined)
                replacement = replacement_by_destination.get(destination)
                if replacement is None:
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                record.state = RepairPathState.PROMOTING
                journal.phase = RepairPhase.PROMOTING
                write_repair_journal(journal_path, journal)
                replacement.staged_path.replace(destination)
                record.state = RepairPathState.PROMOTED
                write_repair_journal(journal_path, journal)
                self._after_move(replacement.staged_path, destination)
            journal.phase = RepairPhase.APPLYING
            write_repair_journal(journal_path, journal)
            if apply_repair is not None:
                apply_repair()
            preserved_state.restore(quarantine_root)
            journal.phase = RepairPhase.VALIDATING
            write_repair_journal(journal_path, journal)
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
        journal.phase = RepairPhase.COMMITTED
        write_repair_journal(journal_path, journal)
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
