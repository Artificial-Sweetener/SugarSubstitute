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

"""Contract tests for the prompt syntax-renderer coordinator seam."""

from __future__ import annotations

from PySide6.QtCore import QPointF

from substitute.application.prompt_editor import (
    PromptAdjustEmphasisAction,
    PromptDocumentService,
    PromptDocumentView,
    PromptSyntaxAction,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
    PromptSyntaxSpanView,
    PromptSyntaxProfileService,
)
from substitute.presentation.editor.prompt_editor.syntax_renderers import (
    PromptSyntaxRendererCoordinator,
)
from tests.prompt_autocomplete_test_helpers import EmptyPromptWildcardCatalogGateway


class _RendererDouble:
    """Record the syntax-renderer coordinator calls for one fake renderer."""

    def __init__(self, action: PromptSyntaxAction | None = None) -> None:
        """Store the syntax action that hit-testing should return."""

        self.action = action
        self.prompt_state_calls: list[
            tuple[PromptDocumentView, PromptSyntaxRenderPlan]
        ] = []
        self.active_span_calls: list[tuple[PromptSyntaxSpanView | None, int]] = []
        self.refresh_geometry_calls = 0
        self.clear_transient_state_calls = 0
        self.hit_test_calls: list[QPointF] = []

    def set_prompt_state(
        self,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> None:
        """Record one prompt-state update from the coordinator."""

        self.prompt_state_calls.append((document_view, render_plan))

    def set_active_span(
        self,
        active_span: PromptSyntaxSpanView | None,
        *,
        cursor_position: int,
    ) -> None:
        """Record one active-span update from the coordinator."""

        self.active_span_calls.append((active_span, cursor_position))

    def refresh_geometry(self) -> None:
        """Record one geometry refresh request from the coordinator."""

        self.refresh_geometry_calls += 1

    def clear_transient_state(self) -> None:
        """Record one transient-state clear request from the coordinator."""

        self.clear_transient_state_calls += 1

    def hit_test_action(self, position: QPointF) -> PromptSyntaxAction | None:
        """Return the configured action for one deterministic test position."""

        self.hit_test_calls.append(position)
        return self.action


def _document_state(text: str) -> tuple[PromptDocumentView, PromptSyntaxRenderPlan]:
    """Build one real prompt document view plus render plan for coordinator tests."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(EmptyPromptWildcardCatalogGateway())
    profile_service = PromptSyntaxProfileService()
    document_view = document_service.build_document_view(text)
    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["emphasis", "wildcard"]}),
    )
    return document_view, render_plan


def test_coordinator_fans_prompt_state_to_each_registered_renderer() -> None:
    """Prompt-state refreshes should reach every registered syntax renderer."""

    document_view, render_plan = _document_state("(cat:1.05)")
    first_renderer = _RendererDouble()
    second_renderer = _RendererDouble()
    coordinator = PromptSyntaxRendererCoordinator((first_renderer, second_renderer))

    coordinator.set_prompt_state(document_view, render_plan)

    assert first_renderer.prompt_state_calls == [(document_view, render_plan)]
    assert second_renderer.prompt_state_calls == [(document_view, render_plan)]


def test_coordinator_fans_active_span_to_each_registered_renderer() -> None:
    """Caret-state refreshes should reach every registered syntax renderer."""

    document_view, render_plan = _document_state("(cat:1.05)")
    active_span = render_plan.syntax_spans[0]
    first_renderer = _RendererDouble()
    second_renderer = _RendererDouble()
    coordinator = PromptSyntaxRendererCoordinator((first_renderer, second_renderer))

    coordinator.set_active_span(active_span, cursor_position=3)

    assert first_renderer.active_span_calls == [(active_span, 3)]
    assert second_renderer.active_span_calls == [(active_span, 3)]
    assert document_view.source_text == "(cat:1.05)"


def test_coordinator_refreshes_geometry_and_clears_transient_state() -> None:
    """Coordinator-wide refresh and clear requests should fan to each renderer."""

    first_renderer = _RendererDouble()
    second_renderer = _RendererDouble()
    coordinator = PromptSyntaxRendererCoordinator((first_renderer, second_renderer))

    coordinator.refresh_geometry()
    coordinator.clear_transient_state()

    assert first_renderer.refresh_geometry_calls == 1
    assert second_renderer.refresh_geometry_calls == 1
    assert first_renderer.clear_transient_state_calls == 1
    assert second_renderer.clear_transient_state_calls == 1


def test_coordinator_returns_topmost_matching_syntax_action() -> None:
    """Hit-testing should prefer the last-registered renderer with an action."""

    back_action = PromptAdjustEmphasisAction(
        outer_start=0,
        outer_end=10,
        delta=-0.05,
    )
    front_action = PromptAdjustEmphasisAction(
        outer_start=0,
        outer_end=10,
        delta=0.05,
    )
    back_renderer = _RendererDouble(action=back_action)
    front_renderer = _RendererDouble(action=front_action)
    coordinator = PromptSyntaxRendererCoordinator((back_renderer, front_renderer))
    point = QPointF(11.0, 7.0)

    action = coordinator.syntax_action_at(point)

    assert action == front_action
    assert front_renderer.hit_test_calls == [point]
    assert back_renderer.hit_test_calls == []


def test_coordinator_ignores_renderers_without_matching_actions() -> None:
    """Hit-testing should skip empty renderers until one returns an action."""

    action_renderer = _RendererDouble(
        action=PromptAdjustEmphasisAction(
            outer_start=0,
            outer_end=10,
            delta=0.05,
        )
    )
    empty_renderer = _RendererDouble()
    coordinator = PromptSyntaxRendererCoordinator((action_renderer, empty_renderer))
    point = QPointF(11.0, 7.0)

    action = coordinator.syntax_action_at(point)

    assert action == action_renderer.action
    assert action_renderer.hit_test_calls == [point]
    assert empty_renderer.hit_test_calls == [point]
