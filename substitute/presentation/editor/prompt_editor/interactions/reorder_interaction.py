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

"""Coordinate reorder intents across application policy and one Qt overlay session."""

from __future__ import annotations

from typing import Protocol

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.application.prompt_editor.reorder.intents import (
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderKeyboardMoveIntent,
)
from substitute.application.prompt_editor.reorder.lifecycle import (
    PromptReorderLifecycleOwner,
)
from substitute.application.prompt_editor.reorder.session import (
    PromptReorderCommitOutcome,
    PromptReorderCommitSnapshot,
    PromptReorderSessionState,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from ..models import PromptEditorInteractionMode
from ..projection.observability import log_reorder_drag_timing, reorder_drag_started_at
from .reorder_commit_execution import (
    PromptReorderCommandResultPort,
    PromptReorderCommandSurface,
    PromptReorderCommitExecutor,
)
from .reorder_overlay_port import PromptReorderOverlayFactory, PromptReorderOverlayPort
from .reorder_overlay_session import (
    PromptReorderOverlaySessionEditor,
    PromptReorderOverlaySessionHost,
    PromptReorderOverlaySessionOwner,
)
from .reorder_preview_publication import PromptReorderPreviewPublicationOwner


class PromptReorderInteractionEditor(
    PromptReorderCommandSurface,
    PromptReorderOverlaySessionEditor,
    Protocol,
):
    """Expose the narrow editor ports required by complete reorder interaction."""

    def prompt_command_source_identity(self) -> PromptSourceIdentity | None:
        """Return the current source identity for stale-safe reorder commit policy."""


class PromptReorderInteractionHost(
    PromptReorderCommandResultPort,
    PromptReorderOverlaySessionHost,
    Protocol,
):
    """Expose application-host facts required by reorder entry and result adoption."""


class PromptReorderInteractionOwner:
    """Own complete reorder intent coordination without overlay construction details."""

    def __init__(
        self,
        editor: PromptReorderInteractionEditor,
        *,
        host: PromptReorderInteractionHost,
        document_service: PromptDocumentService,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
        preview_publication: PromptReorderPreviewPublicationOwner,
        overlay_factory: PromptReorderOverlayFactory,
    ) -> None:
        """Compose application lifecycle, Qt session, and command execution owners."""

        self._editor = editor
        self._lifecycle = PromptReorderLifecycleOwner(document_service)
        self._overlay_session = PromptReorderOverlaySessionOwner(
            editor,
            host=host,
            document_service=document_service,
            lifecycle=self._lifecycle,
            preview_publication=preview_publication,
            overlay_factory=overlay_factory,
        )
        self._commit_executor = PromptReorderCommitExecutor(
            editor,
            result_port=host,
            mutation_service=mutation_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
        )

    @property
    def segment_overlay(self) -> PromptReorderOverlayPort | None:
        """Return the session-owned overlay for the outer interaction adapter."""

        return self._overlay_session.overlay

    @property
    def interaction_mode(self) -> PromptEditorInteractionMode:
        """Return the mode held by the presentation overlay session."""

        return self._overlay_session.interaction_mode

    @property
    def segment_reorder_session(self) -> PromptReorderSessionState:
        """Return immutable application session truth for owner-level contracts."""

        return self._lifecycle.session_state

    @property
    def latest_commit_snapshot(self) -> PromptReorderCommitSnapshot | None:
        """Return the latest application-owned commit snapshot."""

        return self._lifecycle.latest_commit_snapshot

    def enter(self) -> None:
        """Enter one presentation reorder session when entry policy permits it."""

        self._overlay_session.enter()

    def cancel(self, intent: PromptReorderCancelIntent) -> None:
        """Cancel one active presentation session without mutating prompt source."""

        self._overlay_session.cancel(intent)

    def commit(self, intent: PromptReorderCommitIntent) -> None:
        """Resolve, close, execute, and publish one typed reorder commit intent."""

        total_started_at = reorder_drag_started_at()
        snapshot = (
            intent.snapshot
            or self._lifecycle.latest_commit_snapshot
            or self._overlay_session.commit_snapshot()
        )
        if snapshot is None:
            log_reorder_drag_timing(
                "interaction.commit_segment_overlay.noop",
                started_at=total_started_at,
                reason="no_overlay",
                intent_reason=intent.reason,
            )
            return
        source_identity = self._editor.prompt_command_source_identity()
        commit_plan = self._lifecycle.resolve_commit(
            snapshot,
            source_revision=(
                None if source_identity is None else source_identity.source_revision
            ),
            source_length=(
                None if source_identity is None else source_identity.source_length
            ),
        )
        if commit_plan.outcome is PromptReorderCommitOutcome.UNCHANGED:
            self._overlay_session.close(commit_plan.close_transition)
            log_reorder_drag_timing(
                "interaction.commit_segment_overlay.noop",
                started_at=total_started_at,
                reason="unchanged_order",
                intent_reason=intent.reason,
            )
            return
        if commit_plan.outcome is PromptReorderCommitOutcome.MISSING_STATE:
            self._overlay_session.close(commit_plan.close_transition)
            log_reorder_drag_timing(
                "interaction.commit_segment_overlay.noop",
                started_at=total_started_at,
                reason="missing_reorder_state",
                intent_reason=intent.reason,
            )
            return
        request = commit_plan.request
        if request is None:
            raise RuntimeError("Commit policy approved reorder without a request.")
        relative_selection_available = (
            request.selection_start_offset_within_selected_chip is not None
            and request.selection_end_offset_within_selected_chip is not None
        )
        phase_started_at = reorder_drag_started_at()
        self._overlay_session.close(commit_plan.close_transition)
        close_elapsed_ms = log_reorder_drag_timing(
            "interaction.commit_segment_overlay.close",
            started_at=phase_started_at,
            relative_selection_available=relative_selection_available,
            intent_reason=intent.reason,
        )
        execution = self._commit_executor.execute(request, reason=intent.reason)
        log_reorder_drag_timing(
            "interaction.commit_segment_overlay.total",
            started_at=total_started_at,
            relative_selection_available=relative_selection_available,
            intent_reason=intent.reason,
            close_elapsed_ms=f"{close_elapsed_ms:.3f}",
            command_elapsed_ms=f"{execution.command_elapsed_ms:.3f}",
            apply_elapsed_ms=f"{execution.apply_elapsed_ms:.3f}",
        )

    def move_keyboard(self, intent: PromptReorderKeyboardMoveIntent) -> None:
        """Apply one keyboard move through the active overlay session."""

        self._overlay_session.move_keyboard(intent)

    def position(self) -> None:
        """Align the active overlay session with the visible editor viewport."""

        self._overlay_session.position()


__all__ = [
    "PromptReorderInteractionEditor",
    "PromptReorderInteractionHost",
    "PromptReorderInteractionOwner",
]
