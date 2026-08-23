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

"""Tests for prompt projection incremental editing surface behavior."""

from __future__ import annotations

from typing import Any, cast


import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    delay_projection_update_scheduler,
    first_emphasis_token,
    flush_projection_update_scheduler,
    flush_semantic_refresh,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    StaticPromptLoraCatalog,
    valid_transient_insertion_overlay,
)
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile

from .support import (
    _publish_test_source,
)


def test_projection_surface_defers_simple_typed_edit_rebuild_with_existing_syntax(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trailing plain typing should catch up without a full projection rebuild."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "x")
    overlay = valid_transient_insertion_overlay(surface)
    assert overlay is not None
    assert overlay.text == "x"
    flush_semantic_refresh(box)

    assert box.toPlainText() == "(cat:1.05), x"
    assert rebuild_count == 0
    assert surface.has_pending_projection_update() is True

    flush_projection_update_scheduler(surface)
    process_events(app)

    assert box.toPlainText() == "(cat:1.05), x"
    assert first_emphasis_token(box).display_text == "cat"
    assert rebuild_count == 0
    assert valid_transient_insertion_overlay(surface) is None


def test_projection_surface_scheduled_middle_plain_edit_uses_incremental_apply(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scheduled safe-typing catch-up should avoid full rebuild for local edits."""

    box = show_prompt_editor(
        widgets,
        text="alpha beta",
        width=360,
    )
    surface = surface_for(box)
    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(()),
    )
    previous_render_plan = surface.editor_state.projection_semantic.render_plan
    next_text = "alphax beta"
    next_document_view = document_service.build_document_view(next_text)
    next_render_plan = syntax_service.build_render_plan(
        next_document_view,
        prompt_syntax_profile("emphasis", "wildcard", "lora"),
    )
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)

    _publish_test_source(surface, next_text)
    cast(Any, surface)._prompt_state_applier.apply_prompt_state_projection(
        surface.editor_state.prepare_semantic(
            next_document_view,
            next_render_plan,
            source_identity=surface.editor_state.source_identity,
        ),
        previous_render_plan_for_fast_path=previous_render_plan,
    )

    assert rebuild_count == 0
    assert surface.projection_document().source_text == next_text
    assert surface.projection_document().projection_text.endswith("alphax beta")


def test_projection_surface_long_middle_plain_edit_uses_incremental_apply(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Long positive prompts should not full-rebuild for safe middle edits."""

    source_lines = [
        f"masterpiece, detailed scene, soft light, cinematic color, subject {index:02d}"
        for index in range(70)
    ]
    source_text = "\n".join(source_lines)
    edit_line_index = 35
    edit_offset = sum(len(line) + 1 for line in source_lines[:edit_line_index]) + 12
    next_text = source_text[:edit_offset] + "x" + source_text[edit_offset:]
    box = show_prompt_editor(
        widgets,
        text=source_text,
        width=520,
    )
    surface = surface_for(box)
    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(()),
    )
    previous_render_plan = surface.editor_state.projection_semantic.render_plan
    next_document_view = document_service.build_document_view(next_text)
    next_render_plan = syntax_service.build_render_plan(
        next_document_view,
        prompt_syntax_profile("emphasis", "wildcard", "lora"),
    )
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)

    _publish_test_source(surface, next_text)
    cast(Any, surface)._prompt_state_applier.apply_prompt_state_projection(
        surface.editor_state.prepare_semantic(
            next_document_view,
            next_render_plan,
            source_identity=surface.editor_state.source_identity,
        ),
        previous_render_plan_for_fast_path=previous_render_plan,
    )

    assert rebuild_count == 0
    assert surface.projection_document().source_text == next_text


def test_projection_surface_scheduled_plain_replacement_uses_incremental_apply(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scheduled plain replacement should avoid rebuilding the whole projection."""

    box = show_prompt_editor(
        widgets,
        text="alpha beta",
        width=360,
    )
    surface = surface_for(box)
    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(()),
    )
    previous_render_plan = surface.editor_state.projection_semantic.render_plan
    next_text = "alpha zeta"
    next_document_view = document_service.build_document_view(next_text)
    next_render_plan = syntax_service.build_render_plan(
        next_document_view,
        prompt_syntax_profile("emphasis", "wildcard", "lora"),
    )
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)

    _publish_test_source(surface, next_text)
    cast(Any, surface)._prompt_state_applier.apply_prompt_state_projection(
        surface.editor_state.prepare_semantic(
            next_document_view,
            next_render_plan,
            source_identity=surface.editor_state.source_identity,
        ),
        previous_render_plan_for_fast_path=previous_render_plan,
    )

    assert rebuild_count == 0
    assert surface.projection_document().source_text == next_text


def test_projection_surface_scheduled_plain_selection_delete_uses_incremental_apply(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scheduled plain selection delete should avoid rebuilding the whole projection."""

    box = show_prompt_editor(
        widgets,
        text="alpha removable beta",
        width=360,
    )
    surface = surface_for(box)
    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(()),
    )
    previous_render_plan = surface.editor_state.projection_semantic.render_plan
    next_text = "alpha beta"
    next_document_view = document_service.build_document_view(next_text)
    next_render_plan = syntax_service.build_render_plan(
        next_document_view,
        prompt_syntax_profile("emphasis", "wildcard", "lora"),
    )
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)

    _publish_test_source(surface, next_text)
    cast(Any, surface)._prompt_state_applier.apply_prompt_state_projection(
        surface.editor_state.prepare_semantic(
            next_document_view,
            next_render_plan,
            source_identity=surface.editor_state.source_identity,
        ),
        previous_render_plan_for_fast_path=previous_render_plan,
    )

    assert rebuild_count == 0
    assert surface.projection_document().source_text == next_text
