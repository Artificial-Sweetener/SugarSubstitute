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

"""Restore declared authoritative state inside replaced repair destinations."""

from __future__ import annotations

import logging
from pathlib import Path
import shutil
import tempfile

from launcher.sugarsubstitute_launcher.application.repair.models import (
    RepairPlan,
)
from sugarsubstitute_shared.repair_recovery.disposition import RepairDisposition
from sugarsubstitute_shared.repair_recovery.errors import RepairTransactionError

_LOGGER = logging.getLogger(__name__)


class PreservedRepairState:
    """Keep original data in quarantine while rebuilding its live package location.

    Restore state after package installation and before validation. All writes
    remain beneath a journaled replacement destination, so existing rollback
    restores the original package even when copying fails partway through.
    """

    def __init__(self, plan: RepairPlan) -> None:
        """Capture existing nested preservation boundaries before any relocation."""
        self._root: Path = plan.install_root.resolve()
        replaced = tuple(
            operation.path
            for operation in plan.operations
            if operation.disposition is not RepairDisposition.PRESERVE
        )
        paths = tuple(
            operation.path
            for operation in plan.operations
            if operation.disposition is RepairDisposition.PRESERVE
            and any(operation.path.is_relative_to(parent) for parent in replaced)
            and operation.path.exists()
        )
        self._paths: tuple[Path, ...] = tuple(
            path
            for path in paths
            if not any(
                path != parent and path.is_relative_to(parent) for parent in paths
            )
        )
        for path in self._paths:
            if any(child.is_relative_to(path) for child in replaced):
                raise RepairTransactionError(
                    f"Preserved repair state contains a replacement boundary: {path}"
                )
            _validate_tree(path, self._root)

    def restore(self, quarantine_root: Path) -> None:
        """Restore original state without merging package-generated defaults."""
        for destination in self._paths:
            source = quarantine_root / destination.relative_to(self._root)
            _validate_tree(source, quarantine_root)
            _validate_ancestors(destination, self._root)
            try:
                if destination.exists():
                    generated = Path(
                        tempfile.mkdtemp(prefix="generated-state-", dir=quarantine_root)
                    )
                    destination.replace(generated / destination.name)
                    _LOGGER.debug(
                        "Retained package-generated defaults before restoring user state",
                        extra={
                            "operation": "repair_preserve_state",
                            "retained_path": str(generated),
                        },
                    )
                destination.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    shutil.copytree(source, destination)
                else:
                    shutil.copy2(source, destination)
            except OSError:
                _LOGGER.exception(
                    "Could not restore authoritative state during repair",
                    extra={
                        "operation": "repair_preserve_state",
                        "destination": str(destination),
                    },
                )
                raise
            _LOGGER.info(
                "Restored authoritative state during repair",
                extra={
                    "operation": "repair_preserve_state",
                    "destination": str(destination),
                },
            )


def _validate_ancestors(path: Path, root: Path) -> None:
    """Reject redirected boundaries before reading or relocating preserved data."""
    if not path.is_relative_to(root) or not path.resolve().is_relative_to(
        root.resolve()
    ):
        raise RepairTransactionError(f"Preserved repair state escapes its root: {path}")
    for candidate in (path, *path.parents):
        if candidate == root:
            break
        if candidate.is_symlink() or candidate.is_junction():
            raise RepairTransactionError(
                f"Preserved repair state is redirected: {candidate}"
            )


def _validate_tree(path: Path, root: Path) -> None:
    """Verify the complete copied tree without traversing redirected children."""
    _validate_ancestors(path, root)
    if not path.exists():
        raise RepairTransactionError(f"Preserved repair state is missing: {path}")
    if path.is_dir():
        for child in path.iterdir():
            _validate_tree(child, root)
