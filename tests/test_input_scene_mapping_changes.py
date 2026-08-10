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

"""Characterize durable scene-mapping change publication."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QTransform
from cutecanvas import LayerPolicy

from substitute.presentation.canvas.input.input_scene_mapping_changes import (
    InputSceneMappingChanges,
)
from substitute.presentation.canvas.input.input_document_change_observer import (
    InputDocumentChangeObserver,
)


@dataclass(frozen=True)
class _Layer:
    """Provide the public scene fields consumed by the monitor."""

    layer_id: UUID
    transform: QTransform
    interaction: LayerPolicy = LayerPolicy()


@dataclass(frozen=True)
class _Scene:
    """Provide one detached public-scene shape."""

    scene_id: UUID
    layers: tuple[_Layer, ...]


class _Canvas(QObject):
    """Publish deterministic scene snapshots through a Qt signal."""

    sceneChanged = Signal(object)

    def __init__(self, scene: _Scene) -> None:
        """Store the initial authoritative scene."""

        super().__init__()
        self.scene = scene

    def currentScene(self) -> _Scene:
        """Return the current detached scene."""

        return self.scene

    def publish(self, scene: _Scene) -> None:
        """Replace and emit one authoritative scene snapshot."""

        self.scene = scene
        self.sceneChanged.emit(scene)


def test_mapping_change_emits_but_policy_and_scene_activation_do_not() -> None:
    """Only a transform change within the same layer set is a mapping edit."""

    scene_id = uuid4()
    layer_id = uuid4()
    canvas = _Canvas(_Scene(scene_id, (_Layer(layer_id, QTransform()),)))
    monitor = InputSceneMappingChanges(canvas)
    changes: list[None] = []
    monitor.changed.connect(lambda: changes.append(None))
    invalidated: list[str] = []
    autosaves: list[None] = []
    observer = InputDocumentChangeObserver(
        changes=(monitor.changed,),
        active_workflow_id=lambda: "workflow-a",
        mark_workflow_changed=invalidated.append,
        request_autosave=lambda: autosaves.append(None),
    )

    canvas.publish(
        _Scene(
            scene_id,
            (_Layer(layer_id, QTransform(), LayerPolicy(selectable=True)),),
        )
    )
    translated = QTransform()
    translated.translate(4.0, 0.0)
    canvas.publish(_Scene(scene_id, (_Layer(layer_id, translated),)))
    canvas.publish(_Scene(uuid4(), (_Layer(uuid4(), QTransform()),)))

    assert changes == [None]
    assert observer is not None
    assert invalidated == ["workflow-a"]
    assert autosaves == [None]
