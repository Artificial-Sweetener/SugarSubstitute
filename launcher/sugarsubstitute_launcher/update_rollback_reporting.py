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

"""Record recoverable update failures without weakening launcher fallback."""

from __future__ import annotations

import logging
from pathlib import Path

from sugarsubstitute_shared.update_rollback_report import (
    UpdateRollbackReport,
    UpdateRollbackReportStore,
    UpdateRollbackStage,
)


_LOGGER = logging.getLogger(__name__)


def record_update_rollback(
    *,
    install_root: Path,
    attempted_version: str,
    stage: UpdateRollbackStage,
    error: BaseException,
) -> None:
    """Persist one best-effort diagnostic receipt after rollback succeeds."""

    try:
        UpdateRollbackReportStore(install_root).save(
            UpdateRollbackReport.capture(
                attempted_version=attempted_version,
                stage=stage,
                error=error,
            )
        )
    except (OSError, ValueError):
        _LOGGER.warning(
            "Failed to persist the rolled-back update report.",
            exc_info=True,
        )


def discard_update_rollback_report(install_root: Path) -> None:
    """Best-effort remove a stale rollback report after update success."""

    try:
        UpdateRollbackReportStore(install_root).acknowledge()
    except OSError:
        _LOGGER.warning(
            "Failed to discard a stale rolled-back update report.",
            exc_info=True,
        )


__all__ = ["discard_update_rollback_report", "record_update_rollback"]
