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

"""Build application preview update DTOs from Comfy visual metadata."""

from __future__ import annotations

from substitute.application.ports.comfy_gateway import PreviewImageUpdate
from substitute.infrastructure.comfy.cube_output_event import SubstituteVisualIdentity


def build_preview_image_update(
    *,
    visual_identity: SubstituteVisualIdentity,
    image: object,
    prompt_id: str,
    node_id: str | None,
    metadata_node_id: str | None = None,
    display_node_id: str | None = None,
    parent_node_id: str | None = None,
    real_node_id: str | None = None,
) -> PreviewImageUpdate:
    """Return an application preview update with Backend visual routing metadata."""

    return PreviewImageUpdate(
        workflow_id=visual_identity.workflow_id,
        image=image,
        generation_run_id=visual_identity.generation_run_id,
        prompt_id=prompt_id,
        client_id=visual_identity.client_id,
        node_id=node_id,
        metadata_node_id=metadata_node_id,
        display_node_id=display_node_id,
        parent_node_id=parent_node_id,
        real_node_id=real_node_id,
        source_key=visual_identity.source_key,
        source_label=visual_identity.source_label,
        scene_run_id=visual_identity.scene_run_id,
        scene_key=visual_identity.scene_key,
        scene_title=visual_identity.scene_title,
        scene_order=visual_identity.scene_order,
        scene_count=visual_identity.scene_count,
    )


__all__ = ["build_preview_image_update"]
