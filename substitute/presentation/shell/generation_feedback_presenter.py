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

"""Apply generation feedback events to live shell presentation surfaces."""

from __future__ import annotations

from typing import Any

from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.application.generation import GenerationFailure
from substitute.application.generation.failure_summary import (
    format_generation_failure_line,
)
from substitute.application.ports import (
    GenerationExecutionTiming,
    ListenerCompleted,
    ModelLoadProgressUpdate,
)
from substitute.application.workflows import LiveFinalOutputEvent, LivePreviewEvent
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("presentation.shell.generation_feedback_presenter")


class GenerationFeedbackPresenter:
    """Own generation feedback application for the shell."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose feedback surfaces should be updated."""

        self._shell = shell

    def clear_output_for_workflow(self, workflow_id: str) -> None:
        """Clear output images for a workflow before queueing a fresh generation."""

        self.mark_sampler_progress_model_field_clear_needed()
        self.clear_model_field_load_progress_for_workflow(workflow_id)
        output_image_pipeline = getattr(self._shell, "output_image_pipeline", None)
        remove_output_workflow = getattr(output_image_pipeline, "remove_workflow", None)
        if callable(remove_output_workflow):
            remove_output_workflow(workflow_id)
        self._shell.output_canvas_projection_coordinator.clear_output_for_workflow(
            self._shell.workflow_session_service.workflows,
            workflow_id,
        )

    def request_clear_output_for_workflow(self, workflow_id: str) -> None:
        """Queue output clearing onto the Qt UI thread."""

        self._shell.clear_output_signal.emit(workflow_id)

    def apply_generation_model_load_progress(
        self,
        progress_update: ModelLoadProgressUpdate,
    ) -> None:
        """Route source-enriched model-loading progress to editor model fields."""

        if (
            progress_update.source_cube_alias is None
            or progress_update.source_workflow_node_name is None
            or progress_update.source_input_key is None
        ):
            log_info(
                _LOGGER,
                "Ignoring model-load telemetry without editor source metadata",
                workflow_id=progress_update.workflow_id,
                prompt_id=progress_update.prompt_id,
                node_id=progress_update.node_id,
                source_node_id=progress_update.source_node_id,
                source_input_key=progress_update.source_input_key,
                source_cube_alias=progress_update.source_cube_alias,
                source_workflow_node_name=(progress_update.source_workflow_node_name),
                percent=progress_update.percent,
                state=progress_update.state,
            )
            return
        editor_panel = self._shell.editor_panels.get(progress_update.workflow_id)
        if editor_panel is None:
            log_info(
                _LOGGER,
                "Ignoring model-load telemetry for missing editor panel",
                workflow_id=progress_update.workflow_id,
                prompt_id=progress_update.prompt_id,
                source_node_id=progress_update.source_node_id,
                source_input_key=progress_update.source_input_key,
                cube_alias=progress_update.source_cube_alias,
                node_name=progress_update.source_workflow_node_name,
                percent=progress_update.percent,
                state=progress_update.state,
            )
            return

        view_state = self._shell.progress_service.build_model_load_view_state(
            percent=progress_update.percent,
            state=progress_update.state,
        )
        if (
            progress_update.phase == "dynamic_vram_staging"
            and progress_update.state == "finished"
        ):
            log_info(
                _LOGGER,
                "Deferring dynamic model-load progress clear until sampler progress",
                workflow_id=progress_update.workflow_id,
                prompt_id=progress_update.prompt_id,
                source_node_id=progress_update.source_node_id,
                source_input_key=progress_update.source_input_key,
                cube_alias=progress_update.source_cube_alias,
                node_name=progress_update.source_workflow_node_name,
                percent=progress_update.percent,
                state=progress_update.state,
            )
            return
        log_info(
            _LOGGER,
            "Routing model-load telemetry to editor field",
            workflow_id=progress_update.workflow_id,
            prompt_id=progress_update.prompt_id,
            source_node_id=progress_update.source_node_id,
            source_input_key=progress_update.source_input_key,
            cube_alias=progress_update.source_cube_alias,
            node_name=progress_update.source_workflow_node_name,
            field_key=progress_update.source_input_key,
            percent=progress_update.percent,
            state=progress_update.state,
            active=view_state.show_overlay,
        )
        self.mark_sampler_progress_model_field_clear_needed()
        editor_panel.set_model_field_load_progress(
            cube_alias=progress_update.source_cube_alias,
            node_name=progress_update.source_workflow_node_name,
            field_key=progress_update.source_input_key,
            percent=view_state.display_percent,
            active=view_state.show_overlay,
        )

    def apply_generation_preview(self, preview_update: LivePreviewEvent) -> None:
        """Route preview updates through existing preview image signal wiring."""

        self._shell.preview_image_signal.emit(preview_update)

    def apply_generation_output_image(
        self,
        output_update: LiveFinalOutputEvent,
    ) -> None:
        """Submit saved output image updates to the asynchronous commit pipeline."""

        self._shell.output_image_pipeline.submit_live_output_event(output_update)

    def apply_generation_timing(
        self,
        timing_update: GenerationExecutionTiming,
    ) -> None:
        """Apply generation timing to existing output metadata."""

        source_durations = {
            timing.source_key: timing.duration_ms
            for timing in timing_update.cube_timings
            if timing.source_key
        }
        cube_durations = {
            timing.cube_alias: timing.duration_ms
            for timing in timing_update.cube_timings
            if timing.cube_alias
        }
        timing_result = (
            self._shell.output_canvas_state_service.apply_output_source_timing(
                self._shell.workflow_session_service.workflows,
                workflow_id=timing_update.workflow_id,
                active_workflow_id=(
                    self._shell.workflow_session_service.active_workflow_id
                ),
                source_durations_ms=source_durations,
                cube_durations_ms=cube_durations,
            )
        )
        if timing_result.projection_intent.should_schedule:
            self._shell.output_image_pipeline.schedule_output_projection(
                timing_result.projection_intent,
            )

    def apply_generation_failure(self, failure: GenerationFailure) -> None:
        """Log generation failures with stage and workflow context."""

        self._shell.generation_action_controller.clear_generation_progress()
        self.mark_sampler_progress_model_field_clear_needed()
        self.clear_model_field_load_progress_for_workflow(failure.workflow_id)
        workspace_canvas_actions = getattr(
            self._shell, "workspace_canvas_actions", None
        )
        clear_previews = getattr(
            workspace_canvas_actions, "clear_output_previews", None
        )
        if callable(clear_previews):
            clear_previews(failure.workflow_id)
        self._shell._comfy_output_stream.append_line(
            render_application_text(format_generation_failure_line(failure))
        )
        error_presenter = getattr(self._shell, "_error_presenter", None)
        if failure.error_report is not None and error_presenter is not None:
            error_presenter.show_error_report(failure.error_report)
        log_warning(
            _LOGGER,
            "Generation flow failed",
            stage=failure.stage,
            workflow_id=failure.workflow_id,
            prompt_id=failure.prompt_id,
            failure_message=failure.message,
        )

    def apply_generation_completed(self, event: ListenerCompleted) -> None:
        """Clear non-visual completion state without exposing prior output images."""

        workflow_id = event.workflow_id
        self.mark_sampler_progress_model_field_clear_needed()
        self.clear_model_field_load_progress_for_workflow(workflow_id)
        self._shell._taskbar_progress_presenter.clear_progress()

    def clear_model_field_load_progress_for_workflow(self, workflow_id: str) -> None:
        """Clear model-loading progress for one workflow editor panel."""

        editor_panel = getattr(self._shell, "editor_panels", {}).get(workflow_id)
        if editor_panel is None:
            return
        editor_panel.clear_model_field_load_progress()

    def clear_all_model_field_load_progress(self) -> None:
        """Clear model-loading progress from every workflow editor panel."""

        for editor_panel in getattr(self._shell, "editor_panels", {}).values():
            editor_panel.clear_model_field_load_progress()

    def clear_model_field_progress_for_sampler_once(self) -> None:
        """Clear model-loading widgets once when sampler progress takes over."""

        if getattr(self._shell, "_sampler_progress_model_fields_cleared", False):
            return
        self.clear_all_model_field_load_progress()
        self._shell._sampler_progress_model_fields_cleared = True

    def mark_sampler_progress_model_field_clear_needed(self) -> None:
        """Allow the next sampler-progress transition to clear model-load widgets."""

        self._shell._sampler_progress_model_fields_cleared = False

    def log_missing_output_canvas(self, workflow_id: str) -> None:
        """Log missing output-canvas state for preview updates."""

        log_warning(
            _LOGGER,
            "Output canvas not found for preview update",
            workflow_id=workflow_id,
        )


def generation_feedback_presenter_for(shell: Any) -> GenerationFeedbackPresenter:
    """Return the composed generation feedback presenter for a shell."""

    presenter = getattr(shell, "generation_feedback_presenter", None)
    if isinstance(presenter, GenerationFeedbackPresenter):
        return presenter
    presenter = GenerationFeedbackPresenter(shell)
    setattr(shell, "generation_feedback_presenter", presenter)
    return presenter


__all__ = [
    "GenerationFeedbackPresenter",
    "generation_feedback_presenter_for",
]
