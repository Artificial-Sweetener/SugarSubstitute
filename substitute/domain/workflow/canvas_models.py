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

from substitute.domain.common import ImageIdentity, MaskAssociationKey
from substitute.domain.workflow.regional_mask_models import (
    RegionalMaskCollection,
    RegionalMaskEntry,
)


class InputAssetRole(StrEnum):
    """Classify one editable upload endpoint by its connected graph use."""

    IMAGE = "image"
    MASK = "mask"


class InputAssetCardinality(StrEnum):
    """Describe whether one editable endpoint authors one asset or an ordered batch."""

    SCALAR = "scalar"
    ORDERED = "ordered"


@dataclass(frozen=True)
class InputAssetEndpoint:
    """Describe one unambiguous upload widget and its used typed output socket."""

    section_key: str
    node_name: str
    field_key: str
    output_index: int
    role: InputAssetRole
    cardinality: InputAssetCardinality = InputAssetCardinality.SCALAR

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


@dataclass(frozen=True, slots=True)
class InputCanvasImageEntry:
    """Keep one graph image node and its Input document layer inseparable."""

    input_key: str
    image_id: UUID


@dataclass(frozen=True, slots=True)
class InputCanvasMaskEntry:
    """Keep one graph mask node, layer, and owning image inseparable."""

    association_key: MaskAssociationKey
    mask_id: UUID
    image_id: UUID


@dataclass
class WorkflowCanvasState:
    """Own workflow-local node-and-layer Input document entries."""

    image_entries: dict[str, InputCanvasImageEntry] = field(default_factory=dict)
    mask_entries: dict[MaskAssociationKey, InputCanvasMaskEntry] = field(
        default_factory=dict
    )
    regional_mask_collections: dict[MaskAssociationKey, RegionalMaskCollection] = field(
        default_factory=dict
    )
    input_image_uuid: UUID | None = None
    active_input_mask_uuid: UUID | None = None
    active_canvas_route: str | None = None

    def image_entry(self, input_key: str) -> InputCanvasImageEntry | None:
        """Return the complete image entry for one graph input identity."""

        return self.image_entries.get(input_key)

    def image_entry_for_id(self, image_id: UUID) -> InputCanvasImageEntry | None:
        """Return the image entry owning one Input document composition."""

        return next(
            (
                entry
                for entry in self.image_entries.values()
                if entry.image_id == image_id
            ),
            None,
        )

    def bind_image(self, input_key: str, image_id: UUID) -> InputCanvasImageEntry:
        """Create or reaffirm one image node-and-layer identity."""

        existing = self.image_entries.get(input_key)
        if existing is not None:
            if existing.image_id != image_id:
                raise ValueError(
                    "image entry identity replacement requires replace_image_entry"
                )
            return existing
        entry = InputCanvasImageEntry(input_key, image_id)
        self.image_entries[input_key] = entry
        return entry

    def replace_image_entry(
        self,
        input_key: str,
        image_id: UUID,
    ) -> InputCanvasImageEntry:
        """Explicitly replace a node's document identity for direct-canvas adoption."""

        entry = InputCanvasImageEntry(input_key, image_id)
        self.image_entries[input_key] = entry
        return entry

    def remove_image_entry(self, input_key: str) -> InputCanvasImageEntry | None:
        """Remove one obsolete image node-and-layer entry."""

        return self.image_entries.pop(input_key, None)

    def image_ids(self) -> tuple[UUID, ...]:
        """Return Input document image identities owned by this workflow."""

        return tuple(entry.image_id for entry in self.image_entries.values())

    def mask_entry(
        self,
        association_key: MaskAssociationKey,
    ) -> InputCanvasMaskEntry | None:
        """Return the complete mask entry for one graph mask node."""

        return self.mask_entries.get(association_key)

    def mask_entry_for_id(self, mask_id: UUID) -> InputCanvasMaskEntry | None:
        """Return the graph mask entry owning one Input document layer."""

        return next(
            (entry for entry in self.mask_entries.values() if entry.mask_id == mask_id),
            None,
        )

    def bind_mask(
        self,
        association_key: MaskAssociationKey,
        mask_id: UUID,
        image_id: UUID,
    ) -> InputCanvasMaskEntry:
        """Create or reaffirm one mask node-and-layer identity."""

        existing = self.mask_entries.get(association_key)
        if existing is not None:
            if existing.mask_id != mask_id or existing.image_id != image_id:
                raise ValueError(
                    "mask entry identity replacement requires replace_mask_entry"
                )
            return existing
        entry = InputCanvasMaskEntry(association_key, mask_id, image_id)
        self.mask_entries[association_key] = entry
        return entry

    def replace_mask_entry(
        self,
        association_key: MaskAssociationKey,
        mask_id: UUID,
        image_id: UUID,
    ) -> InputCanvasMaskEntry:
        """Explicitly replace a mask identity during validated document adoption."""

        entry = InputCanvasMaskEntry(association_key, mask_id, image_id)
        self.mask_entries[association_key] = entry
        return entry

    def remove_mask_entry(
        self,
        association_key: MaskAssociationKey,
    ) -> InputCanvasMaskEntry | None:
        """Remove one obsolete mask node-and-layer entry."""

        return self.mask_entries.pop(association_key, None)

    def mask_ids(self) -> tuple[UUID, ...]:
        """Return Input document mask identities owned by this workflow."""

        return tuple(entry.mask_id for entry in self.mask_entries.values()) + tuple(
            entry.mask_id
            for collection in self.regional_mask_collections.values()
            for entry in collection.entries
            if entry.mask_id is not None
        )

    def regional_mask_collection(
        self,
        association_key: MaskAssociationKey,
    ) -> RegionalMaskCollection | None:
        """Return the ordered regional mask collection for one graph endpoint."""

        return self.regional_mask_collections.get(association_key)

    def ensure_regional_mask_collection(
        self,
        association_key: MaskAssociationKey,
    ) -> RegionalMaskCollection:
        """Return or create the ordered collection for one graph endpoint."""

        collection = self.regional_mask_collections.get(association_key)
        if collection is None:
            collection = RegionalMaskCollection(association_key=association_key)
            self.regional_mask_collections[association_key] = collection
        return collection

    def remove_regional_mask_collection(
        self,
        association_key: MaskAssociationKey,
    ) -> RegionalMaskCollection | None:
        """Remove one ordered regional endpoint collection."""

        return self.regional_mask_collections.pop(association_key, None)

    def regional_mask_entry_for_id(self, mask_id: UUID) -> RegionalMaskEntry | None:
        """Return one ordered-region entry by canvas mask identity."""

        return next(
            (
                entry
                for collection in self.regional_mask_collections.values()
                if (entry := collection.entry_for_mask(mask_id)) is not None
            ),
            None,
        )

    def owns_mask(self, mask_id: UUID, image_id: UUID) -> bool:
        """Return whether scalar or ordered state owns one image-bound mask."""

        scalar = self.mask_entry_for_id(mask_id)
        if scalar is not None:
            return scalar.image_id == image_id
        regional = self.regional_mask_entry_for_id(mask_id)
        return regional is not None and regional.image_id == image_id

    def mask_image_owners(self) -> dict[UUID, UUID]:
        """Return every materialized mask layer and its owning image."""

        owners = {entry.mask_id: entry.image_id for entry in self.mask_entries.values()}
        owners.update(
            {
                entry.mask_id: entry.image_id
                for collection in self.regional_mask_collections.values()
                for entry in collection.entries
                if entry.mask_id is not None
            }
        )
        return owners


__all__ = [
    "InputAssetCardinality",
    "InputAssetEndpoint",
    "InputAssetEndpointIndex",
    "InputAssetRole",
    "InputCanvasImageEntry",
    "InputCanvasMaskEntry",
    "WorkflowCanvasState",
]
