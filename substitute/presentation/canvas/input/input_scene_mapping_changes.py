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

"""Publish durable Input layer-mapping edits without observing previews."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from PySide6.QtCore import QObject, Signal, SignalInstance


class SceneLayerPort(Protocol):
    """Describe stable identity and mapping from a public scene layer."""

    @property
    def layer_id(self) -> UUID:
        """Return the stable layer identity."""

    @property
    def transform(self) -> object:
        """Return the detached layer mapping."""


class SceneSnapshotPort(Protocol):
    """Describe the public scene fields used for mapping comparison."""

    @property
    def scene_id(self) -> UUID:
        """Return the stable scene identity."""

    @property
    def layers(self) -> Sequence[SceneLayerPort]:
        """Return the scene's ordered detached layers."""


class SceneCanvasPort(Protocol):
    """Describe public CuteCanvas scene observation."""

    sceneChanged: SignalInstance

    def currentScene(self) -> SceneSnapshotPort | None:
        """Return the active detached scene snapshot."""


LayerMappingSnapshot = tuple[tuple[UUID, object], ...]


class InputSceneMappingChanges(QObject):
    """Distinguish committed mapping edits from policy and activation changes."""

    changed = Signal()

    def __init__(
        self, canvas: SceneCanvasPort, *, parent: QObject | None = None
    ) -> None:
        """Capture the initial scene and observe authoritative scene publication."""

        super().__init__(parent)
        self._canvas = canvas
        self._scene_id: UUID | None = None
        self._layer_ids: tuple[UUID, ...] = ()
        self._mappings: LayerMappingSnapshot = ()
        self._capture_baseline()
        canvas.sceneChanged.connect(self._scene_changed)

    def _scene_changed(self, *_args: object) -> None:
        """Emit only when an existing active layer set changes its mapping."""

        scene = self._canvas.currentScene()
        if scene is None:
            self._scene_id = None
            self._layer_ids = ()
            self._mappings = ()
            return
        layer_ids = tuple(layer.layer_id for layer in scene.layers)
        mappings = self._mapping_snapshot(scene.layers)
        changed = (
            scene.scene_id == self._scene_id
            and layer_ids == self._layer_ids
            and mappings != self._mappings
        )
        self._scene_id = scene.scene_id
        self._layer_ids = layer_ids
        self._mappings = mappings
        if changed:
            self.changed.emit()

    def _capture_baseline(self) -> None:
        """Record current mappings without publishing an edit."""

        scene = self._canvas.currentScene()
        if scene is None:
            return
        self._scene_id = scene.scene_id
        self._layer_ids = tuple(layer.layer_id for layer in scene.layers)
        self._mappings = self._mapping_snapshot(scene.layers)

    @staticmethod
    def _mapping_snapshot(
        layers: Sequence[SceneLayerPort],
    ) -> LayerMappingSnapshot:
        """Detach comparable mapping values in stable layer order."""

        return tuple(
            (layer.layer_id, copy.deepcopy(layer.transform)) for layer in layers
        )


__all__ = ["InputSceneMappingChanges"]
