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

"""Adapt launcher rollback-report persistence to the application port."""

from __future__ import annotations

import json
from pathlib import Path

from sugarsubstitute_shared.update_rollback_report import (
    UpdateRollbackReport,
    UpdateRollbackReportStore,
)

from substitute.shared.logging.logger import get_logger, log_exception


_LOGGER = get_logger("infrastructure.launcher_update.update_rollback_report")


class FileUpdateRollbackReportRepository:
    """Load and acknowledge the launcher-owned rollback report safely."""

    def __init__(self, install_root: Path) -> None:
        """Bind the shared store to one installation root."""

        self._store = UpdateRollbackReportStore(install_root)

    def load(self) -> UpdateRollbackReport | None:
        """Return a valid pending report or discard malformed transient state."""

        try:
            return self._store.load()
        except (OSError, ValueError, json.JSONDecodeError):
            log_exception(
                _LOGGER,
                "Discarding an unreadable update rollback report",
                report_path=str(self._store.path),
            )
            self._discard_unreadable_report()
            return None

    def acknowledge(self) -> None:
        """Remove a report after the user dismisses its modal."""

        self._store.acknowledge()

    def _discard_unreadable_report(self) -> None:
        """Prevent malformed transient state from failing every startup."""

        try:
            self._store.acknowledge()
        except OSError:
            log_exception(
                _LOGGER,
                "Failed to discard an unreadable update rollback report",
                report_path=str(self._store.path),
            )


__all__ = ["FileUpdateRollbackReportRepository"]
