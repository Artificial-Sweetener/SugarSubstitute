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

"""Route dispatched generation feedback to its owning shell controllers."""

from __future__ import annotations

from typing import Any

from substitute.application.generation import GenerationFailure
from substitute.application.generation.progress_service import ProgressViewState
from substitute.application.ports import (
    GenerationExecutionTiming,
    ListenerCompleted,
    ModelLoadProgressUpdate,
    ProgressUpdate,
)
from substitute.application.workflows import LiveFinalOutputEvent, LivePreviewEvent
from substitute.presentation.shell.generation_action_controller import (
    generation_action_controller_for,
)
from substitute.presentation.shell.generation_feedback_presenter import (
    generation_feedback_presenter_for,
)


class ShellGenerationFeedbackSink:
    """Dispatch generation feedback to action and feedback presentation owners."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose composed controllers should receive feedback."""

        self._shell = shell

    def apply_generation_progress(self, update: ProgressUpdate) -> None:
        """Apply one progress update through the generation action owner."""

        generation_action_controller_for(self._shell).apply_generation_progress(update)

    def apply_generation_progress_state(self, state: ProgressViewState) -> None:
        """Apply one projected progress state through the action owner."""

        generation_action_controller_for(self._shell).apply_generation_progress_state(
            state
        )

    def apply_generation_model_load_progress(
        self,
        update: ModelLoadProgressUpdate,
    ) -> None:
        """Apply one model-load update through the feedback presenter."""

        generation_feedback_presenter_for(
            self._shell
        ).apply_generation_model_load_progress(update)

    def apply_generation_preview(self, update: LivePreviewEvent) -> None:
        """Apply one preview update through the feedback presenter."""

        generation_feedback_presenter_for(self._shell).apply_generation_preview(update)

    def apply_generation_output_image(self, update: LiveFinalOutputEvent) -> None:
        """Apply one final-output update through the feedback presenter."""

        generation_feedback_presenter_for(self._shell).apply_generation_output_image(
            update
        )

    def apply_generation_timing(self, update: GenerationExecutionTiming) -> None:
        """Apply one timing update through the feedback presenter."""

        generation_feedback_presenter_for(self._shell).apply_generation_timing(update)

    def apply_generation_failure(self, failure: GenerationFailure) -> None:
        """Apply one generation failure through the feedback presenter."""

        generation_feedback_presenter_for(self._shell).apply_generation_failure(failure)

    def apply_generation_completed(self, event: ListenerCompleted) -> None:
        """Apply one completion event through the feedback presenter."""

        generation_feedback_presenter_for(self._shell).apply_generation_completed(event)


def shell_generation_feedback_sink_for(shell: Any) -> ShellGenerationFeedbackSink:
    """Return the composed dispatcher sink for a shell."""

    sink = getattr(shell, "generation_feedback_sink", None)
    if isinstance(sink, ShellGenerationFeedbackSink):
        return sink
    sink = ShellGenerationFeedbackSink(shell)
    setattr(shell, "generation_feedback_sink", sink)
    return sink


__all__ = [
    "ShellGenerationFeedbackSink",
    "shell_generation_feedback_sink_for",
]
