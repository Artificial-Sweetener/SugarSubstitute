#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
"""Capture one coherent Input document revision for generation."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID

from cutecanvas import (
    CanvasContentReference,
    EmbeddedImageExportSnapshot,
    MaskExportSnapshot,
)


@dataclass(frozen=True, slots=True)
class InputGenerationCapture:
    """Carry detached image and mask products from one coherent document state."""

    images: Mapping[UUID, EmbeddedImageExportSnapshot]
    masks: Mapping[UUID, MaskExportSnapshot]

    def __post_init__(self) -> None:
        """Freeze product lookup maps against accidental request mutation."""
        object.__setattr__(self, "images", MappingProxyType(dict(self.images)))
        object.__setattr__(self, "masks", MappingProxyType(dict(self.masks)))


class InputDocumentGenerationCapture:
    """Retry a multi-resource capture until its composition revisions agree."""

    def __init__(
        self,
        *,
        composition_for_image: Callable[[UUID], UUID | None],
        composition_for_mask: Callable[[UUID], UUID | None],
        content_reference: Callable[[UUID], CanvasContentReference],
        capture_image: Callable[
            [UUID],
            EmbeddedImageExportSnapshot | None,
        ],
        capture_mask: Callable[[UUID, UUID], MaskExportSnapshot | None],
    ) -> None:
        """Bind stable identity, revision, and detached capture operations."""
        self._composition_for_image = composition_for_image
        self._composition_for_mask = composition_for_mask
        self._content_reference = content_reference
        self._capture_image = capture_image
        self._capture_mask = capture_mask

    def capture(
        self,
        *,
        image_ids: Iterable[UUID],
        mask_ids: Iterable[UUID],
    ) -> InputGenerationCapture | None:
        """Return products only when all addressed compositions stay unchanged."""
        ordered_images = tuple(dict.fromkeys(image_ids))
        ordered_masks = tuple(dict.fromkeys(mask_ids))
        compositions = self._resolve_compositions(ordered_images, ordered_masks)
        if compositions is None:
            return None
        for _attempt in range(3):
            before = self._references(compositions)
            if before is None:
                return None
            images = self._capture_images(ordered_images)
            masks = self._capture_masks(ordered_masks)
            after = self._references(compositions)
            if (
                images is not None
                and masks is not None
                and after is not None
                and before == after
            ):
                return InputGenerationCapture(images=images, masks=masks)
        return None

    def _resolve_compositions(
        self,
        image_ids: tuple[UUID, ...],
        mask_ids: tuple[UUID, ...],
    ) -> tuple[UUID, ...] | None:
        """Resolve every product identity to one retained composition."""
        resolved: list[UUID] = []
        for image_id in image_ids:
            composition_id = self._composition_for_image(image_id)
            if composition_id is None:
                return None
            resolved.append(composition_id)
        for mask_id in mask_ids:
            composition_id = self._composition_for_mask(mask_id)
            if composition_id is None:
                return None
            resolved.append(composition_id)
        return tuple(dict.fromkeys(resolved))

    def _references(
        self,
        composition_ids: tuple[UUID, ...],
    ) -> tuple[CanvasContentReference, ...] | None:
        """Capture current composition revisions without changing activation."""
        try:
            return tuple(
                self._content_reference(composition_id)
                for composition_id in composition_ids
            )
        except KeyError:
            return None

    def _capture_images(
        self,
        image_ids: tuple[UUID, ...],
    ) -> dict[UUID, EmbeddedImageExportSnapshot] | None:
        """Capture every exact embedded image resource."""
        captured: dict[UUID, EmbeddedImageExportSnapshot] = {}
        for image_id in image_ids:
            composition_id = self._composition_for_image(image_id)
            if composition_id is None:
                return None
            snapshot = self._capture_image(composition_id)
            if snapshot is None or snapshot.composition_id != composition_id:
                return None
            captured[image_id] = snapshot
        return captured

    def _capture_masks(
        self,
        mask_ids: tuple[UUID, ...],
    ) -> dict[UUID, MaskExportSnapshot] | None:
        """Capture every exact canvas-bounded mask resource."""
        captured: dict[UUID, MaskExportSnapshot] = {}
        for mask_id in mask_ids:
            composition_id = self._composition_for_mask(mask_id)
            if composition_id is None:
                return None
            snapshot = self._capture_mask(mask_id, composition_id)
            if (
                snapshot is None
                or snapshot.mask_id != mask_id
                or snapshot.composition_id != composition_id
            ):
                return None
            captured[mask_id] = snapshot
        return captured


__all__ = ["InputDocumentGenerationCapture", "InputGenerationCapture"]
