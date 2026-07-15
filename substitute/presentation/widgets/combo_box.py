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

"""Provide typed ComboBox facades and deterministic item-list helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, Sequence, cast

from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtGui import (
    QFocusEvent,
    QKeyEvent,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPalette,
)
from PySide6.QtWidgets import QStyle, QStyleOptionFrame

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLineEdit as _RuntimeComboBox
    from PySide6.QtWidgets import QSizePolicy
    from PySide6.QtWidgets import QWidget

    from .searchable_combo_popup import SearchableComboPopup
else:
    try:
        from qfluentwidgets import EditableComboBox as _RuntimeComboBox
    except ImportError:  # pragma: no cover - runtime fallback only
        from PySide6.QtWidgets import QComboBox as _RuntimeComboBox
    from PySide6.QtWidgets import QSizePolicy, QWidget

    try:
        from .searchable_combo_popup import SearchableComboPopup
    except ImportError:  # pragma: no cover - qfluentwidgets fallback only
        SearchableComboPopup = None

from .inline_completion import inline_completion_suffix
from .searchable_combo_helpers import filtered_combo_indexes

_COMBO_TEXT_CHROME_WIDTH = 44
_COMBO_MINIMUM_TEXT_WIDTH = 16
_COMBO_SHRINKABLE_MINIMUM_WIDTH = _COMBO_TEXT_CHROME_WIDTH + _COMBO_MINIMUM_TEXT_WIDTH
_COMBO_DROPDOWN_TEXT_MARGIN = 29
_COMBO_DROPDOWN_TEXT_GAP = 4


class _SignalEmitter(Protocol):
    """Define the minimal signal emitter contract used by ComboBoxBase."""

    def emit(self, *args: object) -> None: ...


class _ComboState(Protocol):
    """Define storage/state requirements consumed by ComboBoxBase helpers."""

    items: list["ComboItem"]
    _currentIndex: int
    currentTextChanged: _SignalEmitter
    currentIndexChanged: _SignalEmitter


@dataclass(slots=True)
class ComboItem:
    """Represent a single combo option used by deterministic helper tests."""

    text: str
    userData: object | None = None


def _clamp_index(index: int, lower: int, upper: int) -> int:
    """Clamp an index into an inclusive numeric range."""

    return max(lower, min(upper, index))


class ComboBoxBase:
    """Provide list/index mechanics for contract tests and lightweight doubles."""

    def addItem(self, text: str, userData: object | None = None) -> None:
        """Append a single item and initialize selection when first item appears."""

        state = cast(_ComboState, self)
        state.items.append(ComboItem(text=text, userData=userData))
        if len(state.items) == 1:
            self.setCurrentIndex(0)

    def addItems(self, texts: list[str]) -> None:
        """Append all items in order."""

        for text in texts:
            self.addItem(text)

    def insertItems(self, index: int, texts: list[str]) -> None:
        """Insert items and shift current selection when insertion is before it."""

        if not texts:
            return
        state = cast(_ComboState, self)
        target_index = _clamp_index(index, 0, len(state.items))
        inserted_items = [ComboItem(text=text) for text in texts]
        state.items[target_index:target_index] = inserted_items
        if state._currentIndex >= target_index:
            state._currentIndex += len(inserted_items)

    def removeItem(self, index: int) -> None:
        """Remove item at index and keep selection semantics deterministic."""

        state = cast(_ComboState, self)
        if index < 0 or index >= len(state.items):
            return

        del state.items[index]
        if not state.items:
            state._currentIndex = -1
            return

        if index < state._currentIndex:
            self.setCurrentIndex(state._currentIndex - 1)
            return

        if index == state._currentIndex:
            replacement_index = _clamp_index(index, 0, len(state.items) - 1)
            self.setCurrentIndex(replacement_index)

    def clear(self) -> None:
        """Remove all items and reset selection."""

        state = cast(_ComboState, self)
        state.items.clear()
        state._currentIndex = -1

    def count(self) -> int:
        """Return item count."""

        state = cast(_ComboState, self)
        return len(state.items)

    def itemText(self, index: int) -> str:
        """Return item text or empty string when index is invalid."""

        state = cast(_ComboState, self)
        if index < 0 or index >= len(state.items):
            return ""
        return state.items[index].text

    def itemData(self, index: int) -> object | None:
        """Return item user data or None when index is invalid."""

        state = cast(_ComboState, self)
        if index < 0 or index >= len(state.items):
            return None
        return state.items[index].userData

    def findText(self, text: str) -> int:
        """Return the first index matching text, or -1 when not found."""

        state = cast(_ComboState, self)
        for index, item in enumerate(state.items):
            if item.text == text:
                return index
        return -1

    def currentIndex(self) -> int:
        """Return current selected index."""

        state = cast(_ComboState, self)
        return state._currentIndex

    def currentText(self) -> str:
        """Return text for current index, or empty string for no selection."""

        state = cast(_ComboState, self)
        if state._currentIndex < 0 or state._currentIndex >= len(state.items):
            return ""
        return state.items[state._currentIndex].text

    def setCurrentIndex(self, index: int) -> None:
        """Set selected index and emit index/text change signals when it changes."""

        state = cast(_ComboState, self)
        next_index = _clamp_index(index, -1, len(state.items) - 1)
        if next_index == state._currentIndex:
            return
        state._currentIndex = next_index
        state.currentTextChanged.emit(self.currentText())
        state.currentIndexChanged.emit(next_index)

    def setCurrentText(self, text: str) -> None:
        """Set selection to the first matching text."""

        index = self.findText(text)
        if index >= 0:
            self.setCurrentIndex(index)


class ComboBox(_RuntimeComboBox):
    """Select-only searchable combo box with stable item-based sizing."""

    currentTextChanged: Any
    currentIndexChanged: Any
    activated: Any
    textActivated: Any

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize searchable selection state and qfluent chrome."""

        super().__init__(parent)
        self._max_hint_width: int | None = None
        self._widest_item_text_width_cache = 0
        self._search_active = False
        self._programmatic_text_update = False
        self._inline_completion_suffix = ""
        self._popup: SearchableComboPopup | None = None
        self._connect_popup()
        runtime = cast(Any, self)
        if hasattr(runtime, "setClearButtonEnabled"):
            runtime.setClearButtonEnabled(False)
        self._restore_combo_text_margins()
        if hasattr(runtime, "setEditable"):
            runtime.setEditable(True)
        self.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Fixed,
        )

    def addItem(self, text: str, *args: object, **kwargs: object) -> None:
        """Add one item and refresh the stable width hint."""

        self._programmatic_text_update = True
        try:
            cast(Any, super()).addItem(text, *args, **kwargs)
        finally:
            self._programmatic_text_update = False
        self._restore_closed_native_text_after_item_mutation()
        self._refresh_item_width_hint()

    def addItems(self, texts: Sequence[str]) -> None:
        """Add items and refresh the stable width hint once."""

        self._programmatic_text_update = True
        try:
            cast(Any, super()).addItems(texts)
        finally:
            self._programmatic_text_update = False
        self._restore_closed_native_text_after_item_mutation()
        self._refresh_item_width_hint()

    def insertItem(
        self, index: int, text: str, *args: object, **kwargs: object
    ) -> None:
        """Insert one item and refresh the stable width hint."""

        self._programmatic_text_update = True
        try:
            cast(Any, super()).insertItem(index, text, *args, **kwargs)
        finally:
            self._programmatic_text_update = False
        self._restore_closed_native_text_after_item_mutation()
        self._refresh_item_width_hint()

    def insertItems(self, index: int, texts: Sequence[str]) -> None:
        """Insert items and refresh the stable width hint once."""

        self._programmatic_text_update = True
        try:
            cast(Any, super()).insertItems(index, texts)
        finally:
            self._programmatic_text_update = False
        self._restore_closed_native_text_after_item_mutation()
        self._refresh_item_width_hint()

    def removeItem(self, index: int) -> None:
        """Remove one item and refresh the stable width hint."""

        cast(Any, super()).removeItem(index)
        if self.count() > 0 and self.currentIndex() < 0:
            self.setCurrentIndex(0)
        self._restore_committed_text()
        self._refresh_item_width_hint()

    def clear(self) -> None:
        """Clear all items and refresh the stable width hint."""

        self._programmatic_text_update = True
        try:
            cast(Any, super()).clear()
        finally:
            self._programmatic_text_update = False
        self._search_active = False
        self._clear_inline_completion()
        self._clear_native_search_text()
        self._refresh_item_width_hint()

    def setItemText(self, index: int, text: str) -> None:
        """Update item text and refresh the stable width hint."""

        self._programmatic_text_update = True
        try:
            cast(Any, super()).setItemText(index, text)
        finally:
            self._programmatic_text_update = False
        if index == self.currentIndex():
            self._restore_committed_text()
        self._refresh_item_width_hint()

    def count(self) -> int:
        """Return the number of allowed combo items."""

        return int(cast(Any, super()).count())

    def itemText(self, index: int) -> str:
        """Return the item label at an index, or an empty string."""

        return str(cast(Any, super()).itemText(index))

    def itemData(self, index: int) -> object | None:
        """Return user data stored for one item."""

        return cast(object | None, cast(Any, super()).itemData(index))

    def findText(self, text: str) -> int:
        """Return the first exact item-text match, or -1."""

        return int(cast(Any, super()).findText(text))

    def currentIndex(self) -> int:
        """Return the committed selected item index."""

        return int(cast(Any, super()).currentIndex())

    def currentText(self) -> str:
        """Return the committed selected text, not transient search text."""

        index = self.currentIndex()
        if index < 0 or index >= self.count():
            return ""
        return self.itemText(index)

    def setCurrentIndex(self, index: int) -> None:
        """Commit an allowed item by index."""

        self._commit_index(index, emit_activated=False)

    def setCurrentText(self, text: str) -> None:
        """Commit an allowed item by exact text."""

        index = self.findText(text)
        if index >= 0:
            self.setCurrentIndex(index)

    def setMaxHintWidth(self, width: int | None) -> None:
        """Set optional width cap used by downstream layout code."""

        self._max_hint_width = width
        self.updateGeometry()

    def maxHintWidth(self) -> int | None:
        """Return optional width cap when configured."""

        return getattr(self, "_max_hint_width", None)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint closed labels and search-mode inline completion without mutation."""

        if self._should_paint_inline_completion_context():
            super().paintEvent(event)
            self._paint_inline_completion()
            return

        super().paintEvent(event)
        self._paint_closed_display_text()

    def event(self, event: QEvent) -> bool:
        """Accept Tab completion before Qt treats Tab as focus traversal."""

        if (
            event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() == Qt.Key.Key_Tab
            and self._commit_highlighted_or_completion()
        ):
            event.accept()
            return True
        return bool(super().event(event))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Route search and popup keyboard commands before normal text editing."""

        if event.modifiers() not in (
            Qt.KeyboardModifier.NoModifier,
            Qt.KeyboardModifier.KeypadModifier,
        ):
            super().keyPressEvent(event)
            return

        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._restore_committed_text()
            self._close_popup()
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._commit_highlighted_or_completion():
                event.accept()
                return
            self._restore_committed_text()
            event.accept()
            return
        if key == Qt.Key.Key_Down:
            if self._popup_is_visible():
                self._popup_for_state().highlight_next()
                self._refresh_inline_completion()
            else:
                self._open_full_popup()
            event.accept()
            return
        if key == Qt.Key.Key_Up and self._popup_is_visible():
            self._popup_for_state().highlight_previous()
            self._refresh_inline_completion()
            event.accept()
            return
        if key == Qt.Key.Key_Space and not self._search_active:
            self._open_full_popup()
            event.accept()
            return
        if event.text() and not event.text().isspace() and not self._search_active:
            self._search_active = True
            self._clear_native_search_text()

        super().keyPressEvent(event)
        if self._search_active:
            self._refresh_filtered_popup(self._button_text())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Open the full list from body clicks while preserving text editing."""

        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and self.count() > 0:
            self._open_full_popup()

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Restore committed text when focus leaves without a valid commit."""

        super().focusOutEvent(event)
        if self._popup_is_visible():
            return
        if self._search_active:
            self._restore_committed_text()
            self._close_popup()

    def sizeHint(self) -> QSize:
        """Return preferred width from the widest item, capped when requested."""

        base_hint = super().sizeHint()
        minimum_hint = self.minimumSizeHint()
        preferred_width = max(
            base_hint.width(),
            minimum_hint.width(),
            self._closed_display_control_width_for_text_width(
                self._widest_item_text_width_cache
            ),
        )
        max_hint_width = self.maxHintWidth()
        if max_hint_width is not None:
            preferred_width = min(
                preferred_width,
                max(minimum_hint.width(), max_hint_width),
            )
        return QSize(preferred_width, base_hint.height())

    def minimumSizeHint(self) -> QSize:
        """Return a small minimum so constrained layouts can elide text."""

        minimum_height = max(24, self.fontMetrics().height() + 12)
        return QSize(_COMBO_SHRINKABLE_MINIMUM_WIDTH, minimum_height)

    def _widest_item_text_width(self) -> int:
        """Return the widest item text width for stable combo sizing."""

        font_metrics = self.fontMetrics()
        width = max(
            (
                font_metrics.horizontalAdvance(self.itemText(index))
                for index in range(self.count())
            ),
            default=0,
        )
        return width

    def _closed_display_text_for_width(self, width: int) -> str:
        """Return closed combo text elided for the available widget width."""

        display_text = self._closed_display_text()
        available_width = max(0, width - self._closed_display_text_chrome_width())
        return self.fontMetrics().elidedText(
            display_text,
            Qt.TextElideMode.ElideRight,
            available_width,
        )

    def _closed_display_control_width_for_text_width(self, text_width: int) -> int:
        """Return control width needed for text in the actual closed paint rect."""

        return max(
            self.minimumSizeHint().width(),
            text_width + self._closed_display_text_chrome_width(),
        )

    def _closed_display_text_chrome_width(self) -> int:
        """Return non-text width consumed by frame, margins, and dropdown chrome."""

        text_rect_width = self._closed_display_text_rect().width()
        measured_chrome_width = self.width() - text_rect_width
        return max(_COMBO_TEXT_CHROME_WIDTH, measured_chrome_width)

    def _button_text(self) -> str:
        """Return runtime line-edit text for qfluent-backed combos."""

        text = getattr(self, "text", None)
        if not callable(text):
            return ""
        return str(text())

    def _onComboTextChanged(self, text: str) -> None:
        """Treat inherited qfluent text changes as transient search input."""

        if self._programmatic_text_update:
            return
        self._search_active = True
        self._refresh_filtered_popup(text)

    def _onReturnPressed(self) -> None:
        """Commit highlighted items instead of adding arbitrary typed text."""

        if not self._commit_highlighted_or_completion():
            self._restore_committed_text()

    def _onClearButtonClicked(self) -> None:
        """Restore the committed selection instead of clearing to invalid text."""

        self._restore_committed_text()

    def _toggleComboMenu(self) -> None:
        """Toggle the full unfiltered popup."""

        if self._popup_is_visible():
            self._close_popup()
        else:
            self._open_full_popup()

    def _connect_popup(self) -> None:
        """Create and connect the popup once for this combo."""

        if SearchableComboPopup is None:
            self._popup = None
            return
        self._popup = SearchableComboPopup(self)
        self._popup.activatedIndex.connect(self._commit_user_index)
        self._popup.dismissedByOutsideClick.connect(
            self._on_popup_dismissed_by_outside_click
        )
        self._popup.highlightedIndexChanged.connect(self._on_highlighted_index_changed)
        self._popup.closedSignal.connect(self._on_popup_closed)

    def _popup_for_state(self) -> SearchableComboPopup:
        """Return the popup, creating it if object lifetime cleanup removed it."""

        if self._popup is None:
            self._connect_popup()
        if self._popup is None:
            raise RuntimeError("Searchable combo popup requires qfluentwidgets.")
        return self._popup

    def _open_full_popup(self) -> None:
        """Open the dropdown with every allowed item visible."""

        self._search_active = False
        self._clear_inline_completion()
        self._show_popup_for_indexes(
            list(range(self.count())),
            preferred_source_index=self.currentIndex(),
        )

    def _refresh_filtered_popup(self, query: str) -> None:
        """Refresh popup rows for the current search query."""

        indexes = filtered_combo_indexes(self._all_item_texts(), query)
        if not indexes:
            self._clear_inline_completion()
            self._close_popup()
            self.update()
            return
        self._show_popup_for_indexes(indexes, preferred_source_index=indexes[0])
        self._refresh_inline_completion()

    def _show_popup_for_indexes(
        self,
        source_indexes: Sequence[int],
        *,
        preferred_source_index: int,
    ) -> None:
        """Populate and show the popup for source item indexes."""

        if not source_indexes:
            self._close_popup()
            return
        popup = self._popup_for_state()
        popup_was_visible = popup.isVisible()
        labels = [self.itemText(index) for index in source_indexes]
        popup.set_items(
            labels=labels,
            source_indexes=source_indexes,
            preferred_source_index=preferred_source_index,
        )
        if popup_was_visible:
            popup.reflow_for(self)
        else:
            popup.popup_for(self)
        self._refresh_inline_completion()

    def _commit_highlighted_or_completion(self) -> bool:
        """Commit the highlighted popup item or inline completion candidate."""

        popup = self._popup
        if popup is None or not popup.isVisible():
            return False
        source_index = popup.highlighted_source_index()
        if source_index is None:
            return False
        self._commit_index(source_index, emit_activated=True)
        return True

    def _commit_user_index(self, index: int) -> None:
        """Commit an item activated by the popup surface."""

        self._commit_index(index, emit_activated=True)

    def _on_highlighted_index_changed(self, _index: int) -> None:
        """Refresh ghost text when hover or keyboard focus changes the candidate."""

        self._refresh_inline_completion()

    def _on_popup_dismissed_by_outside_click(self) -> None:
        """Cancel transient search when the popup is dismissed from outside."""

        self._restore_committed_text()

    def _on_popup_closed(self) -> None:
        """Restore transient search text when the popup closes after focus moved away."""

        if self._search_active and not self.hasFocus():
            self._restore_committed_text()

    def _commit_index(self, index: int, *, emit_activated: bool) -> None:
        """Commit an allowed item and emit selection signals for real changes."""

        if index < 0 or index >= self.count():
            return
        old_index = self.currentIndex()
        old_text = self.currentText()
        runtime = cast(Any, self)
        runtime._currentIndex = index
        self._search_active = False
        self._clear_inline_completion()
        self._clear_native_search_text()
        self._close_popup()

        next_text = self.currentText()
        if next_text != old_text:
            self.currentTextChanged.emit(next_text)
        if index != old_index:
            self.currentIndexChanged.emit(index)
        if emit_activated:
            self.activated.emit(index)
            self.textActivated.emit(next_text)
        self.update()

    def _restore_committed_text(self) -> None:
        """Restore closed display after transient search without changing selection."""

        self._search_active = False
        self._clear_inline_completion()
        self._clear_native_search_text()
        self.update()

    def _clear_native_search_text(self) -> None:
        """Clear transient native search text without changing committed selection."""

        self._set_native_search_text("")

    def _set_native_search_text(self, text: str) -> None:
        """Set native line-edit search text while suppressing search handling."""

        self._programmatic_text_update = True
        try:
            setter = getattr(super(), "setText", None)
            if callable(setter):
                setter(text)
            else:
                cast(Any, self).setText(text)
        finally:
            self._programmatic_text_update = False

    def _restore_closed_native_text_after_item_mutation(self) -> None:
        """Keep closed-mode native text empty after qfluent item mutations."""

        if not self._search_active:
            self._clear_native_search_text()

    def _restore_combo_text_margins(self) -> None:
        """Restore qfluent editable-combo text margins after clear-button setup."""

        set_text_margins = getattr(self, "setTextMargins", None)
        if callable(set_text_margins):
            set_text_margins(0, 0, _COMBO_DROPDOWN_TEXT_MARGIN, 0)

    def _all_item_texts(self) -> list[str]:
        """Return all item labels in source order."""

        return [self.itemText(index) for index in range(self.count())]

    def _popup_is_visible(self) -> bool:
        """Return whether the popup exists and is currently visible."""

        return bool(self._popup is not None and self._popup.isVisible())

    def _close_popup(self) -> None:
        """Close the popup if it is visible."""

        if self._popup is not None and self._popup.isVisible():
            self._popup.close()

    def _highlighted_text(self) -> str:
        """Return the highlighted popup item text, or an empty string."""

        popup = self._popup
        if popup is None:
            return ""
        source_index = popup.highlighted_source_index()
        if source_index is None:
            return ""
        return self.itemText(source_index)

    def _refresh_inline_completion(self) -> None:
        """Update display-only completion text from the highlighted item."""

        typed_text = self._button_text()
        highlighted_text = self._highlighted_text()
        if not self._should_paint_inline_completion_context() or not highlighted_text:
            self._clear_inline_completion()
            return
        if not typed_text:
            self._inline_completion_suffix = highlighted_text
            self.update()
            return
        self._inline_completion_suffix = inline_completion_suffix(
            typed_text=typed_text,
            candidate_text=highlighted_text,
        )
        self.update()

    def _should_paint_inline_completion_context(self) -> bool:
        """Return whether the current combo state may show ghost completion."""

        return self._search_active or (
            self._popup_is_visible() and not self._button_text()
        )

    def _clear_inline_completion(self) -> None:
        """Clear any display-only inline completion suffix."""

        if self._inline_completion_suffix:
            self._inline_completion_suffix = ""
            self.update()

    def _closed_display_text(self) -> str:
        """Return the committed text used by closed-state rendering."""

        return self.currentText()

    def _paint_closed_display_text(self) -> None:
        """Draw the committed selected label elided to the closed text rect."""

        display_text = self._closed_display_text()
        if not display_text:
            return
        text_rect = self._closed_display_text_rect()
        if text_rect.width() <= 0:
            return
        painted_text = self._closed_display_text_for_width(
            text_rect.width() + self._closed_display_text_chrome_width()
        )
        if not painted_text:
            return
        painter = QPainter(self)
        painter.setClipRect(text_rect)
        color_group = (
            QPalette.ColorGroup.Normal
            if self.isEnabled()
            else QPalette.ColorGroup.Disabled
        )
        painter.setPen(self.palette().color(color_group, QPalette.ColorRole.Text))
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            painted_text,
        )

    def _paint_inline_completion(self) -> None:
        """Paint inline completion suffix after transient search text."""

        if not self._inline_completion_suffix:
            return
        typed_text = self._button_text()
        if self.hasSelectedText() or self.cursorPosition() != len(typed_text):
            return
        painter = QPainter(self)
        text_rect = self._inline_completion_text_rect(typed_text)
        painter.setClipRect(text_rect)
        color = self.palette().placeholderText().color()
        painter.setPen(color)
        painted_suffix = self._elided_inline_completion_text(text_rect.width())
        if not painted_suffix:
            return
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            painted_suffix,
        )

    def _elided_inline_completion_text(self, available_width: int) -> str:
        """Return the ghost suffix elided to the available paint width."""

        if available_width <= 0 or not self._inline_completion_suffix:
            return ""
        return self.fontMetrics().elidedText(
            self._inline_completion_suffix,
            Qt.TextElideMode.ElideRight,
            available_width,
        )

    def _styled_text_rect(self) -> QRect:
        """Return the qfluent/Qt styled line-edit text area for custom painting."""

        option = QStyleOptionFrame()
        option.initFrom(self)
        option_state = cast(Any, option)
        option_state.rect = self.rect()
        option_state.lineWidth = self.style().pixelMetric(
            QStyle.PixelMetric.PM_DefaultFrameWidth,
            option,
            self,
        )
        option_state.midLineWidth = 0
        style_rect = self.style().subElementRect(
            QStyle.SubElement.SE_LineEditContents,
            option,
            self,
        )
        margins = self.textMargins()
        left = style_rect.left() + margins.left()
        top = style_rect.top() + margins.top()
        right = style_rect.right() - margins.right()
        bottom = style_rect.bottom() - margins.bottom()
        drop_button = getattr(self, "dropButton", None)
        if isinstance(drop_button, QWidget) and drop_button.isVisible():
            text_right = drop_button.geometry().left() - _COMBO_DROPDOWN_TEXT_GAP
            right = min(right, text_right)
        return QRect(
            left,
            top,
            max(0, right - left + 1),
            max(0, bottom - top + 1),
        )

    def _inline_completion_text_rect(self, typed_text: str) -> QRect:
        """Return the styled suffix rect after transient search text."""

        base_rect = self._styled_text_rect()
        typed_width = self.fontMetrics().horizontalAdvance(typed_text)
        left = base_rect.left() + typed_width
        right = base_rect.right()
        return QRect(
            left,
            base_rect.top(),
            max(0, right - left + 1),
            base_rect.height(),
        )

    def _editable_text_rect(self) -> QRect:
        """Return the styled text area available for custom painting."""

        return self._styled_text_rect()

    def _closed_display_text_rect(self) -> QRect:
        """Return the styled rect used for the closed committed label."""

        return self._styled_text_rect()

    def _refresh_item_width_hint(self) -> None:
        """Refresh cached preferred text width after item labels change."""

        self._widest_item_text_width_cache = self._widest_item_text_width()
        self.updateGeometry()


EditableComboBox = ComboBox


__all__ = [
    "ComboBox",
    "ComboBoxBase",
    "ComboItem",
    "EditableComboBox",
]
