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

"""Verify output pattern token autocomplete behavior."""

from __future__ import annotations

from pathlib import Path

from tests.presentation.settings.generation.support import (
    application,
    build_output_page,
)


def test_output_pattern_token_autocomplete_filters_and_inserts(tmp_path: Path) -> None:
    """A token fragment should offer matching tokens and insert selection."""

    app = application()
    page = build_output_page(default_output_root=tmp_path / "default-output")
    page.show()
    app.processEvents()

    page.output_path_pattern_edit.setFocus()
    page.set_output_path_pattern("{workflow}\\{da")
    page.output_path_pattern_edit.setCursorPosition(len("{workflow}\\{da"))
    assert page.output_token_autocomplete is not None
    page.output_token_autocomplete.refresh()
    app.processEvents()

    assert page.output_token_autocomplete.is_visible() is True
    assert page.output_token_autocomplete.visible_tokens() == ("{date}", "{day}")
    assert page.output_token_autocomplete.accept_current() is True
    assert page.output_path_pattern_edit.text() == "{workflow}\\{date}"
    page.close()


def test_output_pattern_token_autocomplete_inserts_seed(tmp_path: Path) -> None:
    """A seed fragment should offer and insert the seed token."""

    app = application()
    page = build_output_page(default_output_root=tmp_path / "default-output")
    page.show()
    app.processEvents()

    page.output_path_pattern_edit.setFocus()
    page.set_output_path_pattern("{see")
    page.output_path_pattern_edit.setCursorPosition(len("{see"))
    assert page.output_token_autocomplete is not None
    page.output_token_autocomplete.refresh()
    app.processEvents()

    assert page.output_token_autocomplete.is_visible() is True
    assert page.output_token_autocomplete.visible_tokens() == ("{seed}",)
    assert page.output_token_autocomplete.accept_current() is True
    assert page.output_path_pattern_edit.text() == "{seed}"
    page.close()
