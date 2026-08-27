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

"""Test Danbooru wiki modal header and surface structure."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QFrame
from qfluentwidgets import TitleLabel, ToolButton  # type: ignore[import-untyped]
from qfluentwidgets.components.widgets.tool_tip import (  # type: ignore[import-untyped]
    ToolTipFilter,
)

import substitute.presentation.dialogs.danbooru_wiki_dialog as dialog_module
from substitute.presentation.dialogs.danbooru_wiki_dialog import DanbooruWikiDialog
from tests.presentation.danbooru.wiki_dialog.collaborators import (
    DanbooruWikiDialogOwner,
    ImmediateDispatcher,
    StubDanbooruWikiService,
    install_recording_clipboard,
)
from tests.presentation.danbooru.wiki_dialog.content_support import (
    page_view,
    success_result,
)


def test_header_uses_icon_only_house_actions(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Use house modal action widgets, title class, and accessible tooltips."""

    dialog = _build_default_dialog(danbooru_dialog_owner)

    assert dialog._back_button.text() == ""
    assert dialog._forward_button.text() == ""
    assert dialog._copy_button.text() == ""
    assert dialog._open_button.text() == ""
    assert dialog._close_button.text() == ""
    assert type(dialog._back_button) is ToolButton
    assert type(dialog._forward_button) is ToolButton
    assert type(dialog._copy_button) is ToolButton
    assert type(dialog._open_button) is ToolButton
    assert type(dialog._close_button) is ToolButton
    assert isinstance(dialog._title_label, TitleLabel)
    assert dialog._title_label.text() == '"long hair"'
    assert dialog._back_button.toolTip() == "Back"
    assert dialog._forward_button.toolTip() == "Forward"
    assert dialog._copy_button.toolTip() == "Copy tag title"
    assert dialog._open_button.toolTip() == "Open tag wiki article in browser"
    assert dialog._close_button.toolTip() == "Close"
    assert dialog._back_button.findChildren(ToolTipFilter)
    assert dialog._forward_button.findChildren(ToolTipFilter)
    assert dialog._copy_button.findChildren(ToolTipFilter)
    assert dialog._open_button.findChildren(ToolTipFilter)
    assert dialog._close_button.findChildren(ToolTipFilter)


def test_header_has_no_divider_frame(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Avoid a separator line beneath the title rows."""

    dialog = _build_default_dialog(danbooru_dialog_owner)

    assert not any(
        frame.frameShape() == QFrame.Shape.HLine
        for frame in dialog._header.findChildren(QFrame)
    )


def test_footer_button_group_is_collapsed(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Hide the obsolete footer without reserving vertical space."""

    dialog = _build_default_dialog(danbooru_dialog_owner)

    assert dialog.buttonGroup.isHidden() is True
    assert dialog.buttonGroup.height() == 0


def test_surface_styling_separates_header_and_body(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep dark header and body surface ownership explicit in the stylesheet."""

    monkeypatch.setattr(dialog_module, "_is_dark_theme", lambda: True)
    dialog = _build_default_dialog(danbooru_dialog_owner)

    stylesheet = dialog.widget.styleSheet()
    assert "QWidget#DanbooruWikiDialogHeader {" in stylesheet
    assert "background: #2b2b2b;" in stylesheet
    assert "QWidget#DanbooruWikiDialogSurface {" in stylesheet
    assert "QWidget#DanbooruWikiDialogBody {" in stylesheet
    assert "background: #202020;" in stylesheet
    assert "rgba(32, 32, 32, 0.94)" not in stylesheet
    assert "rgba(251, 251, 251, 0.97)" not in stylesheet
    assert "rgba(244, 244, 244, 0.98)" not in stylesheet


def test_header_copy_uses_unquoted_title(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Copy the semantic title rather than its quoted visual label."""

    clipboard = install_recording_clipboard(monkeypatch)
    dialog = _build_default_dialog(danbooru_dialog_owner)

    dialog._copy_button.click()

    assert clipboard.text == "long hair"


def test_close_button_rejects_dialog(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Route the header close action through modal rejection."""

    dialog = _build_default_dialog(danbooru_dialog_owner)

    dialog._close_button.click()

    assert dialog.result() == DanbooruWikiDialog.DialogCode.Rejected


def _build_default_dialog(
    owner: DanbooruWikiDialogOwner,
) -> DanbooruWikiDialog:
    """Build one loaded representative wiki dialog."""

    return owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={"long hair": success_result(page_view())}
        ),
        selection_text="long hair",
        lookup_dispatcher=ImmediateDispatcher(),
    )
