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

"""Expose reusable Qt media wall widgets and layout primitives."""

from __future__ import annotations

from substitute.presentation.widgets.media_wall.justified_layout import (
    DEFAULT_JUSTIFIED_WALL_ASPECT_RATIO,
    PICKER_JUSTIFIED_WALL_GUTTER,
    PickerJustifiedWallProfile,
    JustifiedLayoutInput,
    JustifiedLayoutItem,
    JustifiedLayoutRow,
    JustifiedLayoutRowItem,
    build_justified_rows,
    normalize_aspect_ratio,
)
from substitute.presentation.widgets.media_wall.media_wall_item import (
    MediaWallItem,
    ThumbnailVariantReference,
)
from substitute.presentation.widgets.media_wall.media_wall_thumbnail_cache import (
    MediaWallPixmapCacheKey,
    MediaWallThumbnailCache,
)
from substitute.presentation.widgets.media_wall.media_wall_thumbnail_preloader import (
    MediaWallThumbnailPreloader,
)
from substitute.presentation.widgets.media_wall.media_wall_view import MediaWallView
from substitute.presentation.widgets.media_wall.thumbnail_readiness import (
    MediaThumbnailReadiness,
    MediaThumbnailReadinessStatus,
    unavailable_thumbnail_readiness,
)

__all__ = [
    "DEFAULT_JUSTIFIED_WALL_ASPECT_RATIO",
    "PICKER_JUSTIFIED_WALL_GUTTER",
    "PickerJustifiedWallProfile",
    "JustifiedLayoutInput",
    "JustifiedLayoutItem",
    "JustifiedLayoutRow",
    "JustifiedLayoutRowItem",
    "MediaWallItem",
    "MediaWallPixmapCacheKey",
    "MediaWallThumbnailCache",
    "MediaWallThumbnailPreloader",
    "MediaWallView",
    "MediaThumbnailReadiness",
    "MediaThumbnailReadinessStatus",
    "ThumbnailVariantReference",
    "build_justified_rows",
    "normalize_aspect_ratio",
    "unavailable_thumbnail_readiness",
]
