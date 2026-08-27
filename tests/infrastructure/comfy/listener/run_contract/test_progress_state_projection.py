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

"""Verify listener progress-state projection into workflow and sampler updates."""

from __future__ import annotations

import json

import pytest
from _pytest.monkeypatch import MonkeyPatch

from tests.infrastructure.comfy.listener.contract_harness import _run_listener_messages


def test_run_uses_progress_state_for_workflow_and_sampler_progress(
    monkeypatch: MonkeyPatch,
) -> None:
    """Project finished and running state into workflow and sampler percentages."""

    monkeypatch.setenv("SUGAR_COMFY_WS_TRACE", "1")
    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={
            "1": {"class_type": "CheckpointLoaderSimple"},
            "2": {"class_type": "KSampler"},
        },
        messages=[
            json.dumps(
                {
                    "type": "progress_state",
                    "data": {
                        "prompt_id": "pid-1",
                        "nodes": {
                            "1": {"state": "finished", "value": 1, "max": 1},
                            "2": {"state": "running", "value": 3, "max": 10},
                        },
                    },
                }
            ),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert progress[0].workflow_percent == pytest.approx(30.0)
    assert progress[0].sampler_percent == 30.0
    assert (progress[1].workflow_percent, progress[1].sampler_percent) == (
        100.0,
        None,
    )


def test_run_normalizes_progress_state_dotted_child_nodes(
    monkeypatch: MonkeyPatch,
) -> None:
    """Normalize dynamic child telemetry through its displayed workflow owner."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={
            "21": {"class_type": "PCLazyTextEncode"},
            "24": {"class_type": "KSampler"},
        },
        messages=[
            json.dumps(
                {
                    "type": "progress_state",
                    "data": {
                        "prompt_id": "pid-1",
                        "nodes": {
                            "21.0.0.1": {
                                "node_id": "21.0.0.1",
                                "display_node_id": "21",
                                "state": "finished",
                                "value": 1,
                                "max": 1,
                            },
                            "24": {
                                "node_id": "24",
                                "display_node_id": "24",
                                "state": "running",
                                "value": 5,
                                "max": 10,
                            },
                        },
                    },
                }
            ),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert progress[0].workflow_percent == pytest.approx(75.0)
    assert progress[0].sampler_percent == 50.0
    assert (progress[1].workflow_percent, progress[1].sampler_percent) == (
        100.0,
        None,
    )


def test_run_advances_workflow_progress_during_sampler_phase(
    monkeypatch: MonkeyPatch,
) -> None:
    """Advance taskbar progress proportionally while the sampler is running."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={
            "1": {"class_type": "CheckpointLoaderSimple"},
            "2": {"class_type": "CLIPTextEncode"},
            "3": {"class_type": "KSampler"},
            "4": {"class_type": "VAEDecode"},
            "5": {"class_type": "SugarCubes.CubeOutput"},
        },
        messages=[
            json.dumps(
                {
                    "type": "progress_state",
                    "data": {
                        "prompt_id": "pid-1",
                        "nodes": {
                            "1": {"state": "finished", "value": 1, "max": 1},
                            "2": {"state": "finished", "value": 1, "max": 1},
                            "3": {"state": "running", "value": 14, "max": 28},
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "type": "progress_state",
                    "data": {
                        "prompt_id": "pid-1",
                        "nodes": {
                            "1": {"state": "finished", "value": 1, "max": 1},
                            "2": {"state": "finished", "value": 1, "max": 1},
                            "3": {"state": "running", "value": 28, "max": 28},
                        },
                    },
                }
            ),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert progress[0].workflow_percent == pytest.approx(37.5)
    assert progress[0].sampler_percent == 50.0
    assert progress[1].workflow_percent == pytest.approx(50.0)
    assert progress[1].sampler_percent == 100.0
    assert (progress[2].workflow_percent, progress[2].sampler_percent) == (
        100.0,
        None,
    )
