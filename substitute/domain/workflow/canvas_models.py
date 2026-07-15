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

from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import UUID

from substitute.domain.common import (
    ImageIdentity,
    InputImageMap,
    MaskAssociationKey,
    MaskAssociationMap,
    MaskToImageMap,
)


@dataclass(frozen=True)
class EditableMaskBinding:
    """Identify one editable image-mask relationship exposed by a cube graph."""

    cube_alias: str
    image_node_name: str
    mask_node_name: str
    consumer_node_name: str

    @property
    def association_key(self) -> MaskAssociationKey:
        """Return the workflow mask-association key for this binding."""

        return (self.cube_alias, self.mask_node_name)

    @property
    def image_identity(self) -> ImageIdentity:
        """Return the workflow image identity for this binding."""

        return (self.cube_alias, self.image_node_name)


@dataclass(frozen=True)
class EditableMaskBindingIndex:
    """Expose unambiguous editable mask bindings for one cube graph."""

    bindings: tuple[EditableMaskBinding, ...] = ()
    ambiguous_mask_keys: frozenset[MaskAssociationKey] = frozenset()

    @classmethod
    def from_bindings(
        cls,
        bindings: Iterable[EditableMaskBinding],
    ) -> EditableMaskBindingIndex:
        """Build an index while dropping mask bindings that resolve ambiguously."""

        ordered = tuple(bindings)
        grouped: dict[MaskAssociationKey, list[EditableMaskBinding]] = {}
        for binding in ordered:
            grouped.setdefault(binding.association_key, []).append(binding)

        ambiguous = frozenset(
            key for key, candidates in grouped.items() if len(candidates) > 1
        )
        unique_bindings: list[EditableMaskBinding] = []
        seen_bindings: set[EditableMaskBinding] = set()
        for binding in ordered:
            if binding.association_key in ambiguous or binding in seen_bindings:
                continue
            seen_bindings.add(binding)
            unique_bindings.append(binding)
        return cls(bindings=tuple(unique_bindings), ambiguous_mask_keys=ambiguous)

    def binding_for_mask(
        self,
        cube_alias: str,
        mask_node_name: str,
    ) -> EditableMaskBinding | None:
        """Return the unique editable binding for one mask node when available."""

        association_key = (cube_alias, mask_node_name)
        if association_key in self.ambiguous_mask_keys:
            return None
        for binding in self.bindings:
            if binding.association_key == association_key:
                return binding
        return None

    def bindings_for_image(
        self,
        cube_alias: str,
        image_node_name: str,
    ) -> tuple[EditableMaskBinding, ...]:
        """Return editable mask bindings attached to one image identity."""

        image_identity = (cube_alias, image_node_name)
        return tuple(
            binding
            for binding in self.bindings
            if binding.image_identity == image_identity
        )

    def image_identities(self) -> tuple[ImageIdentity, ...]:
        """Return image identities that expose at least one editable mask binding."""

        ordered: list[ImageIdentity] = []
        seen: set[ImageIdentity] = set()
        for binding in self.bindings:
            if binding.image_identity in seen:
                continue
            seen.add(binding.image_identity)
            ordered.append(binding.image_identity)
        return tuple(ordered)


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
    "EditableMaskBinding",
    "EditableMaskBindingIndex",
    "WorkflowCanvasState",
]
