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

"""Bind materialized Input document subjects to live editor-node previews."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeGuard
from uuid import UUID

from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.panel.widgets.fields.load_image import ImagePicker
from substitute.presentation.editor.panel.widgets.fields.load_mask import MaskPicker

from .input_node_preview_widget import InputNodePreviewWidget
from .input_preview_binding import InputDocumentPreviewBindings, InputPreviewBinding


class InputNodePreviewCoordinator:
    """Own node identity lookup and live preview widget replacement."""

    def __init__(
        self,
        *,
        bindings: InputDocumentPreviewBindings,
        active_panel: Callable[[], QWidget | None],
    ) -> None:
        """Capture the document binding owner and active panel resolver."""
        self._bindings = bindings
        self._active_panel = active_panel

    def bind_materialization(self, result: object) -> frozenset[tuple[str, str]]:
        """Bind one result and return mask-node identities now backed by live views."""
        bound_masks: set[tuple[str, str]] = set()
        image_id = getattr(result, "image_id", None)
        section_key = getattr(result, "section_key", None)
        surface_key = getattr(result, "surface_key", None)
        if (
            isinstance(image_id, UUID)
            and isinstance(section_key, str)
            and isinstance(surface_key, str)
        ):
            binding = self._bindings.image(image_id)
            if binding is not None:
                self._bind_image(section_key, surface_key, binding)
        raw_masks = getattr(result, "mask_results", ())
        mask_results = tuple(raw_masks) if isinstance(raw_masks, Iterable) else ()
        for mask_result in mask_results:
            if self.bind_mask_result(mask_result):
                association_key = getattr(mask_result, "association_key", None)
                if _association_key(association_key):
                    bound_masks.add(association_key)
        return frozenset(bound_masks)

    def bind_mask_result(self, result: object) -> bool:
        """Bind one materialized mask result to its graph node picker."""
        image_id = getattr(result, "image_id", None)
        mask_id = getattr(result, "mask_id", None)
        association_key = getattr(result, "association_key", None)
        if (
            not isinstance(image_id, UUID)
            or not isinstance(mask_id, UUID)
            or not _association_key(association_key)
        ):
            return False
        binding = self._bindings.mask(image_id, mask_id)
        if binding is None:
            return False
        cube_alias, node_name = association_key
        return self._bind_mask(cube_alias, node_name, binding)

    def _bind_image(
        self,
        cube_alias: str,
        node_name: str,
        binding: InputPreviewBinding,
    ) -> bool:
        """Replace the matching Load Image thumbnail with a live document view."""
        panel = self._active_panel()
        if panel is None:
            return False
        for picker in panel.findChildren(ImagePicker):
            metadata = picker.property("input_metadata")
            if _matches(metadata, cube_alias, node_name):
                preview = InputNodePreviewWidget(binding, picker)
                preview.clicked.connect(picker.handle_thumbnail_click)
                picker.set_live_preview(preview)
                return True
        return False

    def _bind_mask(
        self,
        cube_alias: str,
        node_name: str,
        binding: InputPreviewBinding,
    ) -> bool:
        """Replace the matching Load Mask thumbnail with live grayscale coverage."""
        panel = self._active_panel()
        if panel is None:
            return False
        for picker in panel.findChildren(MaskPicker):
            metadata = picker.property("input_metadata")
            if _matches(metadata, cube_alias, node_name):
                preview = InputNodePreviewWidget(binding, picker)
                preview.clicked.connect(picker.handle_thumbnail_click)
                picker.set_live_preview(preview)
                return True
        return False

    def mask_preview_mounted(self, cube_alias: str, node_name: str) -> bool:
        """Return whether one mask picker already owns a live document viewport."""
        panel = self._active_panel()
        if panel is None:
            return False
        for picker in panel.findChildren(MaskPicker):
            if _matches(picker.property("input_metadata"), cube_alias, node_name):
                return isinstance(picker.live_preview(), InputNodePreviewWidget)
        return False


def _matches(metadata: object, cube_alias: str, node_name: str) -> bool:
    """Return whether picker metadata names one exact graph node."""
    return (
        isinstance(metadata, dict)
        and metadata.get("cube_alias") == cube_alias
        and metadata.get("node_name") == node_name
    )


def _association_key(value: object) -> TypeGuard[tuple[str, str]]:
    """Return whether a mask association contains two concrete strings."""
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], str)
    )


__all__ = ["InputNodePreviewCoordinator"]
