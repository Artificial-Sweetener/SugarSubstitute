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

"""Verify responsive generation output Settings layout."""

from __future__ import annotations

from pathlib import Path

from substitute.presentation.settings.settings_card import SettingsCard
from substitute.presentation.settings.settings_workspace_panel import (
    SettingsPageDescriptor,
    SettingsWorkspacePanel,
)
from tests.presentation.settings.generation.support import (
    application,
    build_output_page,
)


def test_generation_page_output_rows_do_not_clip_at_narrow_width(
    tmp_path: Path,
) -> None:
    """Output organization rows should wrap within their cards."""

    app = application()
    page = build_output_page(default_output_root=tmp_path / "default-output")
    panel = SettingsWorkspacePanel()
    panel.resize(360, 620)
    panel.set_pages(
        (SettingsPageDescriptor("generation", "Generation", "Preview", None, page),)
    )
    panel.show()
    app.processEvents()

    output_cards = {
        card.title_label.text(): card for card in page.findChildren(SettingsCard)
    }
    for title in ("Output folder", "Output pattern", "Output preview"):
        card = output_cards[title]
        assert card.layout_mode() in {"wrapped", "wrapped_no_icon"}
        assert card.trailing_widget is not None
        assert card.trailing_widget.width() <= card.width()

    panel.close()


def test_generation_page_output_fields_keep_preferred_width_when_wide(
    tmp_path: Path,
) -> None:
    """Output fields should keep their comfortable width when space permits."""

    app = application()
    page = build_output_page(default_output_root=tmp_path / "default-output")
    panel = SettingsWorkspacePanel()
    panel.resize(1500, 620)
    panel.set_pages(
        (SettingsPageDescriptor("generation", "Generation", "Preview", None, page),)
    )
    panel.show()
    app.processEvents()

    assert page.output_root_edit.width() == 420
    assert page.output_path_pattern_edit.width() == 360
    assert page.output_preview_edit.width() == 420

    panel.close()
