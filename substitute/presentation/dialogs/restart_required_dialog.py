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

"""Render pending restart requirements in a shared confirmation modal."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedPrimaryPushButton,
    LocalizedPushButton,
    LocalizedSubtitleLabel,
)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    MessageBoxBase,
)
from shiboken6 import isValid

from substitute.application.restart_requirements import RestartRequirementSnapshot
from substitute.presentation.shell.chrome_style import (
    connect_theme_refresh,
    winui_card_border_color,
    winui_card_fill_color,
)

_FALLBACK_PARENT: QWidget | None = None
_DIALOG_WIDTH = 640
_DIALOG_MAX_HEIGHT_MARGIN = 48
_CONTENT_TOP_MARGIN = 24
_CONTENT_SIDE_MARGIN = 24
_CONTENT_BOTTOM_MARGIN = 16
_CONTENT_SPACING = 12
_ACTION_BUTTON_HEIGHT = 32
_ACTION_BUTTON_MINIMUM_WIDTH = 128


class RestartRequiredDialog(MessageBoxBase):  # type: ignore[misc]
    """Show the restart cart and return whether the user wants to restart now."""

    def __init__(
        self,
        *,
        snapshot: RestartRequirementSnapshot,
        parent: object | None = None,
    ) -> None:
        """Build the pending restart requirements modal."""

        parent_widget = _resolve_parent(parent)
        super().__init__(parent_widget)
        self._snapshot = snapshot
        self._restart_now_selected = False
        self._dialog_max_height = _dialog_max_height(parent_widget)
        self.setClosableOnMaskClicked(False)
        self.setModal(True)
        self.widget.setMinimumWidth(_DIALOG_WIDTH)
        self.widget.setMaximumWidth(_DIALOG_WIDTH)
        self.widget.setMaximumHeight(self._dialog_max_height)
        self.viewLayout.setContentsMargins(
            _CONTENT_SIDE_MARGIN,
            _CONTENT_TOP_MARGIN,
            _CONTENT_SIDE_MARGIN,
            _CONTENT_BOTTOM_MARGIN,
        )
        self.viewLayout.setSpacing(0)

        self._build_body_container()
        self._build_header()
        self._build_items()
        self._build_actions()
        self._sync_body_height()
        self._apply_theme()
        connect_theme_refresh(self, self._apply_theme)

    @property
    def snapshot(self) -> RestartRequirementSnapshot:
        """Return the snapshot rendered by this dialog."""

        return self._snapshot

    def item_labels(self) -> tuple[str, ...]:
        """Return labels for the pending restart items shown in the dialog."""

        return tuple(item.label for item in self._snapshot.items)

    def restart_now_selected(self) -> bool:
        """Return whether the user selected the restart action."""

        return self._restart_now_selected

    def _build_header(self) -> None:
        """Create the modal title and explanatory copy."""

        self.title_label = LocalizedSubtitleLabel(
            app_text("Restart required"), self.widget
        )
        self.body_label = LocalizedBodyLabel(
            app_text("These changes will apply after restart."),
            self.widget,
        )
        self.body_label.setWordWrap(True)
        self._body_layout.addWidget(self.title_label)
        self._body_layout.addWidget(self.body_label)

    def _build_items(self) -> None:
        """Create the restart item list."""

        self.items_container = QWidget(self.widget)
        self.items_container.setObjectName("RestartRequiredItems")
        layout = QVBoxLayout(self.items_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.item_rows: list[QFrame] = []
        for item in self._snapshot.items:
            row = QFrame(self.items_container)
            row.setObjectName("RestartRequiredItemRow")
            row.setFrameShape(QFrame.Shape.NoFrame)
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(12, 10, 12, 10)
            row_layout.setSpacing(2)
            label = BodyLabel(item.label, row)
            label.setObjectName("RestartRequiredItemLabel")
            label.setWordWrap(True)
            row_layout.addWidget(label)
            if item.detail:
                detail = CaptionLabel(item.detail, row)
                detail.setObjectName("RestartRequiredItemDetail")
                detail.setWordWrap(True)
                row_layout.addWidget(detail)
            row.setStyleSheet(
                "QFrame#RestartRequiredItemRow {"
                "background: rgba(128, 128, 128, 26);"
                "border: 1px solid rgba(128, 128, 128, 58);"
                "border-radius: 6px;"
                "}"
            )
            self.item_rows.append(row)
            layout.addWidget(row)
        self._body_layout.addWidget(self.items_container)

    def _build_actions(self) -> None:
        """Configure modal actions."""

        self.buttonGroup.show()
        self.buttonGroup.setFixedHeight(68)
        _clear_layout(self.buttonLayout)
        self.hideYesButton()
        self.hideCancelButton()
        self.buttonLayout.setContentsMargins(24, 16, 24, 16)
        self.buttonLayout.setSpacing(12)
        self.buttonLayout.addStretch(1)

        self.later_button = LocalizedPushButton(app_text("Later"), self.buttonGroup)
        self.later_button.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        self.later_button.setMinimumWidth(_ACTION_BUTTON_MINIMUM_WIDTH)
        self.later_button.clicked.connect(self._reject_restart)
        self.buttonLayout.addWidget(
            self.later_button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        self.restart_now_button = LocalizedPrimaryPushButton(
            app_text("Restart now"), self.buttonGroup
        )
        self.restart_now_button.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        self.restart_now_button.setMinimumWidth(_ACTION_BUTTON_MINIMUM_WIDTH)
        self.restart_now_button.clicked.connect(self._accept_restart)
        self.buttonLayout.addWidget(
            self.restart_now_button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

    def _build_body_container(self) -> None:
        """Create the scrollable body area above the fixed footer."""

        self._body_scroll_area = QScrollArea(self.widget)
        self._body_scroll_area.setWidgetResizable(True)
        self._body_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._body_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._body_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._body_scroll_area.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
            "QScrollArea > QWidget { background: transparent; }"
        )
        self._body_scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._body_widget = QWidget(self._body_scroll_area)
        self._body_layout = QVBoxLayout(self._body_widget)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(_CONTENT_SPACING)
        self._body_scroll_area.setWidget(self._body_widget)
        self.viewLayout.addWidget(self._body_scroll_area)

    def _sync_body_height(self) -> None:
        """Size the scroll body naturally unless parent height forces scrolling."""

        self._body_layout.activate()
        self._body_widget.adjustSize()
        content_height = self._body_widget.sizeHint().height()
        margins = self.viewLayout.contentsMargins()
        maximum_body_height = max(
            1,
            self._dialog_max_height
            - self.buttonGroup.height()
            - margins.top()
            - margins.bottom(),
        )
        needs_scroll = content_height > maximum_body_height
        self._body_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if needs_scroll
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._body_scroll_area.setFixedHeight(
            maximum_body_height
            if needs_scroll
            else min(content_height + 2, maximum_body_height)
        )

    def _apply_theme(self) -> None:
        """Refresh WinUI-style restart item colors for the current theme."""

        fill = _rgba_string(winui_card_fill_color())
        border = _rgba_string(winui_card_border_color())
        for row in self.item_rows:
            row.setStyleSheet(
                "QFrame#RestartRequiredItemRow {"
                f"background: {fill};"
                f"border: 1px solid {border};"
                "border-radius: 8px;"
                "}"
            )

    def _accept_restart(self) -> None:
        """Accept the dialog with a normal Qt accepted result."""

        self._restart_now_selected = True
        QDialog.accept(self)

    def _reject_restart(self) -> None:
        """Reject the dialog with a normal Qt rejected result."""

        self._restart_now_selected = False
        QDialog.reject(self)


def _resolve_parent(parent: object | None) -> QWidget:
    """Return a QWidget parent because qfluent mask dialogs require one."""

    if isinstance(parent, QWidget) and isValid(parent):
        return parent
    active_window = QApplication.activeWindow()
    if isinstance(active_window, QWidget) and isValid(active_window):
        return active_window
    global _FALLBACK_PARENT
    if _FALLBACK_PARENT is None or not isValid(_FALLBACK_PARENT):
        _FALLBACK_PARENT = QWidget()
        _FALLBACK_PARENT.resize(1024, 768)
    return _FALLBACK_PARENT


def _dialog_max_height(parent: QWidget) -> int:
    """Return a modal height cap that stays inside the owner window."""

    return max(320, parent.height() - _DIALOG_MAX_HEIGHT_MARGIN)


def _clear_layout(layout: QLayout) -> None:
    """Remove default qfluent footer widgets before building custom actions."""

    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)


def _rgba_string(color: tuple[int, int, int, int]) -> str:
    """Return a Qt stylesheet rgba value from an RGBA tuple."""

    red, green, blue, alpha = color
    return f"rgba({red}, {green}, {blue}, {alpha})"


__all__ = ["RestartRequiredDialog"]
