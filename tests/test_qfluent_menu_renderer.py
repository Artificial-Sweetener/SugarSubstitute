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

from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget
import pytest
from qfluentwidgets.components.widgets.menu import RoundMenu  # type: ignore[import-untyped]

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
from tests.prompt_projection_test_helpers import ensure_qapp


@pytest.fixture
def parent_widget() -> Iterator[QWidget]:
    """Create a Qt parent for rendered menus."""

    ensure_qapp()
    parent = QWidget()
    try:
        yield parent
    finally:
        parent.deleteLater()


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
