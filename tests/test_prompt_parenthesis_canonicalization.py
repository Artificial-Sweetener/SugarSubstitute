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

"""Characterize tag-aware prompt parenthesis canonicalization and intent."""

from __future__ import annotations

import pytest

from substitute.application.ports import PromptTagLexiconSnapshot
from substitute.application.prompt_editor import PromptSourceNormalizationService
from substitute.application.prompt_editor.prompt_literal_parenthesis_normalizer import (
    PromptParenthesisTransitionKind,
    canonicalize_prompt_parentheses,
)
from substitute.infrastructure.persistence.file_prompt_autocomplete_gateway import (
    FilePromptAutocompleteGateway,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptCursorState,
    PromptEditingSession,
    PromptSourceEditOrigin,
    PromptUndoSnapshot,
)


def _undo_snapshot(session: PromptEditingSession[str]) -> PromptUndoSnapshot[str]:
    """Capture source intent alongside source and cursor state."""

    return PromptUndoSnapshot(
        source_text=session.source_text,
        cursor_state=session.cursor_state,
        parenthesis_intents=session.source_snapshot().parenthesis_intents,
        generated_emphases=session.source_snapshot().generated_emphases,
    )


def _session(source_text: str) -> PromptEditingSession[str]:
    """Build one editing session for parenthesis-intent tests."""

    return PromptEditingSession(
        source_text=source_text,
        source_revision=0,
        cursor_state=PromptCursorState(len(source_text), len(source_text)),
        max_undo_states=10,
        max_redo_states=10,
    )


def test_explicit_numeric_emphasis_has_no_magnitude_heuristic() -> None:
    """Preserve every parsed explicit numeric weight regardless of magnitude."""

    assert canonicalize_prompt_parentheses("(wide shot:6)").text == "(wide shot:6)"
    assert canonicalize_prompt_parentheses("(wide shot:1999)").text == (
        "(wide shot:1999)"
    )
    assert canonicalize_prompt_parentheses("(wide shot:0.01)").text == (
        "(wide shot:0.01)"
    )


def test_unknown_implicit_emphasis_is_stabilized_with_exact_nesting_weight() -> None:
    """Rewrite implicit ComfyUI nesting without losing deeper precision."""

    assert canonicalize_prompt_parentheses("(blue laces)").text == ("(blue laces:1.10)")
    assert canonicalize_prompt_parentheses("((blue laces))").text == (
        "(blue laces:1.21)"
    )
    assert canonicalize_prompt_parentheses("(((blue laces)))").text == (
        "(blue laces:1.331)"
    )


def test_known_tag_parentheses_are_escaped_from_prepared_snapshot() -> None:
    """Escape a literal only when exact prepared tag knowledge identifies it."""

    snapshot = PromptTagLexiconSnapshot(
        normalized_tags=frozenset({"vertin (reverse:1999)"})
    )
    service = PromptSourceNormalizationService(tag_snapshot=snapshot)

    assert service.normalize_for_paste("vertin (reverse:1999)").text == (
        r"vertin \(reverse:1999\)"
    )
    assert service.normalize_for_paste("unknown (reverse:1999)").text == (
        "unknown (reverse:1999.00)"
    )


def test_prepared_gateway_snapshot_never_loads_on_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep exact-tag reads on interactive paths free from asset I/O."""

    gateway = FilePromptAutocompleteGateway()

    def fail_load() -> object:
        raise AssertionError("prepared snapshot attempted asset I/O")

    monkeypatch.setattr(gateway, "_load_rows", fail_load)

    assert gateway.prepared_prompt_tag_snapshot().normalized_tags == frozenset()


def test_manual_unescape_is_preserved_until_complete_segment_replacement() -> None:
    """Keep user-authored escapement intent through later local edits."""

    source = r"\(blue laces\)"
    session = _session(source)
    normalizer = PromptSourceNormalizationService()
    first = session.replace_source_range(
        start=0,
        end=1,
        replacement_text="",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )
    closing_slash = first.next_snapshot.source_text.index(r"\)")
    session.replace_source_range(
        start=closing_slash,
        end=closing_slash + 1,
        replacement_text="",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )
    session.replace_source_range(
        start=len(session.source_text) - 1,
        end=len(session.source_text) - 1,
        replacement_text="!",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )

    assert session.source_text == "(blue laces!)"
    assert session.source_snapshot().parenthesis_intents

    session.replace_source_range(
        start=0,
        end=len(session.source_text),
        replacement_text="(fresh)",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.PASTE,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )

    assert session.source_text == "(fresh:1.10)"
    assert session.source_snapshot().parenthesis_intents == ()


def test_manual_escapement_intent_round_trips_with_undo_redo() -> None:
    """Restore user parenthesis intent together with source history."""

    session = _session(r"\(blue laces\)")
    normalizer = PromptSourceNormalizationService()
    session.replace_source_range(
        start=0,
        end=1,
        replacement_text="",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )
    closing_slash = session.source_text.index(r"\)")
    session.replace_source_range(
        start=closing_slash,
        end=closing_slash + 1,
        replacement_text="",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )

    undo_result = session.undo(_undo_snapshot(session))

    assert undo_result is not None
    assert session.source_text == r"(blue laces\)"
    assert session.source_snapshot().parenthesis_intents

    redo_result = session.redo(_undo_snapshot(session))

    assert redo_result is not None
    assert session.source_text == "(blue laces)"
    assert session.source_snapshot().parenthesis_intents


def test_generated_emphasis_provenance_round_trips_with_undo_redo() -> None:
    """Restore generated-weight ownership so later wrapping still re-evaluates."""

    session = _session("(test")
    normalizer = PromptSourceNormalizationService()
    session.replace_source_range(
        start=len(session.source_text),
        end=len(session.source_text),
        replacement_text=")",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )
    generated_snapshot = _undo_snapshot(session)

    assert session.undo(generated_snapshot) is not None
    assert session.redo(_undo_snapshot(session)) is not None
    assert session.source_snapshot().generated_emphases

    session.replace_source_range(
        start=0,
        end=0,
        replacement_text="(",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )
    session.replace_source_range(
        start=len(session.source_text),
        end=len(session.source_text),
        replacement_text=")",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )

    assert session.source_text == "(test:1.21)"
    assert session.source_snapshot().generated_emphases[0].nesting_depth == 2


def test_canonicalizer_emits_authoritative_transitions_and_boundaries() -> None:
    """Carry semantic rewrites and cursor mappings in one result owner."""

    result = canonicalize_prompt_parentheses("alpha, ((blue laces))")

    assert result.text == "alpha, (blue laces:1.21)"
    assert result.boundary_positions[0] == 0
    assert result.boundary_positions[-1] == len(result.text)
    assert [transition.kind for transition in result.transitions] == [
        PromptParenthesisTransitionKind.IMPLICIT_EMPHASIS
    ]
    assert result.transitions[0].nesting_depth == 2


def test_nested_implicit_group_inside_explicit_emphasis_is_stabilized() -> None:
    """Preserve an authored outer weight while making inner nesting explicit."""

    assert (
        canonicalize_prompt_parentheses("outer (blue (butterfly) bow:1.20)").text
        == "outer (blue (butterfly:1.10) bow:1.20)"
    )


def test_typed_large_integer_reclassifies_escaped_group_as_emphasis() -> None:
    """Re-evaluate an auto-owned literal when typed syntax becomes explicit."""

    source = r"\(wide shot:6\)"
    service = PromptSourceNormalizationService()
    result = service.normalize_for_typed_edit_range(
        source,
        start=12,
        end=13,
        replacement_text="6",
    )

    assert result.text == "(wide shot:6)"
    assert result.transitions[0].kind is (
        PromptParenthesisTransitionKind.ESCAPED_LITERAL_TO_EMPHASIS
    )


def test_typed_known_tag_re_evaluates_complete_segment() -> None:
    """Use the whole segment for exact tag recognition when its paren closes."""

    snapshot = PromptTagLexiconSnapshot(
        normalized_tags=frozenset({"vertin (reverse:1999)"})
    )
    service = PromptSourceNormalizationService(tag_snapshot=snapshot)
    source = "vertin (reverse:1999)"

    result = service.normalize_for_typed_edit_range(
        source,
        start=len(source) - 1,
        end=len(source),
        replacement_text=")",
    )

    assert result.text == r"vertin \(reverse:1999\)"


@pytest.mark.parametrize(
    "source",
    (
        '"(quoted)"',
        "don't (stop)",
        r"already \(literal\)",
        "unbalanced (group",
    ),
)
def test_structural_scanner_respects_quotes_escapes_and_unbalanced_groups(
    source: str,
) -> None:
    """Keep quoted, escaped, and incomplete structures tolerant and predictable."""

    result = canonicalize_prompt_parentheses(source).text

    if source == "don't (stop)":
        assert result == "don't (stop:1.10)"
    else:
        assert result == source
