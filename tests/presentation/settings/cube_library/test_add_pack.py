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

"""Test Cube Library GitHub pack validation and addition."""

from __future__ import annotations


import pytest
from qfluentwidgets import LineEdit  # type: ignore[import-untyped]

from substitute.presentation.settings.cube_library_page import (
    parse_github_cube_pack_url,
)
from tests.presentation.settings.cube_library.support import (
    FakeCubeLibraryService,
    application,
    build_page,
    title_label_texts,
)


def test_cube_library_page_validates_and_adds_github_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adding should parse, validate, sync, and render validation details."""

    app = application()
    service = FakeCubeLibraryService()
    page = build_page(monkeypatch, service=service)
    page.github_url_edit.setText("https://github.com/Owner/Repo")
    candidate = page._add_pack_candidate()
    assert candidate is not None

    page._validate_and_add_pack(candidate)
    app.processEvents()

    assert page.notification_bar.severity() == "success"
    assert service.preflight_calls == [("Owner", "Repo", "main")]
    assert service.add_calls == [("Owner", "Repo", "main", True)]
    assert page.validation_result_row.isHidden() is False
    assert page.add_pack_expander.has_content_available() is True
    assert page.add_pack_expander.is_expanded() is True
    assert "Owner/Repo" in page.validation_result_row.description_label.text()
    assert "demo.cube" in page.validation_result_row.description_label.text()
    page.close()


def test_cube_library_page_add_url_enablement_and_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Add controls should require a parseable GitHub repository URL."""

    page = build_page(monkeypatch)

    page.github_url_edit.setText("")

    assert page.add_button.isEnabled() is False
    assert page.add_pack_expander.has_content_available() is False
    assert page.add_pack_expander.is_expanded() is False

    page.github_url_edit.setText("https://github.com/Owner/Repo")

    assert page._add_pack_candidate() == parse_github_cube_pack_url(
        "https://github.com/Owner/Repo"
    )
    assert page.add_button.isEnabled() is True
    assert page.add_button.text() == "Add"
    assert page.add_pack_expander.header_card.findChildren(LineEdit) == [
        page.github_url_edit
    ]
    page.add_pack_expander.header_card.activated.emit()
    assert page.add_pack_expander.is_expanded() is False
    assert "GitHub URL" not in title_label_texts(
        page.add_pack_expander.content_widget()
    )
    assert "Add pack" not in title_label_texts(page.add_pack_expander.content_widget())
    page.close()


def test_parse_github_cube_pack_url_accepts_github_urls_and_shorthand() -> None:
    """GitHub pack parser should accept pasted URLs and owner/repo shorthand."""

    assert parse_github_cube_pack_url("https://github.com/Owner/Repo") is not None
    assert parse_github_cube_pack_url("github.com/Owner/Repo.git") is not None
    assert parse_github_cube_pack_url("Owner/Repo") is not None
    assert parse_github_cube_pack_url("https://example.com/Owner/Repo") is None
    assert parse_github_cube_pack_url("https://github.com/Owner") is None
