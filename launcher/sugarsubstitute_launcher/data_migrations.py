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

"""Own deterministic, restart-safe persisted-data epoch migrations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Final, Self

from sugarsubstitute_shared.launcher_update.persistence import write_json_atomic
from sugarsubstitute_shared.update_compatibility import DataMigrationStep
from sugarsubstitute_shared.update_compatibility import UpdateCompatibilityContract


_LEDGER_SCHEMA_VERSION: Final = 1
_LEDGER_NAME: Final = "data-migrations.json"


@dataclass(frozen=True, slots=True)
class DataMigrationLedger:
    """Record the durable boundary around one idempotent migration."""

    current_epoch: int
    completed: tuple[str, ...]
    active: str | None = None

    @classmethod
    def from_json(cls, payload: object) -> Self:
        """Parse one ledger while rejecting ambiguous progress."""

        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("Unsupported data migration ledger schema.")
        epoch = payload.get("current_epoch")
        completed = payload.get("completed")
        active = payload.get("active")
        if type(epoch) is not int or epoch < 0:
            raise ValueError("Data migration epoch is invalid.")
        if (
            not isinstance(completed, list)
            or any(not isinstance(value, str) or not value for value in completed)
            or len(set(completed)) != len(completed)
        ):
            raise ValueError("Completed data migrations are invalid.")
        if active is not None and (not isinstance(active, str) or not active):
            raise ValueError("Active data migration is invalid.")
        return cls(current_epoch=epoch, completed=tuple(completed), active=active)

    def to_json(self) -> dict[str, object]:
        """Return the stable ledger representation."""

        return {
            "active": self.active,
            "completed": list(self.completed),
            "current_epoch": self.current_epoch,
            "schema_version": _LEDGER_SCHEMA_VERSION,
        }


class DataMigrationRunner:
    """Run declared migrations with a durable before/after journal."""

    def __init__(
        self,
        *,
        steps: tuple[DataMigrationStep, ...],
        operations: Mapping[str, Callable[[Path], None]] | None = None,
    ) -> None:
        """Bind declared transitions to their idempotent operations."""

        self._steps = steps
        self._operations = dict(operations or {})

    def migrate(self, *, install_root: Path, target_epoch: int) -> None:
        """Bring installed data to the target epoch or fail without guessing."""

        ledger_path = install_root / "launcher" / _LEDGER_NAME
        ledger = _load_ledger(ledger_path)
        if target_epoch < ledger.current_epoch:
            raise ValueError("Persisted data cannot be downgraded automatically.")
        steps_by_source = {step.from_epoch: step for step in self._steps}
        while ledger.current_epoch < target_epoch:
            step = steps_by_source.get(ledger.current_epoch)
            if step is None or step.to_epoch > target_epoch:
                raise ValueError("No declared data migration reaches the target epoch.")
            if ledger.active not in {None, step.identifier}:
                raise ValueError("Another data migration is incomplete.")
            running = DataMigrationLedger(
                current_epoch=ledger.current_epoch,
                completed=ledger.completed,
                active=step.identifier,
            )
            write_json_atomic(ledger_path, running.to_json())
            operation = self._operations.get(step.identifier, _adopt_epoch)
            operation(install_root)
            ledger = DataMigrationLedger(
                current_epoch=step.to_epoch,
                completed=(*ledger.completed, step.identifier),
                active=None,
            )
            write_json_atomic(ledger_path, ledger.to_json())


def default_data_migration_runner() -> DataMigrationRunner:
    """Build the runner from the immutable contract packaged with the launcher."""

    packaged = Path(getattr(sys, "_MEIPASS", "")) / "launcher_assets"
    contract_path = packaged / "launcher-contract.json"
    if not contract_path.is_file():
        contract_path = (
            Path(__file__).resolve().parents[2] / "launcher" / "launcher-contract.json"
        )
    contract = UpdateCompatibilityContract.load(contract_path)
    return DataMigrationRunner(steps=contract.data_migrations)


def _load_ledger(path: Path) -> DataMigrationLedger:
    """Load durable migration state or initialize the legacy epoch."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return DataMigrationLedger(current_epoch=0, completed=())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Data migration ledger is unreadable.") from error
    return DataMigrationLedger.from_json(payload)


def _adopt_epoch(_install_root: Path) -> None:
    """Adopt legacy persisted state without mutating authoritative user data."""


__all__ = [
    "DataMigrationLedger",
    "DataMigrationRunner",
    "default_data_migration_runner",
]
