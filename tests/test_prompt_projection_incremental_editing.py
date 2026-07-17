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

import os
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionCaretState,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.incremental_editor import (
    PromptProjectionPlainTextApplyStatus,
)
from substitute.presentation.editor.prompt_editor.projection.snapshot import (
    PromptProjectionLineSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from substitute.presentation.editor.prompt_editor.projection.transient_edit_overlays import (
    PromptProjectionTransientDeletionOverlay,
)
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.prompt_projection_surface_test_helpers import (
    apply_source_range_to_projection,
    delay_projection_update_scheduler,
    first_emphasis_token,
    flush_projection_update_scheduler,
    flush_semantic_refresh,
    install_lora_wildcard_prompt_state,
    new_projection_surface,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    projection_token_kinds,
    render_surface_viewport,
    StaticPromptLoraCatalog,
    valid_transient_insertion_overlay,
)
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection surface tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _projection_line_texts(surface: PromptProjectionSurface) -> tuple[str, ...]:
    """Return visible text grouped by projection visual line."""

    snapshot = cast(Any, surface)._layout._snapshot
    return tuple(
        "".join(
            fragment.text for fragment in line.fragments if hasattr(fragment, "text")
        )
        for line in snapshot.lines
    )


def _projection_lines(
    surface: PromptProjectionSurface,
) -> tuple[PromptProjectionLineSnapshot, ...]:
    """Return the live projection visual-line snapshots for geometry assertions."""

    return cast(
        tuple[PromptProjectionLineSnapshot, ...],
        cast(Any, surface)._layout._snapshot.lines,
    )


def _valid_transient_deletion_overlay(
    surface: PromptProjectionSurface,
) -> PromptProjectionTransientDeletionOverlay | None:
    """Return controller-owned transient deletion overlay state for assertions."""

    return surface._transient_edit_overlays.valid_deletion_overlay(  # noqa: SLF001
        freshness_is_stale_safe=surface.has_stale_projection_geometry(),
        source_revision=surface._source_revision,  # noqa: SLF001
    )


def test_projection_surface_caret_move_clears_stale_active_lora_paint(
    widgets: list[QWidget],
) -> None:
    """Caret movement should update active projection paint before source edits."""

    ensure_qapp()
    surface = new_projection_surface()
    surface.resize(520, 260)
    widgets.append(surface)
    text = "1girl\n\n<lora:Anima\\style\\People:1.00>"
    plain_tag_end = len("1girl")
    install_lora_wildcard_prompt_state(surface, text)

    def active_layout_token_ranges() -> tuple[tuple[int, int], ...]:
        """Return active token ranges from layout-owned paint state."""

        layout = cast(Any, surface)._layout
        active_token_ids = layout.paint_state.active_token_ids
        return tuple(
            (token.source_start, token.source_end)
            for token in layout.projection_document.tokens
            if token.token_id in active_token_ids
        )

    assert active_layout_token_ranges() == ((len("1girl\n\n"), len(text)),)

    surface.set_cursor_positions(
        cursor_position=plain_tag_end,
        anchor_position=plain_tag_end,
    )

    assert active_layout_token_ranges() == ()


def test_projection_surface_immediate_syntax_insert_preserves_unaffected_semantics(
    widgets: list[QWidget],
) -> None:
    """Immediate syntax-sensitive typing should not blank unrelated decorations."""

    ensure_qapp()
    surface = new_projection_surface()
    surface.resize(520, 180)
    widgets.append(surface)
    text = "(cat:1.05), {animal}, <lora:midna:1>, tail"
    install_lora_wildcard_prompt_state(surface, text)
    assert projection_token_kinds(surface) == (
        PromptProjectionTokenKind.EMPHASIS,
        PromptProjectionTokenKind.WILDCARD,
        PromptProjectionTokenKind.LORA,
    )

    next_text = f"{text}<"
    apply_source_range_to_projection(
        surface,
        next_text,
        cursor_position=len(next_text),
        anchor_position=len(next_text),
        emit_text_changed=True,
        rebuild_immediately=True,
        optimistic_prompt_state=None,
        source_edit_start=len(text),
        source_edit_end=len(text),
        source_edit_replacement_text="<",
        previous_source_text=text,
    )

    assert surface.projection_document().source_text == next_text
    assert projection_token_kinds(surface) == (
        PromptProjectionTokenKind.EMPHASIS,
        PromptProjectionTokenKind.WILDCARD,
        PromptProjectionTokenKind.LORA,
    )


def test_projection_surface_immediate_delete_preserves_shifted_semantics(
    widgets: list[QWidget],
) -> None:
    """Immediate backspace/delete before decorations should remap them in place."""

    ensure_qapp()
    surface = new_projection_surface()
    surface.resize(520, 180)
    widgets.append(surface)
    text = "x, {animal}, <lora:midna:1>, tail"
    install_lora_wildcard_prompt_state(surface, text)
    original_lora_token = next(
        token
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    )

    next_text = text[1:]
    apply_source_range_to_projection(
        surface,
        next_text,
        cursor_position=0,
        anchor_position=0,
        emit_text_changed=True,
        rebuild_immediately=True,
        optimistic_prompt_state=None,
        source_edit_start=0,
        source_edit_end=1,
        source_edit_replacement_text="",
        previous_source_text=text,
    )

    shifted_lora_token = next(
        token
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    )
    assert surface.projection_document().source_text == next_text
    assert projection_token_kinds(surface) == (
        PromptProjectionTokenKind.WILDCARD,
        PromptProjectionTokenKind.LORA,
    )
    assert shifted_lora_token.source_start == original_lora_token.source_start - 1
    assert shifted_lora_token.source_end == original_lora_token.source_end - 1


def test_projection_surface_middle_insert_before_blank_line_reflows_immediately(
    widgets: list[QWidget],
) -> None:
    """Middle insertion before a blank line should publish real caret geometry."""

    box = show_prompt_editor(
        widgets,
        text="alpha\n\nomega",
        width=360,
    )
    surface = surface_for(box)
    surface.set_cursor_positions(cursor_position=5, anchor_position=5)
    before_rect = surface._current_caret_document_rect()  # noqa: SLF001

    cast(Any, surface)._insert_viewport_text("x")

    after_rect = surface._current_caret_document_rect()  # noqa: SLF001
    assert surface.toPlainText() == "alphax\n\nomega"
    assert surface.has_stale_projection_geometry() is False
    assert valid_transient_insertion_overlay(surface) is None
    assert after_rect.top() == pytest.approx(before_rect.top())
    assert after_rect.left() > before_rect.left()


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
    previous_render_plan = cast(Any, surface)._render_plan
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

    cast(Any, surface)._prompt_state_applier.apply_prompt_state_projection(
        next_document_view,
        next_render_plan,
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
    previous_render_plan = cast(Any, surface)._render_plan
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

    cast(Any, surface)._prompt_state_applier.apply_prompt_state_projection(
        next_document_view,
        next_render_plan,
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
    previous_render_plan = cast(Any, surface)._render_plan
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

    cast(Any, surface)._prompt_state_applier.apply_prompt_state_projection(
        next_document_view,
        next_render_plan,
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
    previous_render_plan = cast(Any, surface)._render_plan
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

    cast(Any, surface)._prompt_state_applier.apply_prompt_state_projection(
        next_document_view,
        next_render_plan,
        previous_render_plan_for_fast_path=previous_render_plan,
    )

    assert rebuild_count == 0
    assert surface.projection_document().source_text == next_text


def test_projection_surface_allows_plain_layout_miss_fallback_deferral(
    widgets: list[QWidget],
) -> None:
    """Fallback deferral is limited to text that can be safely overlaid."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), alpha beta",
        width=360,
    )
    surface = surface_for(box)
    text = box.toPlainText()
    cursor_position = len(text)

    assert cast(
        Any, surface
    )._incremental_apply_controller._can_defer_immediate_projection_fallback_edit(
        previous_text=text,
        next_text=f"{text[:cursor_position]}x{text[cursor_position:]}",
        start=cursor_position,
        end=cursor_position,
        replacement_text="x",
        projection_deferral_reason="plain_single_character_requires_layout",
    )
    middle_position = box.toPlainText().index(" beta")
    assert not cast(
        Any, surface
    )._incremental_apply_controller._can_defer_immediate_projection_fallback_edit(
        previous_text=text,
        next_text=f"{text[:middle_position]}x{text[middle_position:]}",
        start=middle_position,
        end=middle_position,
        replacement_text="x",
        projection_deferral_reason="plain_single_character_requires_layout",
    )
    assert not cast(
        Any, surface
    )._incremental_apply_controller._can_defer_immediate_projection_fallback_edit(
        previous_text=text,
        next_text=f"{text[:middle_position]}\n{text[middle_position:]}",
        start=middle_position,
        end=middle_position,
        replacement_text="\n",
        projection_deferral_reason="control_character",
    )


def test_projection_surface_empty_middle_line_typing_uses_incremental_layout(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typing into an empty middle line should not force a full projection rebuild."""

    box = show_prompt_editor(
        widgets,
        text="alpha\n\nomega",
        width=360,
    )
    surface = surface_for(box)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    empty_line_position = box.toPlainText().index("\n\n") + 1
    surface.set_cursor_positions(
        cursor_position=empty_line_position,
        anchor_position=empty_line_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "x")

    assert box.toPlainText() == "alpha\nx\nomega"
    assert surface.projection_document().source_text == "alpha\nx\nomega"
    assert rebuild_count == 0
    assert surface.has_stale_projection_geometry() is False
    assert _projection_line_texts(surface) == ("alpha", "x", "omega")


def test_projection_surface_middle_plain_backspace_publishes_real_layout(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plain middle Backspace should reflow text instead of painting an erase block."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), alpha beta gamma",
        width=360,
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
    cursor_position = box.toPlainText().index(" beta")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0
    upstream_token = first_emphasis_token(box)
    upstream_token_rect = surface._layout.token_rect(  # noqa: SLF001
        upstream_token,
        scroll_offset=0.0,
    )
    assert upstream_token_rect is not None
    previous_height = surface.content_height()
    previous_scroll_maximum = surface.verticalScrollBar().maximum()

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "(cat:1.05), alph beta gamma"
    assert rebuild_count <= 1
    assert surface.has_stale_projection_geometry() is False
    assert _valid_transient_deletion_overlay(surface) is None
    current_upstream_token = first_emphasis_token(box)
    current_upstream_token_rect = surface._layout.token_rect(  # noqa: SLF001
        current_upstream_token,
        scroll_offset=0.0,
    )
    assert current_upstream_token_rect is not None
    assert current_upstream_token_rect == upstream_token_rect
    assert surface.content_height() <= previous_height
    assert surface.verticalScrollBar().maximum() <= previous_scroll_maximum

    height_after_backspace = surface.content_height()
    scroll_maximum_after_backspace = surface.verticalScrollBar().maximum()

    flush_semantic_refresh(box)

    assert rebuild_count <= 1
    assert surface.content_height() == pytest.approx(height_after_backspace)
    assert surface.verticalScrollBar().maximum() == scroll_maximum_after_backspace


def test_projection_surface_middle_plain_typing_publishes_real_layout(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plain middle typing should reflow following text instead of overlaying it."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), alpha beta gamma",
        width=360,
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
    cursor_position = box.toPlainText().index(" beta")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0
    upstream_token = first_emphasis_token(box)
    upstream_token_rect = surface._layout.token_rect(  # noqa: SLF001
        upstream_token,
        scroll_offset=0.0,
    )
    assert upstream_token_rect is not None

    QTest.keyClicks(box, "x")

    assert box.toPlainText() == "(cat:1.05), alphax beta gamma"
    assert rebuild_count <= 1
    assert surface.has_stale_projection_geometry() is False
    assert valid_transient_insertion_overlay(surface) is None
    current_upstream_token = first_emphasis_token(box)
    current_upstream_token_rect = surface._layout.token_rect(  # noqa: SLF001
        current_upstream_token,
        scroll_offset=0.0,
    )
    assert current_upstream_token_rect is not None
    assert current_upstream_token_rect == upstream_token_rect

    height_after_typing = surface.content_height()
    scroll_maximum_after_typing = surface.verticalScrollBar().maximum()

    flush_semantic_refresh(box)

    assert rebuild_count <= 1
    assert surface.content_height() == pytest.approx(height_after_typing)
    assert surface.verticalScrollBar().maximum() == scroll_maximum_after_typing


def test_projection_surface_word_edge_typing_keeps_word_wrap_integrity(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typing at a wrap edge should coalesce reflow off the keypress lane."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha beta bl",
        width=260,
    )
    surface = surface_for(box)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record wrap-boundary fallback rebuilds while preserving behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    configured_width: int | None = None
    for width in range(145, 321, 5):
        box.setGeometry(20, 20, width, box.height())
        process_events(app)
        line_texts = _projection_line_texts(surface)
        if len(line_texts) == 1 and line_texts[0].endswith("bl"):
            configured_width = width
            break
    assert configured_width is not None

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    delay_projection_update_scheduler(surface)
    surface.set_cursor_positions(
        cursor_position=len(box.toPlainText()),
        anchor_position=len(box.toPlainText()),
    )

    QTest.keyClicks(box, "ush")
    process_events(app)

    assert surface.has_pending_projection_update() is True
    assert surface.has_stale_projection_geometry() is True
    assert rebuild_count == 0
    flush_projection_update_scheduler(surface)
    process_events(app)

    line_texts = _projection_line_texts(surface)
    assert any("blush" in line_text for line_text in line_texts)
    assert not any(
        line_text.endswith("bl") and next_line_text.startswith("ush")
        for line_text, next_line_text in zip(line_texts, line_texts[1:], strict=False)
    )
    assert rebuild_count <= 1


def test_projection_surface_kept_tag_edit_uses_fast_path_when_layout_stays_local(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kept tag edits should stay fast when the group remains on its line."""

    box = show_prompt_editor(
        widgets,
        text="alpha beta, cowgirl po, omega",
        width=520,
    )
    surface = surface_for(box)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record fallback rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = box.toPlainText().index("po") + 2
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "s")

    assert box.toPlainText() == "alpha beta, cowgirl pos, omega"
    assert rebuild_count == 0


def test_projection_surface_kept_tag_edge_edit_uses_projection_reuse_fallback(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kept tag edge edits should coalesce wrap reflow off the keypress lane."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha beta, cowgirl po, omega",
        width=260,
    )
    surface = surface_for(box)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record fallback rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    configured_width: int | None = None
    for width in range(190, 421, 5):
        box.setGeometry(20, 20, width, box.height())
        process_events(app)
        if any(
            line_text.strip().endswith("cowgirl po,")
            for line_text in _projection_line_texts(surface)
        ):
            configured_width = width
            break
    assert configured_width is not None

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    delay_projection_update_scheduler(surface)
    cursor_position = box.toPlainText().index("po") + 2
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "s")
    process_events(app)

    assert box.toPlainText() == "alpha beta, cowgirl pos, omega"
    if surface.has_pending_projection_update():
        assert surface.has_stale_projection_geometry() is True
        flush_projection_update_scheduler(surface)
        process_events(app)
    else:
        assert surface.has_stale_projection_geometry() is False

    assert any(
        "cowgirl pos," in line_text for line_text in _projection_line_texts(surface)
    )
    assert rebuild_count <= 1


def test_projection_surface_projected_token_delete_preserves_unaffected_tokens(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting inside one projected token should not make the whole prompt raw."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), alpha, (dog:1.10)",
        width=360,
    )
    surface = surface_for(box)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = box.toPlainText().index("t:")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    projected_texts = {
        token.display_text for token in surface.projection_document().tokens
    }
    assert box.toPlainText() == "(ct:1.05), alpha, (dog:1.10)"
    assert "dog" in projected_texts
    assert rebuild_count == 1
    assert surface.has_stale_projection_geometry() is False


def test_projection_surface_source_edit_invalidates_projection_content_cache(
    widgets: list[QWidget],
) -> None:
    """Source edits should not allow a stale projection pixmap cache hit."""

    box = show_prompt_editor(
        widgets,
        text="alpha beta",
        width=360,
    )
    surface = surface_for(box)
    render_surface_viewport(surface)
    paint_cache = cast(Any, surface)._projection_paint_cache
    assert paint_cache.cache_key is not None
    assert paint_cache.cache_pixmap is not None

    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "alpha bet"
    assert paint_cache.cache_key is None
    assert paint_cache.cache_pixmap is None


def test_projection_surface_backspace_updates_for_immediate_visibility(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trailing plain deletion should publish real layout without an erase overlay."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), alpha",
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    committed_height = surface.content_height()
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    original_ensure_caret_visible = surface._ensure_caret_visible  # noqa: SLF001
    original_collapse_expanded_token = (  # noqa: SLF001
        surface._collapse_expanded_token_if_possible  # noqa: SLF001
    )
    rebuild_count = 0
    ensure_caret_visible_count = 0
    collapse_expanded_token_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    def count_ensure_caret_visible() -> None:
        """Record caret visibility sync calls while preserving behavior."""

        nonlocal ensure_caret_visible_count
        ensure_caret_visible_count += 1
        original_ensure_caret_visible()

    def count_collapse_expanded_token() -> None:
        """Record expanded-token collapse checks while preserving behavior."""

        nonlocal collapse_expanded_token_count
        collapse_expanded_token_count += 1
        original_collapse_expanded_token()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    monkeypatch.setattr(surface, "_ensure_caret_visible", count_ensure_caret_visible)
    monkeypatch.setattr(
        surface,
        "_collapse_expanded_token_if_possible",
        count_collapse_expanded_token,
    )
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0
    ensure_caret_visible_count = 0
    collapse_expanded_token_count = 0

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "(cat:1.05), alph"
    assert surface.has_stale_projection_geometry() is False
    assert _valid_transient_deletion_overlay(surface) is None
    assert rebuild_count == 0
    assert ensure_caret_visible_count == 1
    assert collapse_expanded_token_count == 0
    assert surface.content_height() == pytest.approx(committed_height)
    assert surface.has_pending_projection_update() is False
    assert first_emphasis_token(box).display_text == "cat"
    committed_metrics = cast(
        Any, surface
    )._projection_freshness_controller.committed_metrics
    assert committed_metrics is not None
    assert committed_metrics.source_revision == cast(Any, surface)._source_revision


def test_projection_surface_expanded_token_enter_preserves_semantic_projection(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enter while a token is expanded should not publish an all-raw interim layout."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), alpha beta, (dog:1.10)",
        width=360,
    )
    surface = surface_for(box)
    expanded_token = first_emphasis_token(box)
    surface._session.expand_token(expanded_token)  # noqa: SLF001
    surface._rebuild_projection()  # noqa: SLF001
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = box.toPlainText().index(" beta")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClick(box, Qt.Key.Key_Return)

    projected_texts = {
        token.display_text for token in surface.projection_document().tokens
    }
    assert box.toPlainText() == "(cat:1.05), alpha\n beta, (dog:1.10)"
    assert "dog" in projected_texts
    assert surface.has_stale_projection_geometry() is False
    assert rebuild_count == 1

    content_height_after_enter = surface.content_height()
    flush_semantic_refresh(box)

    refreshed_texts = {
        token.display_text for token in surface.projection_document().tokens
    }
    assert "dog" in refreshed_texts
    assert surface.content_height() == pytest.approx(content_height_after_enter)
    assert rebuild_count == 1


def test_projection_surface_expanded_token_newline_backspace_preserves_semantics(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Newline Backspace with an expanded token should avoid all-raw interim layout."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), alpha\n beta, (dog:1.10)",
        width=360,
    )
    surface = surface_for(box)
    expanded_token = first_emphasis_token(box)
    surface._session.expand_token(expanded_token)  # noqa: SLF001
    surface._rebuild_projection()  # noqa: SLF001
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = box.toPlainText().index("\n") + 1
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    projected_texts = {
        token.display_text for token in surface.projection_document().tokens
    }
    assert box.toPlainText() == "(cat:1.05), alpha beta, (dog:1.10)"
    assert "dog" in projected_texts
    assert surface.has_stale_projection_geometry() is False
    assert rebuild_count == 1

    content_height_after_backspace = surface.content_height()
    flush_semantic_refresh(box)

    refreshed_texts = {
        token.display_text for token in surface.projection_document().tokens
    }
    assert "dog" in refreshed_texts
    assert surface.content_height() == pytest.approx(content_height_after_backspace)
    assert rebuild_count == 1


def test_projection_surface_backspace_rebuilds_after_pending_typing_projection(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backspace should safely commit geometry after deferred typing is removed."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=360,
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
    flush_semantic_refresh(box)
    assert surface.has_pending_projection_update() is True

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "(cat:1.05), "
    assert rebuild_count == 1
    assert valid_transient_insertion_overlay(surface) is None
    assert surface.has_pending_projection_update() is False
    assert surface.has_stale_projection_geometry() is False
    assert rebuild_count == 1
    committed_metrics = cast(
        Any, surface
    )._projection_freshness_controller.committed_metrics
    assert committed_metrics is not None
    assert committed_metrics.source_revision == cast(Any, surface)._source_revision


def test_projection_surface_applies_local_middle_comma_without_rebuild(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local comma keep-group edits should avoid synchronous full rebuilds."""

    box = show_prompt_editor(
        widgets,
        text="test test test test, omega",
        width=1000,
    )
    surface = surface_for(box)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len("test")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, ",")

    assert box.toPlainText() == "test, test test test, omega"
    assert rebuild_count == 0
    assert surface.has_pending_projection_update() is False
    assert surface.has_stale_projection_geometry() is False


def test_projection_surface_middle_typing_rejects_transient_overlay(
    widgets: list[QWidget],
) -> None:
    """Typing before existing live text should not paint a stale insertion overlay."""

    box = show_prompt_editor(
        widgets,
        text="alpha omega",
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    cursor_position = len("alpha ")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "x")

    assert box.toPlainText() == "alpha xomega"
    assert valid_transient_insertion_overlay(surface) is None
    assert surface.has_stale_projection_geometry() is False


def test_projection_surface_middle_typing_invalidates_backing_fill(
    widgets: list[QWidget],
) -> None:
    """Incremental middle typing should request host-owned background repaint."""

    box = show_prompt_editor(
        widgets,
        text="alpha omega",
        width=360,
    )
    surface = surface_for(box)
    invalidated_rects: list[QRect] = []
    surface.backingFillInvalidated.connect(invalidated_rects.append)
    cursor_position = len("alpha ")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "x")

    assert box.toPlainText() == "alpha xomega"
    assert invalidated_rects
    assert all(not rect.isEmpty() for rect in invalidated_rects)


def test_projection_surface_wrapped_visual_line_suffix_typing_uses_authoritative_geometry(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typing before wrapped text should not use stale overlay geometry."""

    box = show_prompt_editor(
        widgets,
        text="alpha beta gamma delta epsilon zeta eta theta omega",
        width=150,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    text = box.toPlainText()
    cursor_position = next(
        position
        for position in range(len(text))
        if cast(Any, surface)._layout.source_position_at_visual_line_content_end(
            position
        )
        and text[position] not in {"\n", "\r"}
    )
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "xy")

    overlay = valid_transient_insertion_overlay(surface)
    assert overlay is None
    assert box.toPlainText() == f"{text[:cursor_position]}xy{text[cursor_position:]}"
    flush_semantic_refresh(box)

    if surface.has_pending_projection_update():
        flush_projection_update_scheduler(surface)
        process_events(ensure_qapp())

    assert rebuild_count <= 1
    assert surface.has_stale_projection_geometry() is False


def test_projection_surface_repeated_backspace_publishes_real_layout(
    widgets: list[QWidget],
) -> None:
    """Repeated plain backspace should not hide removed committed characters."""

    box = show_prompt_editor(
        widgets,
        text="alpha",
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    QTest.keyClick(box, Qt.Key.Key_Backspace)

    overlay = _valid_transient_deletion_overlay(surface)
    assert box.toPlainText() == "alp"
    assert overlay is None
    assert cast(Any, surface)._transient_deletion_visible_region() is None
    assert surface.has_stale_projection_geometry() is False


def test_projection_surface_fallback_backspace_rebuilds_without_deletion_overlay(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backspace should rebuild safely when no deletion overlay can be created."""

    box = show_prompt_editor(
        widgets,
        text="alpha beta",
        width=360,
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
    monkeypatch.setattr(
        cast(Any, surface)._source_change_applier,
        "_transient_single_character_deletion_overlay",
        lambda *, start, end, source_revision: None,
    )
    monkeypatch.setattr(
        cast(Any, surface)._incremental_apply_controller,
        "try_apply_fast_trailing_plain_delete_projection",
        lambda **_kwargs: False,
    )
    monkeypatch.setattr(
        cast(Any, surface)._incremental_apply_controller,
        "try_apply_fast_trailing_newline_delete_projection",
        lambda **_kwargs: False,
    )
    monkeypatch.setattr(
        cast(Any, surface)._incremental_apply_controller,
        "try_apply_incremental_plain_text_projection",
        lambda **_kwargs: PromptProjectionPlainTextApplyStatus.REJECTED,
    )
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    first_overlay = _valid_transient_deletion_overlay(surface)
    QTest.keyClick(box, Qt.Key.Key_Backspace)
    second_overlay = _valid_transient_deletion_overlay(surface)

    assert box.toPlainText() == "alpha be"
    assert first_overlay is None
    assert second_overlay is None
    assert cast(Any, surface)._transient_deletion_visible_region() is None
    assert surface.has_pending_projection_update() is False
    assert surface.has_stale_projection_geometry() is False
    assert rebuild_count == 2


def test_projection_surface_backspace_newline_uses_incremental_layout(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting a middle hard line break should publish authoritative geometry."""

    box = show_prompt_editor(
        widgets,
        text="alpha\nbeta",
        width=360,
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
    cursor_position = len("alpha\n")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0
    previous_line_count = cast(Any, surface)._layout.line_count()  # noqa: SLF001

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "alphabeta"
    assert rebuild_count == 0
    assert cast(Any, surface)._layout.line_count() == previous_line_count - 1  # noqa: SLF001
    assert cast(Any, surface)._caret_visibility_prompt_state_revision is None
    assert surface.has_stale_projection_geometry() is False
    flush_projection_update_scheduler(surface)


def test_projection_surface_middle_enter_uses_incremental_layout(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Middle Enter should publish authoritative line-break geometry."""

    box = show_prompt_editor(
        widgets,
        text="alphabeta",
        width=360,
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
    cursor_position = len("alpha")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0
    previous_line_count = cast(Any, surface)._layout.line_count()  # noqa: SLF001

    QTest.keyClick(box, Qt.Key.Key_Return)

    assert box.toPlainText() == "alpha\nbeta"
    assert rebuild_count == 0
    assert cast(Any, surface)._layout.line_count() == previous_line_count + 1  # noqa: SLF001
    assert surface.has_stale_projection_geometry() is False
    flush_projection_update_scheduler(surface)


def test_projection_surface_middle_enter_after_lora_keeps_caret_on_new_line(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enter after projected tokens should keep typed text on the inserted line."""

    text = "<lora:midna:1>\nalphabeta"
    box = show_prompt_editor(
        widgets,
        text=text,
        width=360,
        syntaxes=("emphasis", "wildcard", "lora"),
    )
    surface = surface_for(box)
    install_lora_wildcard_prompt_state(surface, text)
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len("<lora:midna:1>\nalpha")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClick(box, Qt.Key.Key_Return)
    QTest.keyClicks(box, "X")

    assert box.toPlainText() == "<lora:midna:1>\nalpha\nXbeta"
    assert rebuild_count == 0
    assert surface.has_stale_projection_geometry() is False
    flush_projection_update_scheduler(surface)


def test_projection_surface_middle_enter_with_inset_keeps_ordered_line_carets(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incremental Enter should keep line-local caret stops in source order."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alphabeta",
        width=360,
    )
    surface = surface_for(box)
    surface.set_source_line_content_left_inset(24.0)
    process_events(app)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len("alpha")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(app)

    first_line, second_line = _projection_lines(surface)[:2]
    first_line_positions = tuple(
        caret_stop.projection_position for caret_stop in first_line.caret_stops
    )
    content_left = surface._layout.document_margin + 24.0  # noqa: SLF001
    caret_rect = box.cursorRect()
    assert box.toPlainText() == "alpha\nbeta"
    assert rebuild_count == 0
    assert first_line_positions == tuple(sorted(first_line_positions))
    assert first_line.caret_stops[-1].projection_position == len("alpha")
    assert second_line.caret_stops[0].projection_position == len("alpha\n")
    assert caret_rect.x() == pytest.approx(content_left, abs=1.0)
    assert caret_rect.y() == pytest.approx(second_line.top, abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Left)
    process_events(app)
    caret_rect = box.cursorRect()
    assert surface.cursor_position == len("alpha")
    assert caret_rect.x() == pytest.approx(first_line.caret_stops[-1].rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(first_line.top, abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)
    caret_rect = box.cursorRect()
    assert surface.cursor_position == len("alpha\n")
    assert caret_rect.x() == pytest.approx(content_left, abs=1.0)
    assert caret_rect.y() == pytest.approx(second_line.top, abs=1.0)


def test_projection_surface_backspace_newline_after_lora_keeps_geometry_aligned(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting a newline after projected tokens should keep source/projection aligned."""

    text = "<lora:midna:1.00>\nalpha\nbeta"
    box = show_prompt_editor(
        widgets,
        text=text,
        width=360,
        syntaxes=("emphasis", "wildcard", "lora"),
    )
    surface = surface_for(box)
    install_lora_wildcard_prompt_state(surface, text)
    installed_text = box.toPlainText()
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = installed_text.index("\n", installed_text.index("alpha")) + 1
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    QTest.keyClicks(box, "X")

    lines = box.toPlainText().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("<lora:midna:")
    assert lines[1] == "alphaXbeta"
    assert rebuild_count == 0
    assert surface.has_stale_projection_geometry() is False
    flush_projection_update_scheduler(surface)


def test_projection_surface_trailing_enter_uses_incremental_newline_layout(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trailing Enter should append one layout row without full projection rebuild."""

    box = show_prompt_editor(
        widgets,
        text="alpha",
        width=360,
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
    previous_line_count = cast(Any, surface)._layout.line_count()  # noqa: SLF001

    QTest.keyClick(box, Qt.Key.Key_Return)

    assert box.toPlainText() == "alpha\n"
    assert rebuild_count == 0
    assert cast(Any, surface)._layout.line_count() == previous_line_count + 1  # noqa: SLF001
    assert surface.has_stale_projection_geometry() is False


def test_projection_surface_trailing_newline_backspace_uses_incremental_layout(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trailing newline backspace should drop one layout row without full rebuild."""

    box = show_prompt_editor(
        widgets,
        text="alpha\n",
        width=360,
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
    previous_line_count = cast(Any, surface)._layout.line_count()  # noqa: SLF001

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "alpha"
    assert rebuild_count == 0
    assert cast(Any, surface)._layout.line_count() == previous_line_count - 1  # noqa: SLF001
    assert surface.has_stale_projection_geometry() is False


def test_projection_surface_newline_backspace_flushes_pending_typing_before_delete(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Newline Backspace should not full-rebuild against stale typing geometry."""

    box = show_prompt_editor(
        widgets,
        text="alpha\nbeta",
        width=360,
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

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    rebuild_count = 0
    cursor_position = box.toPlainText().index("\n") + 1
    surface._cursor_state = PromptProjectionCaretState(source_position=cursor_position)  # noqa: SLF001
    surface._anchor_state = PromptProjectionCaretState(source_position=cursor_position)  # noqa: SLF001

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "alphabetax"
    assert rebuild_count == 0
    assert surface.has_stale_projection_geometry() is False
    assert surface.has_pending_projection_update() is False
