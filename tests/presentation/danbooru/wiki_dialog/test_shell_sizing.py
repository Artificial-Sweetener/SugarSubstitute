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

"""Test responsive Danbooru wiki modal sizing and centering."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from substitute.presentation.dialogs.danbooru_wiki_dialog import DanbooruWikiDialog
from tests.presentation.danbooru.wiki_dialog.collaborators import (
    DanbooruWikiDialogOwner,
    ImmediateDispatcher,
    StubDanbooruWikiService,
)
from tests.presentation.danbooru.wiki_dialog.content_support import (
    page_view,
    success_result,
    widget_global_center,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_sizes_from_top_level_parent_window(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Size and center from the top-level owner rather than a child widget."""

    parent_window = danbooru_dialog_owner.own_widget(QWidget())
    parent_window.resize(1000, 800)
    parent_window.move(120, 80)
    parent_child = QWidget(parent_window)
    parent_window.show()
    dialog = _build_dialog(danbooru_dialog_owner, parent=parent_child)
    dialog.show()

    wait_for_qt_condition(
        lambda: _matches_geometry(dialog, parent_window, width=850, height=680)
    )


def test_clamps_responsive_size_to_minimums(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Keep the modal usable when its parent is smaller than its minimum."""

    parent_window = danbooru_dialog_owner.own_widget(QWidget())
    parent_window.resize(600, 400)
    parent_window.show()
    dialog = _build_dialog(danbooru_dialog_owner, parent=parent_window)
    dialog.show()

    wait_for_qt_condition(
        lambda: dialog.widget.width() == 840 and dialog.widget.height() == 560
    )


def test_resizes_and_recenters_with_parent_while_open(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Stay proportional and centered when the parent window resizes."""

    parent_window = danbooru_dialog_owner.own_widget(QWidget())
    parent_window.resize(1000, 800)
    parent_window.move(220, 140)
    parent_window.show()
    dialog = _build_dialog(danbooru_dialog_owner, parent=parent_window)
    dialog.show()
    wait_for_qt_condition(
        lambda: _matches_geometry(dialog, parent_window, width=850, height=680)
    )

    parent_window.resize(1400, 1000)

    wait_for_qt_condition(
        lambda: _matches_geometry(dialog, parent_window, width=1190, height=850)
    )


def _build_dialog(
    owner: DanbooruWikiDialogOwner,
    *,
    parent: QWidget,
) -> DanbooruWikiDialog:
    """Build one loaded dialog under a supplied sizing parent."""

    return owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={"long hair": success_result(page_view())}
        ),
        selection_text="long hair",
        lookup_dispatcher=ImmediateDispatcher(),
        parent=parent,
    )


def _matches_geometry(
    dialog: DanbooruWikiDialog,
    parent_window: QWidget,
    *,
    width: int,
    height: int,
) -> bool:
    """Return whether the modal has the expected size and centered position."""

    dialog_center = widget_global_center(dialog.widget)
    parent_center = parent_window.frameGeometry().center()
    return (
        dialog.widget.width() == width
        and dialog.widget.height() == height
        and abs(dialog_center.x() - parent_center.x()) <= 1
        and abs(dialog_center.y() - parent_center.y()) <= 1
    )
