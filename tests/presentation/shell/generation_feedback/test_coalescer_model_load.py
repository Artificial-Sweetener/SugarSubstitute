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

"""Test model-load progress coalescing policy."""

from __future__ import annotations


from substitute.presentation.shell.generation_feedback_coalescer import (
    GenerationFeedbackCoalescer,
)


from tests.presentation.shell.generation_feedback.coalescer_support import (
    _model_load_update,
)


def test_model_load_progress_latest_value_wins_per_field() -> None:
    """Model-load progress should coalesce repeated updates for one editor field."""

    coalescer = GenerationFeedbackCoalescer()
    first = _model_load_update(percent=10.0, state="running")
    second = _model_load_update(percent=20.0, state="running")

    coalescer.submit_model_load_progress(first)
    coalescer.submit_model_load_progress(second)

    assert coalescer.drain_due().model_load_updates == (second,)


def test_model_load_running_progress_uses_scheduled_flush() -> None:
    """Intermediate model-load progress should stay on the coalesced visual lane."""

    coalescer = GenerationFeedbackCoalescer()

    intent = coalescer.submit_model_load_progress(
        _model_load_update(percent=10.0, state="running")
    )

    assert intent.flush_now is False


def test_model_load_state_transition_forces_flush() -> None:
    """Terminal model-load state changes should request immediate GUI delivery."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_model_load_progress(_model_load_update(state="running"))

    intent = coalescer.submit_model_load_progress(_model_load_update(state="finished"))

    assert intent.flush_now is True
