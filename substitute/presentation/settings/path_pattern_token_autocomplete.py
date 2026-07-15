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

"""Provide token autocomplete for editable path pattern fields."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, Signal
from PySide6.QtGui import (
    QEnterEvent,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QResizeEvent,
)
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, LineEdit  # type: ignore[import-untyped]

from substitute.presentation.widgets.fluent_popup_frame import (
    AttachedFluentPopupFrame,
    fluent_menu_hover_fill,
    fluent_menu_selected_fill,
)
from substitute.presentation.widgets.picker_keyboard_navigation import (
    PickerKeyboardAction,
    picker_keyboard_action_from_event,
)

_ROW_HEIGHT = 33
_MAX_VISIBLE_ITEMS = 10
_MIN_PANEL_WIDTH = 240
_MAX_PANEL_WIDTH = 460
_PANEL_MARGIN = 8
_DESCRIPTION_MAX_WIDTH = 190


@dataclass(frozen=True)
class PathPatternTokenSuggestion:
    """Describe one token suggestion shown for a path pattern field."""

    token: str
    description: str


@dataclass(frozen=True)
class PathPatternTokenFragment:
    """Describe the editable token fragment immediately before the cursor."""

    start: int
    end: int
    prefix: str


def active_path_token_fragment(
    text: str,
    cursor_position: int,
) -> PathPatternTokenFragment | None:
    """Return the active path token fragment before the cursor, if any."""

    if cursor_position < 0 or cursor_position > len(text):
        return None
    opener_index = text.rfind("{", 0, cursor_position)
    if opener_index < 0:
        return None
    fragment_text = text[opener_index:cursor_position]
    if "}" in fragment_text:
        return None
    if "\\" in fragment_text or "/" in fragment_text:
        return None
    return PathPatternTokenFragment(
        start=opener_index,
        end=cursor_position,
        prefix=fragment_text[1:],
    )


class PathPatternTokenRow(QWidget):
    """Render one path pattern token autocomplete suggestion."""

    clicked = Signal(int)
    hovered = Signal(int)

    def __init__(
        self,
        suggestion: PathPatternTokenSuggestion,
        index: int,
        parent: QWidget | None = None,
    ) -> None:
        """Create a selectable token suggestion row."""

        super().__init__(parent)
        self._suggestion = suggestion
        self._index = index
        self._is_hovered = False
        self._is_selected = False
        self.setFixedHeight(_ROW_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)
        self._layout = layout
        self._token_label = BodyLabel(suggestion.token, self)
        self._token_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._description_label = CaptionLabel(suggestion.description, self)
        self._description_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._description_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        layout.addWidget(self._token_label, 1)
        layout.addWidget(self._description_label, 0)
        for widget in (self._token_label, self._description_label):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._update_text()

    def natural_token_width(self) -> int:
        """Return the width needed to show the token without elision."""

        return int(
            self._token_label.fontMetrics().horizontalAdvance(self._suggestion.token)
        )

    def natural_description_width(self) -> int:
        """Return the width needed to show the description within row limits."""

        width = int(
            self._description_label.fontMetrics().horizontalAdvance(
                self._suggestion.description
            )
        )
        return min(width, _DESCRIPTION_MAX_WIDTH)

    def set_selected(self, is_selected: bool) -> None:
        """Apply selected-row paint state."""

        if self._is_selected == is_selected:
            return
        self._is_selected = is_selected
        self.update()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Elide row text when the panel narrows."""

        super().resizeEvent(event)
        self._update_text()

    def enterEvent(self, event: QEnterEvent) -> None:
        """Track hover state and synchronize keyboard selection."""

        self._is_hovered = True
        self.hovered.emit(self._index)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear hover state when the pointer leaves the row."""

        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Activate this row without taking focus from the line edit."""

        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._index)
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw selected and hovered row backgrounds."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill_rect = self.rect().adjusted(6, 4, -6, 0)
        if self._is_selected:
            painter.setBrush(fluent_menu_selected_fill())
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(fill_rect, 5, 5)
        elif self._is_hovered:
            painter.setBrush(fluent_menu_hover_fill())
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(fill_rect, 5, 5)
        super().paintEvent(event)

    def _update_text(self) -> None:
        """Apply elision to token and description labels."""

        margins = self._layout.contentsMargins()
        description_width = self.natural_description_width()
        available_token_width = max(
            0,
            self.width()
            - margins.left()
            - margins.right()
            - description_width
            - self._layout.spacing(),
        )
        token_metrics = QFontMetrics(self._token_label.font())
        self._token_label.setText(
            token_metrics.elidedText(
                self._suggestion.token,
                Qt.TextElideMode.ElideRight,
                available_token_width,
            )
        )
        description_metrics = QFontMetrics(self._description_label.font())
        self._description_label.setText(
            description_metrics.elidedText(
                self._suggestion.description,
                Qt.TextElideMode.ElideRight,
                _DESCRIPTION_MAX_WIDTH,
            )
        )


class PathPatternTokenPanel(AttachedFluentPopupFrame):
    """Render path pattern token suggestions near the pattern field."""

    suggestionActivated = Signal(int)
    suggestionHovered = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create an initially hidden token suggestion panel."""

        super().__init__(parent)
        self._suggestions: tuple[PathPatternTokenSuggestion, ...] = ()
        self._rows: list[PathPatternTokenRow] = []
        self._current_index = -1
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.hide()
        layout = self.content_layout()
        layout.setContentsMargins(0, 2, 0, 6)
        layout.setSpacing(0)
        self._layout = layout

    def set_suggestions(
        self,
        suggestions: tuple[PathPatternTokenSuggestion, ...],
    ) -> None:
        """Replace the visible token suggestions."""

        self._suggestions = suggestions[:_MAX_VISIBLE_ITEMS]
        self._clear_rows()
        self._rows = []
        for index, suggestion in enumerate(self._suggestions):
            row = PathPatternTokenRow(suggestion, index, self)
            row.clicked.connect(self.suggestionActivated.emit)
            row.hovered.connect(self.suggestionHovered.emit)
            self._layout.addWidget(row)
            self._rows.append(row)
        self.set_current_index(0 if self._suggestions else -1)
        self.updateGeometry()

    def suggestions(self) -> tuple[PathPatternTokenSuggestion, ...]:
        """Return currently visible token suggestions."""

        return self._suggestions

    def set_current_index(self, index: int) -> None:
        """Select one visible suggestion by index."""

        if not self._rows or index < 0 or index >= len(self._rows):
            self._current_index = -1
            for row in self._rows:
                row.set_selected(False)
            return
        self._current_index = index
        for row_index, row in enumerate(self._rows):
            row.set_selected(row_index == index)

    def current_index(self) -> int:
        """Return the selected suggestion index."""

        return self._current_index

    def show_for_line_edit(self, line_edit: QWidget) -> None:
        """Show the panel below the line edit while clamping to its window."""

        if not self._suggestions:
            self.hide_panel()
            return
        host = self.parentWidget()
        if host is None:
            return
        panel_size = QSize(self._calculate_panel_width(line_edit), self._height())
        line_top_left = line_edit.mapTo(host, QPoint(0, 0))
        below = QPoint(line_top_left.x(), line_top_left.y() + line_edit.height() + 2)
        above = QPoint(line_top_left.x(), line_top_left.y() - panel_size.height() - 2)
        y = below.y()
        if y + panel_size.height() + _PANEL_MARGIN > host.height() and above.y() > 0:
            y = above.y()
        x = max(
            _PANEL_MARGIN,
            min(below.x(), host.width() - panel_size.width() - _PANEL_MARGIN),
        )
        self.setGeometry(x, y, panel_size.width(), panel_size.height())
        self.show()
        self.raise_()

    def hide_panel(self) -> None:
        """Hide the token suggestion panel."""

        self.hide()

    def is_panel_visible(self) -> bool:
        """Return whether suggestions are currently visible."""

        return bool(self.isVisible())

    def _calculate_panel_width(self, line_edit: QWidget) -> int:
        """Return a width that fits suggestions and the pattern field."""

        widest_token = max((row.natural_token_width() for row in self._rows), default=0)
        widest_description = max(
            (row.natural_description_width() for row in self._rows),
            default=0,
        )
        content_width = widest_token + widest_description + 56
        return min(
            max(content_width, line_edit.width(), _MIN_PANEL_WIDTH), _MAX_PANEL_WIDTH
        )

    def _height(self) -> int:
        """Return the visible panel height for current suggestions."""

        margins = self._layout.contentsMargins()
        return margins.top() + margins.bottom() + len(self._rows) * _ROW_HEIGHT

    def _clear_rows(self) -> None:
        """Remove current row widgets."""

        while self._layout.count():
            item = self._layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows = []


class PathPatternTokenAutocomplete(QObject):
    """Coordinate token autocomplete for one path pattern line edit."""

    def __init__(
        self,
        line_edit: LineEdit,
        suggestions: tuple[PathPatternTokenSuggestion, ...],
    ) -> None:
        """Attach autocomplete behavior to the supplied line edit."""

        super().__init__(line_edit)
        self._line_edit = line_edit
        self._all_suggestions = suggestions
        self._active_fragment: PathPatternTokenFragment | None = None
        self._panel: PathPatternTokenPanel | None = None
        self._line_edit.installEventFilter(self)
        self._line_edit.textChanged.connect(lambda _text: self.refresh())
        cursor_signal = getattr(self._line_edit, "cursorPositionChanged", None)
        if cursor_signal is not None:
            cursor_signal.connect(lambda _old, _new: self.refresh())

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Handle keyboard, focus, and geometry events for autocomplete."""

        if watched is not self._line_edit:
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            return self._handle_key_press(event)
        if event.type() == QEvent.Type.FocusOut:
            panel = self._panel
            if panel is None or not panel.underMouse():
                self.hide()
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self.refresh_geometry()
        return super().eventFilter(watched, event)

    def refresh(self) -> None:
        """Refresh visible suggestions for the current pattern cursor state."""

        fragment = active_path_token_fragment(
            self._line_edit.text(),
            self._line_edit.cursorPosition(),
        )
        self._active_fragment = fragment
        if fragment is None:
            self.hide()
            return
        matches = self._matching_suggestions(fragment.prefix)
        if not matches:
            self.hide()
            return
        panel = self._ensure_panel()
        panel.set_suggestions(matches)
        panel.show_for_line_edit(self._line_edit)

    def refresh_geometry(self) -> None:
        """Reposition visible suggestions after the line edit moves or resizes."""

        panel = self._panel
        if panel is not None and panel.is_panel_visible():
            panel.show_for_line_edit(self._line_edit)

    def hide(self) -> None:
        """Hide suggestions and clear the active token fragment."""

        if self._panel is not None:
            self._panel.hide_panel()
        self._active_fragment = None

    def is_visible(self) -> bool:
        """Return whether token suggestions are visible."""

        return self._panel is not None and self._panel.is_panel_visible()

    def visible_tokens(self) -> tuple[str, ...]:
        """Return currently visible token placeholders for tests and diagnostics."""

        if self._panel is None:
            return ()
        return tuple(suggestion.token for suggestion in self._panel.suggestions())

    def accept_current(self) -> bool:
        """Insert the selected token suggestion into the line edit."""

        panel = self._panel
        fragment = self._active_fragment
        if panel is None or fragment is None:
            return False
        suggestions = panel.suggestions()
        index = panel.current_index()
        if index < 0 or index >= len(suggestions):
            return False
        self._accept_suggestion(suggestions[index])
        return True

    def _handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle suggestion navigation keys when the panel is visible."""

        if not self.is_visible():
            return False
        action = picker_keyboard_action_from_event(
            event,
            tab_activates=True,
            escape_dismisses=True,
        )
        panel = self._panel
        if action is None or panel is None:
            return False
        if action is PickerKeyboardAction.DOWN:
            panel.set_current_index(
                min(panel.current_index() + 1, len(panel.suggestions()) - 1)
            )
            return True
        if action is PickerKeyboardAction.UP:
            panel.set_current_index(max(panel.current_index() - 1, 0))
            return True
        if action is PickerKeyboardAction.ACTIVATE:
            return self.accept_current()
        if action is PickerKeyboardAction.DISMISS:
            self.hide()
            return True
        return False

    def _matching_suggestions(
        self,
        prefix: str,
    ) -> tuple[PathPatternTokenSuggestion, ...]:
        """Return suggestions whose token name starts with the typed prefix."""

        normalized_prefix = prefix.lower()
        return tuple(
            suggestion
            for suggestion in self._all_suggestions
            if suggestion.token[1:-1].lower().startswith(normalized_prefix)
        )

    def _ensure_panel(self) -> PathPatternTokenPanel:
        """Return the reusable token suggestion panel."""

        host = self._line_edit.window() or self._line_edit.parentWidget()
        if not isinstance(host, QWidget):
            host = self._line_edit
        if self._panel is None or self._panel.parentWidget() is not host:
            if self._panel is not None:
                self._panel.deleteLater()
            self._panel = PathPatternTokenPanel(host)
            self._panel.suggestionActivated.connect(self._activate_suggestion_index)
            self._panel.suggestionHovered.connect(self._panel.set_current_index)
        return self._panel

    def _activate_suggestion_index(self, index: int) -> None:
        """Accept a clicked suggestion by visible index."""

        panel = self._panel
        if panel is None:
            return
        suggestions = panel.suggestions()
        if index < 0 or index >= len(suggestions):
            return
        self._accept_suggestion(suggestions[index])
        self._line_edit.setFocus()

    def _accept_suggestion(self, suggestion: PathPatternTokenSuggestion) -> None:
        """Replace the active token fragment with a full token placeholder."""

        fragment = self._active_fragment
        if fragment is None:
            return
        text = self._line_edit.text()
        next_text = text[: fragment.start] + suggestion.token + text[fragment.end :]
        next_cursor_position = fragment.start + len(suggestion.token)
        self._line_edit.setText(next_text)
        self._line_edit.setCursorPosition(next_cursor_position)
        self.hide()


__all__ = [
    "PathPatternTokenAutocomplete",
    "PathPatternTokenFragment",
    "PathPatternTokenSuggestion",
    "active_path_token_fragment",
]
