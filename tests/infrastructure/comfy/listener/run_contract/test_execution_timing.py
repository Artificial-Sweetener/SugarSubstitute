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

"""Verify listener run-loop timing publication with a controlled clock."""

from __future__ import annotations

import json

from _pytest.monkeypatch import MonkeyPatch

from substitute.domain.common import JsonObject
from tests.infrastructure.comfy.listener.contract_harness import (
    _run_listener_messages_with_timing,
)


def test_run_emits_prompt_and_cube_timing_before_completion(
    monkeypatch: MonkeyPatch,
) -> None:
    """Publish Comfy prompt time and the summed cube-node time before completion."""

    workflow: JsonObject = {
        "1": {"class_type": "KSampler", "_meta": {"title": "CubeA.KSampler"}},
        "2": {
            "class_type": "VAEDecode",
            "_meta": {"title": "CubeA.Decode"},
            "inputs": {"samples": ["1", 0]},
        },
        "3": {
            "class_type": "SugarCubes.CubeOutput",
            "_meta": {"title": "CubeA.Output"},
            "inputs": {"image": ["2", 0]},
        },
    }
    _progress, timing, failures, completed, event_order = (
        _run_listener_messages_with_timing(
            monkeypatch,
            workflow_payload=workflow,
            messages=[
                json.dumps(
                    {
                        "type": "execution_start",
                        "data": {"prompt_id": "pid-1", "timestamp": 10000},
                    }
                ),
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": "1", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "executed",
                        "data": {"node": "1", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": "2", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "executed",
                        "data": {"node": "2", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "execution_success",
                        "data": {"prompt_id": "pid-1", "timestamp": 13080},
                    }
                ),
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": None, "prompt_id": "pid-1"},
                    }
                ),
            ],
            clock_values=[1.0, 2.0, 3.0, 4.0, 5.5, 6.0],
        )
    )

    assert failures == []
    assert len(completed) == 1
    assert event_order == ["timing", "completed"]
    assert len(timing) == 1
    assert timing[0].job_duration_ms == 3080.0
    assert [
        (item.cube_alias, item.source_key, item.duration_ms)
        for item in timing[0].cube_timings
    ] == [("CubeA", "cube:CubeA", 2500.0)]


def test_run_excludes_cached_nodes_from_cube_timing(
    monkeypatch: MonkeyPatch,
) -> None:
    """Exclude cached nodes from emitted cube execution duration."""

    workflow: JsonObject = {
        "1": {"class_type": "KSampler", "_meta": {"title": "CubeA.KSampler"}},
        "2": {"class_type": "VAEDecode", "_meta": {"title": "CubeB.Decode"}},
    }
    _progress, timing, failures, completed, _event_order = (
        _run_listener_messages_with_timing(
            monkeypatch,
            workflow_payload=workflow,
            messages=[
                json.dumps(
                    {
                        "type": "execution_cached",
                        "data": {"prompt_id": "pid-1", "nodes": ["1"]},
                    }
                ),
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": "1", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": "2", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "executed",
                        "data": {"node": "2", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": None, "prompt_id": "pid-1"},
                    }
                ),
            ],
            clock_values=[1.0, 2.0, 3.0],
        )
    )

    assert failures == []
    assert len(completed) == 1
    assert len(timing) == 1
    assert [(item.cube_alias, item.duration_ms) for item in timing[0].cube_timings] == [
        ("CubeB", 1000.0)
    ]


def test_run_uses_listener_fallback_duration_without_prompt_timestamps(
    monkeypatch: MonkeyPatch,
) -> None:
    """Use controlled listener duration when Comfy omits prompt timestamps."""

    workflow: JsonObject = {
        "1": {"class_type": "KSampler", "_meta": {"title": "CubeA.KSampler"}},
    }
    _progress, timing, failures, completed, _event_order = (
        _run_listener_messages_with_timing(
            monkeypatch,
            workflow_payload=workflow,
            messages=[
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": "1", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": None, "prompt_id": "pid-1"},
                    }
                ),
            ],
            clock_values=[1.0, 1.0, 2.25, 2.25],
        )
    )

    assert failures == []
    assert len(completed) == 1
    assert timing[0].job_duration_ms == 1250.0
    assert timing[0].cube_timings[0].duration_ms == 1250.0
