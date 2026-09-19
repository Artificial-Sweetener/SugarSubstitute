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

"""Configure launcher-owned logging."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import threading

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.interprocess_log_handler import (
    InterprocessFileHandler,
)
from sugarsubstitute_shared.windows_long_paths import logical_path


LOG_FILE_NAME = "launcher.log"
_CONFIGURATION_LOCK = threading.Lock()


def configure_launcher_logging(*, layout: InstallLayout) -> Path:
    """Configure file logging under the launcher install state directory."""

    layout.logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = layout.logs_dir / LOG_FILE_NAME
    with _CONFIGURATION_LOCK:
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        handlers = _file_handlers_for(root_logger, log_path)
        for duplicate in handlers[1:]:
            root_logger.removeHandler(duplicate)
            duplicate.close()
        if not handlers:
            handler = InterprocessFileHandler(log_path, encoding="utf-8")
            handler.setFormatter(
                logging.Formatter(
                    fmt=(
                        "%(asctime)s %(levelname)s process=%(process)d "
                        "%(name)s %(message)s"
                    ),
                    datefmt="%Y-%m-%dT%H:%M:%S",
                )
            )
            root_logger.addHandler(handler)
    return log_path


def _file_handlers_for(
    logger: logging.Logger,
    log_path: Path,
) -> tuple[logging.FileHandler, ...]:
    """Return every file handler already targeting the launcher log."""

    resolved_log_path = _log_path_identity(log_path)
    matching: list[logging.FileHandler] = []
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and (
            _log_path_identity(Path(handler.baseFilename)) == resolved_log_path
        ):
            matching.append(handler)
    return tuple(matching)


def _log_path_identity(path: Path) -> str:
    """Normalize Win32 namespace aliases before comparing file handlers."""

    return os.path.normcase(os.path.abspath(logical_path(path)))
