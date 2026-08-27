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

"""Tests for the shell generation feedback dispatcher sink."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from substitute.application.generation import GenerationFailure
from substitute.application.generation.progress_service import ProgressViewState
from substitute.application.ports import (
    GenerationExecutionTiming,
    ListenerCompleted,
    ModelLoadProgressUpdate,
    ProgressUpdate,
)
from substitute.application.workflows import LiveFinalOutputEvent, LivePreviewEvent
from substitute.presentation.shell import generation_feedback_sink
from substitute.presentation.shell.generation_feedback_sink import (
    ShellGenerationFeedbackSink,
    shell_generation_feedback_sink_for,
)


def test_sink_for_reuses_composed_shell_instance() -> None:
    """Sink lookup should preserve the shell-composed dispatcher sink."""

    shell = SimpleNamespace()
    sink = ShellGenerationFeedbackSink(shell)
    shell.generation_feedback_sink = sink

    assert shell_generation_feedback_sink_for(shell) is sink


def test_sink_routes_progress_to_action_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatcher progress callbacks should route to the action controller."""

    calls: list[tuple[str, object]] = []
    action_controller = SimpleNamespace(
        apply_generation_progress=lambda update: calls.append(("progress", update)),
        apply_generation_progress_state=lambda state: calls.append(("state", state)),
    )
    monkeypatch.setattr(
        generation_feedback_sink,
        "generation_action_controller_for",
        lambda _shell: action_controller,
    )

    shell = SimpleNamespace()
    sink = ShellGenerationFeedbackSink(shell)
    progress_update = cast(ProgressUpdate, object())
    progress_state = cast(ProgressViewState, object())

    sink.apply_generation_progress(progress_update)
    sink.apply_generation_progress_state(progress_state)

    assert calls == [("progress", progress_update), ("state", progress_state)]


def test_sink_routes_feedback_to_presenter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dispatcher feedback callbacks should route to the feedback presenter."""

    calls: list[tuple[str, object]] = []
    presenter = SimpleNamespace(
        apply_generation_model_load_progress=lambda update: calls.append(
            ("model_load", update)
        ),
        apply_generation_preview=lambda update: calls.append(("preview", update)),
        apply_generation_output_image=lambda update: calls.append(("output", update)),
        apply_generation_timing=lambda update: calls.append(("timing", update)),
        apply_generation_failure=lambda failure: calls.append(("failure", failure)),
        apply_generation_completed=lambda event: calls.append(("completed", event)),
    )
    monkeypatch.setattr(
        generation_feedback_sink,
        "generation_feedback_presenter_for",
        lambda _shell: presenter,
    )

    shell = SimpleNamespace()
    sink = ShellGenerationFeedbackSink(shell)
    model_load = cast(ModelLoadProgressUpdate, object())
    preview = cast(LivePreviewEvent, object())
    output = cast(LiveFinalOutputEvent, object())
    timing = cast(GenerationExecutionTiming, object())
    failure = cast(GenerationFailure, object())
    completed = cast(ListenerCompleted, object())

    sink.apply_generation_model_load_progress(model_load)
    sink.apply_generation_preview(preview)
    sink.apply_generation_output_image(output)
    sink.apply_generation_timing(timing)
    sink.apply_generation_failure(failure)
    sink.apply_generation_completed(completed)

    assert calls == [
        ("model_load", model_load),
        ("preview", preview),
        ("output", output),
        ("timing", timing),
        ("failure", failure),
        ("completed", completed),
    ]
