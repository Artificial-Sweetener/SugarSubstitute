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
from pathlib import Path

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


LOG_FILE_NAME = "launcher.log"


def configure_launcher_logging(*, layout: InstallLayout) -> Path:
    """Configure file logging under the launcher install state directory."""

    layout.logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = layout.logs_dir / LOG_FILE_NAME
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if not _has_file_handler(root_logger, log_path):
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        root_logger.addHandler(handler)
    return log_path


def _has_file_handler(logger: logging.Logger, log_path: Path) -> bool:
    """Return whether an equivalent file handler is already installed."""

    resolved_log_path = log_path.resolve()
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            if Path(handler.baseFilename).resolve() == resolved_log_path:
                return True
    return False
