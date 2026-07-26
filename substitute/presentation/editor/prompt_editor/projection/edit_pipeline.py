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

"""Execute one classifier-owned source-edit projection strategy plan."""

from __future__ import annotations

from .edit_classifier import PromptEditClassifier
from .deferred_feedback_strategy import PromptDeferredFeedbackStrategy
from .direct_feedback_strategy import PromptDirectFeedbackStrategy
from .edit_pipeline_contracts import (
    PromptProjectionApplyPath,
    PromptProjectionSourceChangeApplyOutcome,
    PromptProjectionSourceChangeApplyRequest,
)
from .edit_strategy import PromptEditStrategy
from .edit_publication import PromptEditPublication
from .history_checkpoint_strategy import PromptHistoryCheckpointStrategy
from .incremental_reflow_strategy import PromptIncrementalReflowStrategy
from .incremental_edit_contracts import (
    PromptProjectionPlainTextApplyResult,
    PromptProjectionPlainTextApplyStatus,
)
from .observability import log_projection_timing, projection_observability_started_at
from .trailing_edit_strategy import PromptTrailingEditStrategy

_DIRECT_FEEDBACK_OUTCOME = PromptProjectionSourceChangeApplyOutcome(
    apply_path=PromptProjectionApplyPath.DEFERRED_FEEDBACK,
    direct_feedback_applied=True,
)


class PromptEditPipeline:
    """Own source-edit strategy execution and terminal outcome publication."""

    def __init__(
        self,
        *,
        direct_feedback_strategy: PromptDirectFeedbackStrategy,
        deferred_strategy: PromptDeferredFeedbackStrategy,
        history_strategy: PromptHistoryCheckpointStrategy,
        trailing_strategy: PromptTrailingEditStrategy,
        reflow_strategy: PromptIncrementalReflowStrategy,
        publication: PromptEditPublication,
        classifier: PromptEditClassifier | None = None,
    ) -> None:
        """Store focused strategies, publication, and allocation-free policy."""

        self._direct_feedback_strategy = direct_feedback_strategy
        self._deferred_strategy = deferred_strategy
        self._history_strategy = history_strategy
        self._trailing_strategy = trailing_strategy
        self._reflow_strategy = reflow_strategy
        self._publication = publication
        self._classifier = classifier or PromptEditClassifier()

    def apply(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> PromptProjectionSourceChangeApplyOutcome:
        """Execute the classifier's bounded strategy order."""

        strategy_plan = self._classifier.classify(request)
        if (
            strategy_plan.candidates[0] is PromptEditStrategy.DEFER_DIRECT_FEEDBACK
            and self._direct_feedback_strategy.try_defer_direct(request)
        ):
            return _DIRECT_FEEDBACK_OUTCOME
        started_at = projection_observability_started_at()
        incremental_attempted = False
        plain_result: PromptProjectionPlainTextApplyResult | None = None
        incremental_rejection_reason = ""
        previous_layout_identity = None
        previous_text = request.previous_source_text
        edit_start = request.source_edit_start
        edit_end = request.source_edit_end
        for strategy in strategy_plan.candidates:
            if strategy is PromptEditStrategy.RESTORE_CHECKPOINT:
                restored_document = self._history_strategy.try_restore(
                    request.restore_checkpoint,
                    blockers=request.restore_checkpoint_blockers,
                    expected_source_text=request.next_document_view.source_text,
                )
                if restored_document is not None:
                    self._publication.publish_checkpoint(restored_document)
                    return self._finish(
                        request,
                        started_at=started_at,
                        apply_path=PromptProjectionApplyPath.CHECKPOINT_RESTORE,
                        fast_projection_applied=True,
                        incremental_plain_edit_attempted=incremental_attempted,
                    )
            elif strategy is PromptEditStrategy.DEFER_DIRECT_FEEDBACK:
                if self._direct_feedback_strategy.try_defer_direct(request):
                    return _DIRECT_FEEDBACK_OUTCOME
            elif strategy is PromptEditStrategy.EXTEND_DEFERRED_WRAP:
                if request.direct_deferred_feedback_allowed and self._defer_wrap(
                    request
                ):
                    return self._finish_deferred(
                        request,
                        started_at=started_at,
                        incremental_plain_edit_attempted=incremental_attempted,
                    )
            elif strategy is PromptEditStrategy.TRAILING_PLAIN_DELETE:
                assert previous_text is not None
                assert edit_start is not None
                assert edit_end is not None
                previous_layout_identity = self._publication.current_layout_identity()
                trailing_result = self._trailing_strategy.try_plain_delete(
                    previous_text=previous_text,
                    next_text=request.text,
                    start=edit_start,
                    end=edit_end,
                )
                if trailing_result is not None:
                    self._publication.publish_plain_delete(
                        trailing_result,
                        start=edit_start,
                        end=edit_end,
                        previous_layout_identity=previous_layout_identity,
                    )
                    return self._finish_fast(
                        request,
                        started_at=started_at,
                        incremental_plain_edit_attempted=incremental_attempted,
                    )
            elif strategy is PromptEditStrategy.TRAILING_NEWLINE_DELETE:
                assert previous_text is not None
                assert edit_start is not None
                assert edit_end is not None
                trailing_result = self._trailing_strategy.try_newline_delete(
                    previous_text=previous_text,
                    next_text=request.text,
                    start=edit_start,
                    end=edit_end,
                )
                if trailing_result is not None:
                    self._publication.publish_newline_delete(trailing_result)
                    return self._finish_fast(
                        request,
                        started_at=started_at,
                        incremental_plain_edit_attempted=incremental_attempted,
                    )
            elif strategy is PromptEditStrategy.TRAILING_NEWLINE_INSERT:
                assert previous_text is not None
                assert edit_start is not None
                assert edit_end is not None
                trailing_result = self._trailing_strategy.try_newline_insert(
                    document_view=request.next_document_view,
                    render_plan=request.next_render_plan,
                    previous_text=previous_text,
                    start=edit_start,
                    end=edit_end,
                )
                if trailing_result is not None:
                    self._publication.publish_trailing_insert(
                        trailing_result,
                        cache_reason="projection_fast_newline_insert",
                    )
                    return self._finish_fast(
                        request,
                        started_at=started_at,
                        incremental_plain_edit_attempted=incremental_attempted,
                    )
            elif strategy is PromptEditStrategy.TRAILING_PLAIN_INSERT:
                incremental_attempted = True
                trailing_result = self._trailing_strategy.try_plain_insert(
                    document_view=request.next_document_view,
                    render_plan=request.next_render_plan,
                )
                if trailing_result is not None:
                    self._publication.publish_trailing_insert(
                        trailing_result,
                        cache_reason="projection_fast_insert",
                    )
                    return self._finish_fast(
                        request,
                        started_at=started_at,
                        incremental_plain_edit_attempted=incremental_attempted,
                    )
            elif strategy is PromptEditStrategy.INCREMENTAL_PLAIN:
                incremental_attempted = True
                assert previous_text is not None
                assert edit_start is not None
                assert edit_end is not None
                previous_layout_identity = self._publication.current_layout_identity()
                replacement_text = request.source_edit_replacement_text or ""
                plain_result = self._reflow_strategy.try_incremental(
                    previous_text=previous_text,
                    next_text=request.text,
                    start=edit_start,
                    end=edit_end,
                    replacement_text=replacement_text,
                )
                incremental_rejection_reason = plain_result.rejection_reason
                if plain_result.status is PromptProjectionPlainTextApplyStatus.APPLIED:
                    self._publication.publish_incremental(
                        plain_result,
                        start=edit_start,
                        end=edit_end,
                        replacement_text=replacement_text,
                        previous_layout_identity=previous_layout_identity,
                    )
                    return self._finish(
                        request,
                        started_at=started_at,
                        apply_path=PromptProjectionApplyPath.INCREMENTAL,
                        fast_projection_applied=True,
                        incremental_plain_edit_attempted=incremental_attempted,
                        incremental_rejection_reason=incremental_rejection_reason,
                    )
                if (
                    plain_result.status
                    is PromptProjectionPlainTextApplyStatus.APPLIED_REFLOW
                ):
                    self._publication.publish_reflow(plain_result)
                    return self._finish(
                        request,
                        started_at=started_at,
                        apply_path=PromptProjectionApplyPath.REFLOW,
                        fast_projection_applied=True,
                        incremental_plain_edit_attempted=incremental_attempted,
                        incremental_rejection_reason=incremental_rejection_reason,
                    )
            elif strategy is PromptEditStrategy.DEFER_INCREMENTAL_WRAP:
                if (
                    plain_result is not None
                    and plain_result.status
                    is PromptProjectionPlainTextApplyStatus.DEFERRED_WRAP_REFLOW
                    and request.direct_deferred_feedback_allowed
                    and self._defer_wrap(request)
                ):
                    return self._finish_deferred(
                        request,
                        started_at=started_at,
                        incremental_plain_edit_attempted=incremental_attempted,
                        incremental_rejection_reason=incremental_rejection_reason,
                    )
            elif strategy is PromptEditStrategy.DEFER_TRANSIENT_FALLBACK:
                if self._deferred_strategy.try_defer_fallback(request):
                    return self._finish_deferred(
                        request,
                        started_at=started_at,
                        incremental_plain_edit_attempted=incremental_attempted,
                        incremental_rejection_reason=incremental_rejection_reason,
                    )
            elif strategy is PromptEditStrategy.PUBLISH_PREBUILT_REFLOW:
                applied_reflow = (
                    None
                    if plain_result is None
                    else self._reflow_strategy.apply_prebuilt(plain_result, request)
                )
                if applied_reflow is not None:
                    self._publication.publish_reflow(applied_reflow)
                    return self._finish(
                        request,
                        started_at=started_at,
                        apply_path=PromptProjectionApplyPath.REFLOW,
                        fast_projection_applied=True,
                        incremental_plain_edit_attempted=incremental_attempted,
                        incremental_rejection_reason=incremental_rejection_reason,
                    )
            elif strategy is PromptEditStrategy.BUILD_CANONICAL_REFLOW:
                canonical_reflow = self._reflow_strategy.try_canonical(request)
                if canonical_reflow is not None:
                    self._publication.publish_reflow(canonical_reflow)
                    return self._finish(
                        request,
                        started_at=started_at,
                        apply_path=PromptProjectionApplyPath.REFLOW,
                        fast_projection_applied=True,
                        incremental_plain_edit_attempted=incremental_attempted,
                        incremental_rejection_reason=incremental_rejection_reason,
                    )
            elif strategy is PromptEditStrategy.FULL_REBUILD:
                self._publication.rebuild_projection()
                return self._finish(
                    request,
                    started_at=started_at,
                    apply_path=PromptProjectionApplyPath.FULL_REBUILD,
                    fast_projection_applied=False,
                    incremental_plain_edit_attempted=incremental_attempted,
                    incremental_rejection_reason=incremental_rejection_reason,
                )
        raise RuntimeError("Prompt edit strategy plan has no terminal fallback.")

    def _defer_wrap(self, request: PromptProjectionSourceChangeApplyRequest) -> bool:
        """Try the wrap-only scheduling strategy."""

        return self._deferred_strategy.defer_wrap(
            previous_document_view=request.previous_document_view,
            previous_render_plan=request.previous_render_plan,
        )

    def _finish_fast(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
        *,
        started_at: float,
        incremental_plain_edit_attempted: bool,
    ) -> PromptProjectionSourceChangeApplyOutcome:
        """Return one successful trailing-strategy outcome."""

        return self._finish(
            request,
            started_at=started_at,
            apply_path=PromptProjectionApplyPath.FAST_TRAILING,
            fast_projection_applied=True,
            incremental_plain_edit_attempted=incremental_plain_edit_attempted,
        )

    def _finish_deferred(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
        *,
        started_at: float,
        incremental_plain_edit_attempted: bool,
        incremental_rejection_reason: str = "",
    ) -> PromptProjectionSourceChangeApplyOutcome:
        """Return one successful deferred-strategy outcome."""

        return self._finish(
            request,
            started_at=started_at,
            apply_path=PromptProjectionApplyPath.DEFERRED_WRAP,
            fast_projection_applied=False,
            wrap_reflow_deferred=True,
            incremental_plain_edit_attempted=incremental_plain_edit_attempted,
            incremental_rejection_reason=incremental_rejection_reason,
        )

    def _finish(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
        *,
        started_at: float,
        apply_path: PromptProjectionApplyPath,
        fast_projection_applied: bool,
        direct_feedback_applied: bool = False,
        wrap_reflow_deferred: bool = False,
        incremental_plain_edit_attempted: bool,
        incremental_rejection_reason: str = "",
    ) -> PromptProjectionSourceChangeApplyOutcome:
        """Publish cache consequences, timing, and one typed outcome."""

        if (
            request.can_preserve_diagnostic_fragment_cache
            and wrap_reflow_deferred
            and not fast_projection_applied
        ):
            self._publication.clear_diagnostic_fragment_cache(
                reason="source_changed_deferred_projection"
            )
        log_projection_timing(
            "incremental_apply.source_change",
            started_at=started_at,
            text_length=len(request.text),
            apply_path=apply_path.value,
            fast_projection_applied=fast_projection_applied,
            wrap_reflow_deferred=wrap_reflow_deferred,
            incremental_plain_edit_attempted=incremental_plain_edit_attempted,
        )
        return PromptProjectionSourceChangeApplyOutcome(
            apply_path=apply_path,
            fast_projection_applied=fast_projection_applied,
            direct_feedback_applied=direct_feedback_applied,
            wrap_reflow_deferred=wrap_reflow_deferred,
            incremental_rejection_reason=incremental_rejection_reason,
        )


__all__ = ["PromptEditPipeline"]
