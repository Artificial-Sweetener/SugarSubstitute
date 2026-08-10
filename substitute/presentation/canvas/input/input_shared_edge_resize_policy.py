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

"""Own temporary Input mask-layer policy for shared-edge resize mode."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from PySide6.QtCore import QObject
from cutecanvas import CuteCanvas, LayerPolicy


class InputSharedEdgeResizePolicy(QObject):
    """Enable every current mask participant and restore host policy exactly."""

    def __init__(self, canvas: CuteCanvas, *, parent: QObject) -> None:
        """Observe public mode and scene transitions from one Input canvas."""

        super().__init__(parent)
        self._canvas = canvas
        self._original_policies: dict[tuple[UUID, UUID], LayerPolicy] = {}
        self._active = self._is_active_mode(canvas.getControlMode())
        self._reconciling = False
        self._closed = False
        canvas.controlModeChanged.connect(self._control_mode_changed)
        canvas.compositionSelectionChanged.connect(self.reconcile)
        canvas.compositionChanged.connect(self.reconcile)
        canvas.sceneChanged.connect(self.reconcile)
        if self._active:
            self.reconcile()

    def reconcile(self, *_args: object) -> None:
        """Apply temporary movement only to mask layers in the active scene."""

        if self._closed or self._reconciling:
            return
        self._reconciling = True
        try:
            if not self._active:
                self._restore_policies()
                return
            scene = self._canvas.currentScene()
            if scene is None:
                return
            mask_layer_ids = {
                mask.layer_id
                for mask in self._canvas.listMasksForComposition()
                if mask.layer_id is not None
            }
            for layer in scene.layers:
                if layer.layer_id not in mask_layer_ids:
                    continue
                enabled = replace(
                    layer.interaction,
                    selectable=True,
                    movable=True,
                )
                if enabled != layer.interaction:
                    identity = (scene.scene_id, layer.layer_id)
                    self._original_policies.setdefault(identity, layer.interaction)
                    self._canvas.setLayerInteractionPolicy(
                        scene.scene_id,
                        layer.layer_id,
                        enabled,
                    )
        finally:
            self._reconciling = False

    def close(self, *_args: object) -> None:
        """Restore active-scene policies and reject later signal delivery."""

        if self._closed:
            return
        self._active = False
        self._restore_policies()
        self._closed = True

    def _control_mode_changed(self, mode: str) -> None:
        """Reconcile when entering or leaving shared-edge resize mode."""

        active = self._is_active_mode(mode)
        if active == self._active:
            return
        self._active = active
        self.reconcile()

    def _restore_policies(self) -> None:
        """Restore captured policies for the active public scene."""

        scene = self._canvas.currentScene()
        if scene is None:
            return
        current_layer_ids = {layer.layer_id for layer in scene.layers}
        restored: list[tuple[UUID, UUID]] = []
        for (scene_id, layer_id), policy in self._original_policies.items():
            if scene_id != scene.scene_id or layer_id not in current_layer_ids:
                continue
            self._canvas.setLayerInteractionPolicy(scene_id, layer_id, policy)
            restored.append((scene_id, layer_id))
        for identity in restored:
            self._original_policies.pop(identity, None)

    @staticmethod
    def _is_active_mode(mode: str) -> bool:
        """Return whether the native operation requires shared mask mobility."""

        return mode == CuteCanvas.CONTROL_MODE_SHARED_EDGE_RESIZE


__all__ = ["InputSharedEdgeResizePolicy"]
