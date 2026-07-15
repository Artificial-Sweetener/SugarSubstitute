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

"""Own Qt-free startup readiness retry policy."""

from __future__ import annotations

from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)

TRANSIENT_STARTUP_COMPATIBILITY_STATUSES: frozenset[RuntimeCompatibilityStatus] = (
    frozenset({RuntimeCompatibilityStatus.BACKEND_UNREACHABLE})
)
STARTUP_READINESS_MAX_ATTEMPTS = 600


def should_retry_startup_compatibility(
    *,
    compatibility: BackendCompatibilityResult,
    readiness_attempts: int,
) -> bool:
    """Return whether startup should keep probing a transient compatibility state."""

    return (
        compatibility.status in TRANSIENT_STARTUP_COMPATIBILITY_STATUSES
        and readiness_attempts < STARTUP_READINESS_MAX_ATTEMPTS
    )


__all__ = [
    "STARTUP_READINESS_MAX_ATTEMPTS",
    "TRANSIENT_STARTUP_COMPATIBILITY_STATUSES",
    "should_retry_startup_compatibility",
]
