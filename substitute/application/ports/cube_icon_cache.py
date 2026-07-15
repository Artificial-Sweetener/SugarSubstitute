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

"""Define durable rendered Cube Library icon cache contracts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CubeIconCacheKey:
    """Identify one rendered cube icon variant without Qt dependencies."""

    target_key: str
    catalog_revision: str
    cube_id: str
    cube_content_hash: str
    icon_kind: str
    icon_url: str
    media_type: str
    repo_relative_path: str
    color_behavior: str
    theme_name: str
    logical_size: int
    device_pixel_ratio: float
    renderer_version: int

    def stable_hash(self) -> str:
        """Return a deterministic SHA256 cache key for this render identity."""

        payload = {
            "targetKey": self.target_key,
            "catalogRevision": self.catalog_revision,
            "cubeId": self.cube_id,
            "cubeContentHash": self.cube_content_hash,
            "iconKind": self.icon_kind,
            "iconUrl": self.icon_url,
            "mediaType": self.media_type,
            "repoRelativePath": self.repo_relative_path,
            "colorBehavior": self.color_behavior,
            "themeName": self.theme_name,
            "logicalSize": int(self.logical_size),
            "devicePixelRatio": f"{self.device_pixel_ratio:.4f}",
            "rendererVersion": int(self.renderer_version),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RenderedCubeIconAsset:
    """Carry one Qt-ready rendered cube icon payload from durable storage."""

    cache_key: str
    width: int
    height: int
    qt_format: int
    bytes_per_line: int
    content_format: str
    payload: bytes

    @property
    def byte_size(self) -> int:
        """Return the rendered icon payload byte count."""

        return len(self.payload)


@runtime_checkable
class RenderedCubeIconCacheRepository(Protocol):
    """Persist and retrieve rendered Cube Library icon variants."""

    def read_rendered_icon(
        self,
        key: CubeIconCacheKey,
    ) -> RenderedCubeIconAsset | None:
        """Return one rendered icon variant, or ``None`` when absent."""

    def write_rendered_icon(
        self,
        key: CubeIconCacheKey,
        asset: RenderedCubeIconAsset,
    ) -> None:
        """Persist one rendered icon variant."""

    def delete_for_target(self, target_key: str) -> int:
        """Delete all rendered variants for one target key."""

    def delete_except_catalog_revision(
        self,
        target_key: str,
        catalog_revision: str,
    ) -> int:
        """Delete rendered variants not matching the active catalog revision."""

    def clear(self) -> int:
        """Delete all rendered icon variants."""

    def prune(self, *, maximum_rows: int, maximum_bytes: int) -> int:
        """Prune least recently accessed variants over row or byte budgets."""


__all__ = [
    "CubeIconCacheKey",
    "RenderedCubeIconAsset",
    "RenderedCubeIconCacheRepository",
]
