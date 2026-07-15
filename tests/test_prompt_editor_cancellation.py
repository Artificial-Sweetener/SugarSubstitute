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

"""Contract tests for prompt-editor async cancellation primitives."""

from __future__ import annotations

import pytest

from substitute.presentation.editor.prompt_editor.async_work import (
    PromptEditorCancellationController,
    PromptEditorCancellationSource,
)


def test_cancellation_controller_creates_monotonic_sources() -> None:
    """Cancellation generations should increase for each new source."""

    controller = PromptEditorCancellationController()

    first = controller.next_source()
    second = controller.next_source()

    assert first.generation == 1
    assert second.generation == 2
    assert first.is_cancelled is False
    assert second.reason is None


def test_cancellation_source_records_first_prompt_safe_reason() -> None:
    """Cancellation sources should be idempotent and retain the first reason."""

    source = PromptEditorCancellationSource(generation=3)

    source.cancel(reason="text_changed")
    source.cancel(reason="later_reason")

    assert source.generation == 3
    assert source.is_cancelled is True
    assert source.reason == "text_changed"


def test_cancellation_source_rejects_invalid_inputs() -> None:
    """Cancellation values should reject ambiguous state."""

    with pytest.raises(ValueError, match="generation"):
        PromptEditorCancellationSource(generation=-1)
    with pytest.raises(ValueError, match="initial_generation"):
        PromptEditorCancellationController(initial_generation=-1)

    source = PromptEditorCancellationSource(generation=1)
    with pytest.raises(ValueError, match="reason"):
        source.cancel(reason=" ")
