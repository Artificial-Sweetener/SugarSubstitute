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

"""Present a rolled-back update notice after the restored shell is usable."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from substitute.application.update_rollback_notice import (
    UpdateRollbackErrorSink,
    UpdateRollbackNoticeService,
)
from substitute.infrastructure.launcher_update.update_rollback_report_repository import (
    FileUpdateRollbackReportRepository,
)
from substitute.shared.logging.logger import get_logger, log_exception


_LOGGER = get_logger("app.bootstrap.update_rollback_notice_startup")


def schedule_update_rollback_notice_after_reveal(
    *,
    install_root: Path,
    shell_frame: object,
    main_window_for_shell: Callable[[object], object],
    scheduler: Callable[[int, Callable[[], None]], None],
) -> None:
    """Queue pending-notice presentation after the visible-shell event returns."""

    scheduler(
        0,
        lambda: _present_update_rollback_notice(
            install_root=install_root,
            main_window=main_window_for_shell(shell_frame),
        ),
    )


def schedule_update_rollback_notice_with_post_show_hydration(
    *,
    schedule_hydration: Callable[[], object],
    install_root: Path,
    shell_frame: Callable[[], object | None],
    main_window_for_shell: Callable[[object], object],
    scheduler: Callable[[int, Callable[[], None]], None],
) -> object:
    """Preserve post-show hydration and then queue the optional notice."""

    hydration_result = schedule_hydration()
    revealed_shell = shell_frame()
    if revealed_shell is not None:
        schedule_update_rollback_notice_after_reveal(
            install_root=install_root,
            shell_frame=revealed_shell,
            main_window_for_shell=main_window_for_shell,
            scheduler=scheduler,
        )
    return hydration_result


def _present_update_rollback_notice(
    *,
    install_root: Path,
    main_window: object,
) -> None:
    """Use the shell-owned error presenter without disrupting startup failures."""

    presenter = getattr(main_window, "_error_presenter", None)
    if presenter is None or not callable(getattr(presenter, "show_error_report", None)):
        return
    service = UpdateRollbackNoticeService(
        repository=FileUpdateRollbackReportRepository(install_root),
        error_sink=cast(UpdateRollbackErrorSink, presenter),
    )
    try:
        service.present_if_pending()
    except Exception:
        log_exception(
            _LOGGER,
            "Failed to present the update rollback report",
        )


__all__ = [
    "schedule_update_rollback_notice_after_reveal",
    "schedule_update_rollback_notice_with_post_show_hydration",
]
