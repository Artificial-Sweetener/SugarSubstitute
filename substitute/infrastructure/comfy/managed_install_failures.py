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

"""Define deterministic managed-install failure and storage error policy."""

from __future__ import annotations

import os

_FORCED_FAILURE_STAGE_ENV = "SUGARSUB_FORCE_MANAGED_FAILURE_STAGE"
_STORAGE_ERROR_MARKERS = (
    "no space left on device",
    "oserror(28",
    "[errno 28]",
    "there is not enough space on the disk",
)


class ManagedInstallStorageError(RuntimeError):
    """Raised when managed setup exhausts install-time scratch storage."""


def _forced_failure_stage() -> str | None:
    """Return the requested managed-install failure stage when one is configured."""

    raw_value = os.getenv(_FORCED_FAILURE_STAGE_ENV, "").strip().lower()
    return raw_value or None


def raise_forced_managed_failure(stage: str) -> None:
    """Raise one deterministic managed-install failure for harness scenarios."""

    forced_stage = _forced_failure_stage()
    if forced_stage != stage:
        return
    if stage == "clone":
        raise RuntimeError(
            "Substitute couldn't download ComfyUI into the selected folder."
        )
    if stage == "dependency_install":
        raise RuntimeError(
            "Substitute couldn't finish installing ComfyUI's Python packages."
        )
    raise RuntimeError(f"Unknown managed-install failure stage: {stage}")


def is_storage_exhaustion_message(message: str) -> bool:
    """Return whether command output reports exhausted temporary storage."""

    normalized = message.casefold()
    return any(marker in normalized for marker in _STORAGE_ERROR_MARKERS)
