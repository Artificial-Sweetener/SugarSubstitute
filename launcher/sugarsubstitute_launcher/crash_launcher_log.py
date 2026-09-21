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

"""Capture bounded launcher history with a supervisor-owned crash incident."""

from __future__ import annotations

import logging
from pathlib import Path

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.crash_reporting.protocol import CrashRunContext


LAUNCHER_LOG_TAIL_FILENAME = "launcher-tail.log"
_MAXIMUM_TAIL_BYTES = 256 * 1024
_LOGGER = logging.getLogger(__name__)


def capture_launcher_log_tail(
    *,
    layout: InstallLayout,
    context: CrashRunContext,
    maximum_bytes: int = _MAXIMUM_TAIL_BYTES,
) -> Path | None:
    """Copy a bounded launcher-log tail into the temporary run evidence."""

    if maximum_bytes <= 0:
        raise ValueError("Launcher log tail size must be positive.")
    source = layout.logs_dir / "launcher.log"
    destination = context.run_root / context.run_id / LAUNCHER_LOG_TAIL_FILENAME
    try:
        with source.open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - maximum_bytes))
            content = stream.read().decode("utf-8", errors="replace")
        if not content.strip():
            return None
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        return destination
    except FileNotFoundError:
        return None
    except OSError:
        _LOGGER.warning(
            "Launcher log tail could not be captured for a crash incident",
            extra={"run_id": context.run_id},
            exc_info=True,
        )
        return None


__all__ = ["LAUNCHER_LOG_TAIL_FILENAME", "capture_launcher_log_tail"]
