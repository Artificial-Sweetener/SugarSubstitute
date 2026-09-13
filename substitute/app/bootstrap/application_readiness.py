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

"""Publish a launcher-verifiable receipt after the application shell is usable."""

from __future__ import annotations

import os
from pathlib import Path
from substitute.app.bootstrap.surface_presentation import run_after_surface_paint

from sugarsubstitute_shared.application_readiness import (
    ApplicationReadinessReceipt,
    ApplicationReadinessSurface,
    READINESS_PATH_ENV,
    READINESS_SCHEMA_VERSION,
    READINESS_TOKEN_ENV,
    publish_application_readiness_receipt,
)


def schedule_application_readiness_receipt(
    *,
    surface: ApplicationReadinessSurface,
    window: object,
) -> bool:
    """Publish readiness only after the exact application surface paints."""

    readiness_path = _readiness_path_from_environment()
    readiness_token = os.environ.get(READINESS_TOKEN_ENV, "")
    if readiness_path is None or not readiness_token:
        return False
    run_after_surface_paint(
        window,
        lambda: _write_readiness_receipt(
            readiness_path=readiness_path,
            readiness_token=readiness_token,
            surface=surface,
        ),
    )
    return True


def _readiness_path_from_environment() -> Path | None:
    """Return the absolute launcher-owned receipt path when configured."""

    raw_path = os.environ.get(READINESS_PATH_ENV, "")
    if not raw_path:
        return None
    readiness_path = Path(raw_path)
    if not readiness_path.is_absolute() or readiness_path.suffix != ".json":
        return None
    return readiness_path


def _write_readiness_receipt(
    *,
    readiness_path: Path,
    readiness_token: str,
    surface: ApplicationReadinessSurface,
) -> None:
    """Atomically publish one process-bound application readiness receipt."""

    publish_application_readiness_receipt(
        receipt_path=readiness_path,
        receipt=ApplicationReadinessReceipt(
            pid=os.getpid(),
            token=readiness_token,
            surface=surface,
            parent_pid=os.getppid(),
        ),
    )


def schedule_main_shell_readiness_receipt(window: object) -> bool:
    """Publish readiness after the main application shell paints."""

    return schedule_application_readiness_receipt(
        surface=ApplicationReadinessSurface.MAIN_SHELL,
        window=window,
    )


__all__ = [
    "READINESS_PATH_ENV",
    "READINESS_SCHEMA_VERSION",
    "READINESS_TOKEN_ENV",
    "schedule_application_readiness_receipt",
    "schedule_main_shell_readiness_receipt",
]
