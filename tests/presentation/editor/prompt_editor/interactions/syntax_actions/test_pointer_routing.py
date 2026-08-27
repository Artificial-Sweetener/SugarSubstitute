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

"""Test pointer syntax-action routing."""

from __future__ import annotations

from typing import cast


from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutation,
    PromptMutationService,
)
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptAdjustEmphasisAction,
    PromptConsumeSyntaxAction,
)
from tests.presentation.editor.prompt_editor.interactions.syntax_actions.editor_double import (
    MousePressEventDouble,
)
from tests.presentation.editor.prompt_editor.interactions.syntax_actions.service_doubles import (
    MutationServiceDouble,
)
from tests.presentation.editor.prompt_editor.interactions.syntax_actions.support import (
    autocomplete_with_clear_calls,
    build_controller,
    build_editor,
    build_mutation,
    record_applied_mutations,
)
from tests.presentation.editor.prompt_editor.interactions.support.collaborators import (
    syntax_renderer_double,
)


def test_inline_emphasis_click_consumes_event_and_routes_typed_syntax_action() -> None:
    """Inline control clicks clear autocomplete and route one syntax action."""

    document_service = PromptDocumentService()
    action = PromptAdjustEmphasisAction(outer_start=0, outer_end=10, delta=0.05)
    mutation = build_mutation(document_service, "(cat:1.10)", 1, 4)
    mutation_service = MutationServiceDouble(apply_syntax_action_result=mutation)
    clear_calls: list[str] = []
    syntax_renderers = syntax_renderer_double(action)
    editor = build_editor("(cat:1.05)", position=3)
    controller = build_controller(
        editor,
        autocomplete=autocomplete_with_clear_calls(clear_calls),
        document_service=document_service,
        mutation_service=cast(PromptMutationService, mutation_service),
        syntax_renderers=syntax_renderers,
    )
    applied_mutations: list[tuple[PromptMutation, bool]] = []
    controller._apply_mutation = record_applied_mutations(applied_mutations)

    handled = controller.handle_mouse_press(MousePressEventDouble("hit-point"))

    assert handled is True
    assert syntax_renderers.syntax_action_calls == ["hit-point"]
    assert clear_calls == ["clear"]
    assert mutation_service.apply_syntax_action_calls == [("(cat:1.05)", action)]
    assert applied_mutations == []
    assert editor.toPlainText() == "(cat:1.10)"
    assert editor.executed_weight_requests[0].action == action
    assert editor.focus_calls == 1
    assert editor.pulse_emphasis_feedback_calls == [(0, 10)]
    assert mutation_service.adjust_calls == []


def test_inline_emphasis_click_returns_false_when_pointer_misses_renderer_actions() -> (
    None
):
    """Mouse presses that miss renderer actions fall through to normal editing."""

    mutation_service = MutationServiceDouble()
    clear_calls: list[str] = []
    syntax_renderers = syntax_renderer_double()
    editor = build_editor("(cat:1.05)", position=3)
    controller = build_controller(
        editor,
        autocomplete=autocomplete_with_clear_calls(clear_calls),
        mutation_service=cast(PromptMutationService, mutation_service),
        syntax_renderers=syntax_renderers,
    )

    handled = controller.handle_mouse_press(MousePressEventDouble("miss-point"))

    assert handled is False
    assert syntax_renderers.syntax_action_calls == ["miss-point"]
    assert clear_calls == []
    assert mutation_service.apply_syntax_action_calls == []
    assert editor.focus_calls == 0


def test_inline_emphasis_click_consumes_stale_target_without_fallback_mutation_path() -> (
    None
):
    """Control hits still consume clicks when the underlying span disappears."""

    action = PromptAdjustEmphasisAction(outer_start=0, outer_end=10, delta=-0.05)
    mutation_service = MutationServiceDouble(apply_syntax_action_result=None)
    clear_calls: list[str] = []
    editor = build_editor("(cat:1.05)", position=3)
    controller = build_controller(
        editor,
        autocomplete=autocomplete_with_clear_calls(clear_calls),
        mutation_service=cast(PromptMutationService, mutation_service),
        syntax_renderers=syntax_renderer_double(action),
    )
    applied_mutations: list[tuple[PromptMutation, bool]] = []
    controller._apply_mutation = record_applied_mutations(applied_mutations)

    handled = controller.handle_mouse_press(MousePressEventDouble("stale-point"))

    assert handled is True
    assert clear_calls == ["clear"]
    assert mutation_service.apply_syntax_action_calls == [("(cat:1.05)", action)]
    assert applied_mutations == []
    assert editor.focus_calls == 1


def test_apply_syntax_action_can_consume_passive_actions_without_mutation() -> None:
    """The shared syntax-action path supports consume-only actions."""

    action = PromptConsumeSyntaxAction(syntax_kind="emphasis")
    mutation_service = MutationServiceDouble(apply_syntax_action_result=None)
    clear_calls: list[str] = []
    editor = build_editor("(cat:1.05)", position=3)
    controller = build_controller(
        editor,
        autocomplete=autocomplete_with_clear_calls(clear_calls),
        mutation_service=cast(PromptMutationService, mutation_service),
    )

    controller.weight_interaction.apply_syntax_action(action)

    assert clear_calls == ["clear"]
    assert mutation_service.apply_syntax_action_calls == []
    assert editor.focus_calls == 1
    assert editor.pulse_emphasis_feedback_calls == []


def test_apply_syntax_action_reuses_mouse_click_mutation_path() -> None:
    """Host-overlay syntax actions route through the shared mutation path."""

    document_service = PromptDocumentService()
    action = PromptAdjustEmphasisAction(outer_start=0, outer_end=10, delta=0.05)
    mutation = build_mutation(document_service, "(cat:1.10)", 1, 4)
    mutation_service = MutationServiceDouble(apply_syntax_action_result=mutation)
    clear_calls: list[str] = []
    editor = build_editor("(cat:1.05)", position=3)
    controller = build_controller(
        editor,
        autocomplete=autocomplete_with_clear_calls(clear_calls),
        document_service=document_service,
        mutation_service=cast(PromptMutationService, mutation_service),
    )
    applied_mutations: list[tuple[PromptMutation, bool]] = []
    controller._apply_mutation = record_applied_mutations(applied_mutations)

    controller.weight_interaction.apply_syntax_action(action)

    assert clear_calls == ["clear"]
    assert mutation_service.apply_syntax_action_calls == [("(cat:1.05)", action)]
    assert applied_mutations == []
    assert editor.toPlainText() == "(cat:1.10)"
    assert editor.executed_weight_requests[0].action == action
    assert editor.focus_calls == 1
    assert editor.pulse_emphasis_feedback_calls == [(0, 10)]
