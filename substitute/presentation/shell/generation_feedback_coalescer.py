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

"""Coalesce generation feedback before it reaches expensive UI rendering."""

from __future__ import annotations

from dataclasses import dataclass, field

from substitute.application.generation import (
    GenerationFailure,
    GenerationRunStarted,
    VisualAuthorizationService,
)
from substitute.application.generation.progress_service import ProgressViewState
from substitute.application.generation.workflow_progress_service import (
    GenerationProgressRetirementReason,
    WorkflowProgressIdentity as GenerationProgressIdentity,
    WorkflowProgressService,
)
from substitute.application.ports import (
    GenerationExecutionTiming,
    GenerationVisualIdentity,
    ListenerCompleted,
    ModelLoadProgressUpdate,
    OutputImageUpdate,
    PreviewImageUpdate,
    ProgressUpdate,
)
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    LivePreviewEvent,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.shell.generation_feedback_coalescer")


@dataclass(frozen=True)
class FeedbackFlushIntent:
    """Describe whether a submitted feedback event requires immediate rendering."""

    flush_now: bool = False

    @classmethod
    def schedule(cls) -> "FeedbackFlushIntent":
        """Return an intent for normal timer-based UI delivery."""

        return cls(flush_now=False)

    @classmethod
    def immediate(cls) -> "FeedbackFlushIntent":
        """Return an intent for immediate GUI-thread UI delivery."""

        return cls(flush_now=True)


@dataclass(frozen=True)
class GenerationFeedbackBatch:
    """Capture one drained group of generation feedback updates."""

    progress_states: tuple[ProgressViewState, ...] = ()
    progress_updates: tuple[ProgressUpdate, ...] = ()
    model_load_updates: tuple[ModelLoadProgressUpdate, ...] = ()
    preview_updates: tuple[LivePreviewEvent, ...] = ()
    output_image_updates: tuple[LiveFinalOutputEvent, ...] = ()
    timing_updates: tuple[GenerationExecutionTiming, ...] = ()
    failures: tuple[GenerationFailure, ...] = ()
    completed_events: tuple[ListenerCompleted, ...] = ()

    def is_empty(self) -> bool:
        """Return whether this batch has no pending feedback to apply."""

        return not (
            self.progress_states
            or self.progress_updates
            or self.model_load_updates
            or self.preview_updates
            or self.output_image_updates
            or self.timing_updates
            or self.failures
            or self.completed_events
        )


@dataclass(frozen=True)
class GenerationFeedbackPendingCounts:
    """Expose pending feedback categories for dispatcher scheduling decisions."""

    progress_count: int = 0
    model_load_count: int = 0
    preview_count: int = 0
    output_image_count: int = 0
    timing_count: int = 0
    failure_count: int = 0
    completed_count: int = 0


@dataclass(frozen=True, slots=True)
class GenerationProgressRetirement:
    """Describe an explicit request to retire shell generation progress."""

    reason: GenerationProgressRetirementReason
    workflow_id: str | None = None
    generation_run_id: str | None = None
    prompt_id: str | None = None
    client_id: str | None = None


@dataclass(frozen=True, slots=True)
class _ActiveGenerationRun:
    """Identify the prompt currently allowed to update one workflow."""

    workflow_id: str
    generation_run_id: str
    prompt_id: str
    client_id: str


@dataclass(frozen=True, slots=True)
class VisualLaneKey:
    """Identify one preview/final-output lane inside one generation run."""

    workflow_id: str
    generation_run_id: str
    prompt_id: str
    source_key: str
    scene_run_id: str | None
    scene_key: str | None
    list_index: int | None

    def source_level(self) -> "VisualLaneKey":
        """Return the less-specific lane for ambiguous source previews."""

        return VisualLaneKey(
            workflow_id=self.workflow_id,
            generation_run_id=self.generation_run_id,
            prompt_id=self.prompt_id,
            source_key=self.source_key,
            scene_run_id=self.scene_run_id,
            scene_key=self.scene_key,
            list_index=None,
        )


@dataclass
class GenerationFeedbackCoalescer:
    """Coalesce high-rate generation feedback before UI rendering."""

    _workflow_progress: WorkflowProgressService = field(
        default_factory=WorkflowProgressService
    )
    _pending_progress_by_workflow: dict[str, ProgressUpdate] = field(
        default_factory=dict
    )
    _pending_retirement_by_workflow: dict[str, ProgressViewState] = field(
        default_factory=dict
    )
    _progress_seen_by_workflow: set[str] = field(default_factory=set)
    _sampler_started_by_workflow: set[str] = field(default_factory=set)
    _model_load_updates: dict[
        tuple[str, str, str, str],
        ModelLoadProgressUpdate,
    ] = field(default_factory=dict)
    _preview_updates: dict[
        VisualLaneKey,
        LivePreviewEvent,
    ] = field(default_factory=dict)
    _output_image_updates: list[LiveFinalOutputEvent] = field(default_factory=list)
    _timing_updates: list[GenerationExecutionTiming] = field(default_factory=list)
    _failures: list[GenerationFailure] = field(default_factory=list)
    _completed_events: list[ListenerCompleted] = field(default_factory=list)
    _active_runs: dict[str, _ActiveGenerationRun] = field(default_factory=dict)
    _finalized_lanes: set[VisualLaneKey] = field(default_factory=set)
    _finalized_source_lanes: set[VisualLaneKey] = field(default_factory=set)
    _visual_authorization: VisualAuthorizationService | None = None

    def submit_run_started(
        self,
        event: GenerationRunStarted,
    ) -> FeedbackFlushIntent:
        """Register the prompt/run that is allowed to update a workflow."""

        retirement = self._workflow_progress.register_run(event)
        self._pending_progress_by_workflow.pop(event.workflow_id, None)
        self._progress_seen_by_workflow.discard(event.workflow_id)
        self._sampler_started_by_workflow.discard(event.workflow_id)
        if retirement is not None:
            self._pending_retirement_by_workflow[event.workflow_id] = retirement
        self._active_runs[event.workflow_id] = _ActiveGenerationRun(
            workflow_id=event.workflow_id,
            generation_run_id=event.generation_run_id,
            prompt_id=event.prompt_id,
            client_id=event.client_id,
        )
        if self._visual_authorization is not None:
            self._visual_authorization.register_run(
                workflow_id=event.workflow_id,
                generation_run_id=event.generation_run_id,
                prompt_id=event.prompt_id,
                client_id=event.client_id,
            )
        log_debug(
            _LOGGER,
            "Generation feedback run registered",
            workflow_id=event.workflow_id,
            generation_run_id=event.generation_run_id,
            prompt_id=event.prompt_id,
            client_id=event.client_id,
        )
        self._discard_nonessential_workflow_updates(event.workflow_id)
        self._finalized_lanes = {
            key for key in self._finalized_lanes if key.workflow_id != event.workflow_id
        }
        self._finalized_source_lanes = {
            key
            for key in self._finalized_source_lanes
            if key.workflow_id != event.workflow_id
        }
        if retirement is not None:
            return FeedbackFlushIntent.immediate()
        return FeedbackFlushIntent.schedule()

    def submit_progress(self, update: ProgressUpdate) -> FeedbackFlushIntent:
        """Store the newest progress update and request urgent flushes for boundaries."""

        if self._workflow_progress.apply_update(update) is None:
            return FeedbackFlushIntent.schedule()
        first_update = update.workflow_id not in self._progress_seen_by_workflow
        sampler_started = (
            update.workflow_id not in self._sampler_started_by_workflow
            and update.sampler_percent is not None
            and update.sampler_percent > 0
        )
        completed = (
            update.workflow_percent is not None and update.workflow_percent >= 100.0
        )
        self._pending_progress_by_workflow[update.workflow_id] = update
        self._pending_retirement_by_workflow.pop(update.workflow_id, None)
        self._progress_seen_by_workflow.add(update.workflow_id)
        if sampler_started:
            self._sampler_started_by_workflow.add(update.workflow_id)
        if first_update or sampler_started or completed:
            return FeedbackFlushIntent.immediate()
        return FeedbackFlushIntent.schedule()

    def retire_progress(
        self,
        *,
        reason: GenerationProgressRetirementReason,
        workflow_id: str | None = None,
        generation_run_id: str | None = None,
        prompt_id: str | None = None,
        client_id: str | None = None,
    ) -> FeedbackFlushIntent:
        """Retire active progress and schedule hidden presentation state."""

        if workflow_id is None:
            retirements = self._workflow_progress.retire_all(reason=reason)
            self._pending_progress_by_workflow.clear()
            self._progress_seen_by_workflow.clear()
            self._sampler_started_by_workflow.clear()
            if retirements:
                self._pending_retirement_by_workflow.update(
                    {state.workflow_id or "": state for state in retirements}
                )
            else:
                self._pending_retirement_by_workflow[""] = ProgressViewState.hidden()
            return FeedbackFlushIntent.immediate()
        retirement = self._workflow_progress.retire_progress(
            reason=reason,
            workflow_id=workflow_id,
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            client_id=client_id,
        )
        if retirement is None:
            return FeedbackFlushIntent.schedule()
        self._pending_progress_by_workflow.pop(workflow_id, None)
        self._pending_retirement_by_workflow[workflow_id] = retirement
        self._progress_seen_by_workflow.discard(workflow_id)
        self._sampler_started_by_workflow.discard(workflow_id)
        return FeedbackFlushIntent.immediate()

    def submit_model_load_progress(
        self,
        update: ModelLoadProgressUpdate,
    ) -> FeedbackFlushIntent:
        """Store newest model-load progress and flush only terminal transitions."""

        key = self._model_load_key(update)
        self._model_load_updates[key] = update
        if _is_terminal_model_load_update(update):
            return FeedbackFlushIntent.immediate()
        return FeedbackFlushIntent.schedule()

    def submit_preview(self, update: PreviewImageUpdate) -> FeedbackFlushIntent:
        """Store only the newest preview image for one visible preview slot."""

        live_event = LivePreviewEvent.from_update(update)
        if live_event is None:
            self._log_visual_rejected(update, reason="missing_preview_identity")
            return FeedbackFlushIntent.schedule()
        preview_key = self._preview_key(update)
        if preview_key is None:
            self._log_visual_rejected(update, reason="missing_preview_lane_identity")
            return FeedbackFlushIntent.schedule()
        if not self._preview_is_authorized(update):
            self._log_visual_rejected(update, reason="stale_preview_run")
            return FeedbackFlushIntent.schedule()
        if (
            preview_key in self._finalized_lanes
            or preview_key.source_level() in self._finalized_source_lanes
        ):
            self._log_visual_rejected(update, reason="finalized_preview_lane")
            return FeedbackFlushIntent.schedule()
        self._preview_updates[preview_key] = live_event
        return FeedbackFlushIntent.schedule()

    def submit_output_image(self, update: OutputImageUpdate) -> FeedbackFlushIntent:
        """Append a final output image update without coalescing it."""

        live_event = LiveFinalOutputEvent.from_update(update)
        if live_event is None:
            self._log_visual_rejected(update, reason="missing_output_identity")
            return FeedbackFlushIntent.schedule()
        output_key = self._output_key(update)
        if output_key is None:
            self._log_visual_rejected(update, reason="missing_output_lane_identity")
            return FeedbackFlushIntent.schedule()
        if not self._final_output_is_authorized(update):
            self._log_visual_rejected(update, reason="stale_output_run")
            return FeedbackFlushIntent.schedule()
        source_level_key = output_key.source_level()
        self._preview_updates.pop(output_key, None)
        self._preview_updates.pop(source_level_key, None)
        self._preview_updates = {
            key: preview
            for key, preview in self._preview_updates.items()
            if not (
                key.workflow_id == source_level_key.workflow_id
                and key.generation_run_id == source_level_key.generation_run_id
                and key.prompt_id == source_level_key.prompt_id
                and key.source_key == source_level_key.source_key
                and key.scene_run_id == source_level_key.scene_run_id
                and key.scene_key == source_level_key.scene_key
                and key.list_index is None
            )
        }
        self._finalized_lanes.add(output_key)
        self._finalized_source_lanes.add(source_level_key)
        log_debug(
            _LOGGER,
            "Generation final output closed preview lane",
            workflow_id=update.workflow_id,
            generation_run_id=update.generation_run_id,
            prompt_id=update.prompt_id,
            source_key=update.source_key,
            scene_run_id=update.scene_run_id,
            scene_key=update.scene_key,
            list_index=update.list_index,
        )
        self._output_image_updates.append(live_event)
        return FeedbackFlushIntent.immediate()

    def submit_timing(
        self,
        update: GenerationExecutionTiming,
    ) -> FeedbackFlushIntent:
        """Append a durable timing update without coalescing it."""

        self._timing_updates.append(update)
        return FeedbackFlushIntent.immediate()

    def submit_failure(self, failure: GenerationFailure) -> FeedbackFlushIntent:
        """Append a generation failure and force prompt UI cleanup."""

        if not self._failure_matches_active_run(failure):
            log_debug(
                _LOGGER,
                "Ignoring stale generation failure",
                workflow_id=failure.workflow_id,
                generation_run_id=failure.generation_run_id,
                prompt_id=failure.prompt_id,
            )
            return FeedbackFlushIntent.schedule()
        self._discard_nonessential_workflow_updates(failure.workflow_id)
        if self._visual_authorization is not None and failure.generation_run_id:
            self._visual_authorization.fail_run(
                workflow_id=failure.workflow_id,
                generation_run_id=failure.generation_run_id,
            )
        self._retire_active_run(failure.workflow_id, failure.generation_run_id)
        self.retire_progress(
            reason="failed",
            workflow_id=failure.workflow_id,
            generation_run_id=failure.generation_run_id,
            prompt_id=failure.prompt_id,
        )
        self._failures.append(failure)
        return FeedbackFlushIntent.immediate()

    def submit_completed(self, event: ListenerCompleted) -> FeedbackFlushIntent:
        """Append a generation completion and force prompt UI cleanup."""

        if not self._completed_matches_active_run(event):
            log_debug(
                _LOGGER,
                "Ignoring stale generation completion",
                workflow_id=event.workflow_id,
                generation_run_id=event.generation_run_id,
                prompt_id=event.prompt_id,
            )
            return FeedbackFlushIntent.schedule()
        self._discard_nonessential_workflow_updates(event.workflow_id)
        if self._visual_authorization is not None:
            self._visual_authorization.complete_run(
                workflow_id=event.workflow_id,
                generation_run_id=event.generation_run_id,
                prompt_id=event.prompt_id,
            )
        self._retire_active_run(event.workflow_id, event.generation_run_id)
        self._completed_events.append(event)
        self.retire_progress(
            reason="completed",
            workflow_id=event.workflow_id,
            generation_run_id=event.generation_run_id,
            prompt_id=event.prompt_id,
        )
        return FeedbackFlushIntent.immediate()

    def drain_due(self) -> GenerationFeedbackBatch:
        """Return pending feedback for one normal scheduled UI flush."""

        return self._drain()

    def drain_all(self) -> GenerationFeedbackBatch:
        """Return every pending feedback item for immediate UI delivery."""

        return self._drain()

    def pending_counts(self) -> GenerationFeedbackPendingCounts:
        """Return pending category counts without draining stored feedback."""

        return GenerationFeedbackPendingCounts(
            progress_count=(
                len(self._pending_progress_by_workflow)
                + len(self._pending_retirement_by_workflow)
            ),
            model_load_count=len(self._model_load_updates),
            preview_count=len(self._preview_updates),
            output_image_count=len(self._output_image_updates),
            timing_count=len(self._timing_updates),
            failure_count=len(self._failures),
            completed_count=len(self._completed_events),
        )

    def has_terminal_or_durable_updates(self) -> bool:
        """Return whether pending work must bypass prompt-interaction visual deferral."""

        progress_completed = any(
            update.workflow_percent is not None and update.workflow_percent >= 100.0
            for update in self._pending_progress_by_workflow.values()
        )
        return bool(
            self._pending_retirement_by_workflow
            or progress_completed
            or any(
                _is_terminal_model_load_update(update)
                for update in self._model_load_updates.values()
            )
            or self._output_image_updates
            or self._timing_updates
            or self._failures
            or self._completed_events
        )

    def _drain(self) -> GenerationFeedbackBatch:
        """Move pending feedback into one immutable batch."""

        progress_updates = tuple(self._pending_progress_by_workflow.values())
        progress_states = tuple(self._pending_retirement_by_workflow.values())
        batch = GenerationFeedbackBatch(
            progress_states=progress_states,
            progress_updates=progress_updates,
            model_load_updates=tuple(self._model_load_updates.values()),
            preview_updates=tuple(self._preview_updates.values()),
            output_image_updates=tuple(self._output_image_updates),
            timing_updates=tuple(self._timing_updates),
            failures=tuple(self._failures),
            completed_events=tuple(self._completed_events),
        )
        self._pending_progress_by_workflow.clear()
        self._pending_retirement_by_workflow.clear()
        self._model_load_updates.clear()
        self._preview_updates.clear()
        self._output_image_updates.clear()
        self._timing_updates.clear()
        self._failures.clear()
        self._completed_events.clear()
        return batch

    @staticmethod
    def _model_load_key(
        update: ModelLoadProgressUpdate,
    ) -> tuple[str, str, str, str]:
        """Return the editor-field identity for model-load coalescing."""

        return (
            update.workflow_id,
            update.source_cube_alias or "",
            update.source_workflow_node_name or "",
            update.source_input_key or "",
        )

    @staticmethod
    def _preview_key(update: PreviewImageUpdate) -> VisualLaneKey | None:
        """Return the visible preview slot identity for preview coalescing."""

        if (
            not update.generation_run_id
            or not update.prompt_id
            or not update.source_key
        ):
            return None
        return VisualLaneKey(
            workflow_id=update.workflow_id,
            generation_run_id=update.generation_run_id,
            prompt_id=update.prompt_id,
            source_key=update.source_key,
            scene_run_id=update.scene_run_id,
            scene_key=update.scene_key,
            list_index=None,
        )

    @staticmethod
    def _output_key(update: OutputImageUpdate) -> VisualLaneKey | None:
        """Return the final-output lane identity for lifecycle closure."""

        if (
            not update.generation_run_id
            or not update.prompt_id
            or not update.source_key
            or update.list_index is None
        ):
            return None
        return VisualLaneKey(
            workflow_id=update.workflow_id,
            generation_run_id=update.generation_run_id,
            prompt_id=update.prompt_id,
            source_key=update.source_key,
            scene_run_id=update.scene_run_id,
            scene_key=update.scene_key,
            list_index=update.list_index,
        )

    def _update_matches_active_run(
        self,
        update: PreviewImageUpdate | OutputImageUpdate,
    ) -> bool:
        """Return whether a visual update belongs to the active workflow run."""

        active_run = self._active_runs.get(update.workflow_id)
        return (
            active_run is not None
            and update.generation_run_id == active_run.generation_run_id
            and update.prompt_id == active_run.prompt_id
            and (update.client_id is None or update.client_id == active_run.client_id)
        )

    def _preview_is_authorized(self, update: PreviewImageUpdate) -> bool:
        """Return whether one preview passes the authoritative visual gate."""

        if self._visual_authorization is None:
            return self._update_matches_active_run(update)
        identity = _visual_identity_from_update(update)
        return identity is not None and self._visual_authorization.authorize_preview(
            identity
        )

    def _final_output_is_authorized(self, update: OutputImageUpdate) -> bool:
        """Return whether one final output passes the authoritative visual gate."""

        if self._visual_authorization is None:
            return self._update_matches_active_run(update)
        identity = _visual_identity_from_update(update)
        return (
            identity is not None
            and self._visual_authorization.authorize_final_output(identity)
        )

    def _failure_matches_active_run(self, failure: GenerationFailure) -> bool:
        """Return whether a failure should retire the active run."""

        if failure.generation_run_id is None:
            return True
        active_run = self._active_runs.get(failure.workflow_id)
        return (
            active_run is not None
            and failure.generation_run_id == active_run.generation_run_id
            and (failure.prompt_id is None or failure.prompt_id == active_run.prompt_id)
        )

    def _completed_matches_active_run(self, event: ListenerCompleted) -> bool:
        """Return whether a completion belongs to the active run."""

        active_run = self._active_runs.get(event.workflow_id)
        return (
            active_run is not None
            and event.generation_run_id == active_run.generation_run_id
            and event.prompt_id == active_run.prompt_id
        )

    def _retire_active_run(
        self,
        workflow_id: str,
        generation_run_id: str | None,
    ) -> None:
        """Clear active-run state only when the terminal event owns it."""

        active_run = self._active_runs.get(workflow_id)
        if active_run is None:
            return
        if (
            generation_run_id is not None
            and active_run.generation_run_id != generation_run_id
        ):
            return
        self._active_runs.pop(workflow_id, None)

    @staticmethod
    def _log_visual_rejected(
        update: PreviewImageUpdate | OutputImageUpdate,
        *,
        reason: str,
    ) -> None:
        """Log one visual lifecycle rejection with run and lane context."""

        log_debug(
            _LOGGER,
            "Generation visual update rejected",
            workflow_id=update.workflow_id,
            generation_run_id=update.generation_run_id,
            prompt_id=update.prompt_id,
            client_id=update.client_id,
            node_id=update.node_id,
            source_key=update.source_key,
            scene_run_id=update.scene_run_id,
            scene_key=update.scene_key,
            list_index=getattr(update, "list_index", None),
            reason=reason,
        )

    def _discard_nonessential_workflow_updates(self, workflow_id: str) -> None:
        """Discard stale repaint-only updates for a terminal workflow event."""

        self._model_load_updates = {
            key: update
            for key, update in self._model_load_updates.items()
            if update.workflow_id != workflow_id
        }
        self._preview_updates = {
            key: update
            for key, update in self._preview_updates.items()
            if update.identity.workflow_id != workflow_id
        }


def _is_terminal_model_load_update(update: ModelLoadProgressUpdate) -> bool:
    """Return whether one model-load event should bypass visual coalescing."""

    terminal_states = frozenset(("complete", "completed", "finished"))
    return update.state.casefold() in terminal_states


def _visual_identity_from_update(
    update: PreviewImageUpdate | OutputImageUpdate,
) -> GenerationVisualIdentity | None:
    """Build a strict visual identity from an incoming update."""

    if (
        not update.generation_run_id
        or not update.prompt_id
        or not update.client_id
        or not update.source_key
        or not update.source_label
    ):
        return None
    return GenerationVisualIdentity(
        workflow_id=update.workflow_id,
        generation_run_id=update.generation_run_id,
        prompt_id=update.prompt_id,
        client_id=update.client_id,
        source_key=update.source_key,
        source_label=update.source_label,
        scene_run_id=update.scene_run_id,
        scene_key=update.scene_key,
        scene_title=update.scene_title,
        scene_order=update.scene_order,
        scene_count=update.scene_count,
        node_id=update.node_id,
        display_node_id=getattr(update, "display_node_id", None),
    )


__all__ = [
    "FeedbackFlushIntent",
    "GenerationFeedbackBatch",
    "GenerationFeedbackCoalescer",
    "GenerationFeedbackPendingCounts",
    "GenerationProgressIdentity",
    "GenerationProgressRetirement",
    "GenerationProgressRetirementReason",
    "VisualLaneKey",
]
