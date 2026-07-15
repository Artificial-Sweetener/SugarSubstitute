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

"""Tests for reusable folder route tree and route bar widgets."""

from __future__ import annotations

import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import BreadcrumbBar, SingleDirectionScrollArea  # type: ignore[import-untyped]
from qfluentwidgets.common.smooth_scroll import (  # type: ignore[import-untyped]
    SmoothMode,
)

from substitute.presentation.widgets.folder_route import (
    FolderRouteBar,
    FolderRouteEntry,
    FolderRouteTree,
    folder_route_from_item_path,
    normalize_folder_route,
)


def ensure_qapp() -> QApplication:
    """Return a running Qt application for folder-route widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_normalize_folder_route_handles_empty_and_separators() -> None:
    """Folder routes should normalize empty roots and path separators."""

    assert normalize_folder_route(None) == ()
    assert normalize_folder_route("") == ()
    assert normalize_folder_route(".") == ()
    assert normalize_folder_route(r"illustrious\characters") == (
        "illustrious",
        "characters",
    )
    assert normalize_folder_route("illustrious/characters") == (
        "illustrious",
        "characters",
    )


def test_folder_route_from_item_path_removes_filename() -> None:
    """Relative item paths should contribute folder segments only."""

    assert folder_route_from_item_path(r"illustrious\characters\Midna.safetensors") == (
        "illustrious",
        "characters",
    )
    assert folder_route_from_item_path("Pony.safetensors") == ()


def test_folder_route_tree_returns_immediate_children() -> None:
    """Child discovery should return only the next route level."""

    tree = FolderRouteTree(
        (
            FolderRouteEntry("one", ("illustrious", "characters")),
            FolderRouteEntry("two", ("illustrious", "style")),
            FolderRouteEntry("three", ("pony",)),
        )
    )

    assert [child.route for child in tree.children(())] == [
        ("illustrious",),
        ("pony",),
    ]
    assert [child.route for child in tree.children(("illustrious",))] == [
        ("illustrious", "characters"),
        ("illustrious", "style"),
    ]
    assert tree.children(("pony",)) == ()


def test_folder_route_tree_returns_descendant_item_ids() -> None:
    """Route item lookup should include direct and descendant items."""

    tree = FolderRouteTree(
        (
            FolderRouteEntry("root", ()),
            FolderRouteEntry("direct", ("illustrious",)),
            FolderRouteEntry("nested", ("illustrious", "characters")),
            FolderRouteEntry("other", ("pony",)),
        )
    )

    assert tree.item_ids_under(()) == ("root", "direct", "nested", "other")
    assert tree.item_ids_under(("illustrious",)) == ("direct", "nested")
    assert tree.item_ids_under(("missing",)) == ()


def test_folder_route_tree_sorts_children_and_counts_descendants() -> None:
    """Children should sort predictably and count descendant items."""

    tree = FolderRouteTree(
        (
            FolderRouteEntry("z", ("Zeta", "nested")),
            FolderRouteEntry("a1", ("alpha",)),
            FolderRouteEntry("a2", ("alpha", "nested")),
            FolderRouteEntry("b", ("Beta",)),
        )
    )

    children = tree.children(())

    assert [(child.label, child.item_count) for child in children] == [
        ("alpha", 2),
        ("Beta", 1),
        ("Zeta", 1),
    ]


def test_folder_route_bar_renders_breadcrumb_and_emits_ancestor_route() -> None:
    """Breadcrumb clicks should emit the selected ancestor route."""

    app = ensure_qapp()
    tree = FolderRouteTree(
        (
            FolderRouteEntry("midna", ("illustrious", "characters")),
            FolderRouteEntry("style", ("illustrious", "style")),
        )
    )
    host = QWidget()
    host.resize(360, 120)
    bar = FolderRouteBar(host)
    bar.set_route_tree(tree)
    bar.set_current_route(("illustrious", "characters"))
    host.show()
    app.processEvents()
    emitted: list[tuple[str, ...]] = []
    bar.routeChanged.connect(emitted.append)

    breadcrumb = bar.findChild(BreadcrumbBar)
    assert breadcrumb is not None
    assert breadcrumb.count() == 3
    assert breadcrumb.itemAt(0).text == "All"
    assert breadcrumb.itemAt(1).text == "illustrious"
    assert breadcrumb.itemAt(2).text == "characters"

    root_item = breadcrumb.itemAt(0)
    QTest.qWait(10)
    QTest.mouseClick(
        root_item,
        Qt.MouseButton.LeftButton,
        pos=root_item.rect().center(),
    )
    app.processEvents()

    assert emitted == [()]


def test_folder_route_bar_renders_child_route_buttons() -> None:
    """Child route buttons should represent immediate descendants only."""

    app = ensure_qapp()
    tree = FolderRouteTree(
        (
            FolderRouteEntry("midna", ("illustrious", "characters")),
            FolderRouteEntry("zelda", ("illustrious", "characters")),
            FolderRouteEntry("style", ("illustrious", "style")),
        )
    )
    bar = FolderRouteBar()
    bar.set_route_tree(tree)
    emitted: list[tuple[str, ...]] = []
    bar.routeChanged.connect(emitted.append)
    bar.show()
    app.processEvents()

    buttons = bar.child_route_buttons()

    assert [button.text() for button in buttons] == ["illustrious (3)"]
    assert all(not button.isCheckable() for button in buttons)

    buttons[0].click()
    app.processEvents()

    assert emitted == [("illustrious",)]


def test_folder_route_bar_hides_root_breadcrumb_when_children_exist() -> None:
    """Root should use one row by hiding the redundant All breadcrumb."""

    app = ensure_qapp()
    tree = FolderRouteTree((FolderRouteEntry("midna", ("illustrious",)),))
    bar = FolderRouteBar()
    bar.set_route_tree(tree)
    bar.show()
    app.processEvents()

    breadcrumb = bar.findChild(BreadcrumbBar)
    scroll_area = bar.findChild(SingleDirectionScrollArea)
    assert breadcrumb is not None
    assert scroll_area is not None
    assert breadcrumb.isVisible() is False
    assert scroll_area.isVisible() is True


def test_folder_route_bar_leaf_route_uses_one_breadcrumb_row() -> None:
    """Leaf routes should not reserve a hidden second-row affordance."""

    app = ensure_qapp()
    tree = FolderRouteTree((FolderRouteEntry("midna", ("illustrious", "characters")),))
    bar = FolderRouteBar()
    bar.set_route_tree(tree)
    bar.set_current_route(("illustrious", "characters"))
    bar.show()
    app.processEvents()

    breadcrumb = bar.findChild(BreadcrumbBar)
    scroll_area = bar.findChild(SingleDirectionScrollArea)
    assert breadcrumb is not None
    assert scroll_area is not None
    assert breadcrumb.isVisible() is True
    assert scroll_area.isVisible() is False
    assert bar.sizeHint().height() < 30


def test_folder_route_bar_child_routes_scroll_horizontally_without_wrapping() -> None:
    """The child route row should stay single-line and scroll when overfull."""

    app = ensure_qapp()
    tree = FolderRouteTree(
        tuple(
            FolderRouteEntry(str(index), (f"folder_{index:02d}",))
            for index in range(18)
        )
    )
    host = QWidget()
    host.resize(260, 120)
    bar = FolderRouteBar(host)
    bar.set_route_tree(tree)
    bar.resize(260, bar.sizeHint().height())
    host.show()
    app.processEvents()

    scroll_area = bar.findChild(SingleDirectionScrollArea)
    assert scroll_area is not None
    child_row_height = scroll_area.height()
    content = scroll_area.widget()
    assert content is not None

    assert child_row_height == scroll_area.height()
    assert content.sizeHint().width() > scroll_area.viewport().width()
    assert scroll_area.hScrollBar.maximum() > 0
    assert scroll_area.smoothScroll.smoothMode is SmoothMode.NO_SMOOTH
    assert scroll_area.vScrollBar.duration == 0
    assert scroll_area.hScrollBar.duration == 0
    assert (
        scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert (
        scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert scroll_area.hScrollBar.isVisible() is True
    assert scroll_area.hScrollBar.height() == 6
    host.close()
    bar.deleteLater()
    host.deleteLater()
    app.processEvents()
