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

"""Compose projection source-state owners for the prompt projection surface."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptEditorDocumentState,
)

from .applicator import PromptProjectionApplicator
from .deferred_feedback_strategy import (
    PromptDeferredFeedbackContext,
    PromptDeferredFeedbackStrategy,
)
from .direct_feedback_strategy import (
    PromptDirectFeedbackContext,
    PromptDirectFeedbackStrategy,
)
from .edit_pipeline import PromptEditPipeline
from .edit_publication import PromptEditPublication, PromptEditPublicationSink
from .freshness_controller import PromptProjectionFreshnessController
from .frame_state import PromptProjectionFrameStatePublisher
from .history_checkpoint_strategy import PromptHistoryCheckpointStrategy
from .incremental_reflow_strategy import PromptIncrementalReflowStrategy
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .prompt_state_applier import (
    PromptProjectionPromptStateApplier,
    PromptProjectionPromptStateHost,
)
from .projection_build_context import PromptProjectionBuildContext
from .prompt_state_projection_strategy import PromptStateProjectionStrategy
from .semantic_transition_strategy import PromptSemanticTransitionStrategy
from .semantic_remap import PromptProjectionSemanticRemapper
from .session import PromptProjectionSession
from .source_line_chrome import PromptSourceLineChrome
from .source_projection_application import PromptSourceProjectionApplication
from .source_commit_application import PromptProjectionSourceCommitApplication
from .source_change_transaction import (
    PromptProjectionSourceChangeTransaction,
)
from .source_commit_ports import (
    PromptSourceChangeCaretSink,
    PromptSourceChangeEffectSink,
    PromptSourceReplacementPointerSink,
)
from .source_document_commit_application import (
    PromptSourceDocumentCommitApplication,
    PromptSourceDocumentCommitEffectSink,
)
from .source_edit_projection_facts import (
    PromptSourceEditProjectionFactContext,
    PromptSourceEditProjectionFactResolver,
)
from .source_history_commit_application import PromptSourceHistoryCommitApplication
from .source_range_commit_application import PromptSourceRangeCommitApplication
from .source_document import PromptProjectionSourceDocument
from .transient_edit_overlays import PromptProjectionTransientEditOverlayController
from .trailing_edit_strategy import PromptTrailingEditStrategy
from .undo_payload import PromptProjectionUndoPayload
from .update_scheduler import PendingProjectionUpdate


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceStateOwners:
    """Carry the source-state owners extracted from the projection surface."""

    source_document: PromptProjectionSourceDocument
    source_commit_application: PromptProjectionSourceCommitApplication[
        PromptProjectionUndoPayload
    ]
    transient_edit_overlays: PromptProjectionTransientEditOverlayController
    freshness_controller: PromptProjectionFreshnessController
    edit_pipeline: PromptEditPipeline
    prompt_state_applier: PromptProjectionPromptStateApplier


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceStateBindings:
    """Name every source-state dependency supplied by the composition root."""

    applicator: PromptProjectionApplicator
    editor_state: PromptEditorDocumentState[
        PromptDocumentView,
        PromptSyntaxRenderPlan,
        PromptProjectionDocument,
    ]
    layout: PromptLayoutEditToFrameCoordinator
    source_line_chrome: PromptSourceLineChrome
    session: PromptProjectionSession
    pointer_sink: PromptSourceReplacementPointerSink
    publication_sink: PromptEditPublicationSink
    build_context: PromptProjectionBuildContext
    direct_feedback_context: PromptDirectFeedbackContext
    deferred_feedback_context: PromptDeferredFeedbackContext
    prompt_state_host: PromptProjectionPromptStateHost
    fact_context: PromptSourceEditProjectionFactContext
    source_effect_sink: PromptSourceChangeEffectSink
    source_caret_sink: PromptSourceChangeCaretSink
    document_effect_sink: PromptSourceDocumentCommitEffectSink


class _PromptProjectionScheduledUpdateSink:
    """Forward scheduled projection updates after the prompt-state owner exists."""

    def __init__(self) -> None:
        """Create an unwired scheduled update sink."""

        self._applier: PromptProjectionPromptStateApplier | None = None

    def wire(self, applier: PromptProjectionPromptStateApplier) -> None:
        """Attach the prompt-state applier after owner construction."""

        self._applier = applier

    def apply_update(self, update: PendingProjectionUpdate) -> None:
        """Apply one scheduled update through the prompt-state owner."""

        if self._applier is None:
            raise RuntimeError("Prompt projection prompt-state applier is not wired.")
        self._applier.apply_scheduled_projection_update(update)


def build_prompt_projection_source_state_owners(
    bindings: PromptProjectionSourceStateBindings,
    *,
    parent: QObject,
    frame_state: PromptProjectionFrameStatePublisher,
) -> PromptProjectionSourceStateOwners:
    """Build projection source-state owners around a viewport/paint host."""

    scheduled_update_sink = _PromptProjectionScheduledUpdateSink()
    source_document = PromptProjectionSourceDocument(parent=parent)
    transient_edit_overlays = PromptProjectionTransientEditOverlayController()
    freshness_controller = PromptProjectionFreshnessController(
        apply_update=scheduled_update_sink.apply_update,
        parent=parent,
    )
    trailing_strategy = PromptTrailingEditStrategy(
        applicator=bindings.applicator,
        editor_state=bindings.editor_state,
        layout=bindings.layout,
    )
    publication = PromptEditPublication(
        bindings.publication_sink,
        editor_state=bindings.editor_state,
        frame_state=frame_state,
        layout=bindings.layout,
    )
    reflow_strategy = PromptIncrementalReflowStrategy(
        bindings.build_context,
        applicator=bindings.applicator,
        editor_state=bindings.editor_state,
        layout=bindings.layout,
    )
    semantic_transition = PromptSemanticTransitionStrategy(
        bindings.build_context,
        applicator=bindings.applicator,
        editor_state=bindings.editor_state,
        layout=bindings.layout,
    )
    history_strategy = PromptHistoryCheckpointStrategy(bindings.layout)
    direct_feedback_strategy = PromptDirectFeedbackStrategy(
        bindings.direct_feedback_context,
        editor_state=bindings.editor_state,
        freshness=freshness_controller,
        layout=bindings.layout,
        overlays=transient_edit_overlays,
    )
    deferred_strategy = PromptDeferredFeedbackStrategy(
        bindings.deferred_feedback_context,
        editor_state=bindings.editor_state,
        freshness=freshness_controller,
        layout=bindings.layout,
        overlays=transient_edit_overlays,
        source_line_chrome=bindings.source_line_chrome,
    )
    edit_pipeline = PromptEditPipeline(
        direct_feedback_strategy=direct_feedback_strategy,
        deferred_strategy=deferred_strategy,
        history_strategy=history_strategy,
        trailing_strategy=trailing_strategy,
        reflow_strategy=reflow_strategy,
        publication=publication,
    )
    prompt_state_strategy = PromptStateProjectionStrategy(
        semantic_transition,
        trailing_strategy=trailing_strategy,
        reflow_strategy=reflow_strategy,
        publication=publication,
    )
    prompt_state_applier = PromptProjectionPromptStateApplier(
        bindings.prompt_state_host,
        frame_state=frame_state,
        strategy=prompt_state_strategy,
    )
    scheduled_update_sink.wire(prompt_state_applier)
    projection_facts = PromptSourceEditProjectionFactResolver(
        bindings.fact_context,
        applicator=bindings.applicator,
        editor_state=bindings.editor_state,
        freshness=freshness_controller,
        layout=bindings.layout,
        overlays=transient_edit_overlays,
    )
    semantic_remapper = PromptProjectionSemanticRemapper()
    source_projection_application = PromptSourceProjectionApplication(
        bindings.source_effect_sink,
        bindings.source_caret_sink,
        editor_state=bindings.editor_state,
        freshness=freshness_controller,
        pipeline=edit_pipeline,
        overlays=transient_edit_overlays,
    )
    source_change_transaction = PromptProjectionSourceChangeTransaction[
        PromptProjectionUndoPayload
    ](
        bindings.source_effect_sink,
        bindings.pointer_sink,
        editor_state=bindings.editor_state,
        freshness=freshness_controller,
        projection_application=source_projection_application,
        semantic_remapper=semantic_remapper,
        session=bindings.session,
        source_document=source_document,
    )
    range_application = PromptSourceRangeCommitApplication[PromptProjectionUndoPayload](
        bindings.source_caret_sink,
        editor_state=bindings.editor_state,
        projection_facts=projection_facts,
        semantic_remapper=semantic_remapper,
        session=bindings.session,
        transaction=source_change_transaction,
    )
    history_application = PromptSourceHistoryCommitApplication[
        PromptProjectionUndoPayload
    ](
        bindings.source_effect_sink,
        bindings.source_caret_sink,
        editor_state=bindings.editor_state,
        freshness=freshness_controller,
        projection_application=source_projection_application,
        session=bindings.session,
        source_document=source_document,
    )
    document_application = PromptSourceDocumentCommitApplication[
        PromptProjectionUndoPayload
    ](
        bindings.document_effect_sink,
        bindings.source_caret_sink,
        transaction=source_change_transaction,
    )
    source_commit_application = PromptProjectionSourceCommitApplication[
        PromptProjectionUndoPayload
    ](
        document=document_application,
        history=history_application,
        range_edit=range_application,
    )
    return PromptProjectionSourceStateOwners(
        source_document=source_document,
        source_commit_application=source_commit_application,
        transient_edit_overlays=transient_edit_overlays,
        freshness_controller=freshness_controller,
        edit_pipeline=edit_pipeline,
        prompt_state_applier=prompt_state_applier,
    )


__all__ = [
    "PromptProjectionSourceStateBindings",
    "PromptProjectionSourceStateOwners",
    "build_prompt_projection_source_state_owners",
]
