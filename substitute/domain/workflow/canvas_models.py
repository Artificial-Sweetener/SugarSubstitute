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

"""Define domain workflow canvas state and editable mask binding models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from substitute.domain.common import (
    ImageIdentity,
    InputImageMap,
    MaskAssociationMap,
    MaskToImageMap,
)


class InputAssetRole(StrEnum):
    """Classify one editable upload endpoint by its connected graph use."""

    IMAGE = "image"
    MASK = "mask"


@dataclass(frozen=True)
class InputAssetEndpoint:
    """Describe one unambiguous upload widget and its used typed output socket."""

    section_key: str
    node_name: str
    field_key: str
    output_index: int
    role: InputAssetRole

    @property
    def identity(self) -> ImageIdentity:
        """Return the stable section/node identity used by canvas state."""

        return (self.section_key, self.node_name)


@dataclass(frozen=True)
class InputAssetEndpointIndex:
    """Expose semantically classified upload endpoints for one graph section."""

    endpoints: tuple[InputAssetEndpoint, ...] = ()
    ambiguous_endpoint_nodes: frozenset[str] = frozenset()

    @property
    def image_endpoints(self) -> tuple[InputAssetEndpoint, ...]:
        """Return endpoints classified exclusively as editable images."""

        return tuple(
            endpoint
            for endpoint in self.endpoints
            if endpoint.role is InputAssetRole.IMAGE
        )

    @property
    def mask_endpoints(self) -> tuple[InputAssetEndpoint, ...]:
        """Return endpoints classified exclusively as editable masks."""

        return tuple(
            endpoint
            for endpoint in self.endpoints
            if endpoint.role is InputAssetRole.MASK
        )

    def image_endpoint_for_node(self, node_name: str) -> InputAssetEndpoint | None:
        """Return one image upload widget when its node identity is unambiguous."""

        candidates = tuple(
            endpoint
            for endpoint in self.image_endpoints
            if endpoint.node_name == node_name
        )
        field_keys = {endpoint.field_key for endpoint in candidates}
        if len(field_keys) != 1:
            return None
        return candidates[0]


@dataclass
class WorkflowCanvasState:
    """Store workflow-local input canvas images, masks, and associations."""

    mask_associations: MaskAssociationMap = field(default_factory=dict)
    mask_to_image_map: MaskToImageMap = field(default_factory=dict)
    input_key_map: InputImageMap = field(default_factory=dict)
    input_image_uuid: UUID | None = None
    active_input_mask_uuid: UUID | None = None
    active_canvas_route: str | None = None


__all__ = [
    "InputAssetEndpoint",
    "InputAssetEndpointIndex",
    "InputAssetRole",
    "WorkflowCanvasState",
]
