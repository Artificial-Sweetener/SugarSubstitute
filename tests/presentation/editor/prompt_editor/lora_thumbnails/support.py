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

"""Deterministic thumbnail asset collaborators for cache tests."""

from __future__ import annotations


from substitute.domain.model_metadata import ThumbnailAsset
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionThumbnailVariant,
)


class _FailingThumbnailAssetRepository:
    """Raise while counting thumbnail asset reads."""

    def __init__(self) -> None:
        """Initialize read accounting."""

        self.reads = 0

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Record and fail one thumbnail asset read."""

        _ = storage_key
        self.reads += 1
        raise RuntimeError("thumbnail store unavailable")


class _InvalidThumbnailAssetRepository:
    """Return invalid thumbnail payloads while counting asset reads."""

    def __init__(self) -> None:
        """Initialize read accounting."""

        self.reads = 0

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Record one read and return undecodable payload data."""

        self.reads += 1
        return ThumbnailAsset(
            storage_key=storage_key,
            width=16,
            height=16,
            qt_format=-1,
            bytes_per_line=0,
            content_format="sqthumb-qimage-argb32-premultiplied",
            payload=b"not-image-data",
        )


def _projection_thumbnail_variant(storage_key: str) -> PromptProjectionThumbnailVariant:
    """Return one prepared projection thumbnail reference for cache tests."""

    return PromptProjectionThumbnailVariant(
        size=128,
        storage_key=storage_key,
        width=85,
        height=128,
        content_format="sqthumb-qimage-argb32-premultiplied",
        byte_size=43520,
    )
