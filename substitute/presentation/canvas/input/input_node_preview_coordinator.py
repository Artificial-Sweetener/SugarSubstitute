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

from substitute.domain.workflow import WorkflowState
from substitute.presentation.editor.panel.widgets.fields.load_image import ImagePicker
from substitute.presentation.editor.panel.widgets.fields.load_mask import MaskPicker
from substitute.presentation.editor.panel.widgets.fields.regional_mask_batch import (
    RegionalMaskBatchEditor,
)

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

    def bind_workflow(
        self,
        workflow: WorkflowState,
    ) -> frozenset[tuple[str, str]]:
        """Project restored active-workflow associations into the current panel."""
        panel = self._active_panel()
        if panel is None:
            return frozenset()
        canvas = workflow.canvas
        for image_picker in panel.findChildren(ImagePicker):
            identity = _metadata_identity(image_picker.property("input_metadata"))
            if identity is None:
                continue
            cube_alias, node_name = identity
            image_entry = canvas.image_entry(f"{cube_alias}:{node_name}")
            if image_entry is None:
                continue
            binding = self._bindings.image(image_entry.image_id)
            if binding is not None:
                self._bind_image(cube_alias, node_name, binding)
        bound_masks: set[tuple[str, str]] = set()
        for mask_picker in panel.findChildren(MaskPicker):
            identity = _metadata_identity(mask_picker.property("input_metadata"))
            if identity is None:
                continue
            mask_entry = canvas.mask_entry(identity)
            if mask_entry is None:
                continue
            binding = self._bindings.mask(
                mask_entry.image_id,
                mask_entry.mask_id,
            )
            if binding is not None and self._bind_mask(*identity, binding):
                bound_masks.add(identity)
        for editor in panel.findChildren(RegionalMaskBatchEditor):
            association_key = (editor.cube_alias, editor.node_name)
            if self.bind_regional_collection(workflow, association_key):
                bound_masks.add(association_key)
        return frozenset(bound_masks)

    def bind_regional_collection(
        self,
        workflow: WorkflowState,
        association_key: tuple[str, str],
    ) -> bool:
        """Bind every materialized ordered mask to its matching batch row."""

        panel = self._active_panel()
        if panel is None:
            return False
        collection = workflow.canvas.regional_mask_collection(association_key)
        if collection is None:
            return False
        editors = tuple(
            editor
            for editor in panel.findChildren(RegionalMaskBatchEditor)
            if (editor.cube_alias, editor.node_name) == association_key
        )
        if not editors:
            return False
        bound_any = False
        for index, entry in enumerate(collection.entries):
            if entry.mask_id is None:
                continue
            binding = self._bindings.mask(entry.image_id, entry.mask_id)
            if binding is None:
                continue
            for editor in editors:
                current = editor.live_preview(index)
                if (
                    isinstance(current, InputNodePreviewWidget)
                    and current.binding.identity == binding.identity
                ):
                    bound_any = True
                    continue
                preview = InputNodePreviewWidget(
                    binding,
                    editor,
                )
                if editor.set_live_preview(index, preview):
                    bound_any = True
                else:
                    preview.close()
                    preview.deleteLater()
        return bound_any

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
                current = picker.live_preview()
                if (
                    isinstance(current, InputNodePreviewWidget)
                    and current.binding.identity == binding.identity
                ):
                    return True
                preview = InputNodePreviewWidget(
                    binding,
                    picker,
                    preferred_width=picker.thumbnail_size,
                )
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
                current = picker.live_preview()
                if (
                    isinstance(current, InputNodePreviewWidget)
                    and current.binding.identity == binding.identity
                ):
                    return True
                preview = InputNodePreviewWidget(
                    binding,
                    picker,
                    preferred_width=picker.thumbnail_size,
                )
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


def _metadata_identity(metadata: object) -> tuple[str, str] | None:
    """Return one concrete cube/node identity from picker metadata."""
    if not isinstance(metadata, dict):
        return None
    cube_alias = metadata.get("cube_alias")
    node_name = metadata.get("node_name")
    if not isinstance(cube_alias, str) or not isinstance(node_name, str):
        return None
    return cube_alias, node_name


def _association_key(value: object) -> TypeGuard[tuple[str, str]]:
    """Return whether a mask association contains two concrete strings."""
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], str)
    )


__all__ = ["InputNodePreviewCoordinator"]
