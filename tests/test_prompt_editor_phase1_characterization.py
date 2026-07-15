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

"""Characterize foundational prompt editor text, history, and display contracts."""

from __future__ import annotations

from collections.abc import Iterator
import os
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptAutocompleteSuggestion,
    PromptWildcardResolution,
)
from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptDocumentView,
    PromptLineDropTarget,
    PromptMutationService,
    PromptSetEmphasisWeightAction,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionDisplayMode,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.paint_state import (
    PromptProjectionPaintStateBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.update_scheduler import (
    PendingProjectionUpdate,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptWildcardCatalogGateway,
    RecordingPromptAutocompleteGateway,
    prompt_syntax_profile,
)
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.execution_test_helpers import immediate_prompt_task_executor_factory

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "phase 1 prompt editor characterization tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


@pytest.fixture()
def widgets() -> Iterator[list[QWidget]]:
    """Track widgets created during one prompt editor characterization test."""

    created: list[QWidget] = []
    yield created
    app = ensure_qapp()
    for widget in reversed(created):
        widget.close()
        widget.deleteLater()
    process_events(app)


class _SignalCounts:
    """Count public prompt editor signal emissions during one test action."""

    def __init__(self, box: PromptEditor) -> None:
        """Connect to prompt editor signals exposed by the public widget facade."""

        self.text_changed = 0
        self.cursor_changed = 0
        self.undo_available: list[bool] = []
        self.redo_available: list[bool] = []
        box.textChanged.connect(self._record_text_changed)
        box.cursorPositionChanged.connect(self._record_cursor_changed)
        box.undoAvailableChanged.connect(self.undo_available.append)
        box.redoAvailableChanged.connect(self.redo_available.append)

    def _record_text_changed(self) -> None:
        """Record one textChanged emission."""

        self.text_changed += 1

    def _record_cursor_changed(self) -> None:
        """Record one cursorPositionChanged emission."""

        self.cursor_changed += 1


def _set_cursor_position(box: PromptEditor, position: int) -> None:
    """Move the prompt editor cursor to one raw source position."""

    cursor = box.textCursor()
    cursor.setPosition(position, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)


def _select_range(box: PromptEditor, start: int, end: int) -> None:
    """Select one raw source range in the prompt editor."""

    cursor = box.textCursor()
    cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)


def _selected_text(box: PromptEditor) -> str:
    """Return the editor's selected raw source text."""

    return cast(str, box.textCursor().selectedText())


def _flush_editor_projection(box: PromptEditor) -> None:
    """Synchronize deferred semantic and projection work for deterministic assertions."""

    app = ensure_qapp()
    cast(Any, box)._interaction_controller.flush_pending_semantic_refresh(  # noqa: SLF001
        reason="test"
    )
    surface = surface_for(box)
    if surface.has_pending_projection_update():
        surface.flush_pending_projection_update(reason="test")
    process_events(app)


def _finish_pending_key_edit_block(box: PromptEditor) -> None:
    """Commit pending key-owned undo groups before checking stack availability."""

    cast(Any, box)._edit_controller.finish_pending_key_edit_block(reason="test")  # noqa: SLF001
    process_events(ensure_qapp())


def _show_prompt_editor_with_autocomplete(
    widgets: list[QWidget],
    *,
    text: str,
    prompt_autocomplete_gateway: PromptAutocompleteGateway,
    width: int = 280,
) -> PromptEditor:
    """Create one shown prompt editor with a deterministic autocomplete gateway."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(max(240, width + 48), 340)
    box = PromptEditor(
        host,
        prompt_autocomplete_gateway=prompt_autocomplete_gateway,
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard", "lora"),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    box.setGeometry(20, 20, width, box.minimumEditorHeight())
    host.show()
    host.activateWindow()
    box.show()
    box.setFocus()
    box.setPlainText(text)
    process_events(app)
    widgets.extend([host, box])
    return box


def _prompt_state_for_text(
    text: str,
) -> tuple[PromptDocumentView, PromptSyntaxRenderPlan]:
    """Build prompt document and syntax render state for full-source replacements."""

    document_view = PromptDocumentService().build_document_view(text)
    render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({})
    ).build_render_plan(
        document_view,
        prompt_syntax_profile("emphasis", "wildcard", "lora"),
    )
    return document_view, render_plan


def _projection_signature(
    box: PromptEditor,
) -> tuple[str, tuple[tuple[object, ...], ...]]:
    """Return deterministic projection text and token metadata for parity assertions."""

    document = surface_for(box).projection_document()
    return (
        document.projection_text,
        tuple(
            (
                token.kind,
                token.source_start,
                token.source_end,
                token.display_text,
                token.value_text,
                token.content_start,
                token.content_end,
                token.exists,
            )
            for token in document.tokens
        ),
    )


def _delay_projection_update_scheduler(box: PromptEditor) -> None:
    """Make pending projection scheduler work observable without sleeping."""

    scheduler = surface_for(box)._projection_freshness_controller.update_scheduler  # noqa: SLF001
    scheduler._fixed_interval_ms = 1000  # noqa: SLF001
    scheduler._interval_ms = 1000  # noqa: SLF001
    scheduler._timer.setInterval(1000)  # noqa: SLF001


def test_phase1_to_plain_text_returns_exact_current_source_text(
    widgets: list[QWidget],
) -> None:
    """toPlainText should expose raw source, not projected display text."""

    source = (
        r"plain \(literal\), <lora:demo/model:0.8>, {artist:2}, "
        "(cat:1.10)\nsecond line"
    )
    box = show_prompt_editor(
        widgets,
        text="",
        width=360,
        syntaxes=("emphasis", "wildcard", "lora"),
    )

    box.setSourceText(source)
    process_events(ensure_qapp())

    assert box.toPlainText() == source
    assert box.textCursor().position() == len(source)
    assert not box.textCursor().hasSelection()


def test_phase1_set_plain_text_replaces_source_selection_and_signals(
    widgets: list[QWidget],
) -> None:
    """setPlainText should replace source and collapse selection at the new end."""

    box = show_prompt_editor(widgets, text="cat dog", width=240)
    box.replaceBaselineText("cat dog")
    _select_range(box, 4, 7)
    process_events(ensure_qapp())
    signals = _SignalCounts(box)

    box.setPlainText("bird")
    process_events(ensure_qapp())

    assert box.toPlainText() == "bird"
    assert box.textCursor().position() == 4
    assert box.textCursor().selectionStart() == 4
    assert box.textCursor().selectionEnd() == 4
    assert signals.text_changed == 1
    assert signals.cursor_changed >= 1
    assert box.canUndo()
    assert signals.undo_available[-1:] == [True]


def test_phase1_set_source_text_preserves_exact_unescaped_source_contract(
    widgets: list[QWidget],
) -> None:
    """setSourceText should preserve exact source syntax that storage ingestion normalizes."""

    box = show_prompt_editor(widgets, text="", width=240)

    box.setSourceText("literal (medium)")
    process_events(ensure_qapp())

    assert box.toPlainText() == "literal (medium)"
    assert box.textCursor().position() == len("literal (medium)")
    assert box.canUndo()


def test_phase1_typing_plain_text_updates_source_cursor_projection_and_signals(
    widgets: list[QWidget],
) -> None:
    """Plain typing should update source, cursor, projection text, and public signals."""

    box = show_prompt_editor(widgets, text="", width=240)
    signals = _SignalCounts(box)

    QTest.keyClicks(box, "cat")
    _finish_pending_key_edit_block(box)
    _flush_editor_projection(box)

    assert box.toPlainText() == "cat"
    assert box.textCursor().position() == 3
    assert not box.textCursor().hasSelection()
    assert surface_for(box).projection_document().projection_text == "cat"
    assert signals.text_changed == 3
    assert signals.cursor_changed == 3
    assert box.canUndo()


def test_phase1_typing_replaces_selected_source_range(
    widgets: list[QWidget],
) -> None:
    """Typing over a selection should replace only that raw source range."""

    box = show_prompt_editor(widgets, text="cat dog", width=240)
    _select_range(box, 4, 7)
    process_events(ensure_qapp())

    QTest.keyClicks(box, "bird")
    _flush_editor_projection(box)

    assert box.toPlainText() == "cat bird"
    assert box.textCursor().position() == 8
    assert box.textCursor().selectionStart() == 8
    assert box.textCursor().selectionEnd() == 8
    assert surface_for(box).projection_document().projection_text == "cat bird"


def test_phase1_multiline_blank_line_join_and_split_are_source_backed(
    widgets: list[QWidget],
) -> None:
    """Line split, blank-line insertion, and line join should preserve source cursor state."""

    box = show_prompt_editor(widgets, text="catdog", width=260)
    _set_cursor_position(box, 3)
    process_events(ensure_qapp())

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(ensure_qapp())
    assert box.toPlainText() == "cat\ndog"
    assert box.textCursor().position() == 4

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(ensure_qapp())
    assert box.toPlainText() == "cat\n\ndog"
    assert box.textCursor().position() == 5

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    process_events(ensure_qapp())
    assert box.toPlainText() == "cat\ndog"
    assert box.textCursor().position() == 4


def test_phase1_soft_wrap_does_not_insert_source_newline(
    widgets: list[QWidget],
) -> None:
    """Visual wrapping should not create raw source newline characters."""

    text = " ".join(["verylongpromptsegment"] * 6)
    box = show_prompt_editor(widgets, text="", width=150)

    QTest.keyClicks(box, text)
    _flush_editor_projection(box)

    assert box.toPlainText() == text
    assert "\n" not in box.toPlainText()
    assert surface_for(box).projection_document().projection_text == text
    assert surface_for(box).content_height() > box.lineHeight()


def test_phase1_paste_and_cut_copy_select_all_are_source_backed(
    widgets: list[QWidget],
) -> None:
    """Clipboard commands should operate on raw prompt source ranges."""

    app = ensure_qapp()
    box = show_prompt_editor(widgets, text=r"cat, \(literal\), dog", width=280)
    _select_range(box, 5, 16)
    process_events(app)

    box.copy()
    assert QApplication.clipboard().text() == r"\(literal\)"
    assert box.toPlainText() == r"cat, \(literal\), dog"

    box.cut()
    process_events(app)
    assert QApplication.clipboard().text() == r"\(literal\)"
    assert box.toPlainText() == "cat, , dog"
    assert box.textCursor().position() == 5

    QApplication.clipboard().setText("bird")
    box.paste()
    process_events(app)
    assert box.toPlainText() == "cat, bird, dog"
    assert box.textCursor().position() == 9

    cast(Any, box).selectAll()
    process_events(app)
    assert _selected_text(box) == "cat, bird, dog"


def test_phase1_read_only_blocks_mutation_but_preserves_navigation_and_selection(
    widgets: list[QWidget],
) -> None:
    """Read-only mode should block edits while allowing source-backed navigation."""

    app = ensure_qapp()
    box = show_prompt_editor(widgets, text="cat dog", width=240)
    box.replaceBaselineText("cat dog")
    box.setReadOnly(True)
    _set_cursor_position(box, 3)
    process_events(app)

    QTest.keyClicks(box, "!")
    QTest.keyClick(box, Qt.Key.Key_Backspace)
    QApplication.clipboard().setText(" paste")
    box.paste()
    process_events(app)
    assert box.toPlainText() == "cat dog"

    cursor = box.textCursor()
    cursor.setPosition(0, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(3, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    assert box.toPlainText() == "cat dog"
    assert _selected_text(box) == "cat"
    assert not box.canUndo()


def test_phase1_core_signal_emissions_cover_undo_redo_and_blocked_edits(
    widgets: list[QWidget],
) -> None:
    """Public editor signals should follow source mutations and stay quiet for blocked edits."""

    app = ensure_qapp()
    box = show_prompt_editor(widgets, text="", width=240)
    signals = _SignalCounts(box)

    QTest.keyClicks(box, "cat")
    _finish_pending_key_edit_block(box)
    assert box.toPlainText() == "cat"
    assert signals.text_changed == 3
    assert signals.cursor_changed == 3
    assert signals.undo_available[-1:] == [True]

    before_noop_move = (
        signals.text_changed,
        signals.cursor_changed,
        tuple(signals.undo_available),
        tuple(signals.redo_available),
    )
    _set_cursor_position(box, box.textCursor().position())
    process_events(app)
    assert (
        signals.text_changed,
        signals.cursor_changed,
        tuple(signals.undo_available),
        tuple(signals.redo_available),
    ) == before_noop_move

    box.undo()
    process_events(app)
    assert box.toPlainText() == ""
    assert box.canRedo()
    assert signals.redo_available[-1:] == [True]

    box.redo()
    process_events(app)
    assert box.toPlainText() == "cat"
    assert not box.canRedo()
    assert signals.redo_available[-1:] == [False]

    box.setReadOnly(True)
    text_count_before_blocked_edit = signals.text_changed
    QTest.keyClicks(box, "!")
    QApplication.clipboard().setText(" paste")
    box.paste()
    process_events(app)

    assert box.toPlainText() == "cat"
    assert signals.text_changed == text_count_before_blocked_edit


def test_phase1_plain_replacement_after_undo_clears_redo_stack(
    widgets: list[QWidget],
) -> None:
    """A new edit after undo should clear redo while preserving source-backed cursor state."""

    box = show_prompt_editor(widgets, text="", width=240)
    QTest.keyClicks(box, "cat")
    process_events(ensure_qapp())

    box.undo()
    process_events(ensure_qapp())
    assert box.toPlainText() == ""
    assert box.canRedo()

    QTest.keyClicks(box, "dog")
    _finish_pending_key_edit_block(box)

    assert box.toPlainText() == "dog"
    assert box.textCursor().position() == 3
    assert box.canUndo()
    assert not box.canRedo()


def test_phase1_autocomplete_acceptance_is_one_undoable_source_step(
    widgets: list[QWidget],
) -> None:
    """Accepting a prompt completion should replace the query as one undo step."""

    gateway = RecordingPromptAutocompleteGateway(
        {
            "1g": (
                PromptAutocompleteSuggestion("1girl", 5_889_398),
                PromptAutocompleteSuggestion("1girls", 3_424),
            )
        }
    )
    box = _show_prompt_editor_with_autocomplete(
        widgets,
        text="",
        prompt_autocomplete_gateway=gateway,
    )

    QTest.keyClicks(box, "1g")
    process_events(ensure_qapp(), cycles=8)
    QTest.keyClick(box, Qt.Key.Key_Tab)
    process_events(ensure_qapp(), cycles=8)
    _finish_pending_key_edit_block(box)

    assert gateway.calls[-1:] == [("1g", 10)]
    assert box.toPlainText() == "1girl, "
    assert box.textCursor().position() == len("1girl, ")
    assert box.canUndo()

    box.undo()
    process_events(ensure_qapp())
    assert box.toPlainText() == "1g"
    assert box.canUndo()
    assert box.canRedo()

    box.redo()
    process_events(ensure_qapp())
    assert box.toPlainText() == "1girl, "
    assert box.canUndo()
    assert not box.canRedo()


def test_phase1_weight_change_is_one_undoable_source_step(
    widgets: list[QWidget],
) -> None:
    """Prompt syntax weight mutations should round-trip through undo and redo."""

    source = "(cat:1.05), tail"
    box = show_prompt_editor(
        widgets,
        text=source,
        width=260,
        syntaxes=("emphasis", "wildcard", "lora"),
    )
    box.replaceBaselineSourceText(source)
    action = PromptSetEmphasisWeightAction(
        outer_start=0,
        outer_end=len("(cat:1.05)"),
        weight=1.25,
    )

    cast(Any, box)._interaction_controller.apply_syntax_action(  # noqa: SLF001
        action
    )
    process_events(ensure_qapp())

    assert box.toPlainText() == "(cat:1.25), tail"
    assert box.canUndo()

    box.undo()
    process_events(ensure_qapp())
    assert box.toPlainText() == source
    assert not box.canUndo()
    assert box.canRedo()

    box.redo()
    process_events(ensure_qapp())
    assert box.toPlainText() == "(cat:1.25), tail"
    assert box.canUndo()
    assert not box.canRedo()


def test_phase1_reorder_commit_is_one_undoable_source_step(
    widgets: list[QWidget],
) -> None:
    """Committing a chip reorder should preserve its prompt state through undo and redo."""

    source = "alpha, beta, gamma"
    box = show_prompt_editor(widgets, text=source, width=280)
    box.replaceBaselineSourceText(source)
    mutation = PromptMutationService().reorder_chips(
        source,
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({})
    ).build_render_plan(
        mutation.document_view,
        prompt_syntax_profile("emphasis", "wildcard", "lora"),
    )

    box.replace_document_text_with_prompt_state(
        mutation.text,
        document_view=mutation.document_view,
        render_plan=render_plan,
    )
    process_events(ensure_qapp())

    assert box.toPlainText() == "beta, alpha, gamma"
    assert box.textCursor().position() == len("beta, alpha, gamma")

    box.undo()
    process_events(ensure_qapp())
    assert box.toPlainText() == source
    assert not box.canUndo()
    assert box.canRedo()

    box.redo()
    process_events(ensure_qapp())
    assert box.toPlainText() == "beta, alpha, gamma"
    assert box.textCursor().position() == len("beta, alpha, gamma")
    assert box.canUndo()
    assert not box.canRedo()


def test_phase1_programmatic_replacement_is_one_undoable_source_step(
    widgets: list[QWidget],
) -> None:
    """replace_document_text should be undoable as one full-source replacement."""

    box = show_prompt_editor(widgets, text="cat", width=240)
    box.replaceBaselineText("cat")

    box.replace_document_text("cat, dog")
    process_events(ensure_qapp())
    assert box.toPlainText() == "cat, dog"

    box.undo()
    process_events(ensure_qapp())
    assert box.toPlainText() == "cat"
    assert not box.canUndo()
    assert box.canRedo()

    box.redo()
    process_events(ensure_qapp())
    assert box.toPlainText() == "cat, dog"
    assert box.canUndo()
    assert not box.canRedo()


def test_phase1_undo_redo_restore_cursor_selection_display_and_projection_state(
    widgets: list[QWidget],
) -> None:
    """Undo and redo should restore editor state around one full-source replacement."""

    source = "(cat:1.05), alpha"
    replacement = "(dog:1.25), beta"
    box = show_prompt_editor(widgets, text=source, width=280)
    box.replaceBaselineSourceText(source)
    box.setDisplayMode(PromptProjectionDisplayMode.RAW)
    _select_range(box, 1, 4)
    process_events(ensure_qapp())
    document_view, render_plan = _prompt_state_for_text(replacement)

    box.replace_document_text_with_prompt_state(
        replacement,
        document_view=document_view,
        render_plan=render_plan,
    )
    process_events(ensure_qapp())

    assert box.toPlainText() == replacement
    assert box.displayMode() is PromptProjectionDisplayMode.RAW
    assert surface_for(box).projection_document().projection_text == replacement

    box.undo()
    process_events(ensure_qapp())
    assert box.toPlainText() == source
    assert box.displayMode() is PromptProjectionDisplayMode.RAW
    assert box.textCursor().selectionStart() == 1
    assert box.textCursor().selectionEnd() == 4
    assert surface_for(box).projection_document().projection_text == source
    assert not box.canUndo()
    assert box.canRedo()

    box.redo()
    process_events(ensure_qapp())
    assert box.toPlainText() == replacement
    assert box.displayMode() is PromptProjectionDisplayMode.RAW
    assert surface_for(box).projection_document().projection_text == replacement
    assert box.canUndo()
    assert not box.canRedo()


def test_phase1_nested_edit_block_grouping_matches_current_behavior(
    widgets: list[QWidget],
) -> None:
    """Nested edit blocks should commit all enclosed source replacements as one undo step."""

    box = show_prompt_editor(widgets, text="cat", width=240)
    box.replaceBaselineSourceText("cat")
    edit_controller = cast(Any, box)._edit_controller  # noqa: SLF001

    edit_controller.begin_edit_block()
    try:
        edit_controller.begin_edit_block()
        try:
            box.replace_document_text("cat, dog")
            box.replace_document_text("cat, dog, bird")
        finally:
            edit_controller.end_edit_block()
    finally:
        edit_controller.end_edit_block()
    process_events(ensure_qapp())

    assert box.toPlainText() == "cat, dog, bird"

    box.undo()
    process_events(ensure_qapp())
    assert box.toPlainText() == "cat"
    assert not box.canUndo()
    assert box.canRedo()


def test_phase1_projected_mode_collapses_mixed_prompt_tokens_without_source_mutation(
    widgets: list[QWidget],
) -> None:
    """Projected mode should decorate mixed prompt syntax while preserving raw source."""

    source = "plain, <lora:demo:0.8>, {artist}, (cat:1.10)"
    wildcard_gateway = StaticPromptWildcardCatalogGateway(
        {
            ("artist", "simple", None): PromptWildcardResolution(
                identifier="artist",
                wildcard_form="simple",
                exists=True,
            )
        }
    )
    box = show_prompt_editor(
        widgets,
        text="",
        width=380,
        wildcard_gateway=wildcard_gateway,
        syntaxes=("emphasis", "wildcard", "lora"),
    )
    box.setSourceText(source)
    _flush_editor_projection(box)

    assert box.displayMode() is PromptProjectionDisplayMode.PROJECTED
    assert box.toPlainText() == source
    token_kinds = {
        token.kind for token in surface_for(box).projection_document().tokens
    }
    assert PromptProjectionTokenKind.LORA in token_kinds
    assert PromptProjectionTokenKind.WILDCARD in token_kinds
    assert PromptProjectionTokenKind.EMPHASIS in token_kinds

    box.setDisplayMode(PromptProjectionDisplayMode.RAW)
    process_events(ensure_qapp())
    assert box.toPlainText() == source
    assert surface_for(box).projection_document().projection_text == source


def test_phase1_projected_tokens_expose_source_ranges_and_visible_content(
    widgets: list[QWidget],
) -> None:
    """Projected semantic tokens should keep source ranges tied to visible content."""

    source = "plain, <lora:demo:0.8>, {artist}, (cat:1.10)"
    wildcard_gateway = StaticPromptWildcardCatalogGateway(
        {
            ("artist", "simple", None): PromptWildcardResolution(
                identifier="artist",
                wildcard_form="simple",
                exists=True,
            )
        }
    )
    box = show_prompt_editor(
        widgets,
        text="",
        width=420,
        wildcard_gateway=wildcard_gateway,
        syntaxes=("emphasis", "wildcard", "lora"),
    )
    box.setSourceText(source)
    _flush_editor_projection(box)
    tokens = surface_for(box).projection_document().tokens
    by_kind = {token.kind: token for token in tokens}

    lora = by_kind[PromptProjectionTokenKind.LORA]
    wildcard = by_kind[PromptProjectionTokenKind.WILDCARD]
    emphasis = by_kind[PromptProjectionTokenKind.EMPHASIS]

    assert source[lora.source_start : lora.source_end] == "<lora:demo:0.8>"
    assert lora.display_text == "demo"
    assert lora.value_text == "0.8"
    assert source[wildcard.source_start : wildcard.source_end] == "{artist}"
    assert wildcard.display_text == "artist"
    assert source[emphasis.source_start : emphasis.source_end] == "(cat:1.10)"
    assert emphasis.display_text == "cat"
    assert emphasis.value_text == "1.10"
    assert emphasis.content_range == (
        source.index("cat"),
        source.index("cat") + len("cat"),
    )


def test_phase1_active_token_state_reuses_projection_caret_mapping(
    widgets: list[QWidget],
) -> None:
    """Active-token repaint state should not rebuild projection caret indexes."""

    box = show_prompt_editor(widgets, text="(cat:1.05), suffix", width=260)
    surface = surface_for(box)
    document = surface.projection_document()
    token = next(
        token
        for token in document.tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )

    paint_state = PromptProjectionPaintStateBuilder().build(
        document,
        session=cast(Any, surface)._session,
        active_span_range=(token.source_start, token.source_end),
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )
    cast(Any, surface)._layout.set_projection_paint_state(paint_state)
    active_token = cast(Any, surface)._layout.effective_token_for_paint(token.token_id)

    assert cast(Any, surface)._layout.projection_document is document
    assert (
        cast(Any, surface)._layout.projection_document.caret_map is document.caret_map
    )
    assert active_token is not None
    assert active_token.active is True
    assert any(
        cast(Any, surface)._layout.effective_run_for_paint(run.run_id).active
        for run in document.runs
        if run.token_id == token.token_id
    )


def test_phase1_stale_prompt_state_update_does_not_replace_newer_source(
    widgets: list[QWidget],
) -> None:
    """Deferred prompt-state updates should be ignored after the source revision moves on."""

    box = show_prompt_editor(widgets, text="alpha", width=240)
    surface = surface_for(box)
    _delay_projection_update_scheduler(box)
    _set_cursor_position(box, len("alpha"))
    process_events(ensure_qapp())
    pending_document_view, pending_render_plan = _prompt_state_for_text("alpha")
    source_revision = cast(Any, surface)._source_revision
    cast(Any, surface)._projection_freshness_controller.update_scheduler.schedule(
        PendingProjectionUpdate.create(
            document_view=pending_document_view,
            render_plan=pending_render_plan,
            reason="test",
            source_revision=source_revision,
        )
    )

    QTest.keyClicks(box, " beta gamma")
    assert box.toPlainText() == "alpha beta gamma"

    cast(Any, surface)._projection_freshness_controller.update_scheduler.flush_now(
        reason="test"
    )
    process_events(ensure_qapp())

    assert box.toPlainText() == "alpha beta gamma"
    assert surface.projection_document().projection_text != "alpha"


def test_phase1_incremental_projection_matches_full_rebuild_for_mixed_prompt(
    widgets: list[QWidget],
) -> None:
    """Incremental source edits should converge on the same projection as a fresh editor."""

    source = "plain, <lora:demo:0.8>, {artist}, (cat:1.10)"
    final_source = "plain, <lora:demo:0.8>, {artist}, (cat:1.10), tail"
    wildcard_gateway = StaticPromptWildcardCatalogGateway(
        {
            ("artist", "simple", None): PromptWildcardResolution(
                identifier="artist",
                wildcard_form="simple",
                exists=True,
            )
        }
    )
    edited_box = show_prompt_editor(
        widgets,
        text="",
        width=420,
        wildcard_gateway=wildcard_gateway,
        syntaxes=("emphasis", "wildcard", "lora"),
    )
    edited_box.setSourceText(source)
    _flush_editor_projection(edited_box)
    _set_cursor_position(edited_box, len(edited_box.toPlainText()))
    QTest.keyClicks(edited_box, ", tail")
    _flush_editor_projection(edited_box)

    rebuilt_box = show_prompt_editor(
        widgets,
        text="",
        width=420,
        wildcard_gateway=wildcard_gateway,
        syntaxes=("emphasis", "wildcard", "lora"),
    )
    rebuilt_box.setSourceText(final_source)
    _flush_editor_projection(rebuilt_box)

    assert edited_box.toPlainText() == final_source
    assert _projection_signature(edited_box) == _projection_signature(rebuilt_box)


def test_phase1_mode_switch_preserves_cursor_mapping_for_mixed_token_boundaries(
    widgets: list[QWidget],
) -> None:
    """Mode switches should preserve source cursor positions around projected tokens."""

    source = "plain, <lora:demo:0.8>, {artist}, (cat:1.10)"
    wildcard_gateway = StaticPromptWildcardCatalogGateway(
        {
            ("artist", "simple", None): PromptWildcardResolution(
                identifier="artist",
                wildcard_form="simple",
                exists=True,
            )
        }
    )
    box = show_prompt_editor(
        widgets,
        text="",
        width=380,
        wildcard_gateway=wildcard_gateway,
        syntaxes=("emphasis", "wildcard", "lora"),
    )
    box.setSourceText(source)
    _flush_editor_projection(box)
    positions = (
        source.index("<lora:"),
        source.index("{artist"),
        source.index("(cat") + 1,
        len(source),
    )

    for position in positions:
        _set_cursor_position(box, position)
        process_events(ensure_qapp())
        box.setDisplayMode(PromptProjectionDisplayMode.RAW)
        process_events(ensure_qapp())
        assert box.textCursor().position() == position
        box.setDisplayMode(PromptProjectionDisplayMode.PROJECTED)
        process_events(ensure_qapp())
        assert box.textCursor().position() == position
