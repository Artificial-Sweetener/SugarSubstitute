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

"""Provide a combo-like field backed by the reusable model picker popup."""

from __future__ import annotations

from sugarsubstitute_shared.localization import (
    ApplicationMessage,
    ApplicationText,
    app_text,
)
from sugarsubstitute_shared.presentation.localization import (
    clear_localized_property,
    render_application_text,
    set_localized_placeholder,
)

from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Protocol, cast, runtime_checkable

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCloseEvent,
    QFocusEvent,
    QIcon,
    QKeyEvent,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPalette,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget
from qfluentwidgets import EditableComboBox, FluentIcon as FIF  # type: ignore[import-untyped]
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    setCustomStyleSheet,
    themeColor,
)

from substitute.application.execution import TaskSubmitter
from substitute.application.model_metadata import (
    BANNER_THUMBNAIL_ROLE,
    ModelMetadataRefreshEvent,
    ModelThumbnailVariant,
    RichChoiceItem,
    RichChoiceResolution,
    RichChoiceSource,
    ThumbnailAssetRepository,
)
from substitute.presentation.widgets.combo_banner_decoration import (
    ComboBannerDecoration,
    ComboBannerDisplay,
)
from substitute.presentation.widgets.civitai_page_action import (
    UrlOpener,
    open_external_url,
)
from substitute.presentation.widgets.media_wall import (
    MediaWallThumbnailCache,
    MediaWallThumbnailPreloader,
    ThumbnailVariantReference,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
    ModelMetadataContextMenuPresenter,
    ModelMetadataContextMenuTarget,
)
from substitute.presentation.widgets.model_picker.model_picker_completion import (
    model_picker_inline_completion,
)
from substitute.presentation.widgets.model_picker.model_picker_models import (
    ModelPickerItem,
    model_picker_items_from_rich_choice_items,
)
from substitute.presentation.widgets.model_picker.model_picker_popup import (
    ModelPickerPopup,
)
from substitute.presentation.widgets.text_caret import (
    application_text_caret_blink_interval_ms,
    is_application_text_caret_blink_enabled,
    paint_text_caret,
    text_caret_rect,
    text_caret_repaint_rect,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_warning,
)

_LOGGER = get_logger("presentation.widgets.model_picker.model_picker_field")
_SUPPORTED_MODEL_EXTENSIONS = frozenset({".safetensors", ".ckpt", ".pt"})
_COMBO_MINIMUM_WIDTH = 208
_COMBO_HORIZONTAL_PADDING = 44
_COMBO_TEXT_LEFT_PADDING = 11
_COMBO_TEXT_RIGHT_PADDING = 31
_COMBO_MAXIMUM_HINT_WIDTH = 520
_COMBO_BORDER_RADIUS = 5.0
_COMBO_BANNER_INSET = 1
_MODEL_LOAD_PROGRESS_HEIGHT = 2
_MODEL_LOAD_PROGRESS_HORIZONTAL_INSET = int(_COMBO_BORDER_RADIUS)
_MODEL_LOAD_HELD_PERCENT = 99.0
_MODEL_LOAD_PROGRESS_ALPHA = 220
_MODEL_LOAD_PROGRESS_PULSE_MIN_ALPHA = 120
_MODEL_LOAD_PROGRESS_PULSE_MAX_ALPHA = 235
_MODEL_LOAD_PROGRESS_PULSE_STEP = 18
_MODEL_LOAD_PROGRESS_PULSE_INTERVAL_MS = 90
_PICKER_ITEM_CACHE: dict[tuple[int, int], tuple[ModelPickerItem, ...]] = {}
_MODEL_PICKER_COMBO_LIGHT_STYLE = """
#modelPickerComboSurface {
    border: 1px solid rgba(0, 0, 0, 0.086);
    border-radius: 5px;
    border-top: 1px solid rgba(0, 0, 0, 0.057);
    border-bottom: 1px solid rgba(0, 0, 0, 0.162);
    padding: 5px 31px 6px 11px;
    background-color: rgba(255, 255, 255, 0.78);
    selection-background-color: palette(highlight);
    selection-color: palette(highlighted-text);
    text-align: left;
    outline: none;
}

#modelPickerComboSurface:hover {
    background-color: rgba(249, 249, 249, 0.88);
}

#modelPickerComboSurface:focus {
    border: 1px solid rgba(0, 0, 0, 0.12);
    border-top: 1px solid rgba(0, 0, 0, 0.08);
    border-bottom: 1px solid rgba(0, 0, 0, 0.20);
    background-color: rgba(255, 255, 255, 0.94);
}

#modelPickerComboSurface:disabled {
    color: rgba(0, 0, 0, 0.36);
    background: rgba(249, 249, 249, 0.72);
    border: 1px solid rgba(0, 0, 0, 0.057);
}
"""
_MODEL_PICKER_COMBO_DARK_STYLE = """
#modelPickerComboSurface {
    border: 1px solid rgba(255, 255, 255, 0.053);
    border-radius: 5px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    border-bottom: 1px solid rgba(255, 255, 255, 0.053);
    padding: 5px 31px 6px 11px;
    background-color: rgba(255, 255, 255, 0.0605);
    selection-background-color: palette(highlight);
    selection-color: palette(highlighted-text);
    text-align: left;
    outline: none;
}

#modelPickerComboSurface:hover {
    background-color: rgba(255, 255, 255, 0.0837);
}

#modelPickerComboSurface:focus {
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    background-color: rgba(255, 255, 255, 0.0837);
}

#modelPickerComboSurface:disabled {
    color: rgba(255, 255, 255, 0.3628);
    background: rgba(255, 255, 255, 0.0419);
    border: 1px solid rgba(255, 255, 255, 0.053);
}
"""


@runtime_checkable
class _ExtraRichChoiceSource(Protocol):
    """Expose optional selected-value enrichment for stale Comfy choice lists."""

    def extra_item_for_value(self, value: str) -> RichChoiceItem | None:
        """Return an enriched item for a value outside the current choice list."""


class _ModelPickerComboSurface(EditableComboBox):  # type: ignore[misc]
    """Adapt qfluent editable combo chrome into picker search gestures."""

    openRequested = Signal()
    toggleRequested = Signal()
    searchTextChanged = Signal(str)
    searchConfirmed = Signal()
    dismissRequested = Signal()
    moveCurrentUpRequested = Signal()
    moveCurrentDownRequested = Signal()
    moveCurrentLeftRequested = Signal()
    moveCurrentRightRequested = Signal()
    contextMenuRequested = Signal(QPoint)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        closed_banner_decoration: ComboBannerDecoration | None = None,
    ) -> None:
        """Initialize the qfluent editable combo without using its item menu."""

        super().__init__(parent)
        self.setObjectName("modelPickerComboSurface")
        setCustomStyleSheet(
            self,
            _MODEL_PICKER_COMBO_LIGHT_STYLE,
            _MODEL_PICKER_COMBO_DARK_STYLE,
        )
        self._search_caret_visible = False
        self._search_focus_active = False
        self._search_caret_rect = QRectF()
        self._search_caret_timer = QTimer(self)
        self._search_caret_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._search_caret_timer.timeout.connect(self._toggle_search_caret)
        self._inline_completion_suffix = ""
        self._closed_banner_decoration = closed_banner_decoration
        self._closed_banner_display: ComboBannerDisplay | None = None
        self._drop_button_icon_suppressed = False
        self._model_load_progress_percent: float | None = None
        self._model_load_progress_active = False
        self._model_load_progress_pulse_alpha = _MODEL_LOAD_PROGRESS_PULSE_MAX_ALPHA
        self._model_load_progress_pulse_direction = -1
        self._model_load_progress_pulse_timer = QTimer(self)
        self._model_load_progress_pulse_timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._model_load_progress_pulse_timer.timeout.connect(
            self._advance_model_load_progress_pulse
        )
        set_localized_placeholder(self, "Select model")
        self.set_search_mode(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.textEdited.connect(self.searchTextChanged.emit)
        self.textChanged.connect(self._refresh_search_caret)
        self.cursorPositionChanged.connect(self._refresh_search_caret)
        self.selectionChanged.connect(self._refresh_search_caret)

    def set_search_mode(self, enabled: bool) -> None:
        """Switch between closed combo display and editable search behavior."""

        self.setReadOnly(not enabled)
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus if enabled else Qt.FocusPolicy.NoFocus
        )
        self.setClearButtonEnabled(enabled)
        self.setCursor(
            Qt.CursorShape.IBeamCursor if enabled else Qt.CursorShape.ArrowCursor
        )
        if enabled:
            self._set_drop_button_icon_suppressed(False)
            self._show_search_caret()
        else:
            self.set_search_focus_active(False)
            self.set_inline_completion_suffix("")
            self._hide_search_caret()

    def set_search_focus_active(self, active: bool) -> None:
        """Set logical search focus for popup-backed editing."""

        next_active = bool(active)
        if next_active == self._search_focus_active:
            return
        self._search_focus_active = next_active
        if next_active:
            self._show_search_caret()
        else:
            self._refresh_search_caret()

    def search_focus_active(self) -> bool:
        """Return whether the surface should behave as the active search editor."""

        return not self.isReadOnly() and (self.hasFocus() or self._search_focus_active)

    def set_inline_completion_suffix(self, suffix: str) -> None:
        """Set the display-only search completion suffix."""

        next_suffix = str(suffix)
        if next_suffix == self._inline_completion_suffix:
            return
        self._inline_completion_suffix = next_suffix
        self.update()

    def inline_completion_suffix(self) -> str:
        """Return the active display-only suffix."""

        return self._inline_completion_suffix

    def set_model_load_progress(
        self,
        *,
        percent: float | None,
        active: bool,
    ) -> None:
        """Set bottom-line model loading progress for the closed surface."""

        next_percent = _clamp_progress_percent(percent)
        next_active = bool(active) and next_percent is not None and next_percent < 100.0
        if (
            next_percent == self._model_load_progress_percent
            and next_active == self._model_load_progress_active
        ):
            return
        self._model_load_progress_percent = next_percent
        self._model_load_progress_active = next_active
        self._sync_model_load_progress_pulse()
        self.update()

    def model_load_progress(self) -> tuple[float | None, bool]:
        """Return current bottom-line model loading progress state."""

        return self._model_load_progress_percent, self._model_load_progress_active

    def model_load_progress_pulsing(self) -> bool:
        """Return whether the held model-load state is currently pulsing."""

        return self._model_load_progress_pulse_timer.isActive()

    def set_closed_banner_display(self, display: ComboBannerDisplay | None) -> None:
        """Set the optional closed-state banner display model."""

        if display == self._closed_banner_display:
            return
        self._closed_banner_display = display
        self._set_drop_button_icon_suppressed(False)
        if self.isReadOnly():
            self.update()

    def accept_inline_completion(self) -> bool:
        """Append the visible suffix to transient search text when allowed."""

        if not self._can_accept_inline_completion():
            return False
        next_text = f"{self.text()}{self._inline_completion_suffix}"
        self.setText(next_text)
        self.setCursorPosition(len(next_text))
        self.deselect()
        self.set_inline_completion_suffix("")
        self.searchTextChanged.emit(next_text)
        return True

    def place_native_cursor_at_end(self) -> None:
        """Place qfluent's native line-edit cursor at the end of the search text."""

        self.setCursorPosition(len(self.text()))
        self.deselect()
        self._show_search_caret()

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Start the search caret when the editable combo receives focus."""

        super().focusInEvent(event)
        if not self.isReadOnly():
            self._search_focus_active = True
        self._show_search_caret()

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Stop the search caret when the editable combo loses focus."""

        super().focusOutEvent(event)
        if self.search_focus_active():
            self._show_search_caret()
        else:
            self._hide_search_caret()

    def event(self, event: QEvent) -> bool:
        """Accept inline completion before Qt treats Tab as focus traversal."""

        if (
            event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() == Qt.Key.Key_Tab
            and not self.isReadOnly()
            and self.accept_inline_completion()
        ):
            event.accept()
            return True
        return cast(bool, super().event(event))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Open the picker from closed-state body clicks."""

        if self.isReadOnly() and event.button() == Qt.MouseButton.RightButton:
            self.contextMenuRequested.emit(event.globalPosition().toPoint())
            event.accept()
            return
        if self.isReadOnly() and event.button() == Qt.MouseButton.LeftButton:
            self.openRequested.emit()
            if not self.isReadOnly():
                super().mousePressEvent(event)
            else:
                event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Map combo-style keys to picker popup actions."""

        if not self.isReadOnly():
            if event.key() == Qt.Key.Key_Tab:
                if self.accept_inline_completion():
                    event.accept()
                    return
            if self._route_plain_arrow_key(event):
                event.accept()
                return
        if event.key() == Qt.Key.Key_Escape:
            self.dismissRequested.emit()
            event.accept()
            return
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.searchConfirmed.emit()
            event.accept()
            return
        if self.isReadOnly() and event.key() in {
            Qt.Key.Key_Down,
            Qt.Key.Key_Space,
        }:
            self.openRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw display-only search affordances over the qfluent combo surface."""

        super().paintEvent(event)
        painter = QPainter(self)
        try:
            closed_banner_painted = self._paint_closed_banner_decoration(painter)
            self._set_drop_button_icon_suppressed(closed_banner_painted)
            self._paint_inline_completion(painter)
            self._paint_model_load_progress(painter)
            if self._should_paint_search_caret():
                paint_text_caret(
                    painter,
                    self._current_search_caret_rect(),
                    self.palette(),
                )
        finally:
            painter.end()

    def _toggleComboMenu(self) -> None:
        """Toggle the model picker from qfluent's drop-button click."""

        self.toggleRequested.emit()

    def _showComboMenu(self) -> None:
        """Open the model picker instead of qfluent's built-in combo menu."""

        self.openRequested.emit()

    def _onReturnPressed(self) -> None:
        """Activate the current picker item instead of adding typed combo items."""

        self.searchConfirmed.emit()

    def _onComboTextChanged(self, text: str) -> None:
        """Ignore qfluent selection semantics for transient search edits."""

        _ = text

    def _onClearButtonClicked(self) -> None:
        """Clear transient search text without clearing the backend selection."""

        self.setText("")
        self.searchTextChanged.emit("")

    def _show_search_caret(self) -> None:
        """Show and blink the overlay caret while the combo acts as search input."""

        if (
            self.isReadOnly()
            or not self.search_focus_active()
            or self.hasSelectedText()
        ):
            return
        self._search_caret_visible = True
        self._refresh_search_caret()
        if not self._search_caret_timer.isActive():
            self._start_search_caret_timer()

    def _hide_search_caret(self) -> None:
        """Hide the overlay caret and repaint its previous location."""

        self._search_caret_timer.stop()
        self._search_caret_visible = False
        self._repaint_search_caret_rect(self._search_caret_rect)
        self._search_caret_rect = QRectF()

    def _toggle_search_caret(self) -> None:
        """Blink the overlay caret without losing native cursor placement."""

        if (
            self.isReadOnly()
            or not self.search_focus_active()
            or self.hasSelectedText()
        ):
            self._hide_search_caret()
            return
        self._search_caret_visible = not self._search_caret_visible
        self._refresh_search_caret()

    def _refresh_search_caret(self, *_args: object) -> None:
        """Repaint old and new caret positions after text or cursor movement."""

        if self.isReadOnly():
            self.set_inline_completion_suffix("")
            return
        self._clear_inline_completion_when_unpaintable()
        if self.hasSelectedText():
            self._search_caret_visible = False
        elif _args and self.search_focus_active():
            self._search_caret_visible = True
            self._start_search_caret_timer()
        previous_rect = self._search_caret_rect
        next_rect = self._current_search_caret_rect()
        self._search_caret_rect = next_rect
        self._repaint_search_caret_rect(previous_rect)
        self._repaint_search_caret_rect(next_rect)

    def _current_search_caret_rect(self) -> QRectF:
        """Return the overlay caret rect using shared text-caret geometry."""

        return text_caret_rect(self.cursorRect())

    def _should_paint_search_caret(self) -> bool:
        """Return whether the overlay caret should be painted this frame."""

        return (
            self._search_caret_visible
            and not self.isReadOnly()
            and self.search_focus_active()
            and not self.hasSelectedText()
            and self.isVisible()
        )

    def _should_paint_inline_completion(self) -> bool:
        """Return whether inline completion should be painted this frame."""

        return (
            bool(self._inline_completion_suffix)
            and not self.isReadOnly()
            and self.search_focus_active()
            and not self.hasSelectedText()
            and self.cursorPosition() == len(self.text())
            and self.isVisible()
        )

    def _should_paint_closed_banner_decoration(self) -> bool:
        """Return whether the closed surface should attempt banner decoration."""

        return (
            self._closed_banner_decoration is not None
            and self._closed_banner_display is not None
            and self.isReadOnly()
            and self.isVisible()
        )

    def _should_paint_model_load_progress(self) -> bool:
        """Return whether the bottom progress line should be visible."""

        return (
            self._model_load_progress_active
            and self._model_load_progress_percent is not None
            and self._model_load_progress_percent < 100.0
            and self.isEnabled()
            and self.isVisible()
        )

    def _should_pulse_model_load_progress(self) -> bool:
        """Return whether progress should pulse for first-use materialization."""

        return (
            self._model_load_progress_active
            and self._model_load_progress_percent is not None
            and self._model_load_progress_percent >= _MODEL_LOAD_HELD_PERCENT
        )

    def _can_accept_inline_completion(self) -> bool:
        """Return whether the active suffix can become real search text."""

        return (
            bool(self._inline_completion_suffix)
            and not self.isReadOnly()
            and not self.hasSelectedText()
            and self.cursorPosition() == len(self.text())
        )

    def _route_plain_arrow_key(self, event: QKeyEvent) -> bool:
        """Route unmodified arrow keys to the open picker grid."""

        if event.modifiers() not in (
            Qt.KeyboardModifier.NoModifier,
            Qt.KeyboardModifier.KeypadModifier,
        ):
            return False
        if event.key() == Qt.Key.Key_Left:
            self.moveCurrentLeftRequested.emit()
            return True
        if event.key() == Qt.Key.Key_Right:
            self.moveCurrentRightRequested.emit()
            return True
        if event.key() == Qt.Key.Key_Up:
            self.moveCurrentUpRequested.emit()
            return True
        if event.key() == Qt.Key.Key_Down:
            self.moveCurrentDownRequested.emit()
            return True
        return False

    def _paint_closed_banner_decoration(self, painter: QPainter) -> bool:
        """Paint the optional banner-backed closed combo display."""

        if not self._should_paint_closed_banner_decoration():
            return False
        assert self._closed_banner_decoration is not None
        assert self._closed_banner_display is not None
        return self._closed_banner_decoration.paint_closed_display(
            painter,
            self,
            display=self._closed_banner_display,
            rect=self._closed_banner_content_rect(),
            text_rect=self._editable_text_rect(),
            chevron_rect=self._drop_button_icon_rect(),
            palette=self.palette(),
            font=self.font(),
            border_radius=_COMBO_BORDER_RADIUS - _COMBO_BANNER_INSET,
        )

    def _paint_inline_completion(self, painter: QPainter) -> None:
        """Paint the active suffix after the native cursor position."""

        if not self._should_paint_inline_completion():
            return
        editable_rect = self._editable_text_rect()
        cursor_rect = self.cursorRect()
        text_left = max(editable_rect.left(), cursor_rect.right())
        text_rect = QRect(
            text_left,
            editable_rect.top(),
            max(0, editable_rect.right() - text_left),
            editable_rect.height(),
        )
        if text_rect.width() <= 0:
            return
        painter.save()
        painter.setClipRect(editable_rect)
        painter.setPen(self.palette().color(QPalette.ColorRole.PlaceholderText))
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._inline_completion_suffix,
        )
        painter.restore()

    def _paint_model_load_progress(self, painter: QPainter) -> None:
        """Paint a thin bottom-line fill for active model loading."""

        if not self._should_paint_model_load_progress():
            return
        assert self._model_load_progress_percent is not None
        progress_rect = self._model_load_progress_rect()
        if progress_rect.isNull():
            return
        painter.save()
        painter.fillRect(progress_rect, self._model_load_progress_color())
        painter.restore()

    def _model_load_progress_rect(self) -> QRect:
        """Return the progress rect constrained to the combo's straight bottom edge."""

        assert self._model_load_progress_percent is not None
        track_left = min(_MODEL_LOAD_PROGRESS_HORIZONTAL_INSET, max(0, self.width()))
        track_width = max(0, self.width() - (2 * track_left))
        progress_width = int(
            round(track_width * (self._model_load_progress_percent / 100.0))
        )
        if progress_width <= 0:
            return QRect()
        return QRect(
            track_left,
            max(0, self.height() - _MODEL_LOAD_PROGRESS_HEIGHT),
            progress_width,
            _MODEL_LOAD_PROGRESS_HEIGHT,
        )

    def _model_load_progress_color(self) -> QColor:
        """Return the accent progress color for the current loading state."""

        color = QColor(themeColor())
        color.setAlpha(
            self._model_load_progress_pulse_alpha
            if self._should_pulse_model_load_progress()
            else _MODEL_LOAD_PROGRESS_ALPHA
        )
        return color

    def _sync_model_load_progress_pulse(self) -> None:
        """Start or stop the held-state pulse timer."""

        if self._should_pulse_model_load_progress():
            if not self._model_load_progress_pulse_timer.isActive():
                self._model_load_progress_pulse_timer.start(
                    _MODEL_LOAD_PROGRESS_PULSE_INTERVAL_MS
                )
            return
        self._model_load_progress_pulse_timer.stop()
        self._model_load_progress_pulse_alpha = _MODEL_LOAD_PROGRESS_PULSE_MAX_ALPHA
        self._model_load_progress_pulse_direction = -1

    def _advance_model_load_progress_pulse(self) -> None:
        """Advance the held-state accent alpha and repaint the underline."""

        next_alpha = (
            self._model_load_progress_pulse_alpha
            + self._model_load_progress_pulse_direction
            * _MODEL_LOAD_PROGRESS_PULSE_STEP
        )
        if next_alpha <= _MODEL_LOAD_PROGRESS_PULSE_MIN_ALPHA:
            next_alpha = _MODEL_LOAD_PROGRESS_PULSE_MIN_ALPHA
            self._model_load_progress_pulse_direction = 1
        elif next_alpha >= _MODEL_LOAD_PROGRESS_PULSE_MAX_ALPHA:
            next_alpha = _MODEL_LOAD_PROGRESS_PULSE_MAX_ALPHA
            self._model_load_progress_pulse_direction = -1
        self._model_load_progress_pulse_alpha = next_alpha
        self.update()

    def _editable_text_rect(self) -> QRect:
        """Return the conservative text area excluding qfluent right-side chrome."""

        return cast(
            QRect,
            self.rect().adjusted(
                _COMBO_TEXT_LEFT_PADDING,
                0,
                -_COMBO_TEXT_RIGHT_PADDING,
                0,
            ),
        )

    def _closed_banner_content_rect(self) -> QRect:
        """Return the inner banner rect that leaves qfluent combo chrome visible."""

        return cast(
            QRect,
            self.rect().adjusted(
                _COMBO_BANNER_INSET,
                _COMBO_BANNER_INSET,
                -_COMBO_BANNER_INSET,
                -_COMBO_BANNER_INSET,
            ),
        )

    def _drop_button_icon_rect(self) -> QRectF:
        """Return the qfluent drop button icon rect in surface coordinates."""

        button_geometry = self.dropButton.geometry()
        icon_size = self.dropButton.iconSize()
        icon_width = float(icon_size.width())
        icon_height = float(icon_size.height())
        return QRectF(
            button_geometry.left() + (button_geometry.width() - icon_width) / 2.0,
            button_geometry.top() + (button_geometry.height() - icon_height) / 2.0,
            icon_width,
            icon_height,
        )

    def _set_drop_button_icon_suppressed(self, suppressed: bool) -> None:
        """Suppress the native child arrow while the parent paints a banner arrow."""

        if suppressed == self._drop_button_icon_suppressed:
            return
        self._drop_button_icon_suppressed = suppressed
        self.dropButton.setIcon(QIcon() if suppressed else FIF.ARROW_DOWN)

    def _clear_inline_completion_when_unpaintable(self) -> None:
        """Clear suffix state when selection or cursor placement suppresses it."""

        if self.hasSelectedText() or self.cursorPosition() != len(self.text()):
            self.set_inline_completion_suffix("")

    def _start_search_caret_timer(self) -> None:
        """Start the caret blink timer using the application text-caret cadence."""

        if not is_application_text_caret_blink_enabled():
            self._search_caret_timer.stop()
            self._search_caret_visible = True
            return
        self._search_caret_timer.start(application_text_caret_blink_interval_ms())

    def _repaint_search_caret_rect(self, rect: QRectF) -> None:
        """Schedule a repaint around one possible caret location."""

        if rect.isNull():
            return
        self.update(text_caret_repaint_rect(rect))


@dataclass(frozen=True, slots=True)
class ModelPickerThumbnailPreloadRoute:
    """Carry execution collaborators for model-picker thumbnail preloads."""

    submitter: TaskSubmitter
    close: Callable[[], None]


class ModelPickerField(QWidget):
    """Expose a combo-like backend-value field using a searchable model picker."""

    currentTextChanged = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        choice_source: RichChoiceSource,
        thumbnail_asset_repository: ThumbnailAssetRepository | None = None,
        current_value: str = "",
        search_placeholder: ApplicationText = app_text("Search models"),
        open_url: UrlOpener | None = None,
        metadata_action_handler: ModelMetadataContextActionHandler | None = None,
        thumbnail_preload_route_factory: (
            Callable[[QWidget], ModelPickerThumbnailPreloadRoute] | None
        ) = None,
    ) -> None:
        """Initialize the closed selector from a resolved rich-choice source."""
        super().__init__(parent)
        self._choice_source = choice_source
        self._thumbnail_asset_repository = thumbnail_asset_repository
        self._search_placeholder = search_placeholder
        self._open_url = open_url or open_external_url
        self._resolution: RichChoiceResolution | None = None
        self._choice_items: tuple[RichChoiceItem, ...] = ()
        self._picker_items: tuple[ModelPickerItem, ...] = ()
        self._picker_items_cache_key: tuple[int, int] | None = None
        self._item_by_backend_value: dict[str, RichChoiceItem] = {}
        self._current_value = ""
        self._closed_display_label = ""
        self._popup: ModelPickerPopup | None = None
        self._max_hint_width: int | None = None
        self._metadata_context_menu = ModelMetadataContextMenuPresenter(
            parent=self,
            open_url=self._open_url,
            action_handler=metadata_action_handler,
        )
        self._metadata_action_handler = metadata_action_handler
        self._thumbnail_cache = MediaWallThumbnailCache(
            asset_repository=thumbnail_asset_repository
        )
        if (
            thumbnail_asset_repository is not None
            and thumbnail_preload_route_factory is None
        ):
            raise RuntimeError(
                "thumbnail_preload_route_factory is required for thumbnail preloads."
            )
        thumbnail_preload_route = (
            thumbnail_preload_route_factory(self)
            if thumbnail_asset_repository is not None
            and thumbnail_preload_route_factory is not None
            else None
        )
        thumbnail_submitter = (
            thumbnail_preload_route.submitter
            if thumbnail_preload_route is not None
            else None
        )
        close_thumbnail_submitter = (
            thumbnail_preload_route.close
            if thumbnail_preload_route is not None
            else None
        )
        self._thumbnail_preloader = (
            MediaWallThumbnailPreloader(
                cache=self._thumbnail_cache,
                asset_repository=thumbnail_asset_repository,
                submitter=thumbnail_submitter,
                close_submitter=close_thumbnail_submitter,
                parent=self,
            )
            if thumbnail_asset_repository is not None
            else None
        )
        if self._thumbnail_preloader is not None:
            self._thumbnail_preloader.thumbnailReady.connect(
                self._handle_thumbnail_ready
            )
        self._closed_banner_decoration = (
            ComboBannerDecoration(
                thumbnail_cache=self._thumbnail_cache,
            )
            if thumbnail_asset_repository is not None
            else None
        )
        self._surface = _ModelPickerComboSurface(
            self,
            closed_banner_decoration=self._closed_banner_decoration,
        )
        self._surface.openRequested.connect(self.open_picker)
        self._surface.toggleRequested.connect(self._toggle_picker)
        self._surface.searchTextChanged.connect(self._apply_search_text)
        self._surface.searchConfirmed.connect(self._activate_current_popup_item)
        self._surface.dismissRequested.connect(self._dismiss_popup)
        self._surface.moveCurrentUpRequested.connect(self._move_popup_current_up)
        self._surface.moveCurrentDownRequested.connect(self._move_popup_current_down)
        self._surface.moveCurrentLeftRequested.connect(self._move_popup_current_left)
        self._surface.moveCurrentRightRequested.connect(self._move_popup_current_right)
        self._surface.contextMenuRequested.connect(
            self._show_selected_model_context_menu
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._surface)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._load_choices(refresh=False)
        self._set_current_text(current_value, emit=False)

    def currentText(self) -> str:
        """Return the selected backend value."""

        return self._current_value

    def setCurrentText(self, value: str) -> None:
        """Set the selected backend value and update the closed display label."""

        self._set_current_text(value, emit=True)

    def displayText(self) -> str:
        """Return the user-facing closed-field label."""

        return cast(str, self._surface.text())

    def setMaxHintWidth(self, width: int | None) -> None:
        """Set an optional cap for the preferred field width."""

        self._max_hint_width = width
        self.updateGeometry()

    def maxHintWidth(self) -> int | None:
        """Return the optional preferred-width cap."""

        return self._max_hint_width

    def set_model_load_progress(
        self,
        *,
        percent: float | None,
        active: bool,
    ) -> None:
        """Show or clear model-loading progress on the picker bottom line."""

        self._surface.set_model_load_progress(percent=percent, active=active)

    def model_load_progress(self) -> tuple[float | None, bool]:
        """Return current picker model-loading progress state."""

        return self._surface.model_load_progress()

    def model_load_progress_pulsing(self) -> bool:
        """Return whether the picker is pulsing held model-load progress."""

        return self._surface.model_load_progress_pulsing()

    def sizeHint(self) -> QSize:
        """Return a combo-like preferred size for editor row layout."""

        base_hint = self._surface.sizeHint()
        minimum_hint = self.minimumSizeHint()
        display_text = self._display_label_for_value(self._current_value)
        if not display_text:
            display_text = render_application_text(self._search_placeholder)
        text_width = self.fontMetrics().horizontalAdvance(display_text)
        preferred_width = max(
            minimum_hint.width(),
            base_hint.width(),
            text_width + _COMBO_HORIZONTAL_PADDING,
        )
        max_hint_width = self._max_hint_width or _COMBO_MAXIMUM_HINT_WIDTH
        preferred_width = min(
            preferred_width,
            max(_COMBO_MINIMUM_WIDTH, max_hint_width),
        )
        return QSize(
            preferred_width,
            max(minimum_hint.height(), base_hint.height()),
        )

    def minimumSizeHint(self) -> QSize:
        """Return a practical combo-like minimum size for constrained layouts."""

        surface_minimum = self._surface.minimumSizeHint()
        return QSize(
            _COMBO_MINIMUM_WIDTH,
            max(32, surface_minimum.height()),
        )

    def open_picker(self) -> None:
        """Refresh metadata and open the attached searchable picker popup."""

        if self._popup is not None and self._popup.isVisible():
            self._popup.raise_()
            self._focus_search_surface()
            return
        self._load_choices(refresh=True)
        picker_items = self._ensure_picker_items_loaded()
        if self._popup is not None:
            self._popup.hide()
            self._popup.deleteLater()
        popup = ModelPickerPopup(
            picker_items,
            asset_repository=self._thumbnail_asset_repository,
            thumbnail_cache=self._thumbnail_cache,
            thumbnail_preloader=self._thumbnail_preloader,
            search_placeholder=self._search_placeholder,
            show_search_field=False,
            dismissal_guard_widgets=(self,),
            open_url=self._open_url,
            metadata_action_handler=self._metadata_action_handler,
            search_focus_requested=self.keep_search_focus_for_popup_interaction,
            external_search_key_pressed=self.handle_popup_search_key,
            parent=self,
        )
        popup.itemActivated.connect(self._select_picker_item)
        popup.dismissed.connect(self._restore_closed_surface)
        self._popup = popup
        self._begin_search_surface()
        anchor_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
        popup.show_attached_to(anchor_rect)
        popup.set_search_text("")
        self._clear_inline_completion()
        QTimer.singleShot(0, self._focus_search_surface)

    def refresh_metadata(self) -> None:
        """Refresh backing metadata and live-update the field surface."""

        popup = self._popup
        popup_visible = popup is not None and popup.isVisible()
        self._load_choices(refresh=True)
        if popup_visible and popup is not None:
            self._sync_open_popup_metadata(popup)
        else:
            self._sync_display_label()
        self.update()

    def reconcile_choice_source(
        self,
        choice_source: RichChoiceSource,
        value: str,
    ) -> None:
        """Replace live choices and value without emitting a user-authored edit."""

        popup = self._popup
        popup_visible = popup is not None and popup.isVisible()
        search_text = popup.search_text() if popup_visible and popup is not None else ""
        self._choice_source = choice_source
        self._load_choices(refresh=False)
        self._set_current_text(value, emit=False)
        if popup_visible and popup is not None:
            self._sync_open_popup_metadata(popup)
            popup.set_search_text(search_text)
            self._refresh_inline_completion()
        else:
            self._sync_display_label()
        self.update()

    def refresh_metadata_for_event(self, event: ModelMetadataRefreshEvent) -> bool:
        """Refresh only when one metadata event affects visible picker state."""

        if not self._metadata_event_matches_loaded_resolution(event):
            return False
        popup = self._popup
        if popup is not None and popup.isVisible():
            self._load_choices(refresh=True)
            self._sync_open_popup_metadata(popup)
            self.update()
            return True
        if self._current_value != event.value and not self._is_visible_closed_field():
            return False
        self._load_choices(refresh=True)
        self._sync_display_label()
        self.update()
        return True

    def clear_thumbnail_cache_for_event(
        self,
        event: ModelMetadataRefreshEvent,
    ) -> bool:
        """Discard rendered thumbnails when one matching event changed image bytes."""

        if (
            not event.thumbnail_updated
            or not self._metadata_event_matches_loaded_resolution(event)
        ):
            return False
        self._thumbnail_cache.clear()
        return True

    def keep_search_focus_for_popup_interaction(self) -> None:
        """Restore field-owned search focus after a popup child interaction."""

        QTimer.singleShot(0, self._restore_search_focus_after_popup_interaction)

    def handle_popup_search_key(self, event: QKeyEvent) -> bool:
        """Route popup-descendant text editing keys to the field search surface."""

        popup = self._popup
        if popup is None or not popup.isVisible() or self._surface.isReadOnly():
            return False
        self._focus_search_surface()
        handled = self._surface.event(event)
        if handled or event.isAccepted():
            self._refresh_inline_completion()
            return True
        return False

    def _toggle_picker(self) -> None:
        """Toggle the popup for chevron clicks while preserving text-field clicks."""

        popup = self._popup
        if popup is not None and popup.isVisible():
            self._dismiss_popup()
            return
        self.open_picker()

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Preserve standard focus handling for the closed selector."""

        super().focusInEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Recompute the closed-field elided label when row geometry changes."""

        super().resizeEvent(event)
        if self._surface.isReadOnly():
            self._sync_closed_surface_text()
            self._request_closed_banner_preload()

    def showEvent(self, event: QShowEvent) -> None:
        """Apply closed-label elision once Qt has assigned visible geometry."""

        super().showEvent(event)
        if self._surface.isReadOnly():
            self._sync_closed_surface_text()
            self._request_closed_banner_preload()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop field-owned thumbnail preload tasks when the field closes."""

        if self._thumbnail_preloader is not None:
            self._thumbnail_preloader.shutdown()
        super().closeEvent(event)

    def _focus_search_surface(self) -> None:
        """Give native line-edit focus to the open search surface."""

        if self._surface.isReadOnly():
            return
        self.window().activateWindow()
        self.activateWindow()
        self._surface.setFocus(Qt.FocusReason.MouseFocusReason)
        self._surface.set_search_focus_active(True)
        self._surface.place_native_cursor_at_end()
        self._refresh_inline_completion()

    def _restore_search_focus_after_popup_interaction(self) -> None:
        """Return keyboard focus to the field-owned search editor when still open."""

        popup = self._popup
        if popup is None or not popup.isVisible() or self._surface.isReadOnly():
            return
        self._focus_search_surface()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Open the picker from standard combo-box keyboard gestures."""

        if event.key() in {
            Qt.Key.Key_Down,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        }:
            self.open_picker()
            event.accept()
            return
        super().keyPressEvent(event)

    def _set_current_text(self, value: str, *, emit: bool) -> None:
        """Set the current backend value and optionally emit the value signal."""

        next_value = str(value)
        if next_value == self._current_value:
            self._sync_display_label()
            return
        self._current_value = next_value
        if next_value and next_value not in self._item_by_backend_value:
            self._load_choices(refresh=False)
        self._sync_display_label()
        self.updateGeometry()
        if emit:
            self.currentTextChanged.emit(self._current_value)

    def _select_picker_item(self, item: object) -> None:
        """Select the backend value from an activated picker item."""

        if not isinstance(item, ModelPickerItem):
            return
        self.setCurrentText(item.backend_value)
        self._dismiss_popup()

    def _show_selected_model_context_menu(self, global_pos: QPoint) -> None:
        """Show metadata actions for the currently selected model when available."""

        target = self._metadata_context_menu_target_for_current_value()
        if target is None:
            return
        self._metadata_context_menu.show_menu(target, global_pos)

    def _metadata_context_menu_target_for_current_value(
        self,
    ) -> ModelMetadataContextMenuTarget | None:
        """Return a shared metadata context-menu target for the selected value."""

        item = self._item_by_backend_value.get(self._current_value)
        if item is None:
            return None
        catalog_item = item.catalog_item
        return ModelMetadataContextMenuTarget(
            title=item.title,
            subtitle=item.subtitle,
            backend_value=item.value,
            relative_path=(
                item.value if catalog_item is None else catalog_item.relative_path
            ),
            model_kind=item.model_kind,
            model_page_url=(
                None if catalog_item is None else catalog_item.model_page_url
            ),
        )

    def _begin_search_surface(self) -> None:
        """Switch the combo surface from closed display into search entry mode."""

        self._surface.set_search_mode(True)
        if isinstance(self._search_placeholder, ApplicationMessage):
            set_localized_placeholder(
                self._surface,
                self._search_placeholder.source_text,
                *self._search_placeholder.arguments,
            )
        else:
            clear_localized_property(self._surface, "placeholder")
            self._surface.setPlaceholderText(self._search_placeholder)
        set_fluent_tooltip_text(self._surface, "")
        self._clear_inline_completion()
        self._set_surface_text("")

    def _restore_closed_surface(self, popup: object | None = None) -> None:
        """Restore closed combo display after popup selection or dismissal."""

        if popup is not None and popup is not self._popup:
            return
        self._clear_inline_completion()
        self._surface.set_search_mode(False)
        set_localized_placeholder(self._surface, "Select model")
        self._sync_display_label()

    def _apply_search_text(self, query: str) -> None:
        """Forward transient field search text to the open popup."""

        popup = self._popup
        if popup is None or not popup.isVisible():
            self._clear_inline_completion()
            return
        popup.set_search_text(query)
        self._refresh_inline_completion()

    def _activate_current_popup_item(self) -> None:
        """Activate the current popup item from the combo surface Return key."""

        popup = self._popup
        if popup is None or not popup.isVisible():
            self.open_picker()
            return
        popup.activate_current()

    def _move_popup_current_up(self) -> None:
        """Move popup current item up and refresh the inline completion suffix."""

        popup = self._popup
        if popup is None or not popup.isVisible():
            return
        popup.move_current_up()
        self._refresh_inline_completion()

    def _move_popup_current_down(self) -> None:
        """Move popup current item down and refresh the inline completion suffix."""

        popup = self._popup
        if popup is None or not popup.isVisible():
            return
        popup.move_current_down()
        self._refresh_inline_completion()

    def _move_popup_current_left(self) -> None:
        """Move popup current item left and refresh the inline completion suffix."""

        popup = self._popup
        if popup is None or not popup.isVisible():
            return
        popup.move_current_left()
        self._refresh_inline_completion()

    def _move_popup_current_right(self) -> None:
        """Move popup current item right and refresh the inline completion suffix."""

        popup = self._popup
        if popup is None or not popup.isVisible():
            return
        popup.move_current_right()
        self._refresh_inline_completion()

    def _dismiss_popup(self) -> None:
        """Hide the active popup and restore closed combo display."""

        popup = self._popup
        if popup is not None and popup.isVisible():
            popup.hide()
            return
        self._restore_closed_surface()

    def _refresh_inline_completion(self) -> None:
        """Refresh search-surface ghost text from the popup current item."""

        popup = self._popup
        if self._surface.isReadOnly() or popup is None or not popup.isVisible():
            self._clear_inline_completion()
            return
        if self._surface.hasSelectedText() or self._surface.cursorPosition() != len(
            self._surface.text()
        ):
            self._clear_inline_completion()
            return
        completion = model_picker_inline_completion(
            query=cast(str, self._surface.text()),
            item=popup.current_item(),
        )
        self._surface.set_inline_completion_suffix(
            "" if completion is None else completion.suffix_text
        )

    def _clear_inline_completion(self) -> None:
        """Clear search-surface ghost text."""

        self._surface.set_inline_completion_suffix("")

    def _metadata_event_matches_loaded_resolution(
        self,
        event: ModelMetadataRefreshEvent,
    ) -> bool:
        """Return whether a metadata event can affect this loaded picker."""

        if self._resolution is None:
            return self._current_value == event.value
        if (
            self._resolution.matched_kinds
            and event.kind not in self._resolution.matched_kinds
        ):
            return False
        return True

    def _is_visible_closed_field(self) -> bool:
        """Return whether the closed field can immediately present metadata changes."""

        return (
            self.isVisible()
            and self._surface.isVisible()
            and self._surface.isReadOnly()
        )

    def _sync_open_popup_metadata(self, popup: ModelPickerPopup) -> None:
        """Replace open popup rows while preserving the user's search query."""

        search_text = popup.search_text()
        popup.set_items(self._ensure_picker_items_loaded())
        popup.set_search_text(search_text)
        self._refresh_inline_completion()

    def _load_choices(self, *, refresh: bool) -> None:
        """Load or refresh picker rows for this field's exact Comfy choices."""

        resolution: RichChoiceResolution | None
        try:
            resolution = (
                self._choice_source.refresh()
                if refresh
                else self._choice_source.current_resolution()
            )
        except Exception as error:
            log_warning(
                _LOGGER,
                "Failed to load model picker choices",
                error=repr(error),
            )
            resolution = (
                _unavailable_resolution(self._resolution, error)
                if refresh
                else self._resolution
            )
        if resolution is None:
            self._choice_items = ()
            self._picker_items = ()
            self._picker_items_cache_key = None
            self._item_by_backend_value = {}
            self._sync_display_label()
            return
        self._resolution = resolution
        self._choice_items = self._choice_items_with_current_value(resolution)
        self._picker_items = ()
        self._picker_items_cache_key = None
        self._item_by_backend_value = {item.value: item for item in self._choice_items}
        self._sync_display_label()

    def _ensure_picker_items_loaded(self) -> tuple[ModelPickerItem, ...]:
        """Materialize popup/media-wall rows only when a picker popup needs them."""

        cache_key = (id(self._choice_items), len(self._choice_items))
        if self._picker_items_cache_key == cache_key:
            return self._picker_items
        cached_picker_items = _PICKER_ITEM_CACHE.get(cache_key)
        if cached_picker_items is None:
            self._picker_items = model_picker_items_from_rich_choice_items(
                self._choice_items
            )
            _PICKER_ITEM_CACHE[cache_key] = self._picker_items
        else:
            self._picker_items = cached_picker_items
        self._picker_items_cache_key = cache_key
        return self._picker_items

    def _choice_items_with_current_value(
        self,
        resolution: RichChoiceResolution,
    ) -> tuple[RichChoiceItem, ...]:
        """Append enriched metadata for a selected model absent from Comfy choices."""

        if (
            not self._current_value
            or any(item.value == self._current_value for item in resolution.items)
            or resolution.unavailable_reason is not None
            or not isinstance(self._choice_source, _ExtraRichChoiceSource)
        ):
            return resolution.items
        extra_item = self._choice_source.extra_item_for_value(self._current_value)
        if extra_item is None:
            return resolution.items
        return (*resolution.items, extra_item)

    def _sync_display_label(self) -> None:
        """Update the closed field with the best known label for the current value."""

        self._closed_display_label = self._display_label_for_value(self._current_value)
        self._surface.set_closed_banner_display(
            self._closed_banner_display_for_value(self._current_value)
        )
        self._sync_closed_surface_text()
        self._request_closed_banner_preload()
        self.updateGeometry()

    def _sync_closed_surface_text(self) -> None:
        """Apply the width-aware right-elided label used by the closed combo."""

        elided_label = self._elided_closed_display_label()
        self._set_surface_text(elided_label)
        set_fluent_tooltip_text(
            self._surface,
            self._closed_display_label
            if elided_label != self._closed_display_label
            else "",
        )
        if self._surface.isReadOnly():
            self._surface.setCursorPosition(0)
            self._surface.deselect()

    def _set_surface_text(self, text: str) -> None:
        """Assign surface text without treating it as user search input."""

        was_blocked = self._surface.blockSignals(True)
        self._surface.setText(text)
        self._surface.blockSignals(was_blocked)

    def _elided_closed_display_label(self) -> str:
        """Return the closed label elided on the right to fit the visible combo text."""

        if not self._closed_display_label:
            return ""
        text_width = self._closed_text_width()
        if text_width <= 0:
            return self._closed_display_label
        return cast(
            str,
            self._surface.fontMetrics().elidedText(
                self._closed_display_label,
                Qt.TextElideMode.ElideRight,
                text_width,
            ),
        )

    def _closed_text_width(self) -> int:
        """Return the closed combo text area width excluding padding and arrow space."""

        surface_width = cast(int, self._surface.width())
        if surface_width <= 0 or not self.isVisible() or not self._surface.isVisible():
            return 0
        return max(0, surface_width - _COMBO_HORIZONTAL_PADDING)

    def _display_label_for_value(self, value: str) -> str:
        """Return a friendly display label while preserving backend value semantics."""

        item = self._item_by_backend_value.get(value)
        if item is not None:
            if item.subtitle:
                return f"{item.title} - {item.subtitle}"
            return item.title
        return _fallback_display_label(value)

    def _closed_banner_display_for_value(
        self,
        value: str,
    ) -> ComboBannerDisplay | None:
        """Return banner decoration content for a selected backend value."""

        if self._closed_banner_decoration is None:
            return None
        item = self._item_by_backend_value.get(value)
        if item is None or not any(
            variant.role == BANNER_THUMBNAIL_ROLE for variant in item.thumbnail_variants
        ):
            return None
        return ComboBannerDisplay(
            title=item.title,
            subtitle=item.subtitle,
            banner_variants=_thumbnail_refs_from_all_model_variants(
                item.thumbnail_variants
            ),
            fallback_key=item.value,
            tooltip=self._display_label_for_value(value),
        )

    def _request_closed_banner_preload(self) -> None:
        """Queue the selected closed banner thumbnail outside paint."""

        preloader = self._thumbnail_preloader
        if preloader is None:
            return
        display = self._surface._closed_banner_display
        if display is None:
            return
        if not self.isVisible() or not self._surface.isVisible():
            return
        banner_size = self._surface._closed_banner_content_rect().size()
        if banner_size.width() <= 0 or banner_size.height() <= 0:
            return
        if preloader.install_pixmap_for_role_now(
            display.banner_variants,
            BANNER_THUMBNAIL_ROLE,
            banner_size,
            device_pixel_ratio=self._surface.devicePixelRatioF(),
        ):
            self._surface.update()
            return
        preloader.preload_pixmap_for_role(
            display.banner_variants,
            BANNER_THUMBNAIL_ROLE,
            banner_size,
            device_pixel_ratio=self._surface.devicePixelRatioF(),
        )

    def _handle_thumbnail_ready(self, storage_key: str) -> None:
        """Repaint the closed surface after selected banner cache publication."""

        _ = storage_key
        self._surface.update()


def _fallback_display_label(value: str) -> str:
    """Return a conservative local display label for an unknown backend value."""

    stripped_value = value.strip()
    if not stripped_value:
        return ""
    normalized_value = stripped_value.replace("\\", "/")
    name = PurePosixPath(normalized_value).name
    return _strip_supported_extension(name) or stripped_value


def _unavailable_resolution(
    previous_resolution: RichChoiceResolution | None,
    error: Exception,
) -> RichChoiceResolution:
    """Return an empty selector resolution after a fresh Backend refresh failure."""

    matched_kinds = (
        () if previous_resolution is None else previous_resolution.matched_kinds
    )
    reason = (
        "model selection unavailable: backend model catalog refresh failed "
        f"({type(error).__name__})"
    )
    return RichChoiceResolution(
        items=(),
        should_use_rich_picker=True,
        matched_kinds=matched_kinds,
        option_count=0
        if previous_resolution is None
        else previous_resolution.option_count,
        enriched_count=0,
        ambiguous_count=0,
        unmatched_count=0,
        reason=reason,
        unavailable_reason=reason,
    )


def _clamp_progress_percent(value: float | None) -> float | None:
    """Clamp optional progress to the visible progress range."""

    if value is None:
        return None
    return min(100.0, max(0.0, float(value)))


def _strip_supported_extension(value: str) -> str:
    """Strip the final model extension from one path while preserving separators."""

    extension = _extension_for_value(value)
    if extension in _SUPPORTED_MODEL_EXTENSIONS:
        return value[: -len(extension)]
    return value


def _extension_for_value(value: str) -> str:
    """Return the final file extension from one backend value."""

    windows_suffix = PureWindowsPath(value).suffix
    posix_suffix = PurePosixPath(value).suffix
    return (windows_suffix or posix_suffix).lower()


def _thumbnail_refs_from_all_model_variants(
    variants: tuple[ModelThumbnailVariant, ...],
) -> tuple[ThumbnailVariantReference, ...]:
    """Return thumbnail references for all roles, including banner variants."""

    return tuple(
        ThumbnailVariantReference(
            storage_key=variant.storage_key,
            size=variant.size,
            width=variant.width,
            height=variant.height,
            content_format=variant.content_format,
            byte_size=variant.byte_size,
            role=variant.role,
        )
        for variant in variants
    )


__all__ = ["ModelPickerField", "ModelPickerThumbnailPreloadRoute"]
