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

"""Bridge restored workspace image references into shell canvas state."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from PySide6.QtGui import QImage

from substitute.application.workflows import ImageMeta
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import (
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
)
from substitute.shared.logging.logger import get_logger, log_warning
from substitute.shared.startup_trace import trace_mark, trace_span

_LOGGER = get_logger("presentation.shell.workspace_restore_image_adapter")


class WorkspaceRestoreImageAdapter:
    """Own restored image loading and canvas-state replay for the shell."""

    def __init__(self, shell: Any) -> None:
        """Store the shell that supplies restore image services."""

        self._shell = shell

    def set_restore_asset_preload(self, preload: object | None) -> None:
        """Attach preloaded restore image bytes for GUI-thread decoding."""

        trace_mark(
            "main_window.set_restore_asset_preload",
            preload_attached=preload is not None,
            preload_type=type(preload).__name__ if preload is not None else "",
        )
        self._shell._restore_asset_preload = preload

    def load_restored_input_image(self, path: Path) -> object | None:
        """Load one input image payload for session materialization."""

        trace_mark(
            "main_window.load_restored_input_image.start",
            path_suffix=Path(path).suffix,
        )
        preloaded_image = self.load_preloaded_restore_image(path)
        if preloaded_image is not None:
            trace_mark(
                "main_window.load_restored_input_image.end",
                source="preload",
            )
            return preloaded_image
        with trace_span(
            "main_window.load_restored_input_image.fallback",
            path_suffix=Path(path).suffix,
        ):
            image = cast(
                object | None,
                self._shell.canvas_io_service.load_input_image(path),
            )
        trace_mark(
            "main_window.load_restored_input_image.end",
            source="canvas_io",
            loaded=image is not None,
        )
        return image

    def restore_input_image(
        self,
        reference: InputImageReference,
        image: object,
    ) -> None:
        """Restore one input image under its session snapshot UUID."""

        trace_mark(
            "main_window.restore_input_image",
            image_id=reference.image_id,
            path_suffix=reference.path.suffix,
        )
        self._shell.input_canvas_state_service.restore_input_image(
            image_id=self._uuid_from_restore_text(reference.image_id),
            image=image,
            path=reference.path,
        )

    def restore_input_mask(self, reference: InputMaskReference) -> bool:
        """Restore one input mask and remap its snapshot id to the live pane id."""

        if getattr(self._shell, "_shell_restore_lifecycle", "") == "prehydrating":
            self.defer_prehydrated_input_mask_restore(reference)
            return True

        snapshot_mask_id = self._uuid_from_restore_text(reference.mask_id)
        image_id = self._uuid_from_restore_text(reference.image_id)
        workflow_match = self.workflow_for_restored_input_mask(
            snapshot_mask_id=snapshot_mask_id,
            image_id=image_id,
            association_key=reference.association_key,
        )
        if workflow_match is None:
            trace_mark(
                "main_window.restore_input_mask.skip",
                mask_id=reference.mask_id,
                reason="workflow_not_found",
            )
            return False
        workflow_id, workflow = workflow_match
        live_mask_id = self._shell.input_canvas_state_service.restore_input_mask(
            workflow_id,
            workflow,
            snapshot_mask_id=snapshot_mask_id,
            image_id=image_id,
            path=reference.path,
            association_key=reference.association_key,
        )
        trace_mark(
            "main_window.restore_input_mask",
            snapshot_mask_id=reference.mask_id,
            live_mask_id=str(live_mask_id) if live_mask_id is not None else "",
            image_id=reference.image_id,
            path_suffix=reference.path.suffix,
            restored=live_mask_id is not None,
        )
        return live_mask_id is not None

    def defer_prehydrated_input_mask_restore(
        self,
        reference: InputMaskReference,
    ) -> None:
        """Queue a mask restore until hydrated workflow canvas state is installed."""

        deferred = getattr(self._shell, "_deferred_prehydrated_input_masks", None)
        if not isinstance(deferred, list):
            deferred = []
            self._shell._deferred_prehydrated_input_masks = deferred
        deferred.append(reference)
        trace_mark(
            "main_window.restore_input_mask.deferred",
            mask_id=reference.mask_id,
            image_id=reference.image_id,
            association_key=str(reference.association_key or ""),
            path_suffix=reference.path.suffix,
            deferred_count=len(deferred),
        )

    def restore_deferred_prehydrated_input_masks(self) -> None:
        """Replay prehydrated mask restores against installed workflow state."""

        references = tuple(
            getattr(self._shell, "_deferred_prehydrated_input_masks", ())
        )
        self._shell._deferred_prehydrated_input_masks = []
        if not references:
            trace_mark(
                "main_window.restore_deferred_prehydrated_input_masks.skip",
                reason="none",
            )
            return
        restored_count = 0
        for reference in references:
            if self.restore_input_mask(reference):
                restored_count += 1
                continue
            log_warning(
                _LOGGER,
                "Deferred prehydrated input mask restore failed",
                mask_id=reference.mask_id,
                image_id=reference.image_id,
                association_key=reference.association_key,
                path=reference.path,
            )
        trace_mark(
            "main_window.restore_deferred_prehydrated_input_masks",
            requested_count=len(references),
            restored_count=restored_count,
        )

    def workflow_for_restored_input_mask(
        self,
        *,
        snapshot_mask_id: UUID,
        image_id: UUID,
        association_key: tuple[str, str] | None,
    ) -> tuple[str, WorkflowState] | None:
        """Return the workflow that owns one restored input mask reference."""

        workflows = getattr(self._shell.workflow_session_service, "workflows", {})
        if not isinstance(workflows, Mapping):
            return None
        for workflow_id, workflow in workflows.items():
            if not isinstance(workflow, WorkflowState):
                continue
            canvas = workflow.canvas
            if association_key is not None:
                mapped_mask_id = canvas.mask_associations.get(association_key)
                if mapped_mask_id == snapshot_mask_id:
                    return str(workflow_id), workflow
            if canvas.mask_to_image_map.get(snapshot_mask_id) == image_id:
                return str(workflow_id), workflow
            if image_id in canvas.input_key_map.values():
                return str(workflow_id), workflow
        return None

    def load_restored_output_image(self, path: Path) -> object | None:
        """Load one output image payload for session materialization."""

        trace_mark(
            "main_window.load_restored_output_image.start",
            path_suffix=Path(path).suffix,
        )
        preloaded_image = self.load_preloaded_restore_image(path)
        if preloaded_image is not None:
            trace_mark(
                "main_window.load_restored_output_image.end",
                source="preload",
            )
            return preloaded_image
        with trace_span(
            "main_window.load_restored_output_image.fallback",
            path_suffix=Path(path).suffix,
        ):
            image = cast(
                object | None,
                self._shell.canvas_io_service.load_output_image(path),
            )
        trace_mark(
            "main_window.load_restored_output_image.end",
            source="canvas_io",
            loaded=image is not None,
        )
        return image

    def load_preloaded_restore_image(self, path: Path) -> QImage | None:
        """Decode preloaded restore bytes into a detached QImage on the GUI thread."""

        preload = getattr(self._shell, "_restore_asset_preload", None)
        image_bytes = getattr(preload, "image_bytes", None)
        if not callable(image_bytes):
            trace_mark(
                "main_window.restore_image_preload_lookup.skip",
                reason="no_preload",
                path_suffix=Path(path).suffix,
            )
            return None
        payload = image_bytes(path)
        if not isinstance(payload, bytes):
            trace_mark(
                "main_window.restore_image_preload_lookup.miss",
                path_suffix=Path(path).suffix,
            )
            return None
        trace_mark(
            "main_window.restore_image_preload_lookup.hit",
            path_suffix=Path(path).suffix,
            byte_count=len(payload),
        )
        with trace_span(
            "main_window.restore_image_preload_decode",
            path_suffix=Path(path).suffix,
            byte_count=len(payload),
        ):
            image = QImage.fromData(payload)
        if image.isNull():
            log_warning(
                _LOGGER,
                "Skipped preloaded restore image because decode returned null",
                path=path,
            )
            return None
        return image

    def restore_output_image(
        self,
        workflow_id: str,
        reference: OutputImageReference,
        image: object,
        image_meta: ImageMeta,
    ) -> None:
        """Restore one output image under its session snapshot UUID."""

        trace_mark(
            "main_window.restore_output_image",
            image_id=reference.image_id,
            path_suffix=reference.path.suffix,
        )
        image_id = self._uuid_from_restore_text(reference.image_id)
        self._shell.output_canvas_state_service.restore_output_image(
            workflow_id=workflow_id,
            image_id=image_id,
            image=image,
            image_meta=image_meta,
        )

    @staticmethod
    def _uuid_from_restore_text(value: str) -> UUID:
        """Parse snapshot UUID text for canvas restore APIs."""

        return UUID(value)


def workspace_restore_image_adapter_for(shell: Any) -> WorkspaceRestoreImageAdapter:
    """Return the composed restore image adapter for a shell."""

    adapter = getattr(shell, "workspace_restore_image_adapter", None)
    if isinstance(adapter, WorkspaceRestoreImageAdapter):
        return adapter
    adapter = WorkspaceRestoreImageAdapter(shell)
    setattr(shell, "workspace_restore_image_adapter", adapter)
    return adapter


__all__ = [
    "WorkspaceRestoreImageAdapter",
    "workspace_restore_image_adapter_for",
]
