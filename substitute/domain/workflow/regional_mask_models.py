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

"""Define ordered regional-mask identity independently from canvas widgets."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from uuid import UUID, uuid4

from substitute.domain.common import MaskAssociationKey
from substitute.domain.workflow.asset_models import WorkflowAssetRef


@dataclass(frozen=True, slots=True)
class RegionalMaskEntry:
    """Identify one region and its optional materialized canvas mask layer."""

    region_id: UUID
    image_id: UUID
    mask_id: UUID | None = None
    asset_ref: WorkflowAssetRef | None = None
    authored_color: str | None = None

    def __post_init__(self) -> None:
        """Reject malformed authored colors at the domain boundary."""

        color = self.authored_color
        if color is not None and (
            len(color) != 7
            or not color.startswith("#")
            or any(character not in "0123456789abcdefABCDEF" for character in color[1:])
        ):
            raise ValueError("Authored region colors must use #RRGGBB notation.")


@dataclass(slots=True)
class RegionalMaskCollection:
    """Own stable region identities and their ordered Comfy mask-batch order."""

    association_key: MaskAssociationKey
    entries: list[RegionalMaskEntry] = field(default_factory=list)
    selected_region_id: UUID | None = None

    def __post_init__(self) -> None:
        """Enforce unique region and layer identities after construction or restore."""

        region_ids = [entry.region_id for entry in self.entries]
        if len(region_ids) != len(set(region_ids)):
            raise ValueError("Regional mask collection contains duplicate region ids.")
        mask_ids = [
            entry.mask_id for entry in self.entries if entry.mask_id is not None
        ]
        if len(mask_ids) != len(set(mask_ids)):
            raise ValueError("Regional mask collection contains duplicate mask ids.")
        if self.selected_region_id is not None and self.selected_region_id not in set(
            region_ids
        ):
            raise ValueError("Selected region must belong to its mask collection.")

    def add_region(
        self,
        image_id: UUID,
        *,
        region_id: UUID | None = None,
        mask_id: UUID | None = None,
        asset_ref: WorkflowAssetRef | None = None,
        authored_color: str | None = None,
    ) -> RegionalMaskEntry:
        """Append one stable region and select it."""

        entry = RegionalMaskEntry(
            region_id=region_id or uuid4(),
            image_id=image_id,
            mask_id=mask_id,
            asset_ref=asset_ref,
            authored_color=authored_color,
        )
        if any(existing.region_id == entry.region_id for existing in self.entries):
            raise ValueError("Region identity already belongs to this collection.")
        if entry.mask_id is not None and any(
            existing.mask_id == entry.mask_id for existing in self.entries
        ):
            raise ValueError("Mask layer already belongs to this collection.")
        self.entries.append(entry)
        self.selected_region_id = entry.region_id
        return entry

    def bind_mask_layer(self, region_id: UUID, mask_id: UUID) -> RegionalMaskEntry:
        """Attach one materialized canvas layer to an existing region identity."""

        if any(
            entry.mask_id == mask_id and entry.region_id != region_id
            for entry in self.entries
        ):
            raise ValueError("Mask layer already belongs to another region.")
        index = self._index_of(region_id)
        entry = replace(self.entries[index], mask_id=mask_id)
        self.entries[index] = entry
        return entry

    def bind_asset(
        self,
        region_id: UUID,
        asset_ref: WorkflowAssetRef,
    ) -> RegionalMaskEntry:
        """Attach one durable source asset to an existing region identity."""

        index = self._index_of(region_id)
        entry = replace(self.entries[index], asset_ref=asset_ref)
        self.entries[index] = entry
        return entry

    def select(self, region_id: UUID) -> None:
        """Select one region while preserving its ordered position."""

        self._index_of(region_id)
        self.selected_region_id = region_id

    def reorder(self, region_id: UUID, target_index: int) -> None:
        """Move one region to a validated Comfy batch position."""

        if not 0 <= target_index < len(self.entries):
            raise IndexError("Regional mask target index is outside the collection.")
        entry = self.entries.pop(self._index_of(region_id))
        self.entries.insert(target_index, entry)

    def remove(self, region_id: UUID) -> RegionalMaskEntry:
        """Remove one region and choose the nearest remaining selection."""

        index = self._index_of(region_id)
        entry = self.entries.pop(index)
        if self.selected_region_id == region_id:
            if self.entries:
                self.selected_region_id = self.entries[
                    min(index, len(self.entries) - 1)
                ].region_id
            else:
                self.selected_region_id = None
        return entry

    def entry(self, region_id: UUID) -> RegionalMaskEntry | None:
        """Return one region by stable identity."""

        return next(
            (entry for entry in self.entries if entry.region_id == region_id),
            None,
        )

    def entry_for_mask(self, mask_id: UUID) -> RegionalMaskEntry | None:
        """Return one region by materialized canvas layer identity."""

        return next((entry for entry in self.entries if entry.mask_id == mask_id), None)

    def _index_of(self, region_id: UUID) -> int:
        """Return one region index or reject a foreign identity."""

        for index, entry in enumerate(self.entries):
            if entry.region_id == region_id:
                return index
        raise KeyError(f"Unknown regional mask identity: {region_id}")


__all__ = ["RegionalMaskCollection", "RegionalMaskEntry"]
