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

"""Render an editor-surface busy wash with animated loading text."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText
from sugarsubstitute_shared.presentation.localization import (
    apply_application_text,
    app_text,
)
from substitute.presentation.localization import (
    LocalizedLabel,
    LocalizedNativePushButton,
)

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from PySide6.QtGui import QHideEvent, QResizeEvent, QShowEvent
    from PySide6.QtWidgets import QProgressBar, QPushButton


class _FallbackSignal:
    """Provide the tiny signal surface needed by import-only tests."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Accept Qt-compatible signal construction."""

    def connect(self, _callback: object) -> None:
        """Ignore connections when Qt signals are unavailable."""

    def emit(self, *_args: object, **_kwargs: object) -> None:
        """Ignore emissions when Qt signals are unavailable."""


def _qt_signal() -> Any:
    """Return a Qt signal when available, otherwise a no-op signal."""

    try:
        from PySide6.QtCore import Signal
    except ImportError:  # pragma: no cover - test stubs without Qt signals
        return _FallbackSignal()
    return Signal()


if not TYPE_CHECKING:
    try:
        from qfluentwidgets import ProgressBar as QProgressBar
        from qfluentwidgets import PushButton as QPushButton
    except ImportError:  # pragma: no cover - test stubs without full Qt widgets
        try:
            from PySide6.QtWidgets import QProgressBar, QPushButton
        except ImportError:  # pragma: no cover - import-only Qt stubs

            class QProgressBar(QWidget):  # type: ignore[no-redef]
                """Fallback progress widget for import-only tests."""

                def setRange(self, _minimum: int, _maximum: int) -> None:
                    """Ignore range updates."""

                def setValue(self, _value: int) -> None:
                    """Ignore value updates."""

            class QPushButton(QWidget):  # type: ignore[no-redef]
                """Fallback button widget for import-only tests."""

                clicked = _FallbackSignal()

                def __init__(self, _text: str, parent: QWidget | None = None) -> None:
                    """Create a fallback widget."""

                    super().__init__(parent)


_ELLIPSIS_INTERVAL_MS = 400
_ELLIPSIS_STATES = ("", ".", "..", "...")
_ELLIPSIS_SLOT_TEXT = "..."


def _qt_application() -> object | None:
    """Return the active Qt application class when the binding exposes it."""

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return None
    return QApplication


class EditorBusyOverlay(QWidget):
    """Cover the editor work surface while cube loading temporarily blocks editing."""

    cancel_requested = _qt_signal()

    def __init__(self, parent: QWidget) -> None:
        """Create a hidden overlay that tracks the parent widget geometry."""

        super().__init__(parent)
        self._message: ApplicationText = app_text("Loading")
        self._ellipsis_index = 0
        self._cursor_overridden = False
        self._timer = QTimer(self)
        self._timer.setInterval(_ELLIPSIS_INTERVAL_MS)
        self._timer.timeout.connect(self._advance_ellipsis)

        self.setObjectName("EditorBusyOverlay")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(
            """
            QWidget#EditorBusyOverlay {
                background-color: rgba(0, 0, 0, 165);
                border: none;
            }
            QLabel#EditorBusyOverlayMessageLabel,
            QLabel#EditorBusyOverlayEllipsisLabel {
                color: rgba(255, 255, 255, 230);
                background: transparent;
                border: none;
                font-size: 18px;
                font-weight: 600;
            }
            """
        )

        self._message_label = QLabel(self)
        self._message_label.setObjectName("EditorBusyOverlayMessageLabel")
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._ellipsis_label = QLabel(self)
        self._ellipsis_label.setObjectName("EditorBusyOverlayEllipsisLabel")
        self._ellipsis_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._download_panel = QWidget(self)
        self._download_panel.setObjectName("EditorBusyOverlayDownloadPanel")
        self._download_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._download_panel.setStyleSheet(
            """
            QWidget#EditorBusyOverlayDownloadPanel {
                background-color: rgba(24, 24, 24, 238);
                border: 1px solid rgba(255, 255, 255, 42);
                border-radius: 8px;
            }
            """
        )
        self._download_title = LocalizedLabel(
            app_text("Downloading model"), self._download_panel
        )
        self._download_message = LocalizedLabel(
            app_text("Downloading the model this recipe needs."),
            self._download_panel,
        )
        self._download_detail = LocalizedLabel(
            app_text("Starting download..."), self._download_panel
        )
        self._download_progress = QProgressBar(self._download_panel)
        self._download_progress.setRange(0, 0)
        self._download_cancel = LocalizedNativePushButton(
            app_text("Cancel"), self._download_panel
        )
        self._download_cancel.clicked.connect(self.cancel_requested.emit)
        download_buttons = QHBoxLayout()
        add_stretch = getattr(download_buttons, "addStretch", None)
        if callable(add_stretch):
            add_stretch(1)
        download_buttons.addWidget(self._download_cancel)
        download_layout = QVBoxLayout(self._download_panel)
        download_layout.setContentsMargins(22, 20, 22, 18)
        download_layout.setSpacing(10)
        download_layout.addWidget(self._download_title)
        download_layout.addWidget(self._download_message)
        download_layout.addWidget(self._download_progress)
        download_layout.addWidget(self._download_detail)
        download_layout.addLayout(download_buttons)
        self._download_panel.hide()

        parent.installEventFilter(self)
        self._sync_geometry()
        self.hide()

    def show_loading(self, message: ApplicationText = app_text("Loading")) -> None:
        """Show the busy wash and start animating the loading ellipses."""

        self._message = message if message.strip() else app_text("Loading")
        self._ellipsis_index = 0
        self._refresh_label()
        self._sync_geometry()
        self.raise_()
        self._download_panel.hide()
        self._message_label.show()
        self._ellipsis_label.show()
        self.show()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self._ensure_wait_cursor()
        if not self._timer.isActive():
            self._timer.start()

    def show_download_progress(
        self,
        *,
        title: ApplicationText,
        message: ApplicationText,
        detail: ApplicationText,
        progress_per_mille: int | None,
        cancel_enabled: bool = True,
    ) -> None:
        """Show workflow-scoped model-download progress without a floating dialog."""

        self._timer.stop()
        self._message_label.hide()
        self._ellipsis_label.hide()
        self._restore_wait_cursor()
        self._download_title.setText(title)
        self._download_message.setText(message)
        self._download_detail.setText(detail)
        self._download_cancel.setEnabled(cancel_enabled)
        if progress_per_mille is None:
            self._download_progress.setRange(0, 0)
        else:
            self._download_progress.setRange(0, 1000)
            self._download_progress.setValue(min(1000, max(0, progress_per_mille)))
        self._sync_geometry()
        self._download_panel.show()
        self.raise_()
        self.show()

    def hide_loading(self) -> None:
        """Hide the busy wash and stop the ellipsis animation."""

        self._timer.stop()
        self._ellipsis_index = 0
        self._refresh_label()
        self._restore_wait_cursor()
        self._download_panel.hide()
        self.hide()

    def is_loading(self) -> bool:
        """Return whether the busy overlay is currently visible and active."""

        return self.isVisible()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Track parent resizes so the wash always covers the editor work surface."""

        if watched is self.parent() and event.type() == QEvent.Type.Resize:
            self._sync_geometry()
        return super().eventFilter(watched, event)

    def showEvent(self, event: QShowEvent) -> None:
        """Synchronize geometry whenever the overlay becomes visible."""

        self._sync_geometry()
        super().showEvent(event)

    def hideEvent(self, event: QHideEvent) -> None:
        """Restore the application cursor if the overlay is hidden externally."""

        self._restore_wait_cursor()
        super().hideEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep loading labels anchored around the overlay center after resize."""

        super().resizeEvent(event)
        self._position_labels()
        self._position_download_panel()

    def _advance_ellipsis(self) -> None:
        """Advance the loading ellipsis animation by one frame."""

        self._ellipsis_index = (self._ellipsis_index + 1) % len(_ELLIPSIS_STATES)
        self._refresh_label()

    def _refresh_label(self) -> None:
        """Apply the current base message and ellipsis frame to separate labels."""

        apply_application_text(self._message_label, self._message)
        self._ellipsis_label.setText(_ELLIPSIS_STATES[self._ellipsis_index])
        self._position_labels()

    def _sync_geometry(self) -> None:
        """Resize the overlay to exactly cover its parent widget."""

        parent = self.parentWidget()
        if parent is None:
            return
        self.setGeometry(parent.rect())
        self._position_labels()
        self._position_download_panel()

    def _position_labels(self) -> None:
        """Center the base message and reserve fixed space for animated ellipses."""

        message_hint = self._message_label.sizeHint()
        message_width = message_hint.width()
        message_height = message_hint.height()
        ellipsis_width = self._ellipsis_label.fontMetrics().horizontalAdvance(
            _ELLIPSIS_SLOT_TEXT
        )
        ellipsis_height = max(message_height, self._ellipsis_label.sizeHint().height())
        center_x = self.width() // 2
        center_y = self.height() // 2
        message_x = center_x - (message_width // 2)
        message_y = center_y - (message_height // 2)
        self._message_label.setGeometry(
            message_x,
            message_y,
            message_width,
            message_height,
        )
        self._ellipsis_label.setGeometry(
            message_x + message_width,
            center_y - (ellipsis_height // 2),
            ellipsis_width,
            ellipsis_height,
        )

    def _position_download_panel(self) -> None:
        """Center the download panel while keeping it inside the overlay bounds."""

        width = min(520, max(360, self.width() - 48))
        size_hint = getattr(self._download_panel, "sizeHint", None)
        height = size_hint().height() if callable(size_hint) else 180
        x = max(24, (self.width() - width) // 2)
        y = max(24, (self.height() - height) // 2)
        self._download_panel.setGeometry(x, y, width, height)

    def _ensure_wait_cursor(self) -> None:
        """Push one application-wide wait cursor while editor loading is active."""

        if self._cursor_overridden:
            return
        application = _qt_application()
        set_override_cursor = getattr(application, "setOverrideCursor", None)
        if not callable(set_override_cursor):
            return
        set_override_cursor(Qt.CursorShape.WaitCursor)
        self._cursor_overridden = True

    def _restore_wait_cursor(self) -> None:
        """Restore the wait cursor override pushed by this overlay."""

        if not self._cursor_overridden:
            return
        application = _qt_application()
        restore_override_cursor = getattr(application, "restoreOverrideCursor", None)
        if callable(restore_override_cursor):
            restore_override_cursor()
        self._cursor_overridden = False


__all__ = ["EditorBusyOverlay"]
