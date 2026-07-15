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

"""Tests for compact generation failure summaries."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from substitute.application.generation.failure_summary import (
    format_generation_failure_line,
    summarize_generation_failure,
)


@pytest.mark.parametrize(
    ("message", "expected"),
    (
        ("No module named 'xformers'", "Missing xformers"),
        (
            "ModuleNotFoundError: No module named 'segment_anything'",
            "Missing segment_anything",
        ),
        ("DLL load failed while importing cv2", "cv2 failed to load"),
        ("ImportError: DLL load failed", "Dependency failed"),
        ("CUDA out of memory while allocating tensor", "Out of memory"),
        ("Connection refused while connecting to ComfyUI", "ComfyUI unavailable"),
        ("HTTP 500 from /prompt", "ComfyUI unavailable"),
        ("checkpoint not found: portrait.safetensors", "Missing model"),
        ("outside allowed root: E:/unsafe", "Invalid input"),
    ),
)
def test_summarize_generation_failure_known_patterns(
    message: str,
    expected: str,
) -> None:
    """Known raw failures should map to compact queue-safe summaries."""

    assert summarize_generation_failure(message) == expected


def test_summarize_generation_failure_uses_detail_for_classification() -> None:
    """Traceback detail should classify the summary without replacing raw fallback."""

    assert (
        summarize_generation_failure(
            "Execution failed",
            detail="ModuleNotFoundError: No module named 'xformers'",
        )
        == "Missing xformers"
    )


def test_summarize_generation_failure_clips_unknown_text() -> None:
    """Unknown long failures should be normalized and clipped."""

    summary = summarize_generation_failure(
        "This generation failed with a very long unknown reason that keeps going."
    )

    assert summary.endswith("...")
    assert len(summary) <= 50


def test_summarize_generation_failure_handles_empty_input() -> None:
    """Empty failure text should return a generic fallback."""

    assert summarize_generation_failure(None) == "Generation failed"
    assert summarize_generation_failure("   ") == "Generation failed"


def test_format_generation_failure_line_includes_stage_message_and_prompt() -> None:
    """Failure lines should include the normalized stage, message, and prompt ID."""

    failure = SimpleNamespace(
        stage="listener_setup",
        message="boom",
        prompt_id="pid-1",
    )

    assert (
        format_generation_failure_line(failure)
        == "Generation failed during listener setup: boom prompt_id=pid-1"
    )


def test_format_generation_failure_line_uses_generation_fallback() -> None:
    """Failure lines should keep an empty failure readable without prompt context."""

    failure = SimpleNamespace(stage="", message="", prompt_id=None)

    assert (
        format_generation_failure_line(failure)
        == "Generation failed during generation."
    )
