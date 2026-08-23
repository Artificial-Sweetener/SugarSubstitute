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

"""Characterize prompt edit strategy classification and fallback order."""

from __future__ import annotations

import pytest

from substitute.presentation.editor.prompt_editor.projection.edit_classifier import (
    PromptEditClassifier,
)
from substitute.presentation.editor.prompt_editor.projection.edit_strategy import (
    PromptEditClassificationFacts,
    PromptEditStrategy,
    PromptSourceEditKind,
    source_edit_kind,
)


def _facts(
    edit_kind: PromptSourceEditKind,
    **overrides: bool,
) -> PromptEditClassificationFacts:
    """Return classification facts with ordinary fast-path defaults."""

    values = {
        "region_structure_requires_rebuild": False,
        "projection_topology_requires_rebuild": False,
        "restore_checkpoint_available": False,
        "direct_deferred_feedback_allowed": False,
        "deferred_plain_edit_extendable": False,
        "typed_character_requires_immediate_projection": False,
        "syntax_sensitive_prefix_deferrable": False,
        "wrap_reflow_deferrable": True,
    }
    values.update(overrides)
    return PromptEditClassificationFacts(edit_kind=edit_kind, **values)


@pytest.mark.parametrize(
    ("facts", "expected_prefix"),
    (
        (
            _facts(
                PromptSourceEditKind.PLAIN_REPLACEMENT,
                region_structure_requires_rebuild=True,
            ),
            (PromptEditStrategy.FULL_REBUILD,),
        ),
        (
            _facts(
                PromptSourceEditKind.NONE,
                restore_checkpoint_available=True,
            ),
            (PromptEditStrategy.RESTORE_CHECKPOINT,),
        ),
        (
            _facts(
                PromptSourceEditKind.PLAIN_REPLACEMENT,
                direct_deferred_feedback_allowed=True,
            ),
            (PromptEditStrategy.DEFER_DIRECT_FEEDBACK,),
        ),
        (
            _facts(
                PromptSourceEditKind.PLAIN_REPLACEMENT,
                deferred_plain_edit_extendable=True,
            ),
            (PromptEditStrategy.EXTEND_DEFERRED_WRAP,),
        ),
        (
            _facts(PromptSourceEditKind.DELETE),
            (
                PromptEditStrategy.TRAILING_PLAIN_DELETE,
                PromptEditStrategy.TRAILING_NEWLINE_DELETE,
                PromptEditStrategy.INCREMENTAL_PLAIN,
            ),
        ),
        (
            _facts(PromptSourceEditKind.NEWLINE_INSERT),
            (
                PromptEditStrategy.TRAILING_NEWLINE_INSERT,
                PromptEditStrategy.INCREMENTAL_PLAIN,
            ),
        ),
        (
            _facts(PromptSourceEditKind.PLAIN_REPLACEMENT),
            (
                PromptEditStrategy.TRAILING_PLAIN_INSERT,
                PromptEditStrategy.INCREMENTAL_PLAIN,
            ),
        ),
        (
            _facts(
                PromptSourceEditKind.PLAIN_REPLACEMENT,
                typed_character_requires_immediate_projection=True,
            ),
            (PromptEditStrategy.INCREMENTAL_PLAIN,),
        ),
        (
            _facts(
                PromptSourceEditKind.PLAIN_REPLACEMENT,
                typed_character_requires_immediate_projection=True,
                syntax_sensitive_prefix_deferrable=True,
            ),
            (
                PromptEditStrategy.TRAILING_PLAIN_INSERT,
                PromptEditStrategy.INCREMENTAL_PLAIN,
            ),
        ),
    ),
)
def test_edit_classifier_preserves_existing_strategy_prefix(
    facts: PromptEditClassificationFacts,
    expected_prefix: tuple[PromptEditStrategy, ...],
) -> None:
    """Keep mutually exclusive edit branches in their current priority order."""

    candidates = PromptEditClassifier().classify(facts).candidates

    assert candidates[: len(expected_prefix)] == expected_prefix


def test_edit_classifier_preserves_terminal_fallback_order() -> None:
    """Keep transient, prebuilt, canonical, and rebuild recovery ordered."""

    candidates = (
        PromptEditClassifier()
        .classify(_facts(PromptSourceEditKind.PLAIN_REPLACEMENT))
        .candidates
    )

    assert candidates[-5:] == (
        PromptEditStrategy.DEFER_INCREMENTAL_WRAP,
        PromptEditStrategy.DEFER_TRANSIENT_FALLBACK,
        PromptEditStrategy.PUBLISH_PREBUILT_REFLOW,
        PromptEditStrategy.BUILD_CANONICAL_REFLOW,
        PromptEditStrategy.FULL_REBUILD,
    )


def test_edit_classifier_reuses_module_lifetime_strategy_plans() -> None:
    """Ordinary classification should not allocate a new strategy plan."""

    classifier = PromptEditClassifier()
    facts = _facts(PromptSourceEditKind.PLAIN_REPLACEMENT)

    assert classifier.classify(facts) is classifier.classify(facts)


def test_edit_classifier_forces_rebuild_for_projection_topology() -> None:
    """Canonical scene topology changes must bypass local strategies."""

    plan = PromptEditClassifier().classify(
        _facts(
            PromptSourceEditKind.PLAIN_REPLACEMENT,
            projection_topology_requires_rebuild=True,
        )
    )

    assert plan.candidates == (PromptEditStrategy.FULL_REBUILD,)


@pytest.mark.parametrize(
    ("start", "end", "previous", "replacement", "expected"),
    (
        (None, None, None, None, PromptSourceEditKind.NONE),
        (1, 2, "abc", "", PromptSourceEditKind.DELETE),
        (1, 1, "abc", "\n", PromptSourceEditKind.NEWLINE_INSERT),
        (1, 1, "abc", "x", PromptSourceEditKind.PLAIN_REPLACEMENT),
    ),
)
def test_source_edit_kind_uses_only_bounded_edit_shape(
    start: int | None,
    end: int | None,
    previous: str | None,
    replacement: str | None,
    expected: PromptSourceEditKind,
) -> None:
    """Classify without reading or scanning source content."""

    assert (
        source_edit_kind(
            start=start,
            end=end,
            previous_source_text=previous,
            replacement_text=replacement,
        )
        is expected
    )
