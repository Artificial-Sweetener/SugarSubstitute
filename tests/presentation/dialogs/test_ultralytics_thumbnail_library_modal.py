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

"""Render and exercise the full-window detector-thumbnail library modal."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtGui import QFont
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.model_metadata.ultralytics_visual_catalog import (
    BundledUltralyticsThumbnailChoice,
)
from substitute.infrastructure.model_thumbnails import (
    BundledUltralyticsThumbnailRepository,
)
from substitute.presentation.dialogs.full_window_modal import FullWindowModalBase
from substitute.presentation.dialogs.ultralytics_thumbnail_library_modal import (
    UltralyticsThumbnailLibraryModal,
)
from tests.presentation.widgets.model_picker.support import ensure_qapp
from tests.support.qt.semantic_wait import wait_for_qt_condition
from tests.support.qt.lifecycle import destroy_qt_object


def test_modal_uses_full_frame_layer_and_renders_complete_library(
    tmp_path: Path,
) -> None:
    """The production modal should render all packaged choices over its owner."""

    ensure_qapp()
    owner = QWidget()
    owner.resize(1200, 820)
    owner.show()
    modal = UltralyticsThumbnailLibraryModal(
        asset_repository=BundledUltralyticsThumbnailRepository(),
        model_display_name="Anzhcs ManFace v02 1024 y8n",
        current_asset_name="person-segmentation",
        parent=owner,
    )
    render_font = QFont("Arial", 10)
    modal.setFont(render_font)
    for widget in modal.findChildren(QWidget):
        widget.setFont(render_font)

    modal.show()
    wait_for_qt_condition(
        lambda: modal.graphicsEffect() is None,
        timeout_ms=1_000,
        description="detector thumbnail modal fade-in",
    )

    assert isinstance(modal, FullWindowModalBase)
    assert modal.modal_owner is owner
    assert modal.geometry() == owner.rect()
    assert len(modal.wall.items()) == 17
    assert (
        modal.title_label.text()
        == "Choose detector thumbnail for Anzhcs ManFace v02 1024 y8n"
    )
    subtitles = {item.subtitle for item in modal.wall.items()}
    assert subtitles == {"Bounding Box", "Segmentation"}
    assert "Detection" not in subtitles
    assert modal.wall.current_payload() is not None
    render_path = tmp_path / "ultralytics-thumbnail-library-modal.png"
    assert modal.widget.grab().save(str(render_path)) is True
    assert render_path.stat().st_size > 10_000

    first_choice = cast(
        BundledUltralyticsThumbnailChoice,
        modal.wall.items()[0].payload,
    )
    finished = QSignalSpy(modal.finished)
    modal.wall.itemActivated.emit(first_choice)
    assert finished.wait(500)
    QApplication.processEvents()
    assert modal.selected_asset_name == first_choice.asset_name
    assert modal.result() == modal.DialogCode.Accepted
    destroy_qt_object(owner)
