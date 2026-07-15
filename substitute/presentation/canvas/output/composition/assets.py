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

"""Compose Output canvas asset lookup collaborators."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from uuid import UUID

from substitute.presentation.canvas.output.output_canvas_asset_lookup import (
    OutputCanvasAssetLookup,
    OutputMetadataLookup,
    OutputPayloadLookup,
)


def output_canvas_asset_lookup(
    *,
    payload_lookup: OutputPayloadLookup | None,
    metadata_lookup: OutputMetadataLookup | None,
    preview_image_cache: Callable[[], Mapping[UUID, object]],
) -> OutputCanvasAssetLookup:
    """Return the asset lookup owner for final output and preview payloads."""

    return OutputCanvasAssetLookup(
        payload_lookup=payload_lookup,
        metadata_lookup=metadata_lookup,
        preview_image_cache=preview_image_cache,
    )
