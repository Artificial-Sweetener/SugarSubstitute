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

"""Own thumbnail-picker fixtures, native lifetime, and observable settling."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from tests.presentation.editor.node_card.builder_support import build_node_card_builder
from tests.support.node_behavior import build_behavior_snapshot, cube_state
from tests.support.qt.lifecycle import destroy_qt_object


_WidgetT = TypeVar("_WidgetT", bound=QWidget)


class ThumbnailNodeDefinitionGateway:
    """Return empty node-definition payloads for focused node-card tests."""

    @staticmethod
    def get_node_definition(node_class: str) -> dict[str, object]:
        """Return the required definition for the supplied node class."""

        return ThumbnailNodeDefinitionGateway.get_required_node_definition(node_class)

    @staticmethod
    def get_required_node_definition(_node_class: str) -> dict[str, object]:
        """Return an empty required node-definition payload."""

        return {}


class ThumbnailCardPanel(QWidget):
    """Provide the minimal panel surface consumed by the node-card builder."""

    inputMaskOpacityChanged = Signal(str, str, float)
    inputMaskOpacityCommitted = Signal(str, str, float, float)

    def __init__(self) -> None:
        """Initialize panel maps used by row registration and wiring."""

        super().__init__()
        self._stack_order = ["A"]
        self._cube_states: dict[str, object] = {}
        self._hidden_field_keys: set[object] = set()
        self.row_widgets: dict[object, tuple[QWidget, QWidget | None]] = {}
        self.col_widgets: dict[object, tuple[QWidget, QWidget, QWidget]] = {}
        self.prompt_link_widgets: dict[object, object] = {}

    @staticmethod
    def is_connection(_value: object) -> bool:
        """Report that the focused test inputs are always literals."""

        return False


@dataclass(frozen=True)
class ThumbnailCardScenario:
    """Expose one mounted thumbnail card and its registered field geometry."""

    host: QWidget
    panel: ThumbnailCardPanel
    wrapper: QWidget

    def picker(self, picker_type: type[_WidgetT]) -> _WidgetT:
        """Return the card's picker of the requested concrete type."""

        matches = self.wrapper.findChildren(picker_type)
        assert len(matches) == 1
        return matches[0]

    def field_geometry(self) -> tuple[QWidget, QWidget]:
        """Return the image field row and its animated card body."""

        row = self.panel.row_widgets[("A", "loader", "image")][1]
        assert row is not None
        content_surface = row.parentWidget()
        assert content_surface is not None
        content_body = content_surface.parentWidget()
        assert content_body is not None
        return row, content_body


class ThumbnailPickerOwner:
    """Own one test's QApplication access and independent widget roots."""

    def __init__(self, application: QApplication) -> None:
        """Retain the worker application and initialize native ownership."""

        self.application = application
        self._roots: list[QWidget] = []

    def own(self, widget: _WidgetT) -> _WidgetT:
        """Retain one independently constructed widget root."""

        self._roots.append(widget)
        return widget

    def build_card(self, *, class_type: str, image_path: str) -> ThumbnailCardScenario:
        """Build and mount one image or mask picker node card."""

        panel = self.own(ThumbnailCardPanel())
        definitions = {
            class_type: {
                "input": {"required": {"image": ["STRING", {}]}},
            }
        }
        cube = cube_state(
            nodes={
                "loader": {
                    "class_type": class_type,
                    "inputs": {"image": image_path},
                }
            },
            definitions=definitions,
        )
        panel._cube_states = {"A": cube}
        snapshot = build_behavior_snapshot(
            cube_states={"A": cube},
            stack_order=["A"],
            definitions_by_class=definitions,
        )
        wrapper = build_node_card_builder(
            panel,
            ThumbnailNodeDefinitionGateway(),
        ).build_node_card(
            node_name="loader",
            inputs={"image": image_path},
            node_type=class_type,
            field_specs=snapshot.field_specs_by_alias["A"]["loader"],
            cube_state=cube,
            resolved_behavior=snapshot.resolved_nodes_by_alias["A"]["loader"],
            alias="A",
        )
        assert wrapper is not None

        host = self.own(QWidget())
        layout = QVBoxLayout(host)
        layout.addWidget(wrapper)
        host.resize(700, 900)
        host.show()
        return ThumbnailCardScenario(host=host, panel=panel, wrapper=wrapper)

    def wait_until(
        self,
        predicate: Callable[[], bool],
        *,
        max_event_cycles: int = 24,
    ) -> None:
        """Advance Qt only until the requested observable state is reached."""

        for _ in range(max_event_cycles):
            if predicate():
                return
            self.application.processEvents()
        assert predicate(), "observable thumbnail-picker state did not settle"

    def destroy_all(self) -> None:
        """Destroy each independent widget root synchronously in reverse order."""

        for widget in reversed(self._roots):
            destroy_qt_object(widget)
        self._roots.clear()


def create_test_image(
    path: Path,
    *,
    width: int,
    height: int,
    color: str,
) -> None:
    """Write one solid-color PNG with the requested dimensions."""

    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    assert image.save(str(path)) is True


__all__ = [
    "ThumbnailCardScenario",
    "ThumbnailPickerOwner",
    "create_test_image",
]
