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

from dataclasses import dataclass, field, replace
from enum import StrEnum
import math
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
    mask_visual_opacities: dict[MaskAssociationKey, float] = field(default_factory=dict)
    input_image_uuid: UUID | None = None
    active_input_mask_uuid: UUID | None = None
    active_canvas_route: str | None = None

    def mask_visual_opacity(self, association_key: MaskAssociationKey) -> float:
        """Return one node's visual mask opacity or CuteCanvas's native default."""

        return self.mask_visual_opacities.get(association_key, 0.5)

    def set_mask_visual_opacity(
        self,
        association_key: MaskAssociationKey,
        opacity: float,
    ) -> None:
        """Persist one bounded node-level mask presentation value."""

        normalized = float(opacity)
        if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
            raise ValueError("Mask visual opacity must be between 0.0 and 1.0.")
        self.mask_visual_opacities[association_key] = normalized

    def remove_mask_visual_opacity(
        self,
        association_key: MaskAssociationKey,
    ) -> None:
        """Remove presentation state for one retired mask node."""

        self.mask_visual_opacities.pop(association_key, None)

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

    def rename_section(self, old_section_key: str, new_section_key: str) -> bool:
        """Migrate every canvas identity owned by one renamed graph section."""

        if old_section_key == new_section_key:
            return False

        def renamed_input_key(input_key: str) -> str:
            """Return an image key with only the matching section replaced."""

            prefix = f"{old_section_key}:"
            return (
                f"{new_section_key}:{input_key[len(prefix) :]}"
                if input_key.startswith(prefix)
                else input_key
            )

        def renamed_association_key(
            association_key: MaskAssociationKey,
        ) -> MaskAssociationKey:
            """Return a mask key with only the matching section replaced."""

            section_key, node_name = association_key
            return (
                (new_section_key, node_name)
                if section_key == old_section_key
                else association_key
            )

        renamed_image_keys = {
            input_key: renamed_input_key(input_key) for input_key in self.image_entries
        }
        renamed_mask_keys = {
            key: renamed_association_key(key) for key in self.mask_entries
        }
        renamed_collection_keys = {
            key: renamed_association_key(key) for key in self.regional_mask_collections
        }
        renamed_opacity_keys = {
            key: renamed_association_key(key) for key in self.mask_visual_opacities
        }
        for source_keys, replacements in (
            (self.image_entries, renamed_image_keys),
            (self.mask_entries, renamed_mask_keys),
            (self.regional_mask_collections, renamed_collection_keys),
            (self.mask_visual_opacities, renamed_opacity_keys),
        ):
            if any(
                target != source and target in source_keys
                for source, target in replacements.items()
            ):
                raise ValueError("Input canvas rename target identity already exists.")
        changed = any(
            source != target
            for replacements in (
                renamed_image_keys,
                renamed_mask_keys,
                renamed_collection_keys,
                renamed_opacity_keys,
            )
            for source, target in replacements.items()
        )
        self.image_entries = {
            target: replace(entry, input_key=target)
            for source, entry in self.image_entries.items()
            for target in (renamed_image_keys[source],)
        }
        self.mask_entries = {
            target: replace(entry, association_key=target)
            for source, entry in self.mask_entries.items()
            for target in (renamed_mask_keys[source],)
        }
        self.regional_mask_collections = {
            renamed_collection_keys[source]: collection
            for source, collection in self.regional_mask_collections.items()
        }
        for association_key, collection in self.regional_mask_collections.items():
            collection.association_key = association_key
        self.mask_visual_opacities = {
            renamed_opacity_keys[source]: opacity
            for source, opacity in self.mask_visual_opacities.items()
        }
        return changed

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

    def mask_association_keys(self) -> tuple[MaskAssociationKey, ...]:
        """Return every scalar or ordered graph mask identity once."""

        return tuple(
            dict.fromkeys(
                (*self.mask_entries.keys(), *self.regional_mask_collections.keys())
            )
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

    def remap_mask_ids(
        self,
        image_id: UUID,
        replacements: tuple[tuple[UUID, UUID], ...],
    ) -> bool:
        """Replace canvas-generated mask resources without changing region identity."""

        remap = {old_id: new_id for old_id, new_id in replacements if old_id != new_id}
        if not remap:
            return False
        if len(remap) != len(
            tuple(item for item in replacements if item[0] != item[1])
        ):
            raise ValueError("Mask identity remap contains duplicate source ids.")
        if len(set(remap.values())) != len(remap):
            raise ValueError("Mask identity remap contains duplicate target ids.")
        owned_occurrences = [
            (entry.mask_id, entry.image_id) for entry in self.mask_entries.values()
        ] + [
            (entry.mask_id, entry.image_id)
            for collection in self.regional_mask_collections.values()
            for entry in collection.entries
            if entry.mask_id is not None
        ]
        for old_id in remap:
            matches = tuple(
                owner for mask_id, owner in owned_occurrences if mask_id == old_id
            )
            if matches != (image_id,):
                raise ValueError(
                    "Mask identity remap source must have one image owner."
                )
        retained_ids = {
            mask_id for mask_id, _owner in owned_occurrences if mask_id not in remap
        }
        if retained_ids.intersection(remap.values()):
            raise ValueError(
                "Mask identity remap target already belongs to the workflow."
            )

        self.mask_entries = {
            association_key: replace(
                entry,
                mask_id=remap.get(entry.mask_id, entry.mask_id),
            )
            for association_key, entry in self.mask_entries.items()
        }
        for collection in self.regional_mask_collections.values():
            collection.entries = [
                replace(
                    entry,
                    mask_id=(
                        remap.get(entry.mask_id, entry.mask_id)
                        if entry.mask_id is not None
                        else None
                    ),
                )
                for entry in collection.entries
            ]
        if self.active_input_mask_uuid in remap:
            self.active_input_mask_uuid = remap[self.active_input_mask_uuid]
        return True


__all__ = [
    "InputAssetCardinality",
    "InputAssetEndpoint",
    "InputAssetEndpointIndex",
    "InputAssetRole",
    "InputCanvasImageEntry",
    "InputCanvasMaskEntry",
    "WorkflowCanvasState",
]
