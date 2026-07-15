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

"""Resolve Output canvas final and preview image assets for presentation code."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from substitute.presentation.canvas.shared.types import OutputImageMeta

OutputPayloadLookup = Callable[[UUID], object | None]
OutputMetadataLookup = Callable[[UUID], OutputImageMeta | None]


def _empty_preview_image_cache() -> Mapping[UUID, object]:
    """Return no preview images by default."""

    return {}


@dataclass(slots=True)
class OutputCanvasAssetLookup:
    """Own final-output and preview asset lookup for Output canvas presenters."""

    payload_lookup: OutputPayloadLookup | None = None
    metadata_lookup: OutputMetadataLookup | None = None
    preview_image_cache: Callable[[], Mapping[UUID, object]] = (
        _empty_preview_image_cache
    )

    def set_final_output_lookup(
        self,
        *,
        payload_lookup: OutputPayloadLookup,
        metadata_lookup: OutputMetadataLookup,
    ) -> None:
        """Install registry-backed final-output lookup callbacks."""

        self.payload_lookup = payload_lookup
        self.metadata_lookup = metadata_lookup

    def final_output_payload(self, image_id: UUID) -> object | None:
        """Return final-output payload for one image when available."""

        lookup = self.payload_lookup
        if lookup is None:
            return None
        return lookup(image_id)

    def final_output_metadata(self, image_id: UUID) -> OutputImageMeta | None:
        """Return final-output metadata for one image when available."""

        lookup = self.metadata_lookup
        if lookup is None:
            return None
        return lookup(image_id)

    def preview_images(self) -> dict[UUID, object]:
        """Return revision-scoped transient preview images."""

        return dict(self.preview_image_cache())

    def scene_request_layer_payload(self, layer: object) -> object | None:
        """Return the payload for one scene request layer."""

        image_id = getattr(layer, "image_id", None)
        if not isinstance(image_id, UUID):
            return None
        metadata = getattr(layer, "metadata", {})
        is_preview = isinstance(metadata, Mapping) and bool(metadata.get("preview"))
        if is_preview:
            return self.preview_images().get(image_id)
        return self.final_output_payload(image_id)

    def scene_request_layer_path(self, layer: object) -> Path | None:
        """Return the final-output path for one scene request layer."""

        metadata = getattr(layer, "metadata", {})
        if isinstance(metadata, Mapping) and bool(metadata.get("preview")):
            return None
        image_id = getattr(layer, "image_id", None)
        if not isinstance(image_id, UUID):
            return None
        image_meta = self.final_output_metadata(image_id)
        raw_path = getattr(image_meta, "path", None)
        return Path(raw_path) if raw_path else None


__all__ = [
    "OutputCanvasAssetLookup",
    "OutputMetadataLookup",
    "OutputPayloadLookup",
]
