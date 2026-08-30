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

"""Own inline-flow widgets and record their rendered context menus."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QApplication, QWidget

import substitute.presentation.danbooru.wiki_inline_flow as wiki_inline_flow_module
from substitute.application.danbooru import DanbooruWikiInlineNode
from substitute.presentation.danbooru import DanbooruWikiInlineFlow
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
from tests.support.qt.lifecycle import destroy_qt_object


class InlineFlowOwner:
    """Own every independent inline-flow widget constructed by one test."""

    def __init__(self) -> None:
        """Initialize empty widget ownership."""

        self._widgets: list[DanbooruWikiInlineFlow] = []

    def build(
        self,
        *,
        inline_nodes: tuple[DanbooruWikiInlineNode, ...],
        width: int = 320,
        height: int = 80,
        compact: bool = False,
        open_url: Callable[[str], bool] | None = None,
    ) -> DanbooruWikiInlineFlow:
        """Build, polish, size, and retain one inline-flow widget."""

        widget = DanbooruWikiInlineFlow(
            inline_nodes=inline_nodes,
            compact=compact,
            open_url=open_url,
        )
        widget.ensurePolished()
        widget.resize(width, height)
        self._widgets.append(widget)
        return widget

    def destroy_all(self) -> None:
        """Synchronously destroy every owned inline-flow widget."""

        for widget in reversed(self._widgets):
            destroy_qt_object(widget)
        self._widgets.clear()


class RecordingRoundMenu:
    """Record menu actions and popup positions without opening a native menu."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Store the parent widget for one recorded popup menu."""

        self.parent = parent
        self.actions: list[RecordingMenuAction] = []
        self.exec_positions: list[QPoint] = []

    def addAction(self, action: RecordingMenuAction) -> None:  # noqa: N802
        """Record one action added to the menu."""

        self.actions.append(action)

    def exec(self, pos: QPoint) -> None:
        """Record one requested popup position."""

        self.exec_positions.append(pos)


class RecordingMenuAction:
    """Retain one rendered menu item and dispatch its callback."""

    def __init__(self, item: MenuItem) -> None:
        """Store the rendered item for inspection and triggering."""

        self._item = item

    def text(self) -> str:
        """Return the rendered action label."""

        return self._item.label

    def trigger(self) -> None:
        """Invoke the rendered menu callback when one is present."""

        if self._item.callback is not None:
            self._item.callback()


class RecordingClipboard:
    """Retain copied tag text without touching the process clipboard."""

    def __init__(self) -> None:
        """Initialize empty clipboard text."""

        self.text = ""

    def setText(self, text: str) -> None:  # noqa: N802
        """Record the copied text."""

        self.text = text


class _ClipboardApplicationBoundary:
    """Expose one test-local clipboard through the QGuiApplication surface."""

    def __init__(self, clipboard: RecordingClipboard) -> None:
        """Store the clipboard returned to production code."""

        self._clipboard = clipboard

    def clipboard(self) -> RecordingClipboard:
        """Return the test-local clipboard."""

        return self._clipboard


class _RecordingMenuRenderer:
    """Render menu models into one test's recorded menu collection."""

    def __init__(
        self,
        *,
        parent: QWidget,
        menus: list[RecordingRoundMenu],
    ) -> None:
        """Store the parent and per-test menu sink."""

        self._parent = parent
        self._menus = menus

    def render(self, model: MenuModel) -> RecordingRoundMenu:
        """Render menu items into a recorded menu surface."""

        menu = RecordingRoundMenu(parent=self._parent)
        for entry in model.entries:
            if isinstance(entry, MenuItem):
                menu.addAction(RecordingMenuAction(entry))
        self._menus.append(menu)
        return menu


def install_recording_menu_renderer(
    monkeypatch: pytest.MonkeyPatch,
) -> list[RecordingRoundMenu]:
    """Install a menu-renderer factory with one test-local recording sink."""

    menus: list[RecordingRoundMenu] = []

    def build_renderer(*, parent: QWidget) -> _RecordingMenuRenderer:
        """Build a renderer bound to this test's menu collection."""

        return _RecordingMenuRenderer(parent=parent, menus=menus)

    monkeypatch.setattr(
        wiki_inline_flow_module,
        "QFluentMenuRenderer",
        build_renderer,
    )
    return menus


def install_recording_clipboard(
    monkeypatch: pytest.MonkeyPatch,
) -> RecordingClipboard:
    """Replace only the inline-flow clipboard output with a test-local sink."""

    clipboard = RecordingClipboard()
    monkeypatch.setattr(
        wiki_inline_flow_module,
        "QGuiApplication",
        _ClipboardApplicationBoundary(clipboard),
    )
    return clipboard


def send_context_menu_event(
    *,
    widget: DanbooruWikiInlineFlow,
    token_text: str,
) -> None:
    """Send one context-menu event centered on a painted token."""

    layout, _ = widget._layout_for_width(widget.width())
    token = next(
        paint_token
        for paint_token in layout
        if paint_token.token.kind != "space" and paint_token.token.text == token_text
    )
    local_pos = token.rect.center().toPoint()
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        local_pos,
        widget.mapToGlobal(local_pos),
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, event)


__all__ = [
    "InlineFlowOwner",
    "RecordingClipboard",
    "RecordingRoundMenu",
    "install_recording_clipboard",
    "install_recording_menu_renderer",
    "send_context_menu_event",
]
