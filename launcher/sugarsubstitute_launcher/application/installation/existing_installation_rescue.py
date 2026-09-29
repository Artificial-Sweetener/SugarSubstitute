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

"""Recognize installer-owned roots and retire incompatible update state safely."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re

from launcher.sugarsubstitute_launcher.application.repair.models import (
    RepairOperation,
    RepairPlan,
    RepairScope,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.installation_recovery import InstallationRecovery
from launcher.sugarsubstitute_launcher.repair_transaction import RepairTransaction
from launcher.sugarsubstitute_launcher.update_activation_journal import (
    UpdateRecoveryError,
    update_journal_paths,
)
from sugarsubstitute_shared.installation_mutation import InstallationMutationOwnership
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord
from sugarsubstitute_shared.repair_recovery.disposition import RepairDisposition


_BOOTSTRAP_RUN_FILES = frozenset(
    {
        "exit-intent.json",
        "exit-receipt.json",
        "python-fault.log",
        "runtime-context.json",
        "startup-output.log",
    }
)
_BOOTSTRAP_INCIDENT_FILES = _BOOTSTRAP_RUN_FILES | frozenset(
    {"incident.json", "launcher-tail.log"}
)
_CANDIDATE_READINESS_NAME = re.compile(r"candidate-[0-9a-f]{32}\.json")
_READINESS_TEMPORARY_NAME = re.compile(
    r"\.(?:ci-installer-chain|candidate-[0-9a-f]{32})\.json\."
    r"[1-9][0-9]*\.[0-9a-f]{16}\.tmp"
)


class InstallationRootKind(str, Enum):
    """Classify a selected root before the installer writes into it."""

    NEW = "new"
    EXISTING_SUBSTITUTE = "existing_substitute"


class ExistingInstallationRecognitionError(RuntimeError):
    """Reject a nonempty directory whose ownership cannot be proven."""


@dataclass(frozen=True, slots=True)
class ExistingInstallationRescueOutcome:
    """Describe recognition and any retained incompatible transaction state."""

    kind: InstallationRootKind
    quarantine_root: Path | None = None


class ExistingInstallationRescueService:
    """Prepare new roots and safely normalize recognized historical installations."""

    def __init__(self, *, transaction: RepairTransaction | None = None) -> None:
        """Store the journaled quarantine transaction owner."""

        self._transaction = transaction or RepairTransaction()

    def prepare(
        self,
        layout: InstallLayout,
        *,
        ownership: InstallationMutationOwnership,
    ) -> ExistingInstallationRescueOutcome:
        """Recover normal state or quarantine an update journal no reader can use."""

        kind = self._inspect(layout)
        try:
            InstallationRecovery(layout).recover(ownership=ownership)
        except UpdateRecoveryError:
            if kind is not InstallationRootKind.EXISTING_SUBSTITUTE:
                raise
            quarantine = self._transaction.execute(
                plan=self._journal_plan(layout),
                replacements=(),
                ownership=ownership,
            )
            return ExistingInstallationRescueOutcome(kind, quarantine)
        return ExistingInstallationRescueOutcome(kind)

    @staticmethod
    def _inspect(layout: InstallLayout) -> InstallationRootKind:
        """Recognize a real Substitute root without trusting unknown nonempty content."""

        root = layout.root
        if (
            not root.exists()
            or not ExistingInstallationRescueService._meaningful_entries(root)
        ):
            return InstallationRootKind.NEW
        try:
            record = LauncherInstallationRecord.load(layout.launcher_installation_path)
        except (OSError, TypeError, ValueError):
            record = None
        if record is not None and record.target_key == layout.target.key:
            return InstallationRootKind.EXISTING_SUBSTITUTE
        try:
            config = LauncherConfig.load(layout.config_path)
        except (OSError, TypeError, ValueError):
            config = None
        if config is not None and config.install_root.resolve() == root.resolve():
            return InstallationRootKind.EXISTING_SUBSTITUTE
        if layout.executable_path.is_file() and layout.launcher_dir.is_dir():
            return InstallationRootKind.EXISTING_SUBSTITUTE
        raise ExistingInstallationRecognitionError(
            "The selected folder is not empty and is not a recognized "
            "SugarSubstitute installation."
        )

    @staticmethod
    def _meaningful_entries(root: Path) -> tuple[Path, ...]:
        """Ignore bootstrap artifacts created before root inspection."""

        entries = tuple(root.iterdir())
        non_repair = tuple(
            path
            for path in entries
            if path.name != ".repair"
            and not ExistingInstallationRescueService._is_bootstrap_launcher_tree(path)
            and not ExistingInstallationRescueService._is_bootstrap_appdata_tree(path)
        )
        if non_repair:
            return non_repair
        repair_root = root / ".repair"
        if not repair_root.is_dir():
            return ()
        return tuple(
            path for path in repair_root.iterdir() if path.name != "mutation.lock"
        )

    @staticmethod
    def _is_bootstrap_launcher_tree(path: Path) -> bool:
        """Recognize only launcher evidence written before root inspection."""

        if path.name != "launcher" or not path.is_dir() or path.is_symlink():
            return False
        allowed_directories = {Path("logs"), Path("readiness")}
        for entry in path.rglob("*"):
            if entry.is_symlink():
                return False
            relative = entry.relative_to(path)
            if entry.is_dir() and relative in allowed_directories:
                continue
            if entry.is_file() and (
                relative == Path("logs", "launcher.log")
                or ExistingInstallationRescueService._is_bootstrap_readiness_file(
                    relative
                )
            ):
                continue
            return False
        return True

    @staticmethod
    def _is_bootstrap_readiness_file(relative: Path) -> bool:
        """Recognize bounded supervisor receipts written before installation."""

        if relative.parent != Path("readiness"):
            return False
        name = relative.name
        return (
            name == "ci-installer-chain.json"
            or _CANDIDATE_READINESS_NAME.fullmatch(name) is not None
            or _READINESS_TEMPORARY_NAME.fullmatch(name) is not None
        )

    @staticmethod
    def _is_bootstrap_appdata_tree(path: Path) -> bool:
        """Recognize bounded crash evidence created by the setup bootstrap."""

        if path.name != "appdata" or not path.is_dir() or path.is_symlink():
            return False
        for entry in path.rglob("*"):
            if entry.is_symlink():
                return False
            relative = entry.relative_to(path)
            parts = relative.parts
            if entry.is_dir() and ExistingInstallationRescueService._is_diagnostic_dir(
                parts
            ):
                continue
            if (
                entry.is_file()
                and ExistingInstallationRescueService._is_diagnostic_file(parts)
            ):
                continue
            return False
        return True

    @staticmethod
    def _is_diagnostic_dir(parts: tuple[str, ...]) -> bool:
        """Return whether one relative directory is bootstrap diagnostic-owned."""

        if parts == ("diagnostics",):
            return True
        if len(parts) == 2 and parts[:1] == ("diagnostics",):
            return parts[1] in {"crashes", "crashpad", "runs"}
        if len(parts) == 3 and parts[:2] in {
            ("diagnostics", "crashes"),
            ("diagnostics", "runs"),
        }:
            return bool(parts[2])
        return parts[:2] == ("diagnostics", "crashpad")

    @staticmethod
    def _is_diagnostic_file(parts: tuple[str, ...]) -> bool:
        """Return whether one relative file is bounded bootstrap evidence."""

        if parts[:2] == ("diagnostics", "crashpad"):
            return True
        if len(parts) != 4 or not parts[2]:
            return False
        if parts[:2] == ("diagnostics", "runs"):
            return parts[3] in _BOOTSTRAP_RUN_FILES
        if parts[:2] == ("diagnostics", "crashes"):
            return parts[3] in _BOOTSTRAP_INCIDENT_FILES or parts[3].endswith(".dmp")
        return False

    @staticmethod
    def _journal_plan(layout: InstallLayout) -> RepairPlan:
        """Build the minimal transaction that retains every update journal verbatim."""

        return RepairPlan(
            scope=RepairScope.APPLICATION,
            install_root=layout.root.resolve(),
            operations=tuple(
                RepairOperation(
                    path=path.resolve(),
                    disposition=RepairDisposition.QUARANTINE,
                    reason="incompatible historical application-update transaction",
                )
                for path in update_journal_paths(layout)
            ),
        )


__all__ = [
    "ExistingInstallationRecognitionError",
    "ExistingInstallationRescueOutcome",
    "ExistingInstallationRescueService",
    "InstallationRootKind",
]
