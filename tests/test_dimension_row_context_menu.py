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

"""Qt contract tests for dimension-row context menu actions."""

from __future__ import annotations

import os
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtWidgets import QApplication, QLineEdit, QSpinBox, QVBoxLayout, QWidget

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.domain.node_behavior import FieldBehavior
from substitute.application.node_behavior import DimensionFieldPair
import substitute.presentation.editor.panel.menus.dimension_row_actions as dimension_row_actions
from substitute.presentation.editor.panel.menus.dimension_preset_models import (
    DimensionPresetMenuItem,
    DimensionPresetMenuModel,
    DimensionPresetMenuSection,
)
from substitute.presentation.editor.panel.menus.dimension_row_actions import (
    AspectRatioPreset,
    DimensionRowBinding,
    DimensionSide,
    apply_aspect_ratio,
)
from substitute.presentation.widgets.menu_model import (
    MenuItem,
    MenuModel,
    MenuSection,
    MenuSeparator,
    MenuSubmenu,
)
from substitute.presentation.editor.panel.widgets.field_row import FieldRowBuilder

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "dimension row QFluent context-menu tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


class _Panel(QWidget):
    """Minimal QWidget panel double for field-row rendering tests."""

    def __init__(self) -> None:
        """Initialize row tracking containers expected by the builder."""

        super().__init__()
        self.row_widgets: dict[object, tuple[QWidget, QWidget | None]] = {}
        self.col_widgets: dict[object, tuple[QWidget, QWidget, QWidget]] = {}
        self._hidden_field_keys: set[object] = set()


class _FakeRoundMenu:
    """Record menu actions, submenus, and execution positions without a popup."""

    instances: list["_FakeRoundMenu"] = []

    def __init__(self, *args: Any, parent: QWidget | None = None) -> None:
        """Record the created menu, title, and parent widget."""

        self.title = args[0] if args and isinstance(args[0], str) else ""
        if parent is None and args and isinstance(args[-1], QWidget):
            parent = args[-1]
        self.parent = parent
        self.actions: list[Any] = []
        self.submenus: list["_FakeRoundMenu"] = []
        self.entries: list[tuple[str, str]] = []
        self.exec_position: QPoint | None = None
        self.instances.append(self)

    def addAction(self, action: Any) -> None:
        """Record one menu action."""

        self.actions.append(action)
        self.entries.append(("action", action.text()))

    def addMenu(self, menu: "_FakeRoundMenu") -> None:
        """Record one nested menu."""

        self.submenus.append(menu)
        self.entries.append(("menu", menu.title))

    def addSeparator(self) -> None:
        """Record one menu separator."""

        self.entries.append(("separator", ""))

    def addWidget(
        self,
        widget: QWidget,
        selectable: bool = True,
        onClick: Any | None = None,
    ) -> None:
        """Record one custom menu widget."""

        _ = (selectable, onClick)
        text = getattr(widget, "text", lambda: "")()
        self.entries.append(("header", text))

    def exec(self, position: QPoint) -> None:
        """Record the requested global popup position."""

        self.exec_position = position


class _FakeAction:
    """Record one rendered menu action and dispatch its callback."""

    def __init__(self, item: MenuItem) -> None:
        """Store the menu item used to create this fake action."""

        self._item = item

    def text(self) -> str:
        """Return the rendered action text."""

        return render_source_application_text(self._item.label)

    def trigger(self) -> None:
        """Invoke the rendered callback."""

        if self._item.callback is not None:
            self._item.callback()


class _FakeQFluentMenuRenderer:
    """Render shared menu models into fake dimension menu trees."""

    def __init__(self, *, parent: QWidget) -> None:
        """Store the parent used for root and child fake menus."""

        self._parent = parent

    def render(self, model: MenuModel) -> _FakeRoundMenu:
        """Return a fake root menu populated from the shared menu model."""

        menu = _FakeRoundMenu(parent=self._parent)
        self.populate_menu(menu, model.entries)
        return menu

    def populate_menu(
        self,
        menu: _FakeRoundMenu,
        entries: tuple[object, ...],
    ) -> None:
        """Populate a fake menu from shared menu entries."""

        for entry in entries:
            if isinstance(entry, MenuItem):
                menu.addAction(_FakeAction(entry))
            elif isinstance(entry, MenuSeparator):
                menu.addSeparator()
            elif isinstance(entry, MenuSection):
                if entry.title is not None:
                    menu.entries.append(
                        ("header", render_source_application_text(entry.title))
                    )
                self.populate_menu(menu, entry.entries)
            elif isinstance(entry, MenuSubmenu):
                submenu = _FakeRoundMenu(
                    render_source_application_text(entry.label),
                    parent=self._parent,
                )
                self.populate_menu(submenu, entry.entries)
                menu.addMenu(submenu)


def _install_fake_dimension_menu(monkeypatch: Any) -> None:
    """Patch dimension menus to render into fake menu trees."""

    _FakeRoundMenu.instances.clear()
    monkeypatch.setattr(dimension_row_actions, "RoundMenu", _FakeRoundMenu)
    monkeypatch.setattr(
        dimension_row_actions,
        "QFluentMenuRenderer",
        _FakeQFluentMenuRenderer,
    )


class _FakeDimensionPresetSource:
    """Return deterministic saved dimension menu data and record saves."""

    def __init__(self, model: DimensionPresetMenuModel) -> None:
        """Store the menu model returned by this source."""

        self.model = model
        self.global_saves: list[tuple[int, int]] = []
        self.model_saves: list[tuple[int, int]] = []

    def current_dimension_preset_menu_model(self) -> DimensionPresetMenuModel | None:
        """Return prepared saved dimension menu sections."""

        return self.model

    def prepare_dimension_preset_menu_model(self, *, reason: str) -> None:
        """Fail if menu rendering tries to prepare foreground data."""

        raise AssertionError(f"unexpected menu-open preparation: {reason}")

    def list_dimension_presets(self) -> DimensionPresetMenuModel:
        """Fail if menu rendering tries to load saved dimensions."""

        raise AssertionError("unexpected menu-open preset loading")

    def save_current_dimensions_globally(self, width: int, height: int) -> None:
        """Record one global save request."""

        self.global_saves.append((width, height))

    def save_current_dimensions_for_model(self, width: int, height: int) -> None:
        """Record one model-family save request."""

        self.model_saves.append((width, height))


class _TimerDouble:
    """Record timer stop calls from submenu click handling."""

    def __init__(self) -> None:
        """Initialize timer call tracking."""

        self.stop_calls = 0

    def stop(self) -> None:
        """Record one stop request."""

        self.stop_calls += 1


class _ClickableMenuDouble(QObject):
    """Record QFluent submenu open state used by the click opener."""

    def __init__(self) -> None:
        """Initialize submenu hover/open tracking."""

        super().__init__()
        self.timer = _TimerDouble()
        self.lastHoverItem: object | None = None
        self.lastHoverSubMenuItem: object | None = None
        self.open_calls = 0

    def _onShowMenuTimeOut(self) -> None:
        """Record immediate submenu opening through QFluent placement logic."""

        self.open_calls += 1


class _SubmenuDouble:
    """Provide a menu item identity for submenu click tests."""

    def __init__(self) -> None:
        """Initialize the submenu item sentinel."""

        self.menuItem = object()


class _CountingSpinBox(QSpinBox):
    """Record value reads separately from normal widget setup."""

    def __init__(self, parent: QWidget) -> None:
        """Initialize read tracking before callers set the value."""

        super().__init__(parent)
        self.value_reads = 0

    def value(self) -> int:
        """Return the spinbox value and record an explicit read."""

        self.value_reads += 1
        return super().value()


def test_dimension_group_context_menu_swaps_width_and_height(
    monkeypatch: Any,
) -> None:
    """Right-clicking a dimension row should expose and run the swap action."""

    app = _ensure_app()
    _install_fake_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=512, key="source_width")
        height = _spinbox(panel, value=768, key="source_height")
        builder = FieldRowBuilder(
            panel=panel,
            icon_builder=lambda _icon: QWidget(panel),
            icon_resolver=lambda _node, _label, column_index=None: None,
        )

        builder.add_n_column_row(
            fields=[("source_width", width), ("source_height", height)],
            field_behaviors={
                "source_width": FieldBehavior(field_key="source_width"),
                "source_height": FieldBehavior(field_key="source_height"),
            },
            content_layout=content_layout,
            node_name="resize",
        )
        row = _first_row(content_layout)

        assert row.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
        assert row.property("dimension_field_group") == [
            "source_width",
            "source_height",
        ]

        row.customContextMenuRequested.emit(QPoint(4, 4))

        menu = _FakeRoundMenu.instances[0]
        assert [action.text() for action in menu.actions] == ["Swap width & height"]
        menu.actions[0].trigger()

        assert width.value() == 768
        assert height.value() == 512
    finally:
        _cleanup_widgets(app, content, panel)


def test_dimension_group_binding_does_not_read_values_during_row_build(
    monkeypatch: Any,
) -> None:
    """Card construction should not read width or height until an action needs values."""

    app = _ensure_app()
    _install_fake_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        width = _counting_spinbox(panel, value=512, key="source_width")
        height = _counting_spinbox(panel, value=768, key="source_height")

        _add_dimension_row(panel, content_layout, width=width, height=height)

        assert width.value_reads == 0
        assert height.value_reads == 0

        width.customContextMenuRequested.emit(QPoint(1, 1))
        assert width.value_reads == 0
        assert height.value_reads == 0

        _FakeRoundMenu.instances[0].actions[0].trigger()
        assert width.value_reads == 1
        assert height.value_reads == 1
    finally:
        _cleanup_widgets(app, content, panel)


def test_dimension_group_without_saved_source_omits_set_dimensions_menu(
    monkeypatch: Any,
) -> None:
    """Saved dimensions should be absent unless a source is provided."""

    app = _ensure_app()
    _install_fake_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=1600, key="source_width")
        height = _spinbox(panel, value=900, key="source_height")
        _add_dimension_row(panel, content_layout, width=width, height=height)

        width.customContextMenuRequested.emit(QPoint(1, 1))

        root_menu = _FakeRoundMenu.instances[0]
        assert [submenu.title for submenu in root_menu.submenus] == [
            "Set ratio by Width"
        ]
    finally:
        _cleanup_widgets(app, content, panel)


def test_dimension_group_context_menu_contains_aspect_ratio_submenus(
    monkeypatch: Any,
) -> None:
    """Dimension row context menu should expose the decided ratio preset lists."""

    app = _ensure_app()
    _install_fake_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=1600, key="source_width")
        height = _spinbox(panel, value=900, key="source_height")
        _add_dimension_row(panel, content_layout, width=width, height=height)

        width.customContextMenuRequested.emit(QPoint(1, 1))

        root_menu = _FakeRoundMenu.instances[0]
        assert [action.text() for action in root_menu.actions] == [
            "Swap width & height"
        ]
        aspect_menu = _submenu(root_menu, "Set ratio by Width")
        landscape_menu = _submenu(aspect_menu, "Landscape")
        portrait_menu = _submenu(aspect_menu, "Portrait")
        assert [action.text() for action in landscape_menu.actions] == [
            "1:1",
            "5:4",
            "4:3",
            "3:2",
            "16:9",
            "2:1",
            "21:9",
        ]
        assert [action.text() for action in portrait_menu.actions] == [
            "1:1",
            "4:5",
            "3:4",
            "2:3",
            "9:16",
            "1:2",
            "9:21",
        ]
    finally:
        _cleanup_widgets(app, content, panel)


def test_dimension_group_with_saved_source_places_set_dimensions_before_ratio(
    monkeypatch: Any,
) -> None:
    """Saved dimensions should appear before ratio and save should sit at the bottom."""

    app = _ensure_app()
    _install_fake_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    source = _FakeDimensionPresetSource(
        DimensionPresetMenuModel(
            sections=(
                DimensionPresetMenuSection(
                    title="Global",
                    presets=(
                        DimensionPresetMenuItem(
                            label="832 x 1216",
                            short_edge=832,
                            long_edge=1216,
                        ),
                    ),
                ),
            )
        )
    )
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=1600, key="source_width")
        height = _spinbox(panel, value=900, key="source_height")
        _add_dimension_row(
            panel,
            content_layout,
            width=width,
            height=height,
            dimension_preset_source=source,
        )

        width.customContextMenuRequested.emit(QPoint(1, 1))

        root_menu = _FakeRoundMenu.instances[0]
        assert root_menu.entries == [
            ("action", "Swap width & height"),
            ("menu", "Set dimensions"),
            ("menu", "Set ratio by Width"),
            ("separator", ""),
            ("menu", "Save current dimensions"),
        ]
        assert [submenu.title for submenu in root_menu.submenus] == [
            "Set dimensions",
            "Set ratio by Width",
            "Save current dimensions",
        ]
        save_menu = _submenu(root_menu, "Save current dimensions")
        assert [action.text() for action in save_menu.actions] == ["Save globally"]
    finally:
        _cleanup_widgets(app, content, panel)


def test_saved_dimension_actions_apply_portrait_and_landscape(
    monkeypatch: Any,
) -> None:
    """Saved dimension presets should write both fields in selected orientation."""

    app = _ensure_app()
    _install_fake_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    source = _FakeDimensionPresetSource(
        DimensionPresetMenuModel(
            sections=(
                DimensionPresetMenuSection(
                    title="For Illustrious",
                    presets=(
                        DimensionPresetMenuItem(
                            label="1024 x 1536",
                            short_edge=1024,
                            long_edge=1536,
                        ),
                    ),
                ),
                DimensionPresetMenuSection(
                    title="Global",
                    presets=(
                        DimensionPresetMenuItem(
                            label="SDXL square",
                            short_edge=1024,
                            long_edge=1024,
                        ),
                    ),
                ),
            ),
            model_save_label="Illustrious",
        )
    )
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=512, key="source_width")
        height = _spinbox(panel, value=768, key="source_height")
        _add_dimension_row(
            panel,
            content_layout,
            width=width,
            height=height,
            dimension_preset_source=source,
        )

        width.customContextMenuRequested.emit(QPoint(1, 1))

        dimensions_menu = _submenu(_FakeRoundMenu.instances[0], "Set dimensions")
        assert dimensions_menu.entries == [
            ("menu", "Portrait"),
            ("menu", "Landscape"),
        ]
        portrait_menu = _submenu(dimensions_menu, "Portrait")
        landscape_menu = _submenu(dimensions_menu, "Landscape")
        assert portrait_menu.entries == [
            ("header", "For Illustrious"),
            ("action", "1024 x 1536"),
            ("separator", ""),
            ("header", "Global"),
            ("action", "SDXL square 1024 x 1024"),
        ]
        assert landscape_menu.entries == [
            ("header", "For Illustrious"),
            ("action", "1536 x 1024"),
            ("separator", ""),
            ("header", "Global"),
            ("action", "SDXL square 1024 x 1024"),
        ]
        assert [action.text() for action in portrait_menu.actions] == [
            "1024 x 1536",
            "SDXL square 1024 x 1024",
        ]
        assert [action.text() for action in landscape_menu.actions] == [
            "1536 x 1024",
            "SDXL square 1024 x 1024",
        ]

        _action(portrait_menu, "1024 x 1536").trigger()
        assert (width.value(), height.value()) == (1024, 1536)

        _action(landscape_menu, "1536 x 1024").trigger()
        assert (width.value(), height.value()) == (1536, 1024)

        _action(portrait_menu, "SDXL square 1024 x 1024").trigger()
        assert (width.value(), height.value()) == (1024, 1024)
    finally:
        _cleanup_widgets(app, content, panel)


def test_save_current_dimensions_actions_call_source(
    monkeypatch: Any,
) -> None:
    """Save actions should pass current absolute dimensions to the source."""

    app = _ensure_app()
    _install_fake_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    source = _FakeDimensionPresetSource(
        DimensionPresetMenuModel(model_save_label="Illustrious")
    )
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=1024, key="source_width")
        height = _spinbox(panel, value=1536, key="source_height")
        _add_dimension_row(
            panel,
            content_layout,
            width=width,
            height=height,
            dimension_preset_source=source,
        )

        width.customContextMenuRequested.emit(QPoint(1, 1))

        save_menu = _submenu(_FakeRoundMenu.instances[0], "Save current dimensions")
        assert [action.text() for action in save_menu.actions] == [
            "Save globally",
            "Save for Illustrious",
        ]
        _action(save_menu, "Save globally").trigger()
        _action(save_menu, "Save for Illustrious").trigger()

        assert source.global_saves == [(1024, 1536)]
        assert source.model_saves == [(1024, 1536)]
    finally:
        _cleanup_widgets(app, content, panel)


def test_save_for_model_is_omitted_without_family(
    monkeypatch: Any,
) -> None:
    """Model-family save action should be absent when no family is available."""

    app = _ensure_app()
    _install_fake_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    source = _FakeDimensionPresetSource(DimensionPresetMenuModel())
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=1024, key="source_width")
        height = _spinbox(panel, value=1536, key="source_height")
        _add_dimension_row(
            panel,
            content_layout,
            width=width,
            height=height,
            dimension_preset_source=source,
        )

        width.customContextMenuRequested.emit(QPoint(1, 1))

        save_menu = _submenu(_FakeRoundMenu.instances[0], "Save current dimensions")
        assert [action.text() for action in save_menu.actions] == ["Save globally"]
    finally:
        _cleanup_widgets(app, content, panel)


def test_submenu_click_opener_consumes_click_and_opens_submenu() -> None:
    """Clicking a submenu row should open the child menu instead of closing menus."""

    app = _ensure_app()
    parent_menu = _ClickableMenuDouble()
    submenu = _SubmenuDouble()
    opener = dimension_row_actions._SubmenuClickOpener(
        parent_menu,
        submenu,
        parent_menu,
    )
    watched = QObject()

    assert opener.eventFilter(watched, QEvent(QEvent.Type.MouseButtonPress)) is True
    assert opener.eventFilter(watched, QEvent(QEvent.Type.MouseButtonRelease)) is True
    app.processEvents()

    assert parent_menu.timer.stop_calls == 1
    assert parent_menu.open_calls == 1
    assert parent_menu.lastHoverItem is submenu.menuItem
    assert parent_menu.lastHoverSubMenuItem is submenu.menuItem


def test_menu_open_consumes_prepared_snapshot_without_loading_presets(
    monkeypatch: Any,
) -> None:
    """Saved dimensions should be rendered only from a prepared model."""

    class _PreparedOnlySource:
        """Expose a prepared model and reject foreground preparation/loading."""

        def __init__(self) -> None:
            """Initialize with no prepared saved dimensions."""

            self.current_calls = 0

        def current_dimension_preset_menu_model(
            self,
        ) -> DimensionPresetMenuModel | None:
            """Return no prepared dimensions for this menu invocation."""

            self.current_calls += 1
            return None

        def prepare_dimension_preset_menu_model(self, *, reason: str) -> None:
            """Fail if context-menu opening tries to prepare data."""

            raise AssertionError(f"unexpected menu-open preparation: {reason}")

        def list_dimension_presets(self) -> DimensionPresetMenuModel:
            """Fail if context-menu opening tries to load presets."""

            raise AssertionError("unexpected menu-open preset loading")

        def save_current_dimensions_globally(self, width: int, height: int) -> None:
            """Unused save method required by the protocol."""

            _ = (width, height)

        def save_current_dimensions_for_model(self, width: int, height: int) -> None:
            """Unused save method required by the protocol."""

            _ = (width, height)

    app = _ensure_app()
    _install_fake_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    source = _PreparedOnlySource()
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=1024, key="source_width")
        height = _spinbox(panel, value=1536, key="source_height")
        _add_dimension_row(
            panel,
            content_layout,
            width=width,
            height=height,
            dimension_preset_source=source,
        )

        width.customContextMenuRequested.emit(QPoint(1, 1))

        assert source.current_calls == 1
        assert [submenu.title for submenu in _FakeRoundMenu.instances[0].submenus] == [
            "Set ratio by Width"
        ]
    finally:
        _cleanup_widgets(app, content, panel)


def test_width_side_ratio_action_preserves_width_and_updates_height(
    monkeypatch: Any,
) -> None:
    """Aspect-ratio actions from the width widget should anchor width."""

    app = _ensure_app()
    _install_fake_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=1600, key="source_width")
        height = _spinbox(panel, value=100, key="source_height")
        _add_dimension_row(panel, content_layout, width=width, height=height)

        width.customContextMenuRequested.emit(QPoint(1, 1))

        _action(
            _submenu(
                _submenu(_FakeRoundMenu.instances[0], "Set ratio by Width"),
                "Landscape",
            ),
            "16:9",
        ).trigger()
        assert width.value() == 1600
        assert height.value() == 900
    finally:
        _cleanup_widgets(app, content, panel)


def test_height_side_ratio_action_preserves_height_and_updates_width(
    monkeypatch: Any,
) -> None:
    """Aspect-ratio actions from the height widget should anchor height."""

    app = _ensure_app()
    _install_fake_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=100, key="source_width")
        height = _spinbox(panel, value=1000, key="source_height")
        _add_dimension_row(panel, content_layout, width=width, height=height)

        height.customContextMenuRequested.emit(QPoint(1, 1))

        _action(
            _submenu(
                _submenu(_FakeRoundMenu.instances[0], "Set ratio by Height"),
                "Portrait",
            ),
            "4:5",
        ).trigger()
        assert width.value() == 800
        assert height.value() == 1000
    finally:
        _cleanup_widgets(app, content, panel)


def test_non_dimension_group_does_not_get_dimension_context_menu() -> None:
    """Non-dimension groups should not receive the swap context action."""

    app = _ensure_app()
    panel = _Panel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=512, key="source_width")
        height = _spinbox(panel, value=768, key="target_height")
        builder = FieldRowBuilder(
            panel=panel,
            icon_builder=lambda _icon: QWidget(panel),
            icon_resolver=lambda _node, _label, column_index=None: None,
        )

        builder.add_n_column_row(
            fields=[("source_width", width), ("target_height", height)],
            field_behaviors={
                "source_width": FieldBehavior(field_key="source_width"),
                "target_height": FieldBehavior(field_key="target_height"),
            },
            content_layout=content_layout,
            node_name="resize",
        )
        row = _first_row(content_layout)

        assert row.contextMenuPolicy() == Qt.ContextMenuPolicy.DefaultContextMenu
        assert row.property("dimension_field_group") is None
    finally:
        _cleanup_widgets(app, content, panel)


def test_unsupported_dimension_widgets_do_not_get_dimension_context_menu() -> None:
    """Dimension rows without readable and writable fields should not bind actions."""

    app = _ensure_app()
    panel = _Panel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        width = QWidget(panel)
        height = QWidget(panel)
        builder = FieldRowBuilder(
            panel=panel,
            icon_builder=lambda _icon: QWidget(panel),
            icon_resolver=lambda _node, _label, column_index=None: None,
        )

        builder.add_n_column_row(
            fields=[("source_width", width), ("source_height", height)],
            field_behaviors={
                "source_width": FieldBehavior(field_key="source_width"),
                "source_height": FieldBehavior(field_key="source_height"),
            },
            content_layout=content_layout,
            node_name="resize",
        )
        row = _first_row(content_layout)

        assert row.contextMenuPolicy() == Qt.ContextMenuPolicy.DefaultContextMenu
        assert row.property("dimension_field_group") is None
    finally:
        _cleanup_widgets(app, content, panel)


@pytest.mark.parametrize(
    ("anchor_side", "preset", "width_value", "height_value", "expected"),
    [
        (DimensionSide.WIDTH, AspectRatioPreset("16:9", 16, 9), 1600, 100, (1600, 900)),
        (DimensionSide.HEIGHT, AspectRatioPreset("16:9", 16, 9), 100, 900, (1600, 900)),
        (DimensionSide.WIDTH, AspectRatioPreset("4:5", 4, 5), 800, 100, (800, 1000)),
        (DimensionSide.HEIGHT, AspectRatioPreset("4:5", 4, 5), 100, 1000, (800, 1000)),
        (DimensionSide.WIDTH, AspectRatioPreset("1:1", 1, 1), 512, 1000, (512, 512)),
        (DimensionSide.HEIGHT, AspectRatioPreset("1:1", 1, 1), 1000, 512, (512, 512)),
    ],
)
def test_apply_aspect_ratio_preserves_anchor_side(
    anchor_side: DimensionSide,
    preset: AspectRatioPreset,
    width_value: int,
    height_value: int,
    expected: tuple[int, int],
) -> None:
    """Aspect-ratio math should update only the non-anchored side."""

    app = _ensure_app()
    panel = _Panel()
    width = _spinbox(panel, value=width_value, key="source_width")
    height = _spinbox(panel, value=height_value, key="source_height")
    try:
        binding = _binding(panel, width=width, height=height)

        apply_aspect_ratio(binding, anchor_side=anchor_side, preset=preset)

        assert (width.value(), height.value()) == expected
    finally:
        _cleanup_widgets(app, panel)


def test_apply_aspect_ratio_ignores_non_numeric_values() -> None:
    """Non-numeric anchors should not cause partial writes."""

    app = _ensure_app()
    panel = _Panel()
    width = QLineEdit(panel)
    height = QLineEdit(panel)
    width.setText("wide")
    height.setText("tall")
    try:
        binding = _binding(panel, width=width, height=height)

        apply_aspect_ratio(
            binding,
            anchor_side=DimensionSide.WIDTH,
            preset=AspectRatioPreset("16:9", 16, 9),
        )

        assert width.text() == "wide"
        assert height.text() == "tall"
    finally:
        _cleanup_widgets(app, panel)


def _ensure_app() -> QApplication:
    """Return an existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _spinbox(parent: QWidget, *, value: int, key: str) -> QSpinBox:
    """Return a spinbox tagged like an editor field widget."""

    spinbox = QSpinBox(parent)
    spinbox.setRange(0, 4096)
    spinbox.setValue(value)
    spinbox.setProperty(
        "input_metadata",
        {"cube_alias": "A", "node_name": "resize", "key": key},
    )
    return spinbox


def _counting_spinbox(parent: QWidget, *, value: int, key: str) -> _CountingSpinBox:
    """Return a counting spinbox tagged like an editor field widget."""

    spinbox = _CountingSpinBox(parent)
    spinbox.setRange(0, 4096)
    spinbox.setValue(value)
    spinbox.value_reads = 0
    spinbox.setProperty(
        "input_metadata",
        {"cube_alias": "A", "node_name": "resize", "key": key},
    )
    return spinbox


def _add_dimension_row(
    panel: _Panel,
    content_layout: QVBoxLayout,
    *,
    width: QWidget,
    height: QWidget,
    dimension_preset_source: Any | None = None,
) -> None:
    """Add a standard source dimension row to the test layout."""

    builder = FieldRowBuilder(
        panel=panel,
        icon_builder=lambda _icon: QWidget(panel),
        icon_resolver=lambda _node, _label, column_index=None: None,
        dimension_preset_source=dimension_preset_source,
    )
    builder.add_n_column_row(
        fields=[("source_width", width), ("source_height", height)],
        field_behaviors={
            "source_width": FieldBehavior(field_key="source_width"),
            "source_height": FieldBehavior(field_key="source_height"),
        },
        content_layout=content_layout,
        node_name="resize",
    )


def _binding(
    parent: QWidget,
    *,
    width: QWidget,
    height: QWidget,
) -> DimensionRowBinding:
    """Return a direct dimension binding for helper tests."""

    return DimensionRowBinding(
        pair=DimensionFieldPair(
            stem="source",
            width_key="source_width",
            height_key="source_height",
        ),
        width_widget=width,
        height_widget=height,
        width_column=QWidget(parent),
        height_column=QWidget(parent),
    )


def _first_row(layout: QVBoxLayout) -> QWidget:
    """Return the first row widget added to a layout."""

    item = layout.itemAt(0)
    assert item is not None
    widget = item.widget()
    assert widget is not None
    return widget


def _submenu(menu: _FakeRoundMenu, title: str) -> _FakeRoundMenu:
    """Return one recorded submenu by title."""

    for submenu in menu.submenus:
        if submenu.title == title:
            return submenu
    raise AssertionError(f"Missing submenu: {title}")


def _action(menu: _FakeRoundMenu, text: str) -> Any:
    """Return one recorded action by text."""

    for action in menu.actions:
        if action.text() == text:
            return action
    raise AssertionError(f"Missing action: {text}")


def _cleanup_widgets(app: QApplication, *widgets: QWidget) -> None:
    """Dispose test widgets before another Qt test runs in the same worker."""

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    app.processEvents()
