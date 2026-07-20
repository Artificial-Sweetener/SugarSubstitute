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

"""Provide a context-aware search bar used by the floating editor search view."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import set_localized_placeholder

from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import QEvent, Qt, Signal

try:
    from PySide6.QtCore import QObject
except ImportError:  # pragma: no cover - test-stub fallback only
    QObject = object  # type: ignore[assignment,misc]
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

if TYPE_CHECKING:
    from PySide6.QtWidgets import QComboBox as _RuntimeComboBox
    from PySide6.QtWidgets import QLineEdit as _RuntimeSearchLineEdit
else:
    try:
        from qfluentwidgets import ComboBox as _RuntimeComboBox
        from qfluentwidgets import SearchLineEdit as _RuntimeSearchLineEdit
    except ImportError:  # pragma: no cover - runtime fallback only
        from PySide6.QtWidgets import QComboBox as _RuntimeComboBox
        from PySide6.QtWidgets import QLineEdit as _RuntimeSearchLineEdit


def _qt_key(attr_name: str, fallback: int) -> int:
    """Resolve key constants across Qt enum styles and stub test doubles."""

    enum_owner = getattr(Qt, "Key", Qt)
    enum_value = getattr(enum_owner, attr_name, None)
    if enum_value is None:
        enum_value = getattr(Qt, attr_name, None)
    if enum_value is None:
        return fallback
    try:
        return int(enum_value)
    except TypeError:
        return fallback


def _qt_shift_modifier() -> int:
    """Resolve shift modifier across Qt enum styles and stub test doubles."""

    enum_owner = getattr(Qt, "KeyboardModifier", Qt)
    modifier = getattr(enum_owner, "ShiftModifier", None)
    if modifier is None:
        modifier = getattr(Qt, "ShiftModifier", None)
    if modifier is None:
        return 0x02000000
    try:
        return int(modifier)
    except TypeError:
        return 0x02000000


def _has_shift_modifier(modifiers: Any) -> bool:
    """Return whether one Qt modifier payload includes Shift across enum styles."""

    shift_modifier = _qt_shift_modifier()
    try:
        return bool(modifiers & shift_modifier)
    except TypeError:
        try:
            return bool(int(modifiers) & shift_modifier)
        except (TypeError, ValueError):
            return False


def _qt_alignment_flag(attr_name: str, fallback: int) -> Any:
    """Resolve alignment constants across Qt enum styles and stub test doubles."""

    align_owner = getattr(Qt, "AlignmentFlag", Qt)
    enum_value: Any = getattr(align_owner, attr_name, None)
    if enum_value is None:
        enum_value = getattr(Qt, attr_name, None)
    if enum_value is None:
        return fallback
    return enum_value


def _qt_search_alignment() -> Any:
    """Resolve left+vertical-center alignment across Qt enum styles and stubs."""

    left_align: Any = _qt_alignment_flag("AlignLeft", 0x0001)
    vcenter_align: Any = _qt_alignment_flag("AlignVCenter", 0x0080)
    try:
        return left_align | vcenter_align
    except TypeError:
        return int(left_align) | int(vcenter_align)


def _fixed_policy() -> QSizePolicy.Policy:
    """Resolve fixed size-policy enum across Qt enum styles and stubs."""

    enum_owner = getattr(QSizePolicy, "Policy", None)
    if enum_owner is not None:
        fixed_policy = getattr(enum_owner, "Fixed", None)
        if fixed_policy is not None:
            return cast(QSizePolicy.Policy, fixed_policy)

    fallback_policy = getattr(QSizePolicy, "Fixed", None)
    if fallback_policy is None:
        return QSizePolicy.Policy.Preferred
    return cast(QSizePolicy.Policy, fallback_policy)


def _event_key_press_type() -> int:
    """Resolve key-press event type across Qt enum styles and stubs."""

    enum_owner = getattr(QEvent, "Type", None)
    if enum_owner is not None:
        key_press = getattr(enum_owner, "KeyPress", None)
        if key_press is not None:
            return int(key_press)

    fallback_type = getattr(QEvent, "KeyPress", None)
    if fallback_type is None:
        return 6
    return int(fallback_type)


class ContextSearchBox(QWidget):
    """Combine search text and context selection with command-prefix parsing."""

    contextSearchChanged = Signal(str, str)
    cycleSearchMatchRequested = Signal()
    cycleSearchMatchRequestedBackward = Signal()

    def __init__(
        self, parent: QWidget | None = None, contexts: list[str] | None = None
    ) -> None:
        """Create context combo and search line-edit controls."""

        super().__init__(parent)
        self.setFixedHeight(32)
        self.setContentsMargins(0, 0, 0, 0)

        self.comboBox = _RuntimeComboBox(self)
        self.comboBox.setFixedWidth(80)
        fixed_policy = _fixed_policy()
        self.comboBox.setSizePolicy(fixed_policy, fixed_policy)
        self.comboBox.setObjectName("SearchContextComboBox")
        self.comboBox.setFixedHeight(32)

        if contexts is None:
            contexts = ["Text", "Field", "Node"]
        self.comboBox.addItems(contexts)
        self.comboBox.setCurrentIndex(0)

        self.searchLineEdit = _RuntimeSearchLineEdit(self)
        set_localized_placeholder(self.searchLineEdit, "Search…")
        self.searchLineEdit.setFixedHeight(32)
        self.searchLineEdit.setFixedWidth(296)
        self.searchLineEdit.setSizePolicy(fixed_policy, fixed_policy)
        self.searchLineEdit.setTextMargins(self.comboBox.width() - 4, 0, 0, 0)
        if hasattr(self.searchLineEdit, "setAlignment"):
            self.searchLineEdit.setAlignment(cast(Any, _qt_search_alignment()))

        self.searchLineEdit.move(0, 0)
        self.comboBox.move(0, 0)
        self.comboBox.raise_()

        self.setFixedWidth(self.searchLineEdit.width())

        self.comboBox.currentTextChanged.connect(self._emit_change)
        self.searchLineEdit.textChanged.connect(self._emit_change)
        self.searchLineEdit.installEventFilter(self)

    def resizeEvent(self, event: QEvent) -> None:
        """Keep overlaid combo and search line-edit aligned on resize."""

        self.searchLineEdit.move(0, 0)
        self.comboBox.move(0, 0)
        if hasattr(event, "accept"):
            event.accept()

    def _emit_change(self) -> None:
        """Emit context/query updates and apply `@context` command prefixes."""

        text = self.searchLineEdit.text()
        lowered = text.lower().lstrip()

        command_prefixes = {
            "@text ": "Text",
            "@field ": "Field",
            "@node ": "Node",
        }
        for prefix, context_label in command_prefixes.items():
            if lowered.startswith(prefix):
                stripped = text[len(prefix) :].lstrip()
                self.comboBox.setCurrentText(context_label)
                self.searchLineEdit.setText(stripped)
                return

        if lowered.startswith("@"):
            return

        self.contextSearchChanged.emit(
            self.comboBox.currentText(),
            self.searchLineEdit.text(),
        )

    def context(self) -> str:
        """Return selected context label."""

        return self.comboBox.currentText()

    def searchText(self) -> str:
        """Return current free-text query."""

        return self.searchLineEdit.text()

    def setContext(self, text: str) -> None:
        """Select a context by label when present."""

        index = self.comboBox.findText(text)
        if index >= 0:
            self.comboBox.setCurrentIndex(index)

    def setQuery(self, text: str) -> None:
        """Set query text programmatically."""

        self.searchLineEdit.setText(text)

    def setSearchText(self, text: str) -> None:
        """Set query text programmatically (legacy API name)."""

        self.searchLineEdit.setText(text)

    def eventFilter(self, source: QObject, event: QEvent) -> bool:
        """Handle Enter/Shift+Enter navigation shortcuts from search line-edit."""

        if (
            source is self.searchLineEdit
            and int(event.type()) == _event_key_press_type()
        ):
            key_event = event if isinstance(event, QKeyEvent) else None
            if key_event is None:
                return False
            enter_key = _qt_key("Key_Enter", 16777221)
            return_key = _qt_key("Key_Return", 16777220)
            key_code = int(key_event.key())
            if key_code in {enter_key, return_key}:
                if self.context() == "Text":
                    modifiers = key_event.modifiers()
                    if _has_shift_modifier(modifiers):
                        self.cycleSearchMatchRequestedBackward.emit()
                    else:
                        self.cycleSearchMatchRequested.emit()
                    return True
        return bool(super().eventFilter(source, event))


__all__ = [
    "ContextSearchBox",
]
