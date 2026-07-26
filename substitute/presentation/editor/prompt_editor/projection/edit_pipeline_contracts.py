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

"""Define immutable source-edit pipeline requests and outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from ..layout.checkpoints import PromptProjectionLayoutCheckpoint
from ..core.projection.caret import PromptProjectionCaretState
from .edit_strategy import PromptSourceEditKind
from .freshness_controller import (
    ProjectionFreshness,
    PromptProjectionFreshnessBlockers,
)
from .transient_edit_overlays import PromptProjectionTransientDeletionOverlay
from .source_edit_projection_policy import PromptSourceEditProjectionDecision


class PromptProjectionApplyPath(Enum):
    """Name the projection apply path selected for one source-state update."""

    PAINT_ONLY = "paint_only"
    SCHEDULED = "scheduled"
    FAST_TRAILING = "fast_trailing"
    INCREMENTAL = "incremental"
    REFLOW = "reflow"
    CHECKPOINT_RESTORE = "checkpoint_restore"
    DEFERRED_FEEDBACK = "deferred_feedback"
    DEFERRED_WRAP = "deferred_wrap"
    FULL_REBUILD = "full_rebuild"
    DROPPED_STALE = "dropped_stale"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceChangeApplyRequest:
    """Carry one committed source edit and its already-computed strategy facts."""

    text: str
    previous_source_text: str | None
    previous_source_identity: PromptSourceIdentity
    source_edit_start: int | None
    source_edit_end: int | None
    source_edit_replacement_text: str | None
    previous_projection_freshness: ProjectionFreshness
    previous_document_view: PromptDocumentView
    previous_render_plan: PromptSyntaxRenderPlan
    next_document_view: PromptDocumentView
    next_render_plan: PromptSyntaxRenderPlan
    previous_deletion_overlay: PromptProjectionTransientDeletionOverlay | None
    next_cursor_state: PromptProjectionCaretState
    next_anchor_state: PromptProjectionCaretState
    can_preserve_diagnostic_fragment_cache: bool
    projection_deferral_reason: str
    region_structure_requires_rebuild: bool
    edit_kind: PromptSourceEditKind
    deferred_plain_edit_extendable: bool
    wrap_reflow_deferrable: bool
    projection_decision: PromptSourceEditProjectionDecision | None = None
    restore_checkpoint: PromptProjectionLayoutCheckpoint | None = None
    restore_checkpoint_blockers: PromptProjectionFreshnessBlockers | None = None

    @property
    def restore_checkpoint_available(self) -> bool:
        """Return whether exact history geometry is available for this edit."""

        return self.restore_checkpoint is not None

    @property
    def direct_deferred_feedback_allowed(self) -> bool:
        """Return whether this edit may publish feedback before layout."""

        decision = self.projection_decision
        return bool(decision is not None and decision.can_defer_projection)

    @property
    def projection_topology_requires_rebuild(self) -> bool:
        """Return whether the source edit changes canonical projection topology."""

        decision = self.projection_decision
        return bool(
            decision is not None and decision.projection_topology_requires_rebuild
        )

    @property
    def typed_character_requires_immediate_projection(self) -> bool:
        """Return the already-resolved typed-character syntax fact."""

        decision = self.projection_decision
        return bool(
            decision is not None and decision.typed_character_requires_projection
        )

    @property
    def syntax_sensitive_prefix_deferrable(self) -> bool:
        """Return the already-resolved incomplete-syntax deferral fact."""

        decision = self.projection_decision
        return bool(
            decision is not None and decision.syntax_sensitive_prefix_deferrable
        )


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceChangeApplyOutcome:
    """Describe how projection state handled one committed source edit."""

    apply_path: PromptProjectionApplyPath
    fast_projection_applied: bool = False
    direct_feedback_applied: bool = False
    wrap_reflow_deferred: bool = False
    incremental_rejection_reason: str = ""


__all__ = [
    "PromptProjectionApplyPath",
    "PromptProjectionSourceChangeApplyOutcome",
    "PromptProjectionSourceChangeApplyRequest",
]
