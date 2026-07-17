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

"""Widget tests for the native Danbooru inline-flow renderer."""

from __future__ import annotations

import os
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QContextMenuEvent, QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget

import substitute.presentation.danbooru.wiki_inline_flow as wiki_inline_flow_module
from substitute.application.danbooru import (
    DanbooruWikiTagChipNode,
    DanbooruWikiTextNode,
    DanbooruWikiWikiLinkNode,
)
from substitute.presentation.danbooru import DanbooruWikiInlineFlow
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "Danbooru inline-flow QWidget rendering tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_inline_flow_exposes_plain_text_and_chip_targets() -> None:
    """Inline-flow widgets should expose semantic text and chip targets for routing."""

    app = _app()
    view = DanbooruWikiInlineFlow(
        inline_nodes=(
            DanbooruWikiTextNode(text="See "),
            DanbooruWikiTagChipNode(
                tag_name="short_hair",
                display_label="short hair",
                category_name="general",
            ),
            DanbooruWikiTextNode(text="."),
        )
    )
    view.resize(320, 200)
    view.show()
    app.processEvents()

    assert view.plain_text() == "See short hair."
    assert view.link_targets() == ("danbooru-wiki:short_hair",)


def test_inline_flow_height_grows_when_width_shrinks() -> None:
    """Wrapped inline content should request more height at narrower widths."""

    _app()
    view = DanbooruWikiInlineFlow(
        inline_nodes=(
            DanbooruWikiTextNode(
                text="This sentence is long enough to wrap in a narrow inline flow."
            ),
        )
    )

    assert view.heightForWidth(120) > view.heightForWidth(480)


def test_inline_flow_keeps_mixed_prose_in_natural_order() -> None:
    """Mixed prose plus chips should preserve normal word spacing and order."""

    app = _app()
    view = DanbooruWikiInlineFlow(
        inline_nodes=(
            DanbooruWikiTextNode(
                text="A character with a serious or solemn demeanor or "
            ),
            DanbooruWikiTagChipNode(
                tag_name="expressionless",
                display_label="expressionless",
                category_name="general",
            ),
            DanbooruWikiTextNode(
                text=", or provided with context such as an impending battle."
            ),
        )
    )
    view.resize(760, 120)
    view.show()
    app.processEvents()

    layout, _ = view._layout_for_width(760)
    painted_words = [
        token.token.text for token in layout if token.token.kind != "space"
    ]

    assert painted_words == [
        "A",
        "character",
        "with",
        "a",
        "serious",
        "or",
        "solemn",
        "demeanor",
        "or",
        "expressionless",
        ",",
        "or",
        "provided",
        "with",
        "context",
        "such",
        "as",
        "an",
        "impending",
        "battle.",
    ]


def test_inline_flow_aligns_chip_text_to_neighboring_prose_baseline() -> None:
    """Chip text should share the same vertical text anchor as adjacent prose."""

    app = _app()
    view = DanbooruWikiInlineFlow(
        inline_nodes=(
            DanbooruWikiTextNode(text="The term for the mechanical "),
            DanbooruWikiTagChipNode(
                tag_name="prosthetic_limbs",
                display_label="prosthetic limbs",
                category_name="general",
            ),
            DanbooruWikiTextNode(text=" used in "),
        )
    )
    view.resize(900, 80)
    view.show()
    app.processEvents()

    layout, _ = view._layout_for_width(900)
    prose_token = next(token for token in layout if token.token.text == "mechanical")
    chip_token = next(
        token for token in layout if token.token.text == "prosthetic limbs"
    )
    following_token = next(token for token in layout if token.token.text == "used")

    assert prose_token.rect.y() == chip_token.rect.y()
    assert chip_token.text_rect.y() == prose_token.text_rect.y()
    assert chip_token.text_rect.y() == following_token.text_rect.y()


def test_inline_flow_keeps_consistent_wrapped_line_spacing_with_chip_prose() -> None:
    """Wrapped prose should keep the same line spacing whether a line has a chip."""

    app = _app()
    view = DanbooruWikiInlineFlow(
        inline_nodes=(
            DanbooruWikiTextNode(text="Alpha beta gamma "),
            DanbooruWikiTagChipNode(
                tag_name="delta",
                display_label="delta",
                category_name="general",
            ),
            DanbooruWikiTextNode(text=" epsilon zeta eta theta iota kappa lambda."),
        )
    )
    layout_width = 160
    view.resize(layout_width, 160)
    view.show()
    app.processEvents()

    layout, _ = view._layout_for_width(layout_width)
    line_tops = sorted(
        {round(token.rect.y(), 2) for token in layout if token.token.kind != "space"}
    )

    assert len(line_tops) >= 3
    deltas = [
        round(line_tops[index + 1] - line_tops[index], 2)
        for index in range(len(line_tops) - 1)
    ]
    assert max(deltas) - min(deltas) <= 0.02


def test_inline_flow_right_click_chip_menu_offers_copy_and_browser_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Right-clicking a chip should show the expected QFluent menu actions."""

    app = _app()
    created_menus: list[_FakeRoundMenu] = []

    _install_fake_inline_flow_menu(monkeypatch, created_menus)
    view = DanbooruWikiInlineFlow(
        inline_nodes=(
            DanbooruWikiTagChipNode(
                tag_name="short_hair",
                display_label="short hair",
                category_name="general",
            ),
        ),
        open_url=lambda _url: True,
    )
    view.resize(320, 80)
    view.show()
    app.processEvents()

    _send_context_menu_event(
        widget=view,
        token_text="short hair",
    )

    assert len(created_menus) == 1
    assert [action.text() for action in created_menus[0].actions] == [
        "Copy tag",
        "Open in browser",
    ]
    assert created_menus[0].exec_positions


def test_inline_flow_copy_tag_uses_target_not_visible_chip_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Copying a chip should use the semantic target plus display normalization."""

    app = _app()
    created_menus: list[_FakeRoundMenu] = []

    _install_fake_inline_flow_menu(monkeypatch, created_menus)
    clipboard = QGuiApplication.clipboard()
    clipboard.clear()
    view = DanbooruWikiInlineFlow(
        inline_nodes=(
            DanbooruWikiTagChipNode(
                tag_name="short_hair",
                display_label="Short Hair",
                category_name="general",
            ),
        ),
        open_url=lambda _url: True,
    )
    view.resize(320, 80)
    view.show()
    app.processEvents()

    _send_context_menu_event(widget=view, token_text="Short Hair")
    cast(Any, created_menus[0].actions[0]).trigger()

    assert clipboard.text() == "short hair"


def test_inline_flow_open_in_browser_uses_tag_wiki_page_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Open-in-browser should route to the external Danbooru wiki page."""

    app = _app()
    created_menus: list[_FakeRoundMenu] = []
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record external browser opens without launching anything."""

        opened_urls.append(url)
        return True

    _install_fake_inline_flow_menu(monkeypatch, created_menus)
    view = DanbooruWikiInlineFlow(
        inline_nodes=(
            DanbooruWikiTagChipNode(
                tag_name="short_hair",
                display_label="short hair",
                category_name="general",
            ),
        ),
        open_url=open_url,
    )
    view.resize(320, 80)
    view.show()
    app.processEvents()

    _send_context_menu_event(widget=view, token_text="short hair")
    cast(Any, created_menus[0].actions[1]).trigger()

    assert opened_urls == ["https://danbooru.donmai.us/wiki_pages/short_hair"]


def test_inline_flow_right_click_plain_text_shows_no_chip_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plain prose should not show the chip-specific context menu."""

    app = _app()
    created_menus: list[_FakeRoundMenu] = []

    _install_fake_inline_flow_menu(monkeypatch, created_menus)
    view = DanbooruWikiInlineFlow(
        inline_nodes=(DanbooruWikiTextNode(text="Just plain text"),),
        open_url=lambda _url: True,
    )
    view.resize(320, 80)
    view.show()
    app.processEvents()

    _send_context_menu_event(widget=view, token_text="Just")

    assert created_menus == []


def test_inline_flow_right_click_non_chip_wiki_link_shows_no_chip_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normal wiki links should not reuse the chip context menu path."""

    app = _app()
    created_menus: list[_FakeRoundMenu] = []

    _install_fake_inline_flow_menu(monkeypatch, created_menus)
    view = DanbooruWikiInlineFlow(
        inline_nodes=(
            DanbooruWikiWikiLinkNode(
                target_title="help:users",
                display_label="help:users",
            ),
        ),
        open_url=lambda _url: True,
    )
    view.resize(320, 80)
    view.show()
    app.processEvents()

    _send_context_menu_event(widget=view, token_text="help:users")

    assert created_menus == []


def test_inline_flow_right_click_caption_chip_matches_body_chip_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compact caption chips should expose the same chip menu actions."""

    app = _app()
    created_menus: list[_FakeRoundMenu] = []

    _install_fake_inline_flow_menu(monkeypatch, created_menus)
    view = DanbooruWikiInlineFlow(
        inline_nodes=(
            DanbooruWikiTagChipNode(
                tag_name="short_hair",
                display_label="short hair",
                category_name="general",
            ),
        ),
        compact=True,
        open_url=lambda _url: True,
    )
    view.resize(320, 80)
    view.show()
    app.processEvents()

    _send_context_menu_event(widget=view, token_text="short hair")

    assert len(created_menus) == 1
    assert [action.text() for action in created_menus[0].actions] == [
        "Copy tag",
        "Open in browser",
    ]


def _app() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


class _FakeRoundMenu:
    """Record menu actions and popup positions without opening a real menu."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Store the parent widget for one fake popup menu."""

        self.parent = parent
        self.actions: list[Any] = []
        self.exec_positions: list[QPoint] = []

    def addAction(self, action: object) -> None:
        """Record one action added to the menu."""

        self.actions.append(action)

    def exec(self, pos: QPoint) -> None:
        """Record one requested popup position."""

        self.exec_positions.append(pos)


class _FakeMenuAction:
    """Record rendered menu item state and dispatch callbacks."""

    def __init__(self, item: MenuItem) -> None:
        """Store the rendered item for later assertions and triggering."""

        self._item = item

    def text(self) -> str:
        """Return the rendered action label."""

        return self._item.label

    def trigger(self) -> None:
        """Invoke the rendered menu callback."""

        if self._item.callback is not None:
            self._item.callback()


class _FakeQFluentMenuRenderer:
    """Render menu models into fake menus for inline-flow tests."""

    def __init__(self, *, parent: QWidget) -> None:
        """Store the parent used for fake menu creation."""

        self._parent = parent

    def render(self, model: MenuModel) -> _FakeRoundMenu:
        """Return a fake menu populated from the shared menu model."""

        menu = _FakeRoundMenu(parent=self._parent)
        for entry in model.entries:
            if isinstance(entry, MenuItem):
                menu.addAction(_FakeMenuAction(entry))
        _created_inline_flow_menus.append(menu)
        return menu


_created_inline_flow_menus: list[_FakeRoundMenu] = []


def _install_fake_inline_flow_menu(
    monkeypatch: pytest.MonkeyPatch,
    created_menus: list[_FakeRoundMenu],
) -> None:
    """Patch the inline flow to record rendered shared menu models."""

    global _created_inline_flow_menus
    _created_inline_flow_menus = created_menus
    _created_inline_flow_menus.clear()
    monkeypatch.setattr(
        wiki_inline_flow_module,
        "QFluentMenuRenderer",
        _FakeQFluentMenuRenderer,
    )


def _send_context_menu_event(
    *,
    widget: DanbooruWikiInlineFlow,
    token_text: str,
) -> None:
    """Send one context-menu event centered on the painted token text."""

    layout, _ = widget._layout_for_width(widget.width())
    token = next(
        paint_token
        for paint_token in layout
        if paint_token.token.kind != "space" and paint_token.token.text == token_text
    )
    local_pos = token.rect.center().toPoint()
    global_pos = widget.mapToGlobal(local_pos)
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        local_pos,
        global_pos,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, event)
