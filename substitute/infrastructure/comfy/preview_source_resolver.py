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

"""Resolve Comfy preview metadata source nodes without listener side effects."""

from __future__ import annotations

from substitute.infrastructure.comfy.comfy_binary_event_decoder import (
    BinaryPreviewMetadata,
)
from substitute.infrastructure.comfy.comfy_progress_event_parser import (
    normalize_node_id,
)


def resolve_preview_metadata_node_id(
    metadata: BinaryPreviewMetadata,
    *,
    all_node_ids: set[str],
) -> str | None:
    """Return the prompt node identity for one metadata-bearing preview."""

    return normalize_node_id(
        node_id=metadata.node_id,
        all_node_ids=all_node_ids,
        display_node_id=metadata.display_node_id,
        parent_node_id=metadata.parent_node_id,
        real_node_id=metadata.real_node_id,
    )


__all__ = ["resolve_preview_metadata_node_id"]
