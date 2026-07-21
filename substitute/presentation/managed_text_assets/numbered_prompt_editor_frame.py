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

"""Wrap the prompt editor with line-numbered managed text asset chrome."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget
from qfluentwidgets import isDarkTheme, themeColor  # type: ignore[import-untyped]

from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptWheelAdjustmentMode,
)
from substitute.application.prompt_editor.prompt_document_semantics import (
    PromptDocumentSemantics,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.runtime_services import (
    PromptEditorRuntimeServices,
)
from substitute.presentation.widgets.wheel_intent_controller import (
    WheelIntentController,
)

_GUTTER_LEFT_PADDING = 4
_NUMBER_RIGHT_PADDING = 2
_GUTTER_OVERLAP = 4
_BORDER_RADIUS = 5.0


class _LineNumberGutter(QWidget):
    """Paint source logical line numbers beside a prompt editor."""

    def __init__(self, frame: "NumberedPromptEditorFrame") -> None:
        """Store the owning frame used as the line geometry source."""

        super().__init__(frame.editor())
        self._frame = frame
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def sizeHint(self) -> QSize:  # noqa: N802
        """Return the current line-number gutter width."""

        return QSize(self._frame.gutter_paint_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint the gutter background, separator, and visible line numbers."""

        self._frame.paint_gutter(event)


class NumberedPromptEditorFrame(QWidget):
    """Compose a prompt editor with Hunters-style line numbers and zebra rows."""

    textChanged = Signal()

    def __init__(
        self,
        *,
        prompt_runtime_services: PromptEditorRuntimeServices,
        prompt_feature_profile: PromptEditorFeatureProfile,
        prompt_document_semantics: PromptDocumentSemantics | None = None,
        wheel_adjustment_mode: PromptWheelAdjustmentMode = (
            PromptWheelAdjustmentMode.HOVER_DWELL
        ),
        parent: QWidget | None = None,
    ) -> None:
        """Create the line-number frame and prompt-aware editor."""

        super().__init__(parent)
        self._editor = PromptEditor(
            self,
            prompt_autocomplete_gateway=prompt_runtime_services.autocomplete_gateway,
            prompt_wildcard_catalog_gateway=(
                prompt_runtime_services.wildcard_catalog_gateway
            ),
            prompt_feature_profile=prompt_feature_profile,
            prompt_document_semantics=prompt_document_semantics,
            danbooru_url_import_service=(
                prompt_runtime_services.danbooru_url_import_service
            ),
            danbooru_wiki_service=prompt_runtime_services.danbooru_wiki_service,
            danbooru_image_preview_service=(
                prompt_runtime_services.danbooru_image_preview_service
            ),
            danbooru_recent_posts_service=(
                prompt_runtime_services.danbooru_recent_posts_service
            ),
            prompt_lora_catalog_service=prompt_runtime_services.lora_catalog_service,
            thumbnail_asset_repository=(
                prompt_runtime_services.thumbnail_asset_repository
            ),
            prompt_scheduled_lora_service=(
                prompt_runtime_services.scheduled_lora_service_or_default()
            ),
            prompt_spellcheck_service=prompt_runtime_services.spellcheck_service,
            prompt_segment_preset_source=(
                prompt_runtime_services.segment_preset_source
            ),
            open_url=prompt_runtime_services.open_url,
            model_metadata_action_handler=(
                prompt_runtime_services.model_metadata_action_handler
            ),
            prompt_task_executor_factory=(
                prompt_runtime_services.prompt_task_executor_factory
            ),
            danbooru_lookup_dispatcher_factory=(
                prompt_runtime_services.danbooru_lookup_dispatcher_factory
            ),
            maximum_visible_lines=None,
        )
        self._editor.set_source_line_chrome_enabled(True)
        self._editor.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._wheel_intent_controller = WheelIntentController(
            self,
            wheel_adjustment_mode=wheel_adjustment_mode,
        )
        self._wheel_intent_controller.configure_widget(self._editor)
        self._gutter = _LineNumberGutter(self)
        self._gutter.setFixedWidth(self.gutter_paint_width())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._editor, 1)

        self._editor.textChanged.connect(self._handle_editor_text_changed)
        self._editor.cursorPositionChanged.connect(self._gutter.update)
        self._editor.resized.connect(self._sync_gutter_geometry)
        self._editor.verticalScrollBar().valueChanged.connect(self._gutter.update)
        self.setMinimumHeight(max(180, self._editor.minimumEditorHeight() * 6))
        self._sync_gutter_width()
        self._sync_gutter_geometry()
        self._gutter.raise_()

    def editor(self) -> PromptEditor:
        """Return the wrapped prompt editor."""

        return self._editor

    def setPlainText(self, text: str) -> None:  # noqa: N802
        """Replace the wrapped prompt editor source text."""

        self._editor.setSourceText(text)
        self._sync_gutter_width()

    def replaceBaselineText(self, text: str) -> None:  # noqa: N802
        """Replace wrapped prompt text and make it the editor undo baseline."""

        self._editor.replaceBaselineText(text)
        self._sync_gutter_width()

    def replaceBaselineSourceText(self, text: str) -> None:  # noqa: N802
        """Replace wrapped exact source text and make it the editor undo baseline."""

        self._editor.replaceBaselineSourceText(text)
        self._sync_gutter_width()

    def replaceBaselineSourceDocument(  # noqa: N802
        self,
        text: str,
        document_semantics: PromptDocumentSemantics,
    ) -> None:
        """Replace semantics and exact source as one editor undo baseline."""

        self._editor.replaceBaselineSourceDocument(text, document_semantics)
        self._sync_gutter_width()

    def toPlainText(self) -> str:
        """Return the wrapped prompt editor source text."""

        return self._editor.toPlainText()

    def undo(self) -> None:
        """Undo one wrapped prompt editor transaction."""

        self._editor.undo()

    def redo(self) -> None:
        """Redo one wrapped prompt editor transaction."""

        self._editor.redo()

    def canUndo(self) -> bool:  # noqa: N802
        """Return whether the wrapped prompt editor can undo."""

        return self._editor.canUndo()

    def canRedo(self) -> bool:  # noqa: N802
        """Return whether the wrapped prompt editor can redo."""

        return self._editor.canRedo()

    def line_count(self) -> int:
        """Return source logical line count based on raw newline delimiters."""

        return max(1, int(self._editor.document().blockCount()))

    def formatted_line_number(self, line_index: int) -> str:
        """Return the one-based padded line number for a zero-based line index."""

        digits = max(2, len(str(self.line_count())))
        return str(line_index + 1).zfill(digits)

    def gutter_width(self) -> int:
        """Return the editor content inset reserved for line numbers."""

        digits = max(2, len(str(self.line_count())))
        return _GUTTER_LEFT_PADDING + self._editor.fontMetrics().horizontalAdvance(
            "0" * digits
        )

    def gutter_paint_width(self) -> int:
        """Return the overlapping paint width used for the editor side gutter."""

        return self.gutter_width() + _GUTTER_OVERLAP

    def zebra_line_indexes(self) -> tuple[int, ...]:
        """Return visible zebra source lines for deterministic tests."""

        return tuple(
            source_line.line_index
            for source_line in self._editor.source_line_rects()
            if source_line.line_index % 2 == 1
        )

    def paint_gutter(self, event: QPaintEvent) -> None:
        """Paint source logical line numbers using prompt projection geometry."""

        painter = QPainter(self._gutter)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setFont(self._editor.font())
            area_rect = self._gutter.rect()
            rounded_path = QPainterPath()
            rounded_path.addRoundedRect(
                QRectF(
                    0.0,
                    0.0,
                    float(area_rect.width() + int(_BORDER_RADIUS)),
                    float(area_rect.height()),
                ),
                _BORDER_RADIUS,
                _BORDER_RADIUS,
            )
            clip_path = QPainterPath()
            clip_path.addRect(
                QRectF(0.0, 0.0, float(area_rect.width()), float(area_rect.height()))
            )
            painter.setClipPath(rounded_path.intersected(clip_path))
            painter.fillRect(
                event.rect(), self._editor.viewport().palette().base().color()
            )
            painter.fillRect(
                self._gutter.width() - 1,
                event.rect().top(),
                1,
                event.rect().height(),
                _separator_color(),
            )
            current_line = self._editor.current_source_line_index()
            y_offset = self._viewport_y_offset_for_gutter()
            for source_line in self._editor.source_line_rects():
                row_rect = source_line.rect.toAlignedRect()
                row_top = row_rect.top() + y_offset
                if source_line.line_index % 2 == 1:
                    painter.fillRect(
                        0,
                        row_top,
                        self.gutter_paint_width(),
                        row_rect.height(),
                        _zebra_color(),
                    )
                if source_line.line_index == current_line and self._editor.hasFocus():
                    painter.fillRect(
                        0,
                        row_top,
                        self.gutter_paint_width(),
                        row_rect.height(),
                        _current_line_color(),
                    )
                    painter.setPen(QPen(QColor(themeColor())))
                else:
                    painter.setPen(_muted_text_color())
                painter.drawText(
                    0,
                    row_top,
                    max(1, self.gutter_paint_width() - _NUMBER_RIGHT_PADDING),
                    max(1, row_rect.height()),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                    self.formatted_line_number(source_line.line_index),
                )
        finally:
            painter.end()

    def event(self, event: QEvent) -> bool:
        """Refresh line chrome when palette or style changes."""

        handled = super().event(event)
        if event.type() in {QEvent.Type.PaletteChange, QEvent.Type.StyleChange}:
            self._gutter.update()
            self._editor.viewport().update()
        return handled

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]  # noqa: N802
        """Keep the gutter repainted after frame resizing."""

        super().resizeEvent(event)
        self._sync_gutter_geometry()

    def _handle_editor_text_changed(self) -> None:
        """Forward text changes after updating line-number geometry."""

        self._sync_gutter_width()
        self.textChanged.emit()

    def _sync_gutter_width(self) -> None:
        """Resize the gutter when the source line count crosses a digit boundary."""

        width = self.gutter_width()
        paint_width = self.gutter_paint_width()
        margins = self._editor.viewportMargins()
        if margins.left() != width:
            self._editor.setViewportMargins(
                width,
                margins.top(),
                margins.right(),
                margins.bottom(),
            )
        self._editor.set_source_line_content_left_inset(0.0)
        if self._gutter.width() == paint_width:
            self._gutter.update()
            self._sync_gutter_geometry()
            return
        self._gutter.setFixedWidth(paint_width)
        self._gutter.updateGeometry()
        self._sync_gutter_geometry()
        self._gutter.update()

    def _sync_gutter_geometry(self) -> None:
        """Keep the line-number gutter aligned to the editor margin side."""

        rect = self._editor.contentsRect()
        self._gutter.setGeometry(
            QRect(
                rect.left() - _GUTTER_OVERLAP,
                rect.top() + 1,
                self.gutter_paint_width(),
                max(0, rect.height() - 2),
            )
        )
        self._gutter.raise_()
        self._gutter.update()

    def _viewport_y_offset_for_gutter(self) -> int:
        """Return the viewport-to-gutter vertical coordinate adjustment."""

        viewport_origin = self._editor.viewport().mapTo(self._editor, QPoint(0, 0))
        return viewport_origin.y() - self._gutter.y()


def _zebra_color() -> QColor:
    """Return the alternating source-row fill color."""

    return QColor(255, 255, 255, 16) if isDarkTheme() else QColor(0, 0, 0, 12)


def _current_line_color() -> QColor:
    """Return the active source-row fill color."""

    color = QColor(themeColor())
    color.setAlpha(38 if isDarkTheme() else 34)
    return color


def _separator_color() -> QColor:
    """Return the gutter separator color."""

    return QColor(255, 255, 255, 18) if isDarkTheme() else QColor(0, 0, 0, 18)


def _muted_text_color() -> QColor:
    """Return the muted line-number text color."""

    return QColor(176, 176, 176) if isDarkTheme() else QColor(118, 118, 118)


__all__ = ["NumberedPromptEditorFrame"]
