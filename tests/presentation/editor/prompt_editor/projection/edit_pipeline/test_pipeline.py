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

"""Guard classifier-to-strategy execution through the edit pipeline owner."""

from __future__ import annotations

from typing import cast

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.layout.checkpoints import (
    PromptProjectionLayoutCheckpoint,
)
from substitute.presentation.editor.prompt_editor.projection.edit_pipeline import (
    PromptEditPipeline,
)
from substitute.presentation.editor.prompt_editor.projection.deferred_feedback_strategy import (
    PromptDeferredFeedbackStrategy,
)
from substitute.presentation.editor.prompt_editor.projection.direct_feedback_strategy import (
    PromptDirectFeedbackStrategy,
)
from substitute.presentation.editor.prompt_editor.projection.edit_pipeline_contracts import (
    PromptProjectionApplyPath,
    PromptProjectionSourceChangeApplyRequest,
)
from substitute.presentation.editor.prompt_editor.projection.edit_strategy import (
    PromptSourceEditKind,
)
from substitute.presentation.editor.prompt_editor.projection.freshness_controller import (
    ProjectionFreshness,
    PromptProjectionFreshnessBlockers,
)
from substitute.presentation.editor.prompt_editor.projection.history_checkpoint_strategy import (
    PromptHistoryCheckpointStrategy,
)
from substitute.presentation.editor.prompt_editor.projection.incremental_reflow_strategy import (
    PromptIncrementalReflowStrategy,
)
from substitute.presentation.editor.prompt_editor.projection.incremental_edit_contracts import (
    PromptProjectionPlainTextApplyResult,
    PromptProjectionPlainTextApplyStatus,
)
from substitute.presentation.editor.prompt_editor.projection.source_edit_projection_policy import (
    PromptSourceEditProjectionDecision,
)
from substitute.presentation.editor.prompt_editor.projection.semantic_transition_strategy import (
    PromptSemanticTransitionResult,
)
from substitute.presentation.editor.prompt_editor.projection.edit_publication import (
    PromptEditPublication,
)
from substitute.presentation.editor.prompt_editor.projection.trailing_edit_strategy import (
    PromptTrailingEditStrategy,
)


def _document(text: str) -> PromptDocumentView:
    """Return the minimal immutable semantic document for pipeline tests."""

    return PromptDocumentView(
        source_text=text,
        segments=(),
        emphasis_spans=(),
        wildcard_spans=(),
        lora_spans=(),
        syntax_spans=(),
        region_structure=PromptRegionStructureView.empty(len(text)),
        has_trailing_comma=False,
    )


def _request(
    *,
    edit_kind: PromptSourceEditKind = PromptSourceEditKind.PLAIN_REPLACEMENT,
    region_rebuild: bool = False,
    topology_rebuild: bool = False,
    checkpoint: PromptProjectionLayoutCheckpoint | None = None,
    deferred_extendable: bool = False,
    direct_deferred: bool = False,
    wrap_deferrable: bool = True,
) -> PromptProjectionSourceChangeApplyRequest:
    """Return one complete request without reading mutable editor state."""

    previous_text = "alpha"
    text = "alphax"
    render_plan = PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=())
    return PromptProjectionSourceChangeApplyRequest(
        text=text,
        previous_source_text=previous_text,
        previous_source_identity=PromptSourceIdentity(
            source_revision=1,
            source_length=len(previous_text),
        ),
        source_edit_start=len(previous_text),
        source_edit_end=len(previous_text),
        source_edit_replacement_text="x",
        previous_projection_freshness=ProjectionFreshness.FRESH,
        previous_document_view=_document(previous_text),
        previous_render_plan=render_plan,
        next_document_view=_document(text),
        next_render_plan=render_plan,
        previous_deletion_overlay=None,
        next_cursor_state=PromptProjectionCaretState(source_position=len(text)),
        next_anchor_state=PromptProjectionCaretState(source_position=len(text)),
        can_preserve_diagnostic_fragment_cache=True,
        projection_deferral_reason="plain_single_character",
        region_structure_requires_rebuild=region_rebuild,
        edit_kind=edit_kind,
        deferred_plain_edit_extendable=deferred_extendable,
        wrap_reflow_deferrable=wrap_deferrable,
        projection_decision=PromptSourceEditProjectionDecision(
            can_defer_projection=direct_deferred,
            deferral_reason="test",
            projection_topology_requires_rebuild=topology_rebuild,
        ),
        restore_checkpoint=checkpoint,
        restore_checkpoint_blockers=(
            None
            if checkpoint is None
            else PromptProjectionFreshnessBlockers(
                display_mode=PromptProjectionDisplayMode.PROJECTED,
                reorder_preview_active=False,
                autocomplete_preview_active=False,
                exact_weight_edit_active=False,
                expanded_source_range_active=False,
            )
        ),
    )


class _StrategyExecutor:
    """Record strategy order and return one configured successful strategy."""

    def __init__(
        self,
        successful_strategy: str,
        *,
        incremental_status: PromptProjectionPlainTextApplyStatus = (
            PromptProjectionPlainTextApplyStatus.REJECTED
        ),
    ) -> None:
        """Store the configured terminal strategy."""

        self.successful_strategy = successful_strategy
        self.incremental_status = incremental_status
        self.calls: list[str] = []
        self.cache_clear_reasons: list[str] = []

    def try_strategy(self, name: str) -> bool:
        """Record one strategy and report configured success."""

        self.calls.append(name)
        return self.successful_strategy == name

    def defer_wrap(
        self,
        *,
        previous_document_view: PromptDocumentView,
        previous_render_plan: PromptSyntaxRenderPlan,
    ) -> bool:
        """Record deferred wrap scheduling."""

        _ = previous_document_view
        _ = previous_render_plan
        return self.try_strategy("defer_wrap")

    def try_defer_direct(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> bool:
        """Record already-approved transient deferral."""

        _ = request
        return self.try_strategy("direct")

    def try_defer_fallback(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> bool:
        """Record transient deferred fallback."""

        _ = request
        return self.try_strategy("transient")

    def rebuild_projection(self) -> None:
        """Record the terminal full rebuild."""

        self.calls.append("rebuild")

    def clear_diagnostic_fragment_cache(self, *, reason: str) -> None:
        """Record deferred cache invalidation."""

        self.cache_clear_reasons.append(reason)


class _TrailingStrategy:
    """Record trailing strategy order through its focused port."""

    def __init__(self, executor: _StrategyExecutor) -> None:
        """Store the shared call recorder."""

        self._executor = executor

    def _try(self, name: str) -> PromptProjectionDocument | None:
        """Return an applied result only for the configured strategy."""

        if not self._executor.try_strategy(name):
            return None
        return PromptProjectionDocument.empty()

    def can_apply_prompt_state_insert(
        self,
        render_plan: PromptSyntaxRenderPlan,
        *,
        previous_render_plan: PromptSyntaxRenderPlan,
    ) -> bool:
        """Record no prompt-state policy work in source-edit tests."""

        _ = render_plan, previous_render_plan
        return True

    def try_plain_insert(
        self,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> PromptProjectionDocument | None:
        """Record trailing plain insertion."""

        _ = document_view, render_plan
        return self._try("trailing_plain_insert")

    def try_newline_insert(
        self,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        previous_text: str,
        start: int,
        end: int,
    ) -> PromptProjectionDocument | None:
        """Record trailing newline insertion."""

        _ = document_view, render_plan, previous_text, start, end
        return self._try("trailing_newline_insert")

    def try_plain_delete(
        self,
        *,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
    ) -> PromptProjectionDocument | None:
        """Record trailing plain deletion."""

        _ = previous_text, next_text, start, end
        return self._try("trailing_plain_delete")

    def try_newline_delete(
        self,
        *,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
    ) -> PromptProjectionDocument | None:
        """Record trailing newline deletion."""

        _ = previous_text, next_text, start, end
        return self._try("trailing_newline_delete")


class _HistoryStrategy:
    """Record checkpoint restoration through its focused port."""

    def __init__(self, executor: _StrategyExecutor) -> None:
        """Store the shared call recorder."""

        self._executor = executor

    def try_restore(
        self,
        checkpoint: PromptProjectionLayoutCheckpoint | None,
        *,
        blockers: PromptProjectionFreshnessBlockers | None,
        expected_source_text: str,
    ) -> PromptProjectionDocument | None:
        """Return a restored document only for the configured strategy."""

        _ = checkpoint, blockers, expected_source_text
        if not self._executor.try_strategy("checkpoint"):
            return None
        return PromptProjectionDocument.empty()


class _ReflowStrategy:
    """Record incremental and canonical strategy order."""

    def __init__(self, executor: _StrategyExecutor) -> None:
        """Store the shared call recorder."""

        self._executor = executor

    def try_incremental(
        self,
        *,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
        replacement_text: str,
    ) -> PromptProjectionPlainTextApplyResult:
        """Record one incremental attempt."""

        _ = previous_text, next_text, start, end, replacement_text
        self._executor.calls.append("incremental")
        return PromptProjectionPlainTextApplyResult(
            status=self._executor.incremental_status
        )

    def try_canonical(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> PromptProjectionPlainTextApplyResult | None:
        """Record canonical recovery."""

        _ = request
        if not self._executor.try_strategy("canonical"):
            return None
        return PromptProjectionPlainTextApplyResult(
            status=PromptProjectionPlainTextApplyStatus.APPLIED_REFLOW
        )

    def apply_prebuilt(
        self,
        result: PromptProjectionPlainTextApplyResult,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> PromptProjectionPlainTextApplyResult | None:
        """Record publication of a retained canonical document."""

        _ = request
        return result if self._executor.try_strategy("prebuilt") else None


class _Publication:
    """Accept focused publication calls for strategy-order tests."""

    def __init__(self, executor: _StrategyExecutor) -> None:
        """Store the shared terminal-effect recorder."""

        self._executor = executor

    def rebuild_projection(self) -> None:
        """Record the terminal full rebuild."""

        self._executor.rebuild_projection()

    def clear_diagnostic_fragment_cache(self, *, reason: str) -> None:
        """Record deferred diagnostic-cache invalidation."""

        self._executor.clear_diagnostic_fragment_cache(reason=reason)

    def current_layout_identity(self) -> PromptLayoutIdentity | None:
        """Return no prior layout identity in strategy-order tests."""

        return None

    def publish_trailing_insert(
        self,
        projection_document: PromptProjectionDocument,
        *,
        cache_reason: str,
    ) -> None:
        """Accept one trailing insertion."""

        _ = projection_document, cache_reason

    def publish_plain_delete(
        self,
        projection_document: PromptProjectionDocument,
        *,
        start: int,
        end: int,
        previous_layout_identity: PromptLayoutIdentity | None,
    ) -> None:
        """Accept one plain deletion."""

        _ = projection_document, start, end, previous_layout_identity

    def publish_newline_delete(
        self,
        projection_document: PromptProjectionDocument,
    ) -> None:
        """Accept one newline deletion."""

        _ = projection_document

    def publish_incremental(
        self,
        result: PromptProjectionPlainTextApplyResult,
        *,
        start: int,
        end: int,
        replacement_text: str,
        previous_layout_identity: PromptLayoutIdentity | None,
    ) -> None:
        """Accept one incremental publication."""

        _ = result, start, end, replacement_text, previous_layout_identity

    def publish_reflow(
        self,
        result: PromptProjectionPlainTextApplyResult,
    ) -> None:
        """Accept one bounded reflow publication."""

        _ = result

    def publish_checkpoint(
        self,
        projection_document: PromptProjectionDocument,
    ) -> None:
        """Accept one restored history checkpoint."""

        _ = projection_document

    def publish_semantic_transition(
        self,
        result: PromptSemanticTransitionResult,
    ) -> None:
        """Accept one same-source semantic transition."""

        _ = result


def _pipeline(executor: _StrategyExecutor) -> PromptEditPipeline:
    """Return a pipeline with focused recording collaborators."""

    return PromptEditPipeline(
        direct_feedback_strategy=cast(PromptDirectFeedbackStrategy, executor),
        deferred_strategy=cast(PromptDeferredFeedbackStrategy, executor),
        history_strategy=cast(
            PromptHistoryCheckpointStrategy,
            _HistoryStrategy(executor),
        ),
        trailing_strategy=cast(
            PromptTrailingEditStrategy,
            _TrailingStrategy(executor),
        ),
        reflow_strategy=cast(
            PromptIncrementalReflowStrategy,
            _ReflowStrategy(executor),
        ),
        publication=cast(PromptEditPublication, _Publication(executor)),
    )


def test_edit_pipeline_restores_checkpoint_before_local_work() -> None:
    """History geometry should publish before any edit strategy is attempted."""

    executor = _StrategyExecutor("checkpoint")
    checkpoint = cast(PromptProjectionLayoutCheckpoint, object())

    outcome = _pipeline(executor).apply(_request(checkpoint=checkpoint))

    assert executor.calls == ["checkpoint"]
    assert outcome.apply_path is PromptProjectionApplyPath.CHECKPOINT_RESTORE


def test_edit_pipeline_forces_topology_directly_to_full_rebuild() -> None:
    """Topology changes should execute no speculative local strategy."""

    executor = _StrategyExecutor("none")

    outcome = _pipeline(executor).apply(_request(topology_rebuild=True))

    assert executor.calls == ["rebuild"]
    assert outcome.apply_path is PromptProjectionApplyPath.FULL_REBUILD


def test_edit_pipeline_defers_approved_feedback_before_local_layout() -> None:
    """Approved transient feedback should bypass speculative layout work."""

    executor = _StrategyExecutor("direct")

    outcome = _pipeline(executor).apply(_request(direct_deferred=True))

    assert executor.calls == ["direct"]
    assert outcome.apply_path is PromptProjectionApplyPath.DEFERRED_FEEDBACK
    assert outcome.direct_feedback_applied
    assert not outcome.wrap_reflow_deferred


def test_edit_pipeline_executes_plain_fast_path_in_classifier_order() -> None:
    """Ordinary typing should try the trailing strategy first."""

    executor = _StrategyExecutor("trailing_plain_insert")

    outcome = _pipeline(executor).apply(_request())

    assert executor.calls == ["trailing_plain_insert"]
    assert outcome.apply_path is PromptProjectionApplyPath.FAST_TRAILING
    assert outcome.fast_projection_applied


def test_edit_pipeline_preserves_delete_strategy_order() -> None:
    """Deletion should try plain then newline trailing strategies."""

    executor = _StrategyExecutor("trailing_newline_delete")

    outcome = _pipeline(executor).apply(_request(edit_kind=PromptSourceEditKind.DELETE))

    assert executor.calls == [
        "trailing_plain_delete",
        "trailing_newline_delete",
    ]
    assert outcome.apply_path is PromptProjectionApplyPath.FAST_TRAILING


def test_edit_pipeline_defers_only_after_incremental_wrap_result() -> None:
    """A visual-safe wrap rejection should schedule catch-up after local work."""

    executor = _StrategyExecutor(
        "defer_wrap",
        incremental_status=PromptProjectionPlainTextApplyStatus.DEFERRED_WRAP_REFLOW,
    )

    outcome = _pipeline(executor).apply(_request(direct_deferred=True))

    assert executor.calls == [
        "direct",
        "direct",
        "trailing_plain_insert",
        "incremental",
        "defer_wrap",
    ]
    assert outcome.apply_path is PromptProjectionApplyPath.DEFERRED_WRAP
    assert outcome.wrap_reflow_deferred
    assert executor.cache_clear_reasons == ["source_changed_deferred_projection"]


def test_edit_pipeline_falls_through_to_prebuilt_then_canonical() -> None:
    """Rejected local strategies should preserve prebuilt/canonical ordering."""

    executor = _StrategyExecutor("canonical")

    outcome = _pipeline(executor).apply(_request(wrap_deferrable=False))

    assert executor.calls == [
        "trailing_plain_insert",
        "incremental",
        "transient",
        "prebuilt",
        "canonical",
    ]
    assert outcome.apply_path is PromptProjectionApplyPath.REFLOW


def test_edit_pipeline_extends_existing_deferred_chain_before_local_work() -> None:
    """A visual-safe stale edit chain should schedule before local work."""

    executor = _StrategyExecutor("defer_wrap")

    outcome = _pipeline(executor).apply(
        _request(deferred_extendable=True, direct_deferred=True)
    )

    assert executor.calls == ["direct", "direct", "defer_wrap"]
    assert outcome.wrap_reflow_deferred


def test_edit_pipeline_rebuilds_when_wrap_deferral_lacks_visible_feedback() -> None:
    """A wrap-boundary edit must not leave source without a visual owner."""

    executor = _StrategyExecutor(
        "prebuilt",
        incremental_status=PromptProjectionPlainTextApplyStatus.DEFERRED_WRAP_REFLOW,
    )

    outcome = _pipeline(executor).apply(_request())

    assert executor.calls == [
        "trailing_plain_insert",
        "incremental",
        "transient",
        "prebuilt",
    ]
    assert outcome.apply_path is PromptProjectionApplyPath.REFLOW
