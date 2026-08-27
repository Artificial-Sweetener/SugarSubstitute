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

"""Test wildcard document reorder behavior."""

from __future__ import annotations


from substitute.application.managed_text_assets.wildcard_csv_document_parser import (
    parse_wildcard_csv_document,
)
from substitute.application.managed_text_assets.wildcard_csv_document_semantics import (
    WildcardCsvDocumentSemantics,
)
from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.reorder.views import PromptReorderStateView


def test_txt_reorder_retains_normal_cross_value_tag_behavior() -> None:
    """TXT wildcard values should share the normal tag reorder model."""

    source = "1girl, blonde hair, blue eyes\nsmile, red dress"
    service = PromptDocumentService()
    document_view = service.build_document_view(source)
    session = service.build_reorder_session_view(document_view)

    reordered = service.serialize_reorder_state_view(
        document_view,
        PromptReorderStateView(
            ordered_chip_indices=(0, 1, 3, 2, 4),
            separator_slots=session.reorder_state.separator_slots,
            has_trailing_comma=False,
        ),
    )

    assert tuple(chip.text for chip in session.chips) == (
        "1girl",
        "blonde hair",
        "blue eyes",
        "smile",
        "red dress",
    )
    assert reordered == ("1girl, blonde hair, smile\nblue eyes, red dress")


def test_csv_reorder_uses_normal_tags_and_preserves_value_containers() -> None:
    """CSV reorder should skip headers and encode tag movement into the same cells."""

    source = 'Prompt\n"1girl, blonde hair, blue eyes"\n"smile, red dress"'
    semantics = WildcardCsvDocumentSemantics()
    service = PromptDocumentService(document_semantics=semantics)
    document_view = service.build_document_view(source)
    session = service.build_reorder_session_view(document_view)
    state = PromptReorderStateView(
        ordered_chip_indices=(0, 1, 3, 2, 4),
        separator_slots=session.reorder_state.separator_slots,
        has_trailing_comma=False,
    )

    reordered = service.serialize_reorder_state_view(document_view, state)

    assert tuple(chip.text for chip in session.chips) == (
        "1girl",
        "blonde hair",
        "blue eyes",
        "smile",
        "red dress",
    )
    assert all(chip.text != "Prompt" for chip in session.chips)
    assert reordered == ('Prompt\n"1girl, blonde hair, smile"\n"blue eyes, red dress"')
    assert parse_wildcard_csv_document(reordered).valid is True


def test_csv_reorder_preserves_multiline_cells_and_column_boundaries() -> None:
    """Structured reorder should distinguish cell boundaries from value newlines."""

    source = 'Name,Prompt\nfox,"red hair,\nblue eyes"\nwolf,"smile, red dress"'
    semantics = WildcardCsvDocumentSemantics()
    service = PromptDocumentService(document_semantics=semantics)
    document_view = service.build_document_view(source)
    session = service.build_reorder_session_view(document_view)
    state = PromptReorderStateView(
        ordered_chip_indices=(0, 2, 1, 3, 4, 5),
        separator_slots=session.reorder_state.separator_slots,
        has_trailing_comma=False,
    )

    reordered = service.serialize_reorder_state_view(document_view, state)
    parsed = parse_wildcard_csv_document(reordered)

    assert tuple(chip.text for chip in session.chips) == (
        "fox",
        "red hair",
        "blue eyes",
        "wolf",
        "smile",
        "red dress",
    )
    assert parsed.valid is True
    assert parsed.records[1][0].value == "fox"
    assert parsed.records[1][1].value == "blue eyes,\nred hair"
