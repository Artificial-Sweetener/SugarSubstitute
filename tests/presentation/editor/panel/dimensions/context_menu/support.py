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

"""Provide exact Qt ownership and test-local menu recording for dimension rows."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QSpinBox, QVBoxLayout, QWidget

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.domain.node_behavior import FieldBehavior
import substitute.presentation.editor.panel.menus.dimension_row_actions as dimension_row_actions
from substitute.presentation.editor.panel.dimension_presets import (
    DimensionPresetCatalog,
    DimensionPresetCatalogSource,
)
from substitute.presentation.editor.panel.widgets.field_row import (
    BuiltFieldRow,
    FieldRowBuilder,
)
from substitute.presentation.widgets.menu_model import (
    MenuEntry,
    MenuItem,
    MenuModel,
    MenuSection,
    MenuSeparator,
    MenuSubmenu,
)
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application

_WidgetT = TypeVar("_WidgetT", bound=QWidget)


class DimensionPanel(QWidget):
    """Provide the field-row state surface required by the production builder."""

    def __init__(self) -> None:
        """Initialize row tracking containers expected by the builder."""

        super().__init__()
        self.row_widgets: dict[object, tuple[QWidget, QWidget | None]] = {}
        self.col_widgets: dict[object, tuple[QWidget, QWidget, QWidget]] = {}
        self._hidden_field_keys: set[object] = set()


class RecordedAction:
    """Record one rendered menu action and dispatch its callback."""

    def __init__(self, item: MenuItem) -> None:
        """Store the menu item rendered into this action."""

        self._item = item

    def text(self) -> str:
        """Return the localized action text."""

        return render_source_application_text(self._item.label)

    def trigger(self) -> None:
        """Invoke the rendered callback when one is present."""

        if self._item.callback is not None:
            self._item.callback()


class MenuRecording:
    """Own the fake menu tree rendered during one test."""

    def __init__(self) -> None:
        """Initialize an empty ordered menu collection."""

        self.menus: list[RecordedRoundMenu] = []

    @property
    def root(self) -> RecordedRoundMenu:
        """Return the first rendered root menu."""

        assert self.menus
        return self.menus[0]


class RecordedRoundMenu:
    """Record menu entries and execution without opening a native popup."""

    def __init__(
        self,
        recording: MenuRecording,
        *args: object,
        parent: QWidget | None = None,
    ) -> None:
        """Record the menu title, parent, and construction order."""

        self.title = args[0] if args and isinstance(args[0], str) else ""
        if parent is None and args and isinstance(args[-1], QWidget):
            parent = args[-1]
        self.parent = parent
        self.actions: list[RecordedAction] = []
        self.submenus: list[RecordedRoundMenu] = []
        self.entries: list[tuple[str, str]] = []
        self.exec_position: QPoint | None = None
        recording.menus.append(self)

    def addAction(self, action: RecordedAction) -> None:  # noqa: N802
        """Record one menu action."""

        self.actions.append(action)
        self.entries.append(("action", action.text()))

    def addMenu(self, menu: RecordedRoundMenu) -> None:  # noqa: N802
        """Record one nested menu."""

        self.submenus.append(menu)
        self.entries.append(("menu", menu.title))

    def addSeparator(self) -> None:  # noqa: N802
        """Record one menu separator."""

        self.entries.append(("separator", ""))

    def addWidget(  # noqa: N802
        self,
        widget: QWidget,
        selectable: bool = True,
        onClick: Callable[[], None] | None = None,
    ) -> None:
        """Record one custom header widget."""

        _ = (selectable, onClick)
        text_getter = getattr(widget, "text", None)
        text = str(text_getter()) if callable(text_getter) else ""
        self.entries.append(("header", text))

    def exec(self, position: QPoint) -> None:
        """Record the requested global popup position."""

        self.exec_position = position


class RecordedMenuFactory(Protocol):
    """Construct recorded menu instances through a test-bound menu type."""

    def __call__(
        self,
        *args: object,
        parent: QWidget | None = None,
    ) -> RecordedRoundMenu:
        """Construct one recorded root or submenu."""


class RecordingMenuRenderer:
    """Render shared menu models into one test-local recorded menu tree."""

    def __init__(
        self,
        *,
        parent: QWidget,
        recording: MenuRecording,
        menu_type: RecordedMenuFactory,
    ) -> None:
        """Store the parent, recording, and bound fake menu type."""

        self._parent = parent
        self._recording = recording
        self._menu_type = menu_type

    def render(self, model: MenuModel) -> RecordedRoundMenu:
        """Render one root menu from the shared menu model."""

        menu = self._menu_type(parent=self._parent)
        self.populate_menu(menu, model.entries)
        return menu

    def populate_menu(
        self,
        menu: RecordedRoundMenu,
        entries: tuple[MenuEntry, ...],
    ) -> None:
        """Populate a recorded menu recursively from shared menu entries."""

        for entry in entries:
            if isinstance(entry, MenuItem):
                menu.addAction(RecordedAction(entry))
            elif isinstance(entry, MenuSeparator):
                menu.addSeparator()
            elif isinstance(entry, MenuSection):
                if entry.title is not None:
                    menu.entries.append(
                        ("header", render_source_application_text(entry.title))
                    )
                self.populate_menu(menu, entry.entries)
            elif isinstance(entry, MenuSubmenu):
                submenu = self._menu_type(
                    render_source_application_text(entry.label),
                    parent=self._parent,
                )
                self.populate_menu(submenu, entry.entries)
                menu.addMenu(submenu)


def install_recording_dimension_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> MenuRecording:
    """Patch menu construction to one test-local recorder and return it."""

    recording = MenuRecording()

    class BoundRecordedRoundMenu(RecordedRoundMenu):
        """Bind every recorded menu instance to this test's recorder."""

        def __init__(
            self,
            *args: object,
            parent: QWidget | None = None,
        ) -> None:
            """Construct one recorded menu in the current test recording."""

            super().__init__(recording, *args, parent=parent)

    class BoundRecordingMenuRenderer(RecordingMenuRenderer):
        """Bind the shared renderer surface to this test's recorder."""

        def __init__(self, *, parent: QWidget) -> None:
            """Construct a renderer for the production-supplied parent."""

            super().__init__(
                parent=parent,
                recording=recording,
                menu_type=BoundRecordedRoundMenu,
            )

    monkeypatch.setattr(
        dimension_row_actions,
        "RoundMenu",
        BoundRecordedRoundMenu,
    )
    monkeypatch.setattr(
        dimension_row_actions,
        "QFluentMenuRenderer",
        BoundRecordingMenuRenderer,
    )
    return recording


class FakeDimensionPresetSource:
    """Return prepared dimension data and record save commands."""

    def __init__(self, model: DimensionPresetCatalog) -> None:
        """Store the prepared catalog returned to menu construction."""

        self.model = model
        self.global_saves: list[tuple[int, int]] = []
        self.model_saves: list[tuple[int, int]] = []

    def current_dimension_preset_catalog(self) -> DimensionPresetCatalog | None:
        """Return the prepared saved-dimension catalog."""

        return self.model

    def prepare_dimension_preset_catalog(self, *, reason: str) -> None:
        """Fail if foreground menu rendering tries to prepare data."""

        raise AssertionError(f"unexpected menu-open preparation: {reason}")

    def list_dimension_presets(self) -> DimensionPresetCatalog:
        """Fail if foreground menu rendering tries to load saved dimensions."""

        raise AssertionError("unexpected menu-open preset loading")

    def save_current_dimensions_globally(self, width: int, height: int) -> None:
        """Record one global save command."""

        self.global_saves.append((width, height))

    def save_current_dimensions_for_model(self, width: int, height: int) -> None:
        """Record one model-family save command."""

        self.model_saves.append((width, height))


class CountingSpinBox(QSpinBox):
    """Count explicit value reads after setup."""

    def __init__(self, parent: QWidget) -> None:
        """Initialize read tracking before callers set the value."""

        super().__init__(parent)
        self.value_reads = 0

    def value(self) -> int:
        """Return the value and record one explicit read."""

        self.value_reads += 1
        return super().value()


def ensure_worker_application() -> QApplication:
    """Return the worker-owned QApplication."""

    return ensure_qt_application()


def spinbox(parent: QWidget, *, value: int, key: str) -> QSpinBox:
    """Build a numeric editor field with production input metadata."""

    widget = QSpinBox(parent)
    widget.setRange(0, 4096)
    widget.setValue(value)
    widget.setProperty(
        "input_metadata",
        {"cube_alias": "A", "node_name": "resize", "key": key},
    )
    return widget


def counting_spinbox(parent: QWidget, *, value: int, key: str) -> CountingSpinBox:
    """Build a read-counting numeric editor field with production metadata."""

    widget = CountingSpinBox(parent)
    widget.setRange(0, 4096)
    widget.setValue(value)
    widget.value_reads = 0
    widget.setProperty(
        "input_metadata",
        {"cube_alias": "A", "node_name": "resize", "key": key},
    )
    return widget


def add_dimension_row(
    panel: DimensionPanel,
    content_layout: QVBoxLayout,
    *,
    width: QWidget,
    height: QWidget,
    dimension_preset_source: DimensionPresetCatalogSource | None = None,
) -> BuiltFieldRow:
    """Build and mount a source-dimension row through the production builder."""

    builder = FieldRowBuilder(
        panel=panel,
        icon_builder=lambda _icon: QWidget(panel),
        icon_resolver=lambda _node, _label, column_index=None: None,
        dimension_preset_source=dimension_preset_source,
    )
    built_row = builder.build_n_column_row(
        fields=[("source_width", width), ("source_height", height)],
        field_behaviors={
            "source_width": FieldBehavior(field_key="source_width"),
            "source_height": FieldBehavior(field_key="source_height"),
        },
        node_name="resize",
    )
    content_layout.addWidget(built_row.row)
    if built_row.field_key is not None:
        panel.row_widgets[built_row.field_key] = (built_row.row, None)
    return built_row


def first_row(layout: QVBoxLayout) -> QWidget:
    """Return the first mounted row widget."""

    item = layout.itemAt(0)
    assert item is not None
    widget = item.widget()
    assert widget is not None
    return widget


def submenu(menu: RecordedRoundMenu, title: str) -> RecordedRoundMenu:
    """Return one recorded submenu by title."""

    return next(child for child in menu.submenus if child.title == title)


def action(menu: RecordedRoundMenu, text: str) -> RecordedAction:
    """Return one recorded action by localized text."""

    return next(candidate for candidate in menu.actions if candidate.text() == text)


def cleanup_widgets(
    application: QApplication,
    *widgets: QWidget,
) -> None:
    """Synchronously destroy independent widget roots in supplied order."""

    _ = application
    for widget in widgets:
        destroy_qt_object(widget)


__all__ = [
    "CountingSpinBox",
    "DimensionPanel",
    "FakeDimensionPresetSource",
    "MenuRecording",
    "RecordedAction",
    "RecordedRoundMenu",
    "action",
    "add_dimension_row",
    "counting_spinbox",
    "cleanup_widgets",
    "ensure_worker_application",
    "first_row",
    "install_recording_dimension_menu",
    "spinbox",
    "submenu",
]
