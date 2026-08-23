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

"""Characterize canvas projection input-document adapter contracts."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any


class _FakeInputDocument:
    """Exercise application-owned Input identity routes without a renderer."""

    def __init__(self) -> None:
        """Initialize mutable document-facing test state."""

        self.images: dict[uuid.UUID, tuple[object, Path | None]] = {}
        self.add_calls: list[tuple[uuid.UUID, object, Path | None]] = []
        self.selection_calls: list[uuid.UUID | None] = []
        self.current_id: uuid.UUID | None = None
        self.active_mask: uuid.UUID | None = None
        self.next_loaded_mask_id: uuid.UUID | None = None
        self.next_blank_mask_id = uuid.uuid4()
        self.removed_masks: list[tuple[uuid.UUID, uuid.UUID]] = []
        self.updated_masks: list[tuple[uuid.UUID, Path]] = []
        self.archived_masks: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.mask_opacity_calls: list[tuple[uuid.UUID | None, uuid.UUID, float]] = []

    def ensure_image_cached(
        self,
        image_id: uuid.UUID,
        image: object,
        path: Path | None,
    ) -> Any:
        """Cache one image under its application UUID."""

        from substitute.application.workflows.input_canvas_document_port import (  # noqa: PLC0415
            CanvasDocumentMutation,
        )

        existing = self.images.get(image_id)
        if existing == (image, path):
            return CanvasDocumentMutation.UNCHANGED
        mutation = (
            CanvasDocumentMutation.REPLACED
            if existing is not None
            else CanvasDocumentMutation.ADDED
        )
        self.images[image_id] = (image, path)
        self.add_calls.append((image_id, image, path))
        return mutation

    def image_path(self, image_id: uuid.UUID) -> Path | None:
        """Return cached source path."""

        payload = self.images.get(image_id)
        return None if payload is None else payload[1]

    def remove_unreferenced_image(self, image_id: uuid.UUID) -> bool:
        """Remove a cached test image."""

        return self.images.pop(image_id, None) is not None

    def set_current_image_id(self, image_id: uuid.UUID | None) -> bool:
        """Record route projection."""

        self.selection_calls.append(image_id)
        self.current_id = image_id
        return True

    def current_image_id(self) -> uuid.UUID | None:
        """Return the visible test identity."""

        return self.current_id

    def set_active_mask_id(self, mask_id: uuid.UUID | None) -> bool:
        """Record mask activation."""

        self.active_mask = mask_id
        return True

    def create_blank_mask(self, _image_id: uuid.UUID, _size: object) -> uuid.UUID:
        """Return the configured new mask identity."""

        return self.next_blank_mask_id

    def load_mask_from_file(
        self,
        _image_id: uuid.UUID,
        _path: Path,
    ) -> uuid.UUID | None:
        """Return the configured restored mask identity."""

        return self.next_loaded_mask_id

    def replace_mask_from_file(self, mask_id: uuid.UUID, path: Path) -> bool:
        """Record an identity-preserving mask replacement."""

        self.updated_masks.append((mask_id, path))
        return True

    def contains_mask(self, image_id: uuid.UUID, mask_id: uuid.UUID) -> bool:
        """Return whether complete document restore already installed a mask."""

        return (image_id, mask_id) in self.archived_masks

    def set_mask_visual_opacity(self, mask_id: uuid.UUID, opacity: float) -> bool:
        """Accept opacity only for a mask in the currently routed composition."""

        self.mask_opacity_calls.append((self.current_id, mask_id, opacity))
        return (self.current_id, mask_id) in self.archived_masks

    def remove_mask_from_image(self, image_id: uuid.UUID, mask_id: uuid.UUID) -> bool:
        """Record mask retirement."""

        self.removed_masks.append((image_id, mask_id))
        return True
