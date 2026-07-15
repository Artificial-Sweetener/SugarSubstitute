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

"""Characterize prompt-specific semantic editor behavior for Phase 2."""

from __future__ import annotations

from collections.abc import Iterator
import os
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.application.prompt_editor import (
    PromptAdjustWildcardTagAction,
    PromptMutationService,
    PromptSetEmphasisWeightAction,
    PromptSetLoraWeightAction,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompletePanel,
    PromptAutocompleteRow,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionDisplayMode,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptAutocompleteGateway,
    prompt_syntax_profile,
)
from tests.prompt_projection_test_helpers import (
    emphasis_controls_for,
    ensure_qapp,
    process_events,
    surface_for,
)
from tests.execution_test_helpers import immediate_prompt_task_executor_factory

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "phase 2 prompt editor characterization tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


class _Phase2WildcardGateway:
    """Return deterministic wildcard autocomplete and resolution data."""

    def __init__(
        self,
        *,
        suggestions_by_prefix: dict[str, tuple[PromptAutocompleteSuggestion, ...]],
        existing_identifiers: set[str] | None = None,
    ) -> None:
        """Store fixed wildcard rows for one test editor."""

        self._suggestions_by_prefix = dict(suggestions_by_prefix)
        self._existing_identifiers = existing_identifiers or set()
        self.search_calls: list[tuple[str, int]] = []

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return suggestions configured for one wildcard prefix."""

        self.search_calls.append((prefix, limit))
        return self._suggestions_by_prefix.get(prefix, ())

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Return found/missing state for each wildcard reference."""

        return tuple(
            PromptWildcardResolution(
                identifier=reference.identifier,
                wildcard_form=reference.wildcard_form,
                csv_column=reference.csv_column,
                exists=reference.identifier in self._existing_identifiers,
            )
            for reference in references
        )


@pytest.fixture()
def widgets() -> Iterator[list[QWidget]]:
    """Track widgets created during one Phase 2 characterization test."""

    created: list[QWidget] = []
    yield created
    app = ensure_qapp()
    for widget in reversed(created):
        widget.close()
        widget.deleteLater()
    process_events(app)


def _show_phase2_editor(
    widgets: list[QWidget],
    *,
    text: str = "",
    wildcard_gateway: _Phase2WildcardGateway | None = None,
    width: int = 360,
) -> PromptEditor:
    """Create a shown prompt editor with Phase 2 syntax features enabled."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(max(260, width + 48), 340)
    box = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=wildcard_gateway
        or _Phase2WildcardGateway(suggestions_by_prefix={}),
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


def _autocomplete_preview_text(box: PromptEditor) -> str:
    """Return the active projection-owned autocomplete preview suffix."""

    preview_state = surface_for(box)._session.autocomplete_preview  # noqa: SLF001
    if preview_state is None:
        return ""
    return preview_state.suffix_text


def _select_range(box: PromptEditor, start: int, end: int) -> None:
    """Select one raw source range in the prompt editor."""

    cursor = box.textCursor()
    cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(ensure_qapp())


def _token_for_kind(
    box: PromptEditor,
    kind: PromptProjectionTokenKind,
) -> PromptProjectionToken:
    """Return the first projected semantic token of one kind."""

    return next(
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind is kind
    )


def _autocomplete_panel(box: PromptEditor) -> PromptAutocompletePanel:
    """Return the live autocomplete panel owned by one prompt editor."""

    panel = getattr(box, "_autocomplete_panel")
    assert isinstance(panel, PromptAutocompletePanel)
    return panel


def _panel_rows(panel: PromptAutocompletePanel) -> list[PromptAutocompleteRow]:
    """Return direct autocomplete row widgets in render order."""

    rows = panel.findChildren(
        PromptAutocompleteRow,
        options=Qt.FindChildOption.FindDirectChildrenOnly,
    )
    return list(rows)


def _weight_rect_for(box: PromptEditor, token: PromptProjectionToken) -> QPoint:
    """Return the viewport-local center of one projected token weight number."""

    rect = surface_for(box).token_weight_text_rect(token)
    assert rect is not None
    return rect.center().toPoint()


def test_phase2_wildcard_autocomplete_preview_acceptance_and_undo(
    widgets: list[QWidget],
) -> None:
    """Wildcard autocomplete should preview the closing brace and accept as one source edit."""

    gateway = _Phase2WildcardGateway(
        suggestions_by_prefix={
            "art": (PromptAutocompleteSuggestion("artist", source_kind="wildcard"),)
        },
        existing_identifiers={"artist"},
    )
    box = _show_phase2_editor(widgets, wildcard_gateway=gateway)

    QTest.keyClicks(box, "{art")
    process_events(ensure_qapp(), cycles=8)

    assert gateway.search_calls[-1:] == [("art", 10)]
    assert box.toPlainText() == "{art"
    assert _autocomplete_preview_text(box) == "ist}"

    QTest.keyClick(box, Qt.Key.Key_Tab)
    process_events(ensure_qapp(), cycles=8)

    assert box.toPlainText() == "{artist}"
    assert _autocomplete_preview_text(box) == ""
    assert _token_for_kind(box, PromptProjectionTokenKind.WILDCARD).display_text == (
        "artist"
    )

    box.undo()
    process_events(ensure_qapp())

    assert box.toPlainText() == "{art"
    assert box.canRedo()


def test_phase2_wildcard_autocomplete_mouse_acceptance_restores_focus(
    widgets: list[QWidget],
) -> None:
    """Clicking a wildcard autocomplete row should accept it and keep editor focus."""

    gateway = _Phase2WildcardGateway(
        suggestions_by_prefix={
            "cha": (
                PromptAutocompleteSuggestion("character", source_kind="wildcard"),
                PromptAutocompleteSuggestion(
                    "character_outfit", source_kind="wildcard"
                ),
            )
        },
        existing_identifiers={"character_outfit"},
    )
    box = _show_phase2_editor(widgets, wildcard_gateway=gateway)

    QTest.keyClicks(box, "{cha")
    process_events(ensure_qapp(), cycles=8)
    panel = _autocomplete_panel(box)
    row = _panel_rows(panel)[1]

    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(ensure_qapp(), cycles=8)

    assert box.toPlainText() == "{character_outfit}"
    assert box.hasFocus()
    assert _autocomplete_preview_text(box) == ""
    assert panel.is_panel_visible() is False


def test_phase2_autocomplete_focus_loss_clears_panel_and_preview(
    widgets: list[QWidget],
) -> None:
    """Focus leaving the editor flow should clear autocomplete rows and ghost text."""

    gateway = _Phase2WildcardGateway(
        suggestions_by_prefix={
            "art": (PromptAutocompleteSuggestion("artist", source_kind="wildcard"),)
        },
        existing_identifiers={"artist"},
    )
    box = _show_phase2_editor(widgets, wildcard_gateway=gateway)

    QTest.keyClicks(box, "{art")
    process_events(ensure_qapp(), cycles=8)
    panel = _autocomplete_panel(box)
    assert panel.is_panel_visible()
    assert _autocomplete_preview_text(box) == "ist}"

    outside = QWidget()
    outside.show()
    widgets.append(outside)
    outside.setFocus()
    process_events(ensure_qapp(), cycles=4)
    cast(Any, box)._interaction_controller.handle_focus_out()  # noqa: SLF001
    process_events(ensure_qapp(), cycles=4)

    assert panel.is_panel_visible() is False
    assert _autocomplete_preview_text(box) == ""


def test_phase2_lora_chip_source_selection_copy_cut_paste_and_undo(
    widgets: list[QWidget],
) -> None:
    """LoRA chips should preserve raw source ranges for clipboard and undo commands."""

    app = ensure_qapp()
    source = "alpha, <lora:demo:0.80>, beta"
    box = _show_phase2_editor(widgets, text=source)
    token = _token_for_kind(box, PromptProjectionTokenKind.LORA)

    _select_range(box, token.source_start, token.source_end)
    box.copy()
    assert QApplication.clipboard().text() == "<lora:demo:0.80>"
    assert box.toPlainText() == source

    box.cut()
    process_events(app)
    assert box.toPlainText() == "alpha, , beta"

    box.undo()
    process_events(app)
    assert box.toPlainText() == source
    assert _token_for_kind(box, PromptProjectionTokenKind.LORA).display_text == "demo"

    _select_range(box, len(source), len(source))
    QApplication.clipboard().setText("<lora:demo:0.80>")
    box.paste()
    process_events(app)

    assert box.toPlainText() == source + "<lora:demo:0.80>"
    tokens = [
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    ]
    assert [token.display_text for token in tokens] == ["demo", "demo"]

    box.undo()
    process_events(app)

    assert box.toPlainText() == source
    assert _token_for_kind(box, PromptProjectionTokenKind.LORA).display_text == "demo"


def test_phase2_lora_exact_weight_edit_ui_commits_and_undoes(
    widgets: list[QWidget],
) -> None:
    """The token-weight UI should commit exact LoRA weights through the editor stack."""

    box = _show_phase2_editor(widgets, text="<lora:demo:0.80>")
    token = _token_for_kind(box, PromptProjectionTokenKind.LORA)
    weight_point = _weight_rect_for(box, token)

    QTest.mouseClick(box.viewport(), Qt.MouseButton.LeftButton, pos=weight_point)
    process_events(ensure_qapp(), cycles=2)
    QTest.mouseClick(box.viewport(), Qt.MouseButton.LeftButton, pos=weight_point)
    process_events(ensure_qapp(), cycles=4)

    edit_token = surface_for(box).exact_weight_edit_token()
    assert edit_token is not None
    assert edit_token.kind is PromptProjectionTokenKind.LORA
    assert edit_token.editing_value_text == "0.80"

    QTest.keyClicks(box, "0.65")
    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(ensure_qapp(), cycles=6)

    assert box.toPlainText() == "<lora:demo:0.65>"
    assert surface_for(box).exact_weight_edit_token() is None

    box.undo()
    process_events(ensure_qapp())

    assert box.toPlainText() == "<lora:demo:0.80>"


def test_phase2_lora_weight_controls_hide_in_raw_mode(
    widgets: list[QWidget],
) -> None:
    """Visible LoRA token controls should clear when projected rendering is disabled."""

    box = _show_phase2_editor(widgets, text="<lora:demo:0.80>")
    controls = emphasis_controls_for(box)
    token = _token_for_kind(box, PromptProjectionTokenKind.LORA)
    anchor_rect = surface_for(box).token_anchor_rect(token)
    assert anchor_rect is not None

    QTest.mouseMove(box.viewport(), anchor_rect.center().toPoint())
    process_events(ensure_qapp(), cycles=6)
    controls.refresh_geometry()
    process_events(ensure_qapp(), cycles=4)

    assert controls.visible_token is not None
    assert controls.visible_token.kind is PromptProjectionTokenKind.LORA

    box.setDisplayMode(PromptProjectionDisplayMode.RAW)
    process_events(ensure_qapp(), cycles=6)
    controls.refresh_geometry()
    process_events(ensure_qapp(), cycles=4)

    assert controls.visible_token is None
    assert controls.increase_rect is None
    assert controls.decrease_rect is None


def test_phase2_semantic_weight_mutations_target_each_token_kind(
    widgets: list[QWidget],
) -> None:
    """Emphasis, LoRA, and wildcard weight actions should mutate only their target token."""

    source = "(cat:1.05), <lora:demo:0.80>, {artist|1}"
    box = _show_phase2_editor(
        widgets,
        text=source,
        wildcard_gateway=_Phase2WildcardGateway(
            suggestions_by_prefix={},
            existing_identifiers={"artist"},
        ),
    )
    service = PromptMutationService()

    emphasis = _token_for_kind(box, PromptProjectionTokenKind.EMPHASIS)
    emphasis_mutation = service.apply_syntax_action(
        box.toPlainText(),
        PromptSetEmphasisWeightAction(
            outer_start=emphasis.source_start,
            outer_end=emphasis.source_end,
            weight=1.25,
        ),
    )
    assert emphasis_mutation is not None
    assert emphasis_mutation.text == "(cat:1.25), <lora:demo:0.80>, {artist|1}"

    lora = _token_for_kind(box, PromptProjectionTokenKind.LORA)
    lora_mutation = service.apply_syntax_action(
        box.toPlainText(),
        PromptSetLoraWeightAction(
            outer_start=lora.source_start,
            outer_end=lora.source_end,
            weight=0.65,
        ),
    )
    assert lora_mutation is not None
    assert lora_mutation.text == "(cat:1.05), <lora:demo:0.65>, {artist|1}"

    wildcard = _token_for_kind(box, PromptProjectionTokenKind.WILDCARD)
    wildcard_mutation = service.apply_syntax_action(
        box.toPlainText(),
        PromptAdjustWildcardTagAction(
            outer_start=wildcard.source_start,
            outer_end=wildcard.source_end,
            current_display_tag="1",
            delta=1,
        ),
    )
    assert wildcard_mutation is not None
    assert wildcard_mutation.text == "(cat:1.05), <lora:demo:0.80>, {artist|2}"


def test_phase2_mixed_semantic_tokens_project_current_labels_and_weight_text(
    widgets: list[QWidget],
) -> None:
    """Mixed semantic chips should expose current labels, weight text, and source detail."""

    box = _show_phase2_editor(
        widgets,
        text="(cat:1.05), <lora:demo:0.80>, {artist|2}",
        wildcard_gateway=_Phase2WildcardGateway(
            suggestions_by_prefix={},
            existing_identifiers={"artist"},
        ),
    )

    emphasis = _token_for_kind(box, PromptProjectionTokenKind.EMPHASIS)
    lora = _token_for_kind(box, PromptProjectionTokenKind.LORA)
    wildcard = _token_for_kind(box, PromptProjectionTokenKind.WILDCARD)

    assert emphasis.display_text == "cat"
    assert emphasis.value_text == "1.05"
    assert lora.display_text == "demo"
    assert lora.value_text == "0.80"
    assert lora.detail_text == "demo"
    assert wildcard.display_text == "artist"
    assert wildcard.wildcard_display_tag == "2"
    assert wildcard.wildcard_tag_is_explicit is True
    assert wildcard.wildcard_tag_is_numeric is True
