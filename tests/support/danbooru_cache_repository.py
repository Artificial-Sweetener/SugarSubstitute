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

"""Build the composed Danbooru cache repository for integration tests."""

from __future__ import annotations

from pathlib import Path

from substitute.infrastructure.persistence.danbooru_cache_repository import (
    ComposedDanbooruCacheRepository,
)
from substitute.infrastructure.persistence.danbooru_cache_store import (
    SqliteDanbooruMetadataStore,
)
from substitute.infrastructure.persistence.danbooru_image_cache_store import (
    SqliteDanbooruImageCacheStore,
)


def build_danbooru_cache_repository(
    cache_dir: Path,
) -> ComposedDanbooruCacheRepository:
    """Return a repository with independently owned metadata and image storage."""

    return ComposedDanbooruCacheRepository(
        metadata=SqliteDanbooruMetadataStore(cache_dir / "metadata"),
        images=SqliteDanbooruImageCacheStore(cache_dir / "images"),
    )


__all__ = ["build_danbooru_cache_repository"]
