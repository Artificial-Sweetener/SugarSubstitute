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
)

_LOGGER = logging.getLogger(__name__)


def recover_interrupted_repair(install_root: Path) -> bool:
    """Restore all relocated paths recorded by an interrupted repair journal."""

    root = install_root.resolve()
    journal_path = root / PENDING_JOURNAL
    journal = read_repair_journal(root)
    if journal is None:
        return False
    records, quarantine_root = journal
    for record in reversed(records):
        destination = root / record["destination"]
        quarantined = quarantine_root / record["destination"]
        if record["relocated"]:
            if not quarantined.exists():
                raise RepairTransactionError(
                    f"Repair rollback source is missing: {quarantined}"
                )
            _retain_failed_candidate(destination, quarantine_root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            quarantined.replace(destination)
        elif (
            record["disposition"] == RepairDisposition.REPLACE.value
            and not record["had_destination"]
        ):
            _retain_failed_candidate(destination, quarantine_root)
    journal_path.unlink()
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
