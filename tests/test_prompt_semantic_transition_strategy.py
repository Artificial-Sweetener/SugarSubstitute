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

"""Verify bounded same-source projection changes through their strategy owner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from substitute.application.prompt_editor.document.views import PromptSyntaxSpanView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.projection.applicator import (
    PromptProjectionApplicator,
)
from substitute.presentation.editor.prompt_editor.projection.builder import (
    PromptProjectionBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.freshness_controller import (
    PromptProjectionFreshnessBlockers,
)
from substitute.presentation.editor.prompt_editor.projection.edit_to_frame import (
    PromptLayoutEditToFrameCoordinator,
)
from substitute.presentation.editor.prompt_editor.projection.projection_build_context import (
    PromptProjectionBuildContext,
)
from substitute.presentation.editor.prompt_editor.projection.semantic_transition_strategy import (
    PromptSemanticTransitionEditorState,
    PromptSemanticTransitionStrategy,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)
from tests.prompt_projection_layout_test_helpers import projection_layout_for


@dataclass(frozen=True, slots=True)
class _ProjectionState:
    """Expose the current projection document to the strategy."""

    document: PromptProjectionDocument


class _EditorState:
    """Provide the projection query used by the semantic strategy."""

    def __init__(self, document: PromptProjectionDocument) -> None:
        """Store the current projected document."""

        self._projection = _ProjectionState(document)

    @property
    def projection(self) -> _ProjectionState:
        """Return current projection state."""

        return self._projection


class _BuildContext:
    """Provide explicit dynamic feature state for one strategy attempt."""

    def __init__(
        self,
        *,
        blockers: PromptProjectionFreshnessBlockers | None = None,
    ) -> None:
        """Store projected mode and optional blockers."""

        self._display_mode = PromptProjectionDisplayMode.PROJECTED
        self._session = PromptProjectionSession()
        self._scene_error_keys: frozenset[str] = frozenset()
        self._blockers = blockers or _blockers()

    def _decoration_accent_ranges(self) -> tuple[tuple[int, int], ...]:
        """Return no extra decoration accents."""

        return ()

    def _projection_freshness_blockers(self) -> PromptProjectionFreshnessBlockers:
        """Return the configured local-build blockers."""

        return self._blockers


def _blockers(
    *,
    autocomplete: bool = False,
) -> PromptProjectionFreshnessBlockers:
    """Return projected-mode semantic transition blockers."""

    return PromptProjectionFreshnessBlockers(
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        reorder_preview_active=False,
        autocomplete_preview_active=autocomplete,
        exact_weight_edit_active=False,
        expanded_source_range_active=False,
    )


def _render_plans(text: str) -> tuple[PromptSyntaxRenderPlan, PromptSyntaxRenderPlan]:
    """Return plans that add one projection-affecting range over unchanged text."""

    start = text.index("beta")
    previous = PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=())
    current = PromptSyntaxRenderPlan(
        syntax_spans=(
            PromptSyntaxSpanView(
                kind="test",
                start=start,
                end=start + len("beta"),
                depth=0,
            ),
        ),
        renderer_views=(),
    )
    return previous, current


def _strategy(
    text: str,
    *,
    context: _BuildContext | None = None,
) -> tuple[PromptSemanticTransitionStrategy, PromptLayoutEditToFrameCoordinator]:
    """Return a production strategy over one prepared projection frame."""

    layout, projection = projection_layout_for(text)
    return (
        PromptSemanticTransitionStrategy(
            cast(PromptProjectionBuildContext, context or _BuildContext()),
            applicator=PromptProjectionApplicator(PromptProjectionBuilder()),
            editor_state=cast(
                PromptSemanticTransitionEditorState,
                _EditorState(projection),
            ),
            layout=layout,
        ),
        layout,
    )


def test_semantic_transition_strategy_publishes_bounded_same_source_frame() -> None:
    """Build changed token topology without a full projection rebuild."""

    text = "alpha beta gamma"
    strategy, layout = _strategy(text)
    previous, current = _render_plans(text)
    document_view = layout.frame.output.prompt_document_view
    assert document_view is not None

    result = strategy.try_apply(
        document_view=document_view,
        render_plan=current,
        previous_render_plan=previous,
    )

    assert result is not None
    assert result.projection_document.source_text == text
    assert result.layout_damage.reflowed_line_count >= 1
    assert layout.frame.output.projection_document is result.projection_document


def test_semantic_transition_strategy_rejects_active_transient_mode() -> None:
    """Keep autocomplete-owned geometry authoritative while it is active."""

    text = "alpha beta gamma"
    strategy, layout = _strategy(
        text,
        context=_BuildContext(blockers=_blockers(autocomplete=True)),
    )
    previous, current = _render_plans(text)
    document_view = layout.frame.output.prompt_document_view
    assert document_view is not None

    assert (
        strategy.try_apply(
            document_view=document_view,
            render_plan=current,
            previous_render_plan=previous,
        )
        is None
    )


def test_semantic_transition_strategy_rejects_unchanged_ranges() -> None:
    """Leave range-stable metadata changes to the canonical fallback."""

    text = "alpha beta gamma"
    strategy, layout = _strategy(text)
    _previous, current = _render_plans(text)
    document_view = layout.frame.output.prompt_document_view
    assert document_view is not None

    assert (
        strategy.try_apply(
            document_view=document_view,
            render_plan=current,
            previous_render_plan=current,
        )
        is None
    )
