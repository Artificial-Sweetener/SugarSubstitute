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

"""Render shared menu models through QFluent without repeated layout churn."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QListWidgetItem, QWidget
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    Action,
    MenuAnimationType,
    RoundMenu,
)

from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)
from sugarsubstitute_shared.presentation.localization import render_application_text
from sugarsubstitute_shared.presentation.localization import (
    ApplicationMessage,
    ApplicationText,
    LocalizationBindings,
)

from .menu_model import (
    LazyMenuSubmenu,
    MenuEntry,
    MenuItem,
    MenuModel,
    MenuSection,
    MenuSeparator,
    MenuSubmenu,
)


class QFluentMenuRenderer:
    """Convert shared menu models into QFluent menus."""

    def __init__(self, *, parent: QWidget) -> None:
        """Store the Qt parent used for generated menus and actions."""

        self._parent = parent
        self._localization_bindings = LocalizationBindings(parent)
        _retain_localization_bindings(parent, self._localization_bindings)

    def render(self, model: MenuModel) -> RoundMenu:
        """Return a QFluent menu populated from ``model``."""

        menu = (
            RoundMenu(render_application_text(model.title), self._parent)
            if model.title
            else RoundMenu(parent=self._parent)
        )
        if model.object_name is not None:
            menu.setObjectName(model.object_name)
        self._bind_text(menu.setTitle, model.title)
        self.populate_menu(menu, model.entries)
        return menu

    def populate_menu(self, menu: RoundMenu, entries: Iterable[MenuEntry]) -> None:
        """Populate ``menu`` from entries using one final size adjustment."""

        writer = _BatchedRoundMenuWriter(menu)
        for entry in entries:
            self._add_entry(writer, entry)
        writer.finish()

    def _add_entry(
        self,
        writer: "_BatchedRoundMenuWriter",
        entry: MenuEntry,
    ) -> None:
        """Add one model entry to a batched menu writer."""

        if isinstance(entry, MenuItem):
            writer.add_action(self._action_for_item(entry))
            return
        if isinstance(entry, MenuSeparator):
            writer.add_separator()
            return
        if isinstance(entry, MenuSection):
            self._add_section(writer, entry)
            return
        if isinstance(entry, MenuSubmenu):
            submenu = self._submenu_for_entry(entry, parent_menu=writer.menu)
            writer.add_menu(submenu)
            return
        if isinstance(entry, LazyMenuSubmenu):
            submenu = _LazyQFluentSubmenu(entry, parent=writer.menu, renderer=self)
            writer.add_menu(submenu)
            return

    def _add_section(
        self,
        writer: "_BatchedRoundMenuWriter",
        section: MenuSection,
    ) -> None:
        """Add one menu section with an optional disabled header."""

        if section.title is not None:
            header = QAction(render_application_text(section.title), self._parent)
            header.setEnabled(False)
            self._bind_text(header.setText, section.title)
            writer.add_action(header)
        for entry in section.entries:
            self._add_entry(writer, entry)

    def _submenu_for_entry(
        self,
        entry: MenuSubmenu,
        *,
        parent_menu: RoundMenu,
    ) -> RoundMenu:
        """Return an eagerly populated submenu for one model entry."""

        submenu = RoundMenu(render_application_text(entry.label), parent_menu)
        self._bind_text(submenu.setTitle, entry.label)
        submenu.setEnabled(
            entry.enabled and menu_entries_have_enabled_action(entry.entries)
        )
        if entry.icon is not None:
            submenu.setIcon(cast(Any, entry.icon))
        self.populate_menu(submenu, entry.entries)
        setattr(submenu, "_sugarsubstitute_localized_menu_label", entry.label)
        return submenu

    def _action_for_item(self, item: MenuItem) -> QAction:
        """Return a Qt action for one model item."""

        action = _new_action(
            label=render_application_text(item.label),
            parent=self._parent,
            icon=item.icon,
        )
        action.setEnabled(item.enabled)
        self._bind_text(action.setText, item.label)
        action.setProperty("menuActionId", item.action_id)
        action.setCheckable(item.checkable)
        if item.checkable:
            action.setChecked(item.checked)
        if item.shortcut is not None:
            action.setShortcut(item.shortcut)
        if item.tooltip is not None:
            set_fluent_tooltip_text(action, render_application_text(item.tooltip))
            self._bind_text(
                lambda text: set_fluent_tooltip_text(action, text),
                item.tooltip,
            )
        if item.data is not None:
            action.setData(item.data)
        for name, value in item.properties.items():
            action.setProperty(name, value)
        if item.callback is not None:
            action.triggered.connect(
                lambda _checked=False, callback=item.callback: callback()
            )
        if item.checked_callback is not None:
            action.toggled.connect(item.checked_callback)
        return action

    def _bind_text(
        self,
        setter: object,
        text: ApplicationText,
    ) -> None:
        """Retranslate marked application copy while preserving opaque content."""

        if not isinstance(text, ApplicationMessage) or not callable(setter):
            return
        self._localization_bindings.bind_setter(
            setter,
            lambda: render_application_text(text),
        )


def menu_entries_have_enabled_action(entries: Iterable[MenuEntry]) -> bool:
    """Return whether a menu entry tree contains an enabled executable action."""

    for entry in entries:
        if isinstance(entry, MenuItem) and entry.enabled:
            return True
        if isinstance(entry, MenuSection) and menu_entries_have_enabled_action(
            entry.entries
        ):
            return True
        if isinstance(entry, MenuSubmenu) and entry.enabled:
            if menu_entries_have_enabled_action(entry.entries):
                return True
        if isinstance(entry, LazyMenuSubmenu) and entry.enabled:
            return True
    return False


class _LazyQFluentSubmenu(RoundMenu):  # type: ignore[misc]
    """Populate a QFluent submenu only when it is opened."""

    def __init__(
        self,
        model: LazyMenuSubmenu,
        *,
        parent: QWidget,
        renderer: QFluentMenuRenderer,
    ) -> None:
        """Store lazy model state until the submenu opens."""

        super().__init__(render_application_text(model.label), parent)
        self._model = model
        self._renderer = renderer
        self._populated = False
        self._renderer._bind_text(self.setTitle, model.label)
        setattr(self, "_sugarsubstitute_localized_menu_label", model.label)
        self.setEnabled(model.enabled)
        if model.icon is not None:
            self.setIcon(cast(Any, model.icon))

    def exec(
        self,
        pos: object,
        ani: bool = True,
        aniType: MenuAnimationType = MenuAnimationType.DROP_DOWN,
    ) -> object:
        """Populate entries before showing the submenu."""

        self.populate_if_needed()
        return super().exec(pos, ani, aniType)

    def populate_if_needed(self) -> None:
        """Populate the submenu once or on each open according to the model."""

        if self._populated and self._model.cache_entries:
            return
        self.clear()
        entries = self._model.entries_factory()
        self._renderer.populate_menu(self, entries)
        self.setEnabled(
            self._model.enabled and menu_entries_have_enabled_action(entries)
        )
        self._populated = True


class _BatchedRoundMenuWriter:
    """Append rows to a RoundMenu while deferring expensive final sizing."""

    def __init__(self, menu: RoundMenu) -> None:
        """Store the QFluent menu being populated."""

        self.menu = menu
        self._changed = False

    def add_action(self, action: QAction) -> None:
        """Append an action without calling RoundMenu.addAction()."""

        create_item = getattr(self.menu, "_createActionItem")
        item = cast(QListWidgetItem, create_item(action))
        self.menu.view.addItem(item)
        self._changed = True

    def add_menu(self, submenu: RoundMenu) -> None:
        """Append a submenu without per-row menu resizing."""

        create_submenu_item = getattr(self.menu, "_createSubMenuItem")
        item, widget = create_submenu_item(submenu)
        label = getattr(submenu, "_sugarsubstitute_localized_menu_label", None)
        if isinstance(label, ApplicationMessage):
            prefix = " " if submenu.icon().isNull() is False else ""
            self._menu_bindings().bind_setter(
                cast(QListWidgetItem, item).setText,
                lambda: f"{prefix}{render_application_text(label)}",
            )
        self.menu.view.addItem(cast(QListWidgetItem, item))
        self.menu.view.setItemWidget(cast(QListWidgetItem, item), cast(QWidget, widget))
        self._changed = True

    def _menu_bindings(self) -> LocalizationBindings:
        """Return the renderer-owned bindings associated with this menu."""

        bindings = getattr(self.menu, "_sugarsubstitute_menu_bindings", None)
        if isinstance(bindings, LocalizationBindings):
            return bindings
        bindings = LocalizationBindings(self.menu)
        setattr(self.menu, "_sugarsubstitute_menu_bindings", bindings)
        return bindings

    def add_separator(self) -> None:
        """Append a separator without calling RoundMenu.addSeparator()."""

        margins = self.menu.view.viewportMargins()
        width = self.menu.view.width() - margins.left() - margins.right()
        item = QListWidgetItem()
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setSizeHint(QSize(width, 9))
        self.menu.view.addItem(item)
        item.setData(Qt.ItemDataRole.DecorationRole, "seperator")
        self._changed = True

    def finish(self) -> None:
        """Run one final size adjustment after batched population."""

        if not self._changed:
            return
        self.menu.view.adjustSize()
        self.menu.adjustSize()


def _new_action(
    *,
    label: str,
    parent: QWidget,
    icon: object | None,
) -> QAction:
    """Return a QAction-compatible row using QFluent icons when provided."""

    if icon is None:
        return QAction(label, parent)
    return cast(QAction, Action(cast(Any, icon), label, parent))


def _retain_localization_bindings(
    owner: QWidget,
    bindings: LocalizationBindings,
) -> None:
    """Retain renderer bindings for the lifetime of their presentation owner."""

    attribute = "_sugarsubstitute_menu_renderer_bindings"
    retained = getattr(owner, attribute, None)
    if not isinstance(retained, list):
        retained = []
        setattr(owner, attribute, retained)
    retained.append(bindings)


__all__ = [
    "QFluentMenuRenderer",
    "menu_entries_have_enabled_action",
]
