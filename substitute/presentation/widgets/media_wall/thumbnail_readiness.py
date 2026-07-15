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

"""Represent foreground-safe media thumbnail readiness state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MediaThumbnailReadinessStatus(StrEnum):
    """Classify thumbnail state available to foreground consumers."""

    READY = "ready"
    PENDING = "pending"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class MediaThumbnailReadiness:
    """Describe whether a thumbnail can be painted without storage I/O."""

    status: MediaThumbnailReadinessStatus
    storage_key: str | None = None
    cache_generation: int | None = None
    unavailable_reason: str | None = None

    @property
    def ready(self) -> bool:
        """Return whether a foreground consumer may expect a cached pixmap."""

        return self.status is MediaThumbnailReadinessStatus.READY


def unavailable_thumbnail_readiness(reason: str) -> MediaThumbnailReadiness:
    """Return a thumbnail readiness value for missing thumbnail capability."""

    return MediaThumbnailReadiness(
        status=MediaThumbnailReadinessStatus.UNAVAILABLE,
        unavailable_reason=reason,
    )


__all__ = [
    "MediaThumbnailReadiness",
    "MediaThumbnailReadinessStatus",
    "unavailable_thumbnail_readiness",
]
