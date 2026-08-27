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

"""Verify inline LoRA rendering geometry and boundary edits."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptLoraRendererView,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from tests.support.prompt_editor.autocomplete_support import (
    prompt_syntax_profile,
)
from tests.support.prompt_editor.projection_surface_support import (
    StaticPromptLoraCatalog,
    apply_source_range_to_projection,
    install_lora_wildcard_prompt_state,
    lora_catalog_item_with_banner,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    set_surface_prompt_state,
    valid_transient_insertion_overlay,
)
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
)
from tests.support.prompt_editor.projection_surface_factory import (
    new_projection_surface,
    surface_source_commands,
)


def test_projection_surface_rebuilds_when_lora_renderer_span_completes_plain_suffix(
    widgets: list[QWidget],
) -> None:
    """LoRA renderer spans should force token projection even without top-level spans."""

    ensure_qapp()
    surface = new_projection_surface()
    surface.resize(420, 180)
    widgets.append(surface)
    surface_source_commands(surface).set_plain_text("<lora:midna:1")
    document_view = PromptDocumentService().build_document_view("<lora:midna:1>")
    full_render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(
            (lora_catalog_item_with_banner(),)
        ),
    ).build_render_plan(document_view, prompt_syntax_profile("lora"))
    lora_renderer_view = cast(
        PromptLoraRendererView,
        full_render_plan.renderer_view_for_kind("lora"),
    )
    renderer_only_render_plan = PromptSyntaxRenderPlan(
        syntax_spans=(),
        renderer_views=(replace(lora_renderer_view, syntax_spans=()),),
    )

    set_surface_prompt_state(surface, document_view, renderer_only_render_plan)
    surface.flush_pending_projection_update(reason="test_renderer_only_state")

    projection_document = surface.projection_document()
    assert [
        (token.kind, token.source_start, token.source_end)
        for token in projection_document.tokens
    ] == [(PromptProjectionTokenKind.LORA, 0, len("<lora:midna:1>"))]
    assert [
        (run.kind.name, run.renderer_key)
        for run in projection_document.runs
        if run.token_id is not None
    ] == [("INLINE_OBJECT", "lora_chip")]
    assert (
        cast(Any, surface)._layout.frame.output.snapshot.inline_object_fragment_count()
        == 1
    )


def test_projection_surface_lora_chip_stays_within_text_row_height(
    widgets: list[QWidget],
) -> None:
    """LoRA chips should sit inside the canonical row without filling it."""

    ensure_qapp()
    surface = new_projection_surface()
    surface.resize(520, 180)
    widgets.append(surface)
    install_lora_wildcard_prompt_state(surface, "<lora:midna:1> tail")

    layout = cast(Any, surface)._layout
    line = next(
        line
        for line in layout.frame.output.snapshot.lines
        if any(
            fragment.__class__.__name__ == "PromptProjectionInlineObjectFragment"
            for fragment in line.fragments
        )
    )
    lora_fragment = next(
        fragment
        for fragment in line.fragments
        if fragment.__class__.__name__ == "PromptProjectionInlineObjectFragment"
    )

    assert line.height == layout.frame.output.configuration.metrics.text_line_height
    assert (
        lora_fragment.rect.height()
        < layout.frame.output.configuration.metrics.text_line_height
    )


def test_projection_surface_lora_boundary_insert_keeps_inserted_text_plain(
    widgets: list[QWidget],
) -> None:
    """Typing at a LoRA edge should not extend the chip over the new character."""

    ensure_qapp()
    surface = new_projection_surface()
    surface.resize(520, 180)
    widgets.append(surface)
    text = "<lora:midna:1>, tail"
    install_lora_wildcard_prompt_state(surface, text)
    lora_token = next(
        token
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    )
    insertion_position = lora_token.source_end
    next_text = text[:insertion_position] + "<" + text[insertion_position:]

    apply_source_range_to_projection(
        surface,
        next_text,
        source_edit_start=insertion_position,
        source_edit_end=insertion_position,
        source_edit_replacement_text="<",
    )

    shifted_lora_token = next(
        token
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    )
    assert shifted_lora_token.source_start == lora_token.source_start
    assert shifted_lora_token.source_end == lora_token.source_end
    assert surface.cursor_position == insertion_position + 1
    assert surface._cursor_state.token_id is None  # noqa: SLF001
    assert [
        (run.kind.name, run.display_text, run.token_id)
        for run in surface.projection_document().runs
    ] == [
        ("INLINE_OBJECT", "Midna", shifted_lora_token.token_id),
        ("TEXT", "<, tail", None),
    ]


def test_projection_surface_lora_suffix_prefix_defers_without_rebuild(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typing a LoRA prefix after a trailing LoRA chip should keep the key path cheap."""

    ensure_qapp()
    surface = new_projection_surface()
    surface.resize(520, 180)
    widgets.append(surface)
    text = "<lora:midna:1>"
    install_lora_wildcard_prompt_state(surface, text)
    surface.set_defer_source_rebuilds_until_prompt_state(True)
    lora_token = next(
        token
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    )
    surface.set_cursor_positions(
        cursor_position=lora_token.source_end,
        anchor_position=lora_token.source_end,
    )
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record full projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)

    surface.textCursor().insertText("<")

    overlay = valid_transient_insertion_overlay(surface)
    assert surface.toPlainText() == f"{text}<"
    assert surface.projection_document().source_text == text
    assert surface.cursor_position == len(text) + 1
    assert overlay is not None
    assert overlay.text == "<"
    assert rebuild_count == 0
