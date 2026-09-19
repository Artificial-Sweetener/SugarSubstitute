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

"""Tests for shared QFluent menu rendering."""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QAction, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem, QWidget
import pytest
from qfluentwidgets.components.widgets.menu import RoundMenu  # type: ignore[import-untyped]
from qfluentwidgets import FluentIcon  # type: ignore[import-untyped]

from substitute.presentation.widgets.menu_model import (
    LazyMenuSubmenu,
    MenuItem,
    MenuModel,
    MenuSection,
    MenuSeparator,
    MenuSubmenu,
)
from substitute.presentation.widgets.qfluent_menu_renderer import (
    QFluentMenuRenderer,
)
from tests.support.qt.lifecycle import destroy_qt_object
from sugarsubstitute_shared.presentation.localization import QFluentFontFamilyAdapter


@pytest.fixture
def parent_widget(qt_application_owner: QApplication) -> Iterator[QWidget]:
    """Yield a menu parent with a fixture-managed Qt lifetime."""

    fonts = QFluentFontFamilyAdapter(qt_application_owner)
    original_fonts = fonts.snapshot()
    fonts.apply_application_font(
        QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    )
    parent = QWidget()
    try:
        yield parent
    finally:
        destroy_qt_object(parent)
        fonts.restore(original_fonts)


def test_qfluent_menu_renderer_preserves_items_and_callbacks(
    parent_widget: QWidget,
) -> None:
    """Rendered menu rows should preserve order, state, and callbacks."""

    callbacks: list[str] = []
    menu = QFluentMenuRenderer(parent=parent_widget).render(
        MenuModel(
            entries=(
                MenuItem(
                    "first",
                    "First",
                    callback=lambda: callbacks.append("first"),
                    tooltip="First tooltip",
                    properties={"promptFullTriggerWordsLabel": "Trigger words: First"},
                ),
                MenuSeparator(),
                MenuItem("disabled", "Disabled", enabled=False),
            )
        )
    )

    actions = _menu_actions(menu)

    assert [action.text() for action in actions] == ["First", "Disabled"]
    assert actions[0].toolTip() == "First tooltip"
    assert actions[0].property("promptFullTriggerWordsLabel") == (
        "Trigger words: First"
    )
    assert actions[1].isEnabled() is False
    actions[0].trigger()
    assert callbacks == ["first"]


@pytest.mark.parametrize("with_icon", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
def test_qfluent_menu_renderer_paints_checkable_action_state(
    parent_widget: QWidget,
    with_icon: bool,
    enabled: bool,
) -> None:
    """Only a checkable row should reserve and paint a Fluent check indicator."""

    menu = QFluentMenuRenderer(parent=parent_widget).render(
        MenuModel(
            entries=(
                MenuItem("ordinary", "Ordinary"),
                MenuItem(
                    "advanced",
                    "Show advanced inputs",
                    checkable=True,
                    checked=True,
                    enabled=enabled,
                    icon=FluentIcon.EDIT.icon() if with_icon else None,
                ),
            )
        )
    )

    actions = _menu_actions(menu)
    assert actions[-1].isCheckable() is True
    assert actions[-1].isChecked() is True
    ordinary = _row_option(menu, 0)
    checked = _row_option(menu, 1)
    check_feature = QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
    assert not ordinary.features & check_feature
    assert checked.features & check_feature
    indicator = menu.view.style().subElementRect(
        QStyle.SubElement.SE_ItemViewItemCheckIndicator, checked, menu.view
    )
    assert not indicator.isEmpty()
    checked_image = _paint_row(menu, 1)
    width = menu.width()
    actions[-1].setChecked(False)
    unchecked_image = _paint_row(menu, 1)
    assert menu.width() == width
    assert checked_image.copy(indicator) != unchecked_image.copy(indicator)
    after_indicator = QRect(indicator.right() + 1, 0, 420, 28)
    assert checked_image.copy(after_indicator) == unchecked_image.copy(after_indicator)
    before_indicator = QRect(0, 0, indicator.left(), 28)
    assert checked_image.copy(before_indicator) == unchecked_image.copy(
        before_indicator
    )


@pytest.mark.parametrize("surface", ["section", "submenu", "lazy_submenu"])
def test_nested_actions_keep_row_local_check_presentation(
    parent_widget: QWidget, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    """Sections and eager or lazy submenus must honor the same row contract."""

    entries = (MenuItem("toggle", "Toggle", checkable=True, checked=True),)
    if surface == "section":
        model = MenuModel(entries=(MenuSection(entries=entries),))
    elif surface == "submenu":
        model = MenuModel(entries=(MenuSubmenu("Nested", entries=entries),))
    else:
        model = MenuModel(
            entries=(LazyMenuSubmenu("Nested", entries_factory=lambda: entries),)
        )
    menu = QFluentMenuRenderer(parent=parent_widget).render(model)
    if surface != "section":
        parent_option = _row_option(menu, 0)
        assert (
            not parent_option.features
            & QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
        )
        menu = _submenus(menu)[0]
        monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)
        menu.exec(QPoint())
    option = _row_option(menu, 0)
    assert option.features & QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
    assert not option.features & QStyleOptionViewItem.ViewItemFeature.HasDecoration
    checked_image = _paint_row(menu, 0)
    _menu_actions(menu)[0].setChecked(False)
    assert _paint_row(menu, 0) != checked_image


def test_checkable_peers_do_not_indent_ordinary_or_submenu_rows(
    parent_widget: QWidget,
) -> None:
    """Adding checks must preserve ordinary text, icons, shortcuts and submenus."""

    entries = (
        MenuItem("plain", "Plain", shortcut="Ctrl+P"),
        MenuItem("icon", "Schedule LoRA", icon=FluentIcon.EDIT.icon()),
        MenuSubmenu("Saved segments", entries=(MenuItem("child", "Child"),)),
    )
    renderer = QFluentMenuRenderer(parent=parent_widget)
    baseline = renderer.render(MenuModel(entries=entries))
    mixed = renderer.render(
        MenuModel(entries=(*entries, MenuItem("check", "Check", checkable=True)))
    )
    for row in range(len(entries)):
        assert _paint_row(baseline, row) == _paint_row(mixed, row)


def _row_option(menu: RoundMenu, row: int) -> QStyleOptionViewItem:
    """Prepare a fixed-size row using the production delegate and Fluent style."""

    menu.ensurePolished()
    menu.view.ensurePolished()
    option = QStyleOptionViewItem()
    option.initFrom(menu.view)
    option.widget = menu.view
    option.rect = QRect(0, 0, 420, 28)
    option.decorationSize = QSize(14, 14)
    index = menu.view.model().index(row, 0)
    if not index.flags() & Qt.ItemFlag.ItemIsEnabled:
        option.state &= ~QStyle.StateFlag.State_Enabled
    menu.view.itemDelegate().initStyleOption(option, index)
    return option


def _paint_row(menu: RoundMenu, row: int) -> QImage:
    """Render one real menu row without opening a native popup or running time."""

    option = _row_option(menu, row)
    image = QImage(option.rect.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        menu.view.itemDelegate().paint(painter, option, menu.view.model().index(row, 0))
    finally:
        painter.end()
    return image


def test_qfluent_menu_renderer_renders_sections_and_submenus(
    parent_widget: QWidget,
) -> None:
    """Sections and eager submenus should render into the QFluent menu tree."""

    menu = QFluentMenuRenderer(parent=parent_widget).render(
        MenuModel(
            entries=(
                MenuSection(
                    title="Group",
                    entries=(MenuItem("child", "Child"),),
                ),
                MenuSubmenu(
                    "Submenu",
                    entries=(MenuItem("nested", "Nested"),),
                ),
            )
        )
    )

    assert _menu_row_texts(menu) == ("Group", "Child")
    assert _submenu_row_texts(menu) == (("Submenu", ("Nested",)),)


def test_qfluent_menu_renderer_defers_lazy_submenu_population(
    monkeypatch: pytest.MonkeyPatch,
    parent_widget: QWidget,
) -> None:
    """Lazy submenu factories should not run while the parent menu renders."""

    factory_calls = 0

    def entries_factory() -> tuple[MenuItem, ...]:
        """Return submenu entries and record lazy execution."""

        nonlocal factory_calls
        factory_calls += 1
        return (MenuItem("lazy", "Lazy row"),)

    menu = QFluentMenuRenderer(parent=parent_widget).render(
        MenuModel(
            entries=(
                LazyMenuSubmenu(
                    "Lazy submenu",
                    entries_factory=entries_factory,
                ),
            )
        )
    )

    assert factory_calls == 0
    assert _submenu_row_texts(menu) == (("Lazy submenu", ()),)

    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)
    submenu = _submenus(menu)[0]
    submenu.exec(QPoint(1, 2))

    assert factory_calls == 1
    assert _menu_row_texts(submenu) == ("Lazy row",)


def test_qfluent_menu_renderer_batches_round_menu_size_adjustment(
    monkeypatch: pytest.MonkeyPatch,
    parent_widget: QWidget,
) -> None:
    """Rendering many rows should not call RoundMenu.adjustSize for every row."""

    adjust_calls = 0
    original_adjust_size = RoundMenu.adjustSize

    def count_adjust_size(self: RoundMenu) -> None:
        """Record renderer-triggered QFluent size adjustments."""

        nonlocal adjust_calls
        adjust_calls += 1
        original_adjust_size(self)

    monkeypatch.setattr(RoundMenu, "adjustSize", count_adjust_size)

    QFluentMenuRenderer(parent=parent_widget).render(
        MenuModel(
            entries=tuple(
                MenuItem(f"item-{index}", f"Item {index}") for index in range(20)
            )
        )
    )

    assert adjust_calls <= 2


def _menu_actions(menu: RoundMenu) -> tuple[QAction, ...]:
    """Return executable actions directly held by one QFluent menu."""

    return tuple(action for action in menu.menuActions() if isinstance(action, QAction))


def _menu_row_texts(menu: RoundMenu) -> tuple[str, ...]:
    """Return text for directly executable QFluent menu rows."""

    return tuple(action.text() for action in _menu_actions(menu))


def _submenu_row_texts(menu: RoundMenu) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return submenu titles and directly executable child row text."""

    return tuple(
        (str(submenu.title()), _menu_row_texts(submenu)) for submenu in _submenus(menu)
    )


def _submenus(menu: RoundMenu) -> tuple[RoundMenu, ...]:
    """Return QFluent submenus from one menu."""

    return tuple(getattr(menu, "_subMenus", ()))
