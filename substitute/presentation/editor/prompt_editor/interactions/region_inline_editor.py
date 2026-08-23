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

"""Own the borderless in-place editor for authored regional names."""

from __future__ import annotations

from collections.abc import Callable
from math import ceil

from PySide6.QtCore import (
    QEvent,
    QObject,
    QRect,
    QRegularExpression,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import QFocusEvent, QKeyEvent, QPalette, QRegularExpressionValidator
from PySide6.QtWidgets import QLineEdit, QWidget

from substitute.presentation.editor.prompt_editor.projection.region_chrome_state import (
    PromptRegionChromeEditTarget,
)

REGION_NAME_INLINE_EDITOR_OBJECT_NAME = "promptRegionNameInlineEditor"

PromptRegionEditTargetProvider = Callable[[int], PromptRegionChromeEditTarget | None]
PromptRegionInlineCommit = Callable[[str], bool]
PromptRegionInlineDraftSink = Callable[[int, str], None]


class _RegionNameLineEdit(QLineEdit):
    """Expose explicit accept and cancel intent around native text editing."""

    acceptRequested = Signal()
    cancelRequested = Signal()
    focusCommitRequested = Signal()
    focusAcquired = Signal()

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        """Record the first native focus acquisition for the active edit session."""

        super().focusInEvent(event)
        self.focusAcquired.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Cancel on Escape and preserve native editing for every other key."""

        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            event.accept()
            self.acceptRequested.emit()
            return
        if event.key() == Qt.Key.Key_Escape:
            event.accept()
            self.cancelRequested.emit()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        """Commit through the owner when focus leaves the inline editor."""

        super().focusOutEvent(event)
        self.focusCommitRequested.emit()


class PromptRegionInlineEditor(QObject):
    """Coordinate one native text editor with projection-owned row geometry."""

    def __init__(
        self,
        *,
        viewport: QWidget,
        target_provider: PromptRegionEditTargetProvider,
        scroll_offset: Callable[[], float],
        active_region_sink: Callable[[int | None], None],
        draft_sink: PromptRegionInlineDraftSink,
    ) -> None:
        """Create one reusable editor attached to the projection viewport."""

        super().__init__(viewport)
        self._viewport = viewport
        self._target_provider = target_provider
        self._scroll_offset = scroll_offset
        self._active_region_sink = active_region_sink
        self._draft_sink = draft_sink
        self._region_index: int | None = None
        self._commit: PromptRegionInlineCommit | None = None
        self._finishing = False
        self._focus_has_been_acquired = False
        self._editor = _RegionNameLineEdit(viewport)
        self._editor.setObjectName(REGION_NAME_INLINE_EDITOR_OBJECT_NAME)
        self._editor.setFrame(False)
        self._editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._editor.setAutoFillBackground(True)
        self._editor.setTextMargins(0, 0, 0, 0)
        self._editor.setValidator(
            _region_name_validator(self._editor),
        )
        self._editor.acceptRequested.connect(self.commit)
        self._editor.cancelRequested.connect(self.cancel)
        self._editor.focusCommitRequested.connect(self._commit_if_focus_remains_lost)
        self._editor.focusAcquired.connect(self._record_focus_acquisition)
        self._editor.textChanged.connect(self._handle_text_changed)
        self._editor.hide()
        viewport.installEventFilter(self)

    @property
    def editor(self) -> QLineEdit:
        """Return the mounted editor for accessibility and deterministic testing."""

        return self._editor

    @property
    def active(self) -> bool:
        """Return whether one separator currently owns the editor."""

        return self._region_index is not None

    def begin(
        self,
        *,
        region_index: int,
        current_name: str,
        commit: PromptRegionInlineCommit,
    ) -> bool:
        """Begin selected in-place editing for one prepared separator row."""

        target = self._target_provider(region_index)
        if target is None:
            return False
        if self.active:
            self.commit()
        self._region_index = region_index
        self._commit = commit
        self._focus_has_been_acquired = False
        self._active_region_sink(region_index)
        self._apply_target_palette(target)
        self._editor.setFont(target.font)
        self._editor.setText(current_name)
        self._handle_text_changed(current_name)
        self._editor.selectAll()
        self.reposition()
        self._editor.show()
        self._editor.raise_()
        self._editor.setFocus(Qt.FocusReason.MouseFocusReason)
        return True

    def reposition(self) -> None:
        """Keep the active editor centered on current projection geometry."""

        region_index = self._region_index
        if region_index is None:
            return
        target = self._target_provider(region_index)
        if target is None:
            self.cancel()
            return
        height = max(1, ceil(target.row_height))
        left = round(target.center.x() - target.width / 2.0)
        top = round(target.center.y() - self._scroll_offset() - height / 2.0)
        geometry = self._editor.geometry()
        next_geometry = QRect(left, top, ceil(target.width), height)
        if geometry != next_geometry:
            self._editor.setGeometry(next_geometry)

    def _handle_text_changed(self, text: str) -> None:
        """Publish draft geometry before repositioning the native editor."""

        region_index = self._region_index
        if region_index is None:
            return
        self._draft_sink(region_index, text)
        self.reposition()

    def commit(self) -> None:
        """Commit the current authored name and close the inline editor."""

        if self._finishing or not self.active:
            return
        commit = self._commit
        authored_name = self._editor.text()
        if commit is None or not commit(authored_name):
            return
        self._finish()

    def _commit_if_focus_remains_lost(self) -> None:
        """Commit only when the next Qt turn confirms a durable focus departure."""

        QTimer.singleShot(0, self._commit_after_focus_transition)

    def _record_focus_acquisition(self) -> None:
        """Permit focus-loss commits only after this edit session received focus."""

        if self.active:
            self._focus_has_been_acquired = True

    def _commit_after_focus_transition(self) -> None:
        """Preserve an active inline draft across transient viewport focus churn."""

        if (
            not self.active
            or not self._focus_has_been_acquired
            or self._editor.hasFocus()
        ):
            return
        self.commit()

    def cancel(self) -> None:
        """Close the editor without mutating source text."""

        if not self.active:
            return
        self._finish()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Follow viewport paint and resize changes only while editing."""

        if (
            watched is self._viewport
            and self.active
            and event.type()
            in {
                QEvent.Type.Paint,
                QEvent.Type.Resize,
                QEvent.Type.Show,
            }
        ):
            self.reposition()
        return super().eventFilter(watched, event)

    def _finish(self) -> None:
        """Clear active identity before focus changes can request another commit."""

        self._finishing = True
        try:
            self._region_index = None
            self._commit = None
            self._focus_has_been_acquired = False
            self._editor.hide()
            self._active_region_sink(None)
        finally:
            self._finishing = False

    def _apply_target_palette(self, target: PromptRegionChromeEditTarget) -> None:
        """Use theme palette backing with the region's authored identity color."""

        palette = QPalette(self._viewport.palette())
        palette.setColor(
            QPalette.ColorRole.Base,
            palette.color(QPalette.ColorRole.Window),
        )
        palette.setColor(QPalette.ColorRole.Text, target.color)
        self._editor.setPalette(palette)


def _region_name_validator(parent: QObject) -> QRegularExpressionValidator:
    """Return a validator that preserves canonical one-line separator syntax."""

    return QRegularExpressionValidator(
        QRegularExpression(r"[^\]\r\n]*"),
        parent,
    )


__all__ = [
    "PromptRegionInlineEditor",
    "REGION_NAME_INLINE_EDITOR_OBJECT_NAME",
]
