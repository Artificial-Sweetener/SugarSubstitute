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

"""Qualify weight-feedback rebasing and render failure recovery in the real editor."""

from __future__ import annotations

from decimal import Decimal

import pytest
from PySide6.QtTest import QSignalSpy

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptAdjustEmphasisAction,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptSyntaxRenderPlan,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from tests.support.prompt_editor.projection_engine_support import surface_for
from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


@pytest.mark.parametrize("render_failure", [False, True])
def test_weight_interaction_rebases_feedback_after_earlier_normalization(
    real_shell_scenario: PromptEditorRealShellScenario,
    monkeypatch: pytest.MonkeyPatch,
    render_failure: bool,
) -> None:
    """Keep the adjusted target current after earlier source expands, including recovery."""

    original = "(dog), (cat:1.05)"
    expected = "(dog:1.10), (cat:1.10)"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=original)
    editor = field.editor
    surface = surface_for(editor)
    interaction = editor._runtime.core.syntax.interaction_controller
    weights = interaction.weight_interaction
    real_shell_scenario.input.set_source_cursor_position(
        field, original.index("cat") + 1
    )
    changed = QSignalSpy(editor.textChanged)
    failed_sources: list[str] = []

    def fail_render_plan(
        self: PromptSyntaxService,
        document_view: PromptDocumentView,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptSyntaxRenderPlan:
        """Inject render preparation unavailability without replacing state adoption."""

        failed_sources.append(document_view.source_text)
        raise RuntimeError("injected weight render-plan failure")

    with monkeypatch.context() as patch:
        if render_failure:
            patch.setattr(PromptSyntaxService, "build_render_plan", fail_render_plan)
        weights.apply_syntax_action(
            PromptAdjustEmphasisAction(
                outer_start=original.index("(cat"),
                outer_end=len(original),
                delta=Decimal("0.05"),
            )
        )

    assert editor.toPlainText() == surface.document().toPlainText() == expected
    assert surface._editing_session.source_text == expected  # noqa: SLF001
    assert surface.editor_state.edit_semantic.document.source_text == expected
    assert surface.projection_document().source_text == expected
    assert surface.cursor_position == expected.index("cat") + 1
    assert surface.anchor_position == surface.cursor_position
    assert changed.count() == 1
    adjustment = editor.emphasis_adjustment_session()
    assert adjustment is not None
    assert (adjustment.content_start, adjustment.content_end) == (
        expected.index("cat"),
        expected.index("cat") + 3,
    )
    if render_failure:
        assert failed_sources
        assert set(failed_sources) == {expected}
        assert surface.editor_state.semantic.document.source_text == original
        interaction.flush_pending_semantic_refresh(reason="retry_weight_render")

    recovered = real_shell_scenario.snapshots.capture(
        field, label="rebased-weight-feedback"
    )
    assert recovered.semantic_is_current
    assert recovered.source_text == expected
    assert not snapshot_invariant_violations(recovered)
    assert [
        span.weight for span in surface.editor_state.semantic.document.emphasis_spans
    ] == [Decimal("1.10"), Decimal("1.10")]

    weights.apply_syntax_action(
        PromptAdjustEmphasisAction(
            outer_start=expected.index("(cat"),
            outer_end=len(expected),
            delta=Decimal("0.05"),
        )
    )
    later = real_shell_scenario.snapshots.capture(field, label="later-weight-step")
    assert later.source_text == "(dog:1.10), (cat:1.15)"
    assert surface.document().toPlainText() == later.source_text
    assert changed.count() == 2
    assert later.semantic_is_current
    assert not snapshot_invariant_violations(later)


def test_failed_weight_adoption_preserves_scheduled_semantic_recovery(
    real_shell_scenario: PromptEditorRealShellScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Let a queued recovery finish when immediate weight-state adoption fails."""

    original = "(cat:1.05), (dog)"
    expected = "(cat:1.10), (dog:1.10)"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=original)
    editor = field.editor
    surface = surface_for(editor)
    interaction = editor._runtime.core.syntax.interaction_controller
    weights = interaction.weight_interaction
    changed = QSignalSpy(editor.textChanged)

    def fail_render_plan(
        self: PromptSyntaxService,
        document_view: PromptDocumentView,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptSyntaxRenderPlan:
        """Prevent immediate state adoption while leaving source publication real."""

        raise RuntimeError("injected weight adoption failure")

    with monkeypatch.context() as patch:
        patch.setattr(PromptSyntaxService, "build_render_plan", fail_render_plan)
        result = weights.execute_emphasis_weight_action(
            PromptAdjustEmphasisAction(
                outer_start=0,
                outer_end=len("(cat:1.05)"),
                delta=Decimal("0.05"),
            ),
            cursor_policy="preserve_cursor",
        )
        assert result.status == "applied"
        assert result.mutation is not None
        assert result.render_plan is None
        interaction._semantic_refresh.queue_source_changed(  # noqa: SLF001
            expected, reason="weight_recovery_after_failed_flush"
        )
        weights.apply_emphasis_weight_result(result)
        pending = real_shell_scenario.snapshots.capture(
            field, label="failed-weight-adoption", settle=False
        )
        assert pending.semantic_refresh_pending
        assert not pending.semantic_is_current
        assert editor.toPlainText() == surface.document().toPlainText() == expected
        assert changed.count() == 1

    real_shell_scenario.wait_until(
        lambda: (
            surface.editor_state.semantic.document.source_text == expected
            and surface.editor_state.semantic.identity.source
            is surface.editor_state.source_identity
        ),
        description="scheduled weight semantic recovery",
    )
    recovered = real_shell_scenario.snapshots.capture(
        field, label="weight-adoption-recovered"
    )
    assert recovered.semantic_is_current
    assert not recovered.semantic_refresh_pending
    assert not recovered.semantic_refresh_active
    assert recovered.source_text == expected
    assert changed.count() == 1
    assert not snapshot_invariant_violations(recovered)
