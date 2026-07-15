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

"""Store shared canvas image payloads and metadata by UUID."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from uuid import UUID

from substitute.domain.workflow import ImageMeta


@dataclass(slots=True)
class CanvasImageRecord:
    """Store one canvas image payload and projection metadata record."""

    payload: object | None
    metadata: ImageMeta


class CanvasImageRegistry:
    """Own canvas image records without workflow membership or display policy."""

    def __init__(self) -> None:
        """Initialize empty UUID-keyed image records."""

        self._records: dict[UUID, CanvasImageRecord] = {}

    def store(
        self,
        image_id: UUID,
        *,
        payload: object | None,
        metadata: ImageMeta,
    ) -> None:
        """Store or replace one image payload and metadata record."""

        self._records[image_id] = CanvasImageRecord(
            payload=payload,
            metadata=metadata,
        )

    def remember_payload(self, image_id: UUID, payload: object) -> bool:
        """Attach a payload to an existing metadata record."""

        record = self._records.get(image_id)
        if record is None:
            return False
        record.payload = payload
        return True

    def record_for(self, image_id: UUID) -> CanvasImageRecord | None:
        """Return the complete image record for image_id when present."""

        return self._records.get(image_id)

    def payload_for(self, image_id: UUID) -> object | None:
        """Return the registered image payload for image_id when present."""

        record = self._records.get(image_id)
        return None if record is None else record.payload

    def metadata_for(self, image_id: UUID) -> ImageMeta | None:
        """Return the registered image metadata for image_id when present."""

        record = self._records.get(image_id)
        return None if record is None else record.metadata

    def payloads_for(self, image_ids: Iterable[UUID]) -> dict[UUID, object]:
        """Return payloads for image_ids that have registered payloads."""

        payloads: dict[UUID, object] = {}
        for image_id in image_ids:
            payload = self.payload_for(image_id)
            if payload is not None:
                payloads[image_id] = payload
        return payloads

    def metadata_for_ids(self, image_ids: Iterable[UUID]) -> dict[UUID, ImageMeta]:
        """Return metadata for image_ids that have registered metadata."""

        metadata: dict[UUID, ImageMeta] = {}
        for image_id in image_ids:
            image_meta = self.metadata_for(image_id)
            if image_meta is not None:
                metadata[image_id] = image_meta
        return metadata

    def metadata_mapping(self) -> Mapping[UUID, ImageMeta]:
        """Return a read-only snapshot of UUID-keyed image metadata."""

        return self.metadata_for_ids(self._records)

    def payload_identity_for(self, image_id: UUID) -> int | None:
        """Return object identity for a registered payload."""

        payload = self.payload_for(image_id)
        return None if payload is None else id(payload)

    def payload_identities_for(
        self,
        image_ids: Iterable[UUID],
    ) -> tuple[tuple[UUID, int | None], ...]:
        """Return payload identities for image_ids in caller-defined order."""

        return tuple(
            (image_id, self.payload_identity_for(image_id)) for image_id in image_ids
        )

    def remove(self, image_id: UUID) -> bool:
        """Remove one image record and return whether it existed."""

        return self._records.pop(image_id, None) is not None

    def __contains__(self, image_id: object) -> bool:
        """Return whether the registry owns a record for image_id."""

        return image_id in self._records


__all__ = ["CanvasImageRecord", "CanvasImageRegistry"]
