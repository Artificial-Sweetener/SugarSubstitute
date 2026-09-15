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

"""Restore original repair destinations from the validated rollback journal."""

from __future__ import annotations

from pathlib import Path
import logging
import tempfile

from launcher.sugarsubstitute_launcher.application.repair.models import (
    RepairDisposition,
)
from launcher.sugarsubstitute_launcher.repair_errors import RepairTransactionError
from launcher.sugarsubstitute_launcher.repair_journal import (
    PENDING_JOURNAL,
    read_repair_journal,
    write_repair_journal,
)
from launcher.sugarsubstitute_launcher.repair_journal_state import (
    RepairPathState,
    RepairPhase,
)

_LOGGER = logging.getLogger(__name__)


def recover_interrupted_repair(install_root: Path) -> bool:
    """Resume rollback or finish committed cleanup without repeating completed moves."""

    root = install_root.resolve()
    journal_path = root / PENDING_JOURNAL
    journal = read_repair_journal(root)
    if journal is None:
        return False
    if journal.phase is RepairPhase.COMMITTED:
        journal_path.unlink()
        _LOGGER.info("Completed committed repair journal cleanup")
        return True
    quarantine_root = root / journal.quarantine_root
    journal.phase = RepairPhase.ROLLING_BACK
    for record in reversed(journal.records):
        if record.state is RepairPathState.RESTORED:
            continue
        destination = root / record.destination
        quarantined = quarantine_root / record.destination
        if quarantined.exists():
            record.state = RepairPathState.RESTORING
            write_repair_journal(journal_path, journal)
            _retain_failed_candidate(destination, quarantine_root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            quarantined.replace(destination)
        elif record.had_destination:
            if (
                record.state
                not in {
                    RepairPathState.PREPARED,
                    RepairPathState.RELOCATING,
                    RepairPathState.RESTORING,
                }
                or not destination.exists()
            ):
                raise RepairTransactionError(
                    f"Repair rollback source is missing: {quarantined}"
                )
        elif record.disposition is RepairDisposition.REPLACE:
            _retain_failed_candidate(destination, quarantine_root)
        record.state = RepairPathState.RESTORED
        write_repair_journal(journal_path, journal)
    journal_path.unlink()
    _LOGGER.info("Completed interrupted repair rollback")
    return True


def _retain_failed_candidate(path: Path, quarantine_root: Path) -> None:
    """Move rejected data aside so deletion permissions cannot prevent rollback."""
    if not (path.exists() or path.is_symlink() or path.is_junction()):
        return
    quarantine_root.mkdir(parents=True, exist_ok=True)
    retained_root = Path(tempfile.mkdtemp(prefix="rejected-", dir=quarantine_root))
    retained_path = retained_root / path.name
    path.replace(retained_path)
    _LOGGER.info(
        "Retained rejected repair candidate before restoring the original",
        extra={
            "operation": "repair_rollback",
            "destination": str(path),
            "retained_path": str(retained_path),
        },
    )
