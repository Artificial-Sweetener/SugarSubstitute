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

"""Serial Qt regressions for thumbnail-picker relayout inside collapsible node cards."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from substitute.presentation.editor.panel.widgets.fields.load_image import ImagePicker
from substitute.presentation.editor.panel.widgets.fields.load_mask import MaskPicker
from tests.node_card_builder_test_helpers import build_node_card_builder
from tests.node_behavior_test_helpers import build_behavior_snapshot, cube_state

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real thumbnail-picker relayout tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


class _Gateway:
    """Return empty node-definition payloads for focused node-card tests."""

    @staticmethod
    def get_node_definition(_node_class: str) -> dict[str, object]:
        """Return an empty node-definition payload."""

        return _Gateway.get_required_node_definition(_node_class)

    @staticmethod
    def get_required_node_definition(_node_class: str) -> dict[str, object]:
        """Return an empty required node-definition payload."""

        return {}


class _Panel(QWidget):
    """Provide the minimal panel surface consumed by NodeCardBuilder."""

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


def ensure_qapp() -> QApplication:
    """Return a running Qt application for real thumbnail-picker tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def process_events(app: QApplication, cycles: int = 6) -> None:
    """Flush a few event-loop turns so deferred relayout work settles."""

    for _ in range(cycles):
        app.processEvents()


def create_test_image(path: Path, *, width: int, height: int, color: str) -> None:
    """Write one solid-color PNG with the requested dimensions."""

    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    saved = image.save(str(path))
    assert saved is True


def build_thumbnail_card(
    *,
    class_type: str,
    image_path: str,
) -> tuple[QWidget, _Panel, QWidget]:
    """Build one collapsible image/mask node card and return its wrapper and row."""

    panel = _Panel()
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
    resolved = snapshot.resolved_nodes_by_alias["A"]["loader"]
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )
    wrapper = builder.build_node_card(
        node_name="loader",
        inputs={"image": image_path},
        node_type=class_type,
        field_specs=snapshot.field_specs_by_alias["A"]["loader"],
        cube_state=cube,
        resolved_behavior=resolved,
        alias="A",
    )
    assert wrapper is not None

    host = QWidget()
    layout = QVBoxLayout(host)
    layout.addWidget(wrapper)
    host.resize(700, 900)
    host.show()
    return host, panel, wrapper


def test_image_picker_card_body_relayouts_after_thumbnail_height_change() -> None:
    """LoadImage card bodies should expand after the selected image becomes taller."""

    app = ensure_qapp()
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        wide_path = temp_path / "wide.png"
        tall_path = temp_path / "tall.png"
        create_test_image(wide_path, width=400, height=100, color="red")
        create_test_image(tall_path, width=400, height=600, color="blue")
        host, panel, wrapper = build_thumbnail_card(
            class_type="LoadImage",
            image_path=str(wide_path),
        )
        try:
            process_events(app)
            picker = next(
                (
                    cast(ImagePicker, child)
                    for child in wrapper.findChildren(QWidget)
                    if isinstance(child, ImagePicker)
                ),
                None,
            )
            assert picker is not None
            row = panel.row_widgets[("A", "loader", "image")][1]
            assert row is not None
            content_surface = row.parentWidget()
            assert content_surface is not None
            content_body = content_surface.parentWidget()
            assert content_body is not None
            initial_row_hint = row.sizeHint().height()

            picker.set_thumbnail(str(tall_path))
            process_events(app)

            assert row.sizeHint().height() > initial_row_hint
            assert content_body.maximumHeight() >= row.sizeHint().height()
        finally:
            host.close()
            host.deleteLater()
            wrapper.close()
            wrapper.deleteLater()
            panel.close()
            panel.deleteLater()
            process_events(app)


def test_mask_picker_card_body_relayouts_after_thumbnail_height_change() -> None:
    """LoadImageMask card bodies should expand after the selected mask becomes taller."""

    app = ensure_qapp()
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        wide_path = temp_path / "wide.png"
        tall_path = temp_path / "tall.png"
        create_test_image(wide_path, width=400, height=100, color="green")
        create_test_image(tall_path, width=400, height=600, color="yellow")
        host, panel, wrapper = build_thumbnail_card(
            class_type="LoadImageMask",
            image_path=str(wide_path),
        )
        try:
            process_events(app)
            picker = next(
                (
                    cast(MaskPicker, child)
                    for child in wrapper.findChildren(QWidget)
                    if isinstance(child, MaskPicker)
                ),
                None,
            )
            assert picker is not None
            row = panel.row_widgets[("A", "loader", "image")][1]
            assert row is not None
            content_surface = row.parentWidget()
            assert content_surface is not None
            content_body = content_surface.parentWidget()
            assert content_body is not None
            initial_row_hint = row.sizeHint().height()

            picker.set_mask_path(str(tall_path))
            process_events(app)

            assert row.sizeHint().height() > initial_row_hint
            assert content_body.maximumHeight() >= row.sizeHint().height()
        finally:
            host.close()
            host.deleteLater()
            wrapper.close()
            wrapper.deleteLater()
            panel.close()
            panel.deleteLater()
            process_events(app)


def test_mask_picker_refresh_mask_path_reads_updated_same_file_bytes() -> None:
    """Autosave thumbnail refresh should not reuse stale same-path image data."""

    ensure_qapp()
    with tempfile.TemporaryDirectory() as temp_dir:
        mask_path = Path(temp_dir) / "mask.png"
        create_test_image(mask_path, width=4, height=4, color="red")
        first = MaskPicker._load_mask_pixmap_from_file_bytes(str(mask_path))

        create_test_image(mask_path, width=4, height=4, color="blue")
        second = MaskPicker._load_mask_pixmap_from_file_bytes(str(mask_path))

    assert first.toImage().pixelColor(0, 0) == QColor("red")
    assert second.toImage().pixelColor(0, 0) == QColor("blue")
