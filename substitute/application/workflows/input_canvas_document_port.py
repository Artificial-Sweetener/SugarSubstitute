#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Define the application boundary for the Input document presentation adapter."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Protocol
from uuid import UUID


class CanvasDocumentMutation(Enum):
    """Describe how one image admission changed a CuteCanvas document."""

    ADDED = "added"
    REPLACED = "replaced"
    UNCHANGED = "unchanged"


class InputCanvasDocumentPort(Protocol):
    """Expose Input CuteCanvas document content operations to workflow services."""

    def ensure_image_cached(
        self, image_id: UUID, image: object, path: Path | None
    ) -> CanvasDocumentMutation:
        """Admit or update one application image without changing its route."""

    def image_path(self, image_id: UUID) -> Path | None:
        """Return the exact application source path for one image."""

    def remove_unreferenced_image(self, image_id: UUID) -> bool:
        """Retire an image after application reference accounting proves it unused."""

    def create_blank_mask(self, image_id: UUID, size: object) -> UUID | None:
        """Create one new mask for an explicitly named input image."""

    def load_mask_from_file(self, image_id: UUID, path: Path) -> UUID | None:
        """Load one new mask for an explicitly named input image."""

    def replace_mask_from_file(self, mask_id: UUID, path: Path) -> bool:
        """Replace pixels of one existing mask without changing its identity."""

    def remove_mask_from_image(self, image_id: UUID, mask_id: UUID) -> bool:
        """Remove one mask association from an explicitly named input image."""


__all__ = ["CanvasDocumentMutation", "InputCanvasDocumentPort"]
