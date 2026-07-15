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

"""Render the SugarSubstitute GPLv3 license reader modal."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QLayout, QSizePolicy, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    MessageBoxBase,
    PrimaryPushButton,
    TextBrowser,
)
from shiboken6 import isValid

_DIALOG_MAX_WIDTH = 780
_DIALOG_MIN_WIDTH = 320
_DIALOG_PARENT_WIDTH_MARGIN = 64
_DIALOG_WIDTH_STARVED_MARGIN = 32
_DIALOG_MAX_HEIGHT = 760
_DIALOG_MIN_HEIGHT = 320
_DIALOG_PARENT_HEIGHT_RATIO = 0.82
_LICENSE_BROWSER_MIN_HEIGHT = 180
_CONTENT_SIDE_MARGIN = 24
_CONTENT_TOP_MARGIN = 24
_CONTENT_BOTTOM_MARGIN = 16
_FOOTER_HEIGHT = 68
_ACTION_BUTTON_HEIGHT = 32
_CLOSE_BUTTON_MINIMUM_WIDTH = 88
_FALLBACK_PARENT: QWidget | None = None


class LicenseDialog(MessageBoxBase):  # type: ignore[misc]
    """Show a read-only GPLv3 license text in the existing modal shell."""

    def __init__(
        self,
        *,
        license_html: str,
        parent: QWidget | None = None,
    ) -> None:
        """Create a parent-sized modal license reader."""

        parent_widget = _resolve_parent(parent)
        super().__init__(parent_widget)
        self.setObjectName("SugarSubstituteLicenseDialog")
        self.setModal(True)
        self.setClosableOnMaskClicked(True)

        dialog_size = _dialog_size(parent_widget)
        self.widget.setMinimumWidth(dialog_size.width())
        self.widget.setMaximumWidth(dialog_size.width())
        self.widget.setMinimumHeight(dialog_size.height())
        self.widget.setMaximumHeight(dialog_size.height())
        self.viewLayout.setContentsMargins(
            _CONTENT_SIDE_MARGIN,
            _CONTENT_TOP_MARGIN,
            _CONTENT_SIDE_MARGIN,
            _CONTENT_BOTTOM_MARGIN,
        )
        self.viewLayout.setSpacing(0)

        self._build_content(license_html, dialog_size.height())
        self._build_actions()

    def _build_content(
        self,
        license_html: str,
        dialog_height: int,
    ) -> None:
        """Create the scrollable license body."""

        self._license_browser = TextBrowser(self.widget)
        self._license_browser.setObjectName("LicenseDialogText")
        self._license_browser.setHtml(_license_document_html(license_html))
        self._license_browser.setOpenExternalLinks(False)
        self._license_browser.setReadOnly(True)
        license_browser_height = _license_browser_height(dialog_height)
        self._license_browser.setMinimumHeight(license_browser_height)
        self._license_browser.setMaximumHeight(license_browser_height)
        self._license_browser.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.viewLayout.addWidget(self._license_browser)

    def _build_actions(self) -> None:
        """Create the single close action in qfluent's modal footer."""

        self.buttonGroup.show()
        self.buttonGroup.setFixedHeight(_FOOTER_HEIGHT)
        self.yesButton.hide()
        self.cancelButton.hide()
        _clear_button_layout(self.buttonLayout)
        self.buttonLayout.setContentsMargins(24, 16, 24, 16)
        self.buttonLayout.setSpacing(12)
        self.buttonLayout.addStretch(1)

        self._close_button = PrimaryPushButton("Close", self.buttonGroup)
        self._close_button.setObjectName("LicenseDialogCloseButton")
        self._close_button.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        self._close_button.setMinimumWidth(_CLOSE_BUTTON_MINIMUM_WIDTH)
        self._close_button.clicked.connect(self.accept)
        self.buttonLayout.addWidget(
            self._close_button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )


def _resolve_parent(parent: QWidget | None) -> QWidget:
    """Return a QWidget parent accepted by qfluent's modal mask."""

    if parent is not None and isValid(parent):
        return parent
    active_window = QApplication.activeWindow()
    if isinstance(active_window, QWidget) and isValid(active_window):
        return active_window
    global _FALLBACK_PARENT  # noqa: PLW0603
    if _FALLBACK_PARENT is None or not isValid(_FALLBACK_PARENT):
        _FALLBACK_PARENT = QWidget()
        _FALLBACK_PARENT.resize(900, 700)
    return _FALLBACK_PARENT


def _dialog_size(parent: QWidget) -> QSize:
    """Return a comfortable modal size constrained by the parent window."""

    parent_size = parent.size()
    parent_width = max(parent_size.width(), _DIALOG_MIN_WIDTH)
    parent_height = max(parent_size.height(), _DIALOG_MIN_HEIGHT)
    width_margin = (
        _DIALOG_WIDTH_STARVED_MARGIN
        if parent_width < _DIALOG_MAX_WIDTH + _DIALOG_PARENT_WIDTH_MARGIN
        else _DIALOG_PARENT_WIDTH_MARGIN
    )
    width = min(
        _DIALOG_MAX_WIDTH,
        max(_DIALOG_MIN_WIDTH, parent_width - width_margin),
    )
    height = min(
        _DIALOG_MAX_HEIGHT,
        max(_DIALOG_MIN_HEIGHT, int(parent_height * _DIALOG_PARENT_HEIGHT_RATIO)),
    )
    return QSize(width, height)


def _license_browser_height(dialog_height: int) -> int:
    """Return a body height that leaves room for the modal footer."""

    reserved_height = _CONTENT_TOP_MARGIN + _CONTENT_BOTTOM_MARGIN + _FOOTER_HEIGHT
    return max(_LICENSE_BROWSER_MIN_HEIGHT, dialog_height - reserved_height)


def _license_document_html(license_html: str) -> str:
    """Return GPLv3 HTML styled for the modal reader."""

    return (
        "<style>"
        "body { font-family: 'Segoe UI', sans-serif; font-size: 13px; "
        "line-height: 1.45; } "
        "h3 { font-size: 17px; margin-top: 0; } "
        "p { margin: 0 0 12px 0; } "
        "ul { margin-top: 0; } "
        "pre { white-space: pre-wrap; }"
        "</style>"
        f"{license_html}"
    )


def _clear_button_layout(layout: QLayout) -> None:
    """Hide and remove qfluent's default footer widgets."""

    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.hide()
        nested_layout = item.layout()
        if nested_layout is not None:
            _clear_button_layout(nested_layout)


__all__ = ["LicenseDialog"]
