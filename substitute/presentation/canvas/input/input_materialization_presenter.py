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

"""Present Input materialization results to canvas and node-field views."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import cast
from uuid import UUID

from substitute.domain.common import MaskAssociationKey
from substitute.domain.workflow import WorkflowState
from substitute.presentation.canvas.input.input_node_preview_coordinator import (
    InputNodePreviewCoordinator,
)

type _MaskColorProvider = Callable[[int, int], object]
type _ScalarMaskRefresh = Callable[[str, str, Path | None], object]
type _OrderedMaskRefresh = Callable[[MaskAssociationKey], None]


class InputMaterializationPresenter:
    """Apply materialized mask color, activation, preview, and list state."""

    def __init__(
        self,
        *,
        input_document: object,
        active_workflow: Callable[[], WorkflowState | None],
        mask_color: _MaskColorProvider,
        refresh_scalar_mask: _ScalarMaskRefresh,
        refresh_ordered_mask: _OrderedMaskRefresh,
        activate_mask: Callable[[WorkflowState, UUID], bool],
        preview_coordinator: InputNodePreviewCoordinator | None = None,
    ) -> None:
        """Store focused canvas, workflow, panel, and preview boundaries."""

        self._input_document = input_document
        self._active_workflow = active_workflow
        self._mask_color = mask_color
        self._refresh_scalar_mask = refresh_scalar_mask
        self._refresh_ordered_mask = refresh_ordered_mask
        self._activate_mask = activate_mask
        self._preview_coordinator = preview_coordinator

    def apply(self, result: object, *, projects_dir: Path | None = None) -> None:
        """Apply one materialization result without assuming widget-local paths."""

        live_mask_previews = (
            frozenset()
            if self._preview_coordinator is None
            else self._preview_coordinator.bind_materialization(result)
        )
        raw_mask_results = getattr(result, "mask_results", ())
        mask_results = (
            tuple(raw_mask_results) if isinstance(raw_mask_results, Iterable) else ()
        )
        workflow = self._active_workflow()
        association_keys: set[MaskAssociationKey] = set()
        for index, mask_result in enumerate(mask_results):
            mask_id = getattr(mask_result, "mask_id", None)
            set_mask_properties = getattr(
                self._input_document,
                "set_mask_properties",
                None,
            )
            if callable(set_mask_properties) and isinstance(mask_id, UUID):
                set_mask_properties(
                    mask_id,
                    color=self._mask_color(index, len(mask_results)),
                )
            association_key = _association_key(
                getattr(mask_result, "association_key", None)
            )
            if association_key is None:
                continue
            association_keys.add(association_key)
            collection = None
            if workflow is not None:
                collection = workflow.canvas.regional_mask_collection(association_key)
            if collection is None and association_key not in live_mask_previews:
                self._refresh_scalar_mask(
                    association_key[0],
                    association_key[1],
                    projects_dir,
                )
        if workflow is not None:
            for association_key in association_keys:
                collection = workflow.canvas.regional_mask_collection(association_key)
                if collection is not None:
                    self._refresh_ordered_mask(association_key)
        first_mask_id = getattr(result, "first_mask_id", None)
        if isinstance(first_mask_id, UUID) and workflow is not None:
            self._activate_mask(workflow, first_mask_id)


def _association_key(value: object) -> MaskAssociationKey | None:
    """Return one concrete mask association tuple from a result payload."""

    if (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], str)
    ):
        return cast(MaskAssociationKey, value)
    return None


__all__ = ["InputMaterializationPresenter"]
