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

"""Contract tests for deterministic Comfy workflow progress tracking."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from substitute.application.generation.progress_estimation import (
    ComfyWorkflowProgressTracker,
    ProgressStateName,
    apply_progress_states_to_tracker,
    classify_node,
)


@dataclass(frozen=True)
class _ProgressState:
    """Test double for normalized backend progress-state entries."""

    owner_node_id: str | None
    state: ProgressStateName
    value: float
    maximum: float


def test_classifier_keeps_loader_work_separate_without_hiding_decode_nodes() -> None:
    """Loader classification should exclude loaders without hiding normal work."""

    assert classify_node({"class_type": "CheckpointLoaderSimple"}) == "loader"
    assert classify_node({"class_type": "UNETLoader"}) == "loader"
    assert classify_node({"class_type": "CLIPTextEncode"}) == "ordinary"
    assert classify_node({"class_type": "VAEDecode"}) == "ordinary"
    assert classify_node({"class_type": "KSampler"}) == "sampler"
    assert classify_node({"class_type": "SugarCubes.CubeOutput"}) == "output"


def test_tracker_excludes_loader_nodes_from_denominator() -> None:
    """Model loader nodes should not contribute to workflow progress."""

    tracker = ComfyWorkflowProgressTracker.from_prompt(
        {
            "loader": {"class_type": "CheckpointLoaderSimple"},
            "encode": {"class_type": "CLIPTextEncode"},
            "sampler": {"class_type": "KSampler"},
        }
    )

    tracker.mark_finished("loader")
    assert tracker.workflow_percent() == 0.0

    tracker.mark_finished("encode")
    assert tracker.workflow_percent() == pytest.approx(50.0)


def test_sampler_fraction_fills_exactly_one_workflow_slot() -> None:
    """Sampler progress should fill only the sampler node's node-count segment."""

    tracker = ComfyWorkflowProgressTracker.from_prompt(
        {
            "text": {"class_type": "CLIPTextEncode"},
            "sampler": {"class_type": "KSampler"},
            "decode": {"class_type": "VAEDecode"},
            "save": {"class_type": "SugarCubes.CubeOutput"},
        }
    )

    tracker.mark_finished("text")
    assert tracker.workflow_percent() == pytest.approx(25.0)

    tracker.mark_sampler_progress("sampler", 0.5)
    assert tracker.workflow_percent() == pytest.approx(37.5)

    tracker.mark_sampler_progress("sampler", 1.0)
    assert tracker.workflow_percent() == pytest.approx(50.0)

    tracker.mark_finished("decode")
    assert tracker.workflow_percent() == pytest.approx(75.0)
    tracker.mark_finished("save")
    assert tracker.workflow_percent() == pytest.approx(100.0)


def test_cached_nodes_are_excluded_from_remaining_work_denominator() -> None:
    """Cached nodes should not create an instant completed-work jump."""

    tracker = ComfyWorkflowProgressTracker.from_prompt(
        {
            "cached": {"class_type": "KSampler"},
            "active": {"class_type": "KSampler"},
        }
    )

    tracker.mark_cached("cached")
    assert tracker.workflow_percent() == 0.0

    tracker.mark_sampler_progress("active", 0.5)
    assert tracker.workflow_percent() == pytest.approx(50.0)


def test_all_cached_workflow_nodes_do_not_advance_until_completion() -> None:
    """A fully cached prompt should stay still until Comfy reports completion."""

    tracker = ComfyWorkflowProgressTracker.from_prompt(
        {
            "cached_a": {"class_type": "KSampler"},
            "cached_b": {"class_type": "VAEDecode"},
        }
    )

    tracker.mark_cached("cached_a")
    tracker.mark_cached("cached_b")

    assert tracker.workflow_percent() == 0.0

    tracker.finish_prompt()
    assert tracker.workflow_percent() == 100.0


def test_unknown_cached_node_ids_are_ignored() -> None:
    """Unknown cached nodes should not affect denominator or numerator."""

    tracker = ComfyWorkflowProgressTracker.from_prompt(
        {
            "active_a": {"class_type": "CLIPTextEncode"},
            "active_b": {"class_type": "VAEDecode"},
        }
    )

    tracker.mark_cached("missing")
    tracker.mark_finished("active_a")

    assert tracker.workflow_percent() == pytest.approx(50.0)


def test_duplicate_finish_events_do_not_double_count() -> None:
    """Duplicate finished events should not inflate workflow completion."""

    tracker = ComfyWorkflowProgressTracker.from_prompt(
        {
            "one": {"class_type": "CLIPTextEncode"},
            "two": {"class_type": "VAEDecode"},
        }
    )

    tracker.mark_finished("one")
    tracker.mark_finished("one")

    assert tracker.workflow_percent() == pytest.approx(50.0)


def test_tracker_never_decreases_with_late_lower_sampler_progress() -> None:
    """Workflow percent should remain monotonic within a prompt."""

    tracker = ComfyWorkflowProgressTracker.from_prompt(
        {"sampler": {"class_type": "KSampler"}}
    )

    tracker.mark_sampler_progress("sampler", 0.8)
    high = tracker.workflow_percent()
    tracker.mark_sampler_progress("sampler", 0.2)
    low = tracker.workflow_percent()

    assert high == pytest.approx(80.0)
    assert low == high


def test_malformed_sampler_fraction_is_ignored() -> None:
    """Missing sampler fractions should not advance workflow progress."""

    tracker = ComfyWorkflowProgressTracker.from_prompt(
        {"sampler": {"class_type": "KSampler"}}
    )

    tracker.mark_sampler_progress("sampler", None)

    assert tracker.workflow_percent() == 0.0


def test_apply_progress_states_updates_finished_running_and_error_nodes() -> None:
    """Progress-state application should mutate the tracker by normalized state."""

    tracker = ComfyWorkflowProgressTracker.from_prompt(
        {
            "text": {"class_type": "CLIPTextEncode"},
            "sampler": {"class_type": "KSampler"},
            "failed": {"class_type": "VAEDecode"},
        }
    )

    apply_progress_states_to_tracker(
        tracker=tracker,
        progress_states=(
            _ProgressState(
                owner_node_id="text",
                state="finished",
                value=1.0,
                maximum=1.0,
            ),
            _ProgressState(
                owner_node_id="sampler",
                state="running",
                value=5.0,
                maximum=10.0,
            ),
            _ProgressState(
                owner_node_id="failed",
                state="error",
                value=0.0,
                maximum=1.0,
            ),
        ),
    )

    assert tracker.workflow_percent() == pytest.approx(50.0)


def test_apply_progress_states_ignores_missing_owner_and_non_sampler_fraction() -> None:
    """Unknown owners and non-sampler running fractions should not advance progress."""

    tracker = ComfyWorkflowProgressTracker.from_prompt(
        {
            "text": {"class_type": "CLIPTextEncode"},
            "sampler": {"class_type": "KSampler"},
        }
    )

    apply_progress_states_to_tracker(
        tracker=tracker,
        progress_states=(
            _ProgressState(
                owner_node_id=None,
                state="finished",
                value=1.0,
                maximum=1.0,
            ),
            _ProgressState(
                owner_node_id="text",
                state="running",
                value=10.0,
                maximum=10.0,
            ),
            _ProgressState(
                owner_node_id="sampler",
                state="running",
                value=10.0,
                maximum=0.0,
            ),
        ),
    )

    assert tracker.workflow_percent() == 0.0
