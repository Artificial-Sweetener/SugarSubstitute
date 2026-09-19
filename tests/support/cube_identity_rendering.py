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

"""Render production cube identity surfaces without showing native windows."""

from __future__ import annotations

from pathlib import Path
import os
import sys
from typing import cast

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from substitute.presentation.editor.panel.widgets.cube_title_label import (
    CubeTitleLabel,
)
from substitute.presentation.workflows.cube_stack_view import CubeStack

_WASH = QColor(251, 251, 251)


def render_cube_identity_screenshots(output_directory: Path) -> tuple[Path, Path]:
    """Save stack and editor identity screenshots from offscreen widgets."""

    application = cast(QApplication | None, QApplication.instance())
    if application is None:
        application = QApplication(sys.argv[:1])
    application.setFont(QFont(_load_headless_font(), 10))
    output_directory.mkdir(parents=True, exist_ok=True)
    stack_path = output_directory / "cube-model-pill-stack.png"
    editor_path = output_directory / "cube-model-pill-editor-alias.png"
    stack_root = _build_stack_gallery()
    editor_root = _build_editor_gallery()
    _render_widget(stack_root, stack_path)
    _render_widget(editor_root, editor_path)
    stack_root.deleteLater()
    editor_root.deleteLater()
    application.processEvents()
    return stack_path, editor_path


def _build_stack_gallery() -> QWidget:
    """Build an offscreen gallery containing the production cube stack."""

    root = _gallery_root(QSize(560, 260))
    layout = QVBoxLayout(root)
    layout.setContentsMargins(26, 22, 26, 22)
    layout.setSpacing(12)
    layout.addWidget(_caption("Cube stack — canonical name and model pill"))
    stack = CubeStack(root)
    stack.setFixedHeight(174)
    icon = _cube_icon()
    stack.insertTab(0, routeKey="SDXL/Text to Image", text="Text to Image", icon=icon)
    stack.setTabPresentation(
        0,
        primary_text="Text to Image",
        secondary_text="v1.1.1 · base-cubes",
        tooltip_text="Text to Image",
    )
    stack.tabItem(0).setTargetModel("Anima")
    stack.insertTab(1, routeKey="Hero Background", text="Hero Background", icon=icon)
    stack.setTabPresentation(
        1,
        primary_text="Hero Background",
        secondary_text="v1.1.1 · base-cubes",
        tooltip_text="Hero Background",
    )
    stack.tabItem(1).setTargetModel("Anima")
    stack.setCurrentIndex(1)
    row = QHBoxLayout()
    row.addWidget(cast(QWidget, stack), 0, Qt.AlignmentFlag.AlignLeft)
    row.addStretch(1)
    layout.addLayout(row)
    return root


def _build_editor_gallery() -> QWidget:
    """Build editor headers demonstrating default and renamed aliases."""

    root = _gallery_root(QSize(760, 252))
    layout = QVBoxLayout(root)
    layout.setContentsMargins(26, 22, 26, 22)
    layout.setSpacing(12)
    layout.addWidget(_caption("Editor panel — identity persists after alias rename"))
    layout.addWidget(_editor_section("Text to Image", "Default cube name"))
    layout.addWidget(_editor_section("Hero Background", "User alias"))
    return root


def _editor_section(title: str, note: str) -> QWidget:
    """Return one editor-like section using the production identity title widget."""

    section = QFrame()
    section.setStyleSheet(
        "QFrame { background: rgba(255, 255, 255, 178); border: 1px solid "
        "rgba(0, 0, 0, 22); border-radius: 7px; }"
    )
    row = QHBoxLayout(section)
    row.setContentsMargins(14, 8, 14, 8)
    row.setSpacing(12)
    title_label = CubeTitleLabel(title, section)
    title_label.setTargetModel("Anima")
    row.addWidget(title_label, 1)
    note_label = QLabel(note, section)
    note_label.setStyleSheet("color: rgb(105, 105, 105); border: none;")
    row.addWidget(note_label)
    return section


def _gallery_root(size: QSize) -> QWidget:
    """Return a fixed gray-wash surface for deterministic compositing."""

    root = QWidget()
    root.setFixedSize(size)
    root.setStyleSheet(
        "background: rgb(251, 251, 251); color: rgb(30, 30, 30); "
        f"font-family: {_load_headless_font()};"
    )
    return root


def _load_headless_font() -> str:
    """Load an explicitly supplied font when the offscreen plugin exposes none."""

    font_path = os.environ.get("SUGARSUBSTITUTE_HEADLESS_FONT", "")
    if font_path:
        font_id = QFontDatabase.addApplicationFont(font_path)
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            return families[0]
    families = QFontDatabase.families()
    return families[0] if families else "Sans Serif"


def _caption(text: str) -> QLabel:
    """Return a restrained gallery caption."""

    label = QLabel(text)
    font = label.font()
    font.setPointSize(11)
    font.setBold(True)
    label.setFont(font)
    return label


def _cube_icon() -> QIcon:
    """Return a high-contrast synthetic cube icon for overlap inspection."""

    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(213, 73, 103))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(255, 255, 255, 225), 4))
    painter.drawPolygon([QPoint(32, 8), QPoint(53, 20), QPoint(32, 32), QPoint(11, 20)])
    painter.drawLine(11, 20, 11, 44)
    painter.drawLine(53, 20, 53, 44)
    painter.drawLine(11, 44, 32, 56)
    painter.drawLine(53, 44, 32, 56)
    painter.drawLine(32, 32, 32, 56)
    painter.end()
    return QIcon(pixmap)


def _render_widget(widget: QWidget, path: Path) -> None:
    """Render a polished widget hierarchy directly into an image file."""

    widget.ensurePolished()
    layout = widget.layout()
    if layout is not None:
        layout.activate()
    image = QImage(widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(_WASH)
    painter = QPainter(image)
    widget.render(painter, QPoint(0, 0), QRect(), QWidget.RenderFlag.DrawChildren)
    painter.end()
    if not image.save(str(path)):
        raise RuntimeError(f"Failed to save headless cube identity screenshot: {path}")


if __name__ == "__main__":
    render_cube_identity_screenshots(Path("build/visual-verification"))
