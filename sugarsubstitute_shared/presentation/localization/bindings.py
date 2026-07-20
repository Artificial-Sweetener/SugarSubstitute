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

"""Bind translated widget properties to Qt's standard language-change event."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QEvent, QObject, QSignalBlocker
from PySide6.QtWidgets import QComboBox, QTableWidget

from sugarsubstitute_shared.localization import ApplicationMessage, ApplicationText
from sugarsubstitute_shared.presentation.localization.application_message import (
    render_application_text,
)

TextFactory = Callable[[], str]


class TextTarget(Protocol):
    """Describe a Qt object exposing a normal text property."""

    def setText(self, text: str) -> None:
        """Set visible text."""


class TooltipTarget(Protocol):
    """Describe a Qt object exposing a tooltip property."""

    def setToolTip(self, text: str) -> None:
        """Set tooltip text."""


class StatusTipTarget(Protocol):
    """Describe a Qt object exposing a status-tip property."""

    def setStatusTip(self, text: str) -> None:
        """Set status-tip text."""


class PlaceholderTarget(Protocol):
    """Describe an editable Qt object exposing placeholder text."""

    def setPlaceholderText(self, text: str) -> None:
        """Set placeholder text."""


class AccessibleNameTarget(Protocol):
    """Describe a Qt object exposing an accessibility name."""

    def setAccessibleName(self, name: str) -> None:
        """Set the screen-reader-visible name."""


class AccessibleDescriptionTarget(Protocol):
    """Describe a Qt object exposing an accessibility description."""

    def setAccessibleDescription(self, description: str) -> None:
        """Set the screen-reader-visible description."""


class WindowTitleTarget(Protocol):
    """Describe a Qt object exposing a window title."""

    def setWindowTitle(self, title: str) -> None:
        """Set the translated window title."""


@dataclass(frozen=True, slots=True)
class LocalizedComboItem:
    """Pair a translated label with its locale-neutral domain identifier."""

    stable_identifier: object
    label: ApplicationText


class LocalizationBindings(QObject):
    """Own idempotent localized-property updates for one widget subtree."""

    def __init__(self, owner: QObject) -> None:
        """Observe the owner while retaining all language-neutral callbacks."""

        super().__init__(owner)
        self._owner = owner
        self._bindings: list[Callable[[], None]] = []
        owner.installEventFilter(self)

    def bind_text(self, target: TextTarget, text: TextFactory) -> None:
        """Bind a label, button, action, or other normal text property."""

        self.bind_setter(target.setText, text)

    def bind_message(self, target: TextTarget, message: ApplicationMessage) -> None:
        """Bind one explicitly marked application message to normal widget text."""

        self.bind_text(target, lambda: render_application_text(message))

    def bind_tooltip(self, target: TooltipTarget, text: TextFactory) -> None:
        """Bind hover help that must refresh with visible labels."""

        from sugarsubstitute_shared.presentation.fluent_tooltips import (
            set_fluent_tooltip_text,
        )

        self.bind_setter(lambda value: set_fluent_tooltip_text(target, value), text)

    def bind_tooltip_message(
        self,
        target: TooltipTarget,
        message: ApplicationMessage,
    ) -> None:
        """Bind one explicitly marked application tooltip."""

        self.bind_tooltip(target, lambda: render_application_text(message))

    def bind_status_tip(self, target: StatusTipTarget, text: TextFactory) -> None:
        """Bind status-bar help for actions and controls."""

        self.bind_setter(target.setStatusTip, text)

    def bind_placeholder(self, target: PlaceholderTarget, text: TextFactory) -> None:
        """Bind an editor placeholder without replacing editable content."""

        self.bind_setter(target.setPlaceholderText, text)

    def bind_accessible_name(
        self,
        target: AccessibleNameTarget,
        text: TextFactory,
    ) -> None:
        """Bind a control's screen-reader-visible name."""

        self.bind_setter(target.setAccessibleName, text)

    def bind_accessible_description(
        self,
        target: AccessibleDescriptionTarget,
        text: TextFactory,
    ) -> None:
        """Bind supporting accessibility text independently from visible text."""

        self.bind_setter(target.setAccessibleDescription, text)

    def bind_window_title(
        self,
        target: WindowTitleTarget,
        text: TextFactory,
    ) -> None:
        """Bind one top-level or dialog window title."""

        self.bind_setter(target.setWindowTitle, text)

    def bind_setter(
        self,
        setter: Callable[[str], None],
        text: TextFactory,
    ) -> None:
        """Bind an app-owned adapter property through a strongly typed setter."""

        def apply() -> None:
            """Resolve and apply this property for the current translator generation."""

            setter(text())

        self._add_binding(apply)

    def bind_combo_items(
        self,
        combo: QComboBox,
        items: Callable[[], Sequence[LocalizedComboItem]],
    ) -> None:
        """Rebuild localized labels while preserving stable selection and signals."""

        def apply() -> None:
            """Replace labels without exposing a false domain selection change."""

            selected_identifier = combo.currentData()
            blocker = QSignalBlocker(combo)
            combo.clear()
            for item in items():
                combo.addItem(
                    render_application_text(item.label),
                    userData=item.stable_identifier,
                )
            selected_index = combo.findData(selected_identifier)
            if selected_index >= 0:
                combo.setCurrentIndex(selected_index)
            del blocker

        self._add_binding(apply)

    def bind_table_headers(
        self,
        table: QTableWidget,
        headers: Callable[[], Sequence[str]],
    ) -> None:
        """Bind horizontal table headers without replacing the table or its rows."""

        def apply() -> None:
            """Refresh only header presentation for the current language."""

            table.setHorizontalHeaderLabels(list(headers()))

        self._add_binding(apply)

    def retranslate(self) -> None:
        """Apply every bound property once for the current translator generation."""

        for binding in tuple(self._bindings):
            binding()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Refresh this owner's bindings during Qt language-change propagation."""

        if watched is self._owner and event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        return False

    def _add_binding(self, binding: Callable[[], None]) -> None:
        """Retain a locale-neutral callback and apply its current value immediately."""

        self._bindings.append(binding)
        binding()


class LocalizedComboItemTextBinding(QObject):
    """Own one explicitly localized label inside a mixed-content combo box."""

    def __init__(
        self,
        combo: QComboBox,
        *,
        item_index: int,
        message: ApplicationMessage,
    ) -> None:
        """Retain the item identity and refresh it without emitting changes."""

        super().__init__(combo)
        self._combo = combo
        self._item_index = item_index
        self._message = message
        combo.installEventFilter(self)
        self.retranslate()

    def update(self, item_index: int, message: ApplicationMessage) -> None:
        """Retarget a reused mixed combo binding after its items are rebuilt."""

        self._item_index = item_index
        self._message = message
        self.retranslate()

    def retranslate(self) -> None:
        """Refresh the owned item without exposing a false selection change."""

        if not 0 <= self._item_index < self._combo.count():
            return
        blocker = QSignalBlocker(self._combo)
        self._combo.setItemText(
            self._item_index,
            render_application_text(self._message),
        )
        del blocker

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Refresh the item when Qt announces an application language change."""

        if watched is self._combo and event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        return False


def set_localized_combo_items(
    combo: QComboBox,
    items: Sequence[LocalizedComboItem],
) -> None:
    """Bind a static set of marked labels to one stable-data combo box."""

    bindings = LocalizationBindings(combo)
    setattr(combo, "_sugarsubstitute_combo_localization", bindings)
    bindings.bind_combo_items(combo, lambda: items)


def set_localized_combo_item(
    combo: QComboBox,
    item_index: int,
    message: ApplicationMessage,
) -> None:
    """Bind one app-owned label in a combo that also contains opaque content."""

    attribute = "_sugarsubstitute_localized_combo_item_bindings"
    bindings = getattr(combo, attribute, None)
    if not isinstance(bindings, dict):
        bindings = {}
        setattr(combo, attribute, bindings)
    binding = bindings.get(item_index)
    if isinstance(binding, LocalizedComboItemTextBinding):
        binding.update(item_index, message)
        return
    bindings[item_index] = LocalizedComboItemTextBinding(
        combo,
        item_index=item_index,
        message=message,
    )


__all__ = [
    "LocalizationBindings",
    "LocalizedComboItem",
    "LocalizedComboItemTextBinding",
    "set_localized_combo_item",
    "set_localized_combo_items",
    "TextFactory",
]
