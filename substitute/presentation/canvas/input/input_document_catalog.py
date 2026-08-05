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

"""Own application identities mapped into one Input CuteCanvas document."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID


class InputMaskIdentity(Protocol):
    """Describe mask identity exposed by the CuteCanvas public facade."""

    @property
    def mask_id(self) -> UUID:
        """Return the public mask identity."""
        ...

    @property
    def layer_id(self) -> UUID | None:
        """Return the layer presenting the mask, when available."""
        ...


@dataclass(frozen=True, slots=True)
class InputDocumentImage:
    """Map one SugarSubstitute Input image identity to document content."""

    image_id: UUID
    composition_id: UUID
    path: Path | None
    payload_revision: int


class InputDocumentCatalog:
    """Resolve image, composition, and mask identities without presentation policy."""

    def __init__(
        self,
        masks_for_composition: Callable[
            [UUID],
            Iterable[InputMaskIdentity],
        ],
    ) -> None:
        """Bind the public mask lookup needed for cross-resource identities."""
        self._masks_for_composition = masks_for_composition
        self._images: dict[UUID, InputDocumentImage] = {}

    def record(
        self,
        image_id: UUID,
        composition_id: UUID,
        *,
        path: Path | None,
        payload_revision: int,
    ) -> None:
        """Install or replace one application-to-document identity record."""
        self._images[image_id] = InputDocumentImage(
            image_id,
            composition_id,
            path,
            payload_revision,
        )

    def record_for(self, image_id: UUID) -> InputDocumentImage | None:
        """Return one image record without changing catalog state."""
        return self._images.get(image_id)

    def remove(self, image_id: UUID) -> InputDocumentImage | None:
        """Remove and return one image record."""
        return self._images.pop(image_id, None)

    def contains(self, image_id: UUID) -> bool:
        """Return whether the catalog contains one image identity."""
        return image_id in self._images

    def image_path(self, image_id: UUID) -> Path | None:
        """Return the source path retained for one image."""
        record = self.record_for(image_id)
        return None if record is None else record.path

    def image_id_for_composition(self, composition_id: UUID) -> UUID | None:
        """Resolve one document composition back to its application image."""
        return next(
            (
                image_id
                for image_id, record in self._images.items()
                if record.composition_id == composition_id
            ),
            None,
        )

    def composition_for_image(self, image_id: UUID) -> UUID | None:
        """Return the document composition owned by one application image."""
        record = self.record_for(image_id)
        return None if record is None else record.composition_id

    def composition_for_mask(self, mask_id: UUID) -> UUID | None:
        """Return the unique Input composition containing one mask resource."""
        matches = tuple(
            record.composition_id
            for record in self._images.values()
            if self._mask(record.composition_id, mask_id) is not None
        )
        return matches[0] if len(matches) == 1 else None

    def mask_layer_for_image(
        self,
        image_id: UUID,
        mask_id: UUID,
    ) -> UUID | None:
        """Return a mask layer only when it belongs to the requested image."""
        composition_id = self.composition_for_image(image_id)
        if composition_id is None:
            return None
        mask = self._mask(composition_id, mask_id)
        return None if mask is None else mask.layer_id

    def contains_mask(self, image_id: UUID, mask_id: UUID) -> bool:
        """Return whether an exact mask identity belongs to one Input image."""
        composition_id = self.composition_for_image(image_id)
        return (
            composition_id is not None
            and self._mask(composition_id, mask_id) is not None
        )

    def contains_mask_resource(self, mask_id: UUID) -> bool:
        """Return whether any Input composition references one mask resource."""
        return any(
            self._mask(record.composition_id, mask_id) is not None
            for record in self._images.values()
        )

    def has_masks(self, image_id: UUID) -> bool:
        """Return whether one image composition currently contains masks."""
        composition_id = self.composition_for_image(image_id)
        return composition_id is not None and bool(
            tuple(self._masks_for_composition(composition_id))
        )

    def restore_compositions(self, composition_ids: tuple[UUID, ...]) -> None:
        """Restore identity records whose composition IDs are application IDs."""
        if self._images:
            raise RuntimeError("Input image identities must be empty before restore")
        for composition_id in composition_ids:
            self.record(
                composition_id,
                composition_id,
                path=None,
                payload_revision=0,
            )

    def _mask(
        self,
        composition_id: UUID,
        mask_id: UUID,
    ) -> InputMaskIdentity | None:
        """Return one mask descriptor from an explicitly named composition."""
        return next(
            (
                mask
                for mask in self._masks_for_composition(composition_id)
                if mask.mask_id == mask_id
            ),
            None,
        )


__all__ = ["InputDocumentCatalog", "InputDocumentImage"]
