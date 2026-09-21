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

"""Own native inline text editing for projected emphasis and LoRA weights."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import (
    QEvent,
    QObject,
    QRectF,
    QRegularExpression,
    QSignalBlocker,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QContextMenuEvent,
    QFocusEvent,
    QFont,
    QFontMetricsF,
    QKeyEvent,
    QMouseEvent,
    QRegularExpressionValidator,
)
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget
from substitute.presentation.widgets.menu_model import (
    MenuEntry,
    MenuItem,
    MenuModel,
    MenuSeparator,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer

from ..core.projection.document import PromptProjectionDocument
from ..core.projection.tokens import PromptProjectionToken, PromptProjectionTokenKind
from .session import PromptProjectionSession
from .inline_renderer_typography import inline_weight_font


class PromptExactWeightEditorHost(Protocol):
    """Provide prepared projection geometry and derived edit-state publication."""

    _session: PromptProjectionSession

    def viewport(self) -> QWidget:
        """Return the viewport that owns the inline input's lifetime."""

    def font(self) -> QFont:
        """Return the font used by the projected prompt."""

    def projection_document(self) -> PromptProjectionDocument:
        """Return the current prepared token projection."""

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the authoritative viewport-local weight bounds."""


class PromptExactWeightEditor(QLineEdit):
    """Keep text, selection, caret, clipboard, and undo under Qt's input owner."""

    commit_requested = Signal()
    cancel_requested = Signal()

    def __init__(
        self,
        host: PromptExactWeightEditorHost,
        *,
        rebuild_projection: Callable[[], None],
    ) -> None:
        """Mount one native input whose geometry derives from the token projection."""

        super().__init__(host.viewport())
        self._host = host
        self._rebuild_projection = rebuild_projection
        self._publishing = False
        self.setObjectName("PromptExactWeightEditor")
        self.setFrame(False)
        self.setTextMargins(0, 0, 0, 0)
        self.setValidator(
            QRegularExpressionValidator(
                QRegularExpression(r"-?\d*(?:\.\d{0,2})?"), self
            )
        )
        self.setStyleSheet(
            "QLineEdit#PromptExactWeightEditor { background: transparent; border: none; padding: 0px; }"
        )
        self.textEdited.connect(self._publish_buffer)
        self.cursorPositionChanged.connect(self._publish_buffer)
        self.selectionChanged.connect(self._publish_buffer)
        host.viewport().installEventFilter(self)
        self.hide()

    @property
    def active(self) -> bool:
        """Return whether the projection still identifies this edit session."""

        return self._host._session.exact_weight_edit is not None

    def start(self, token: PromptProjectionToken) -> None:
        """Select the rendered value without changing the authoritative prompt."""

        if (
            token.kind
            not in {PromptProjectionTokenKind.EMPHASIS, PromptProjectionTokenKind.LORA}
            or token.value_text is None
            or token.content_start is None
            or token.content_end is None
        ):
            return
        self.setFont(inline_weight_font(self._host.font()))
        rect = self._host.token_weight_text_rect(token)
        slot_width = (
            rect.width()
            if rect is not None
            else QFontMetricsF(self.font()).horizontalAdvance(token.value_text)
        )
        with QSignalBlocker(self):
            self.setText(token.value_text)
            self.selectAll()
        self._host._session.start_exact_weight_edit(
            token_id=token.token_id,
            synthetic=token.synthetic,
            outer_start=token.source_start,
            outer_end=token.source_end,
            content_start=token.content_start,
            content_end=token.content_end,
            original_value_text=token.value_text,
            buffer_text=self.text(),
            slot_width=slot_width,
            caret_index=self.cursorPosition(),
            select_all=True,
        )
        self._rebuild_projection()
        self.refresh_geometry()
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.MouseFocusReason)

    def update_buffer(
        self, *, buffer_text: str, caret_index: int, select_all: bool
    ) -> None:
        """Adopt an explicit initial caret handoff through the native input owner."""

        if not self.active:
            return
        with QSignalBlocker(self):
            if self.text() != buffer_text:
                self.setText(buffer_text)
            self.setCursorPosition(caret_index)
            if select_all:
                self.selectAll()
        self._publish_buffer()

    def clear_edit(self) -> None:
        """End the transient edit before hiding can trigger focus delivery."""

        if not self.active:
            self.hide()
            return
        self._host._session.clear_exact_weight_edit()
        self.hide()
        self._rebuild_projection()

    def token(self) -> PromptProjectionToken | None:
        """Resolve the edited token from its source identity after projection changes."""

        state = self._host._session.exact_weight_edit
        if state is None:
            return None
        document = self._host.projection_document()
        token = document.token_by_id(state.token_id)
        if token is not None:
            return token
        return next(
            (
                item
                for item in document.tokens
                if item.kind
                in {PromptProjectionTokenKind.EMPHASIS, PromptProjectionTokenKind.LORA}
                and item.content_start == state.content_start
                and item.content_end == state.content_end
            ),
            None,
        )

    def refresh_geometry(self) -> None:
        """Fit the native input to current prepared token geometry."""

        if not self.active:
            self.hide()
            return
        token = self.token()
        rect = self._host.token_weight_text_rect(token) if token is not None else None
        if rect is None:
            self.hide()
            return
        self.setGeometry(rect.adjusted(-2, -1, 2, 1).toAlignedRect())
        self.raise_()

    def handle_key(self, event: QKeyEvent) -> bool:
        """Route host key delivery to the same native input owner."""

        if not self.active:
            return False
        QApplication.sendEvent(self, event)
        return True

    def handle_viewport_mouse(self, event: QMouseEvent) -> None:
        """Preserve native mouse selection for events delivered through the viewport."""

        if not self.active:
            return
        local_position = self.mapFrom(self._host.viewport(), event.position())
        forwarded = QMouseEvent(
            event.type(),
            local_position,
            event.globalPosition(),
            event.button(),
            event.buttons(),
            event.modifiers(),
            event.pointingDevice(),
        )
        QApplication.sendEvent(self, forwarded)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Keep exact editing keys local and publish explicit finish actions."""

        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.commit_requested.emit()
            self._focus_surface()
        elif event.key() == Qt.Key.Key_Escape:
            self.cancel_requested.emit()
            self._focus_surface()
        elif event.key() == Qt.Key.Key_Space and event.text() == " ":
            self.commit_requested.emit()
            self._focus_surface()
            QApplication.sendEvent(self._host.viewport(), event)
        else:
            super().keyPressEvent(event)
        event.accept()

    def _focus_surface(self) -> None:
        """Return explicit keyboard completion to the owning prompt surface."""

        surface = self._host.viewport().parentWidget()
        if surface is not None:
            surface.setFocus(Qt.FocusReason.OtherFocusReason)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Finalize a value when focus leaves the input and its context menu."""

        super().focusOutEvent(event)
        if self.active and event.reason() != Qt.FocusReason.PopupFocusReason:
            self.commit_requested.emit()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Expose the application's Fluent text actions for the native input."""

        native_actions = self.createStandardContextMenu()
        entries: list[MenuEntry] = []
        for index, action in enumerate(native_actions.actions()):
            if action.isSeparator():
                entries.append(MenuSeparator())
            else:
                label, _, shortcut = action.text().partition("\t")
                entries.append(
                    MenuItem(
                        action_id=f"native-edit-{index}",
                        label=re.sub(r"&(.)", r"\1", label),
                        callback=action.trigger,
                        enabled=action.isEnabled(),
                        shortcut=shortcut or None,
                        icon=action.icon(),
                    )
                )
        menu = QFluentMenuRenderer(parent=self).render(
            MenuModel(entries=tuple(entries))
        )
        native_actions.setParent(menu)
        menu.closedSignal.connect(menu.deleteLater)
        menu.exec(event.globalPos(), ani=True)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Follow viewport geometry without owning a second token layout."""

        if watched is self._host.viewport() and event.type() in {
            QEvent.Type.Paint,
            QEvent.Type.Resize,
            QEvent.Type.Move,
        }:
            self.refresh_geometry()
        return super().eventFilter(watched, event)

    def _publish_buffer(self) -> None:
        """Publish a derived projection snapshot after native input changes."""

        if self._publishing or not self.active:
            return
        state = self._host._session.exact_weight_edit
        select_all = self.hasSelectedText() and self.selectedText() == self.text()
        if state is not None and (
            state.buffer_text == self.text()
            and state.caret_index == self.cursorPosition()
            and state.select_all == select_all
        ):
            return
        self._publishing = True
        try:
            self._host._session.update_exact_weight_edit(
                buffer_text=self.text(),
                caret_index=self.cursorPosition(),
                select_all=select_all,
            )
            self._rebuild_projection()
            self.refresh_geometry()
        finally:
            self._publishing = False
