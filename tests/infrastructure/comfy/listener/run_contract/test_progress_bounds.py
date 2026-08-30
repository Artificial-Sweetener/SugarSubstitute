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

"""Verify listener progress accounting clamps cached and sampler telemetry."""

from __future__ import annotations

import json

from _pytest.monkeypatch import MonkeyPatch

from tests.infrastructure.comfy.listener.contract_harness import _run_listener_messages


def test_run_ignores_unknown_cached_node_ids(monkeypatch: MonkeyPatch) -> None:
    """Ignore unknown cache IDs when calculating workflow completion."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={
            "1": {"class_type": "KSampler"},
            "2": {"class_type": "KSampler"},
        },
        messages=[
            json.dumps(
                {
                    "type": "execution_cached",
                    "data": {"prompt_id": "pid-1", "nodes": ["1", "2", "3"]},
                }
            ),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert [(event.workflow_percent, event.sampler_percent) for event in progress] == [
        (100.0, None)
    ]
    assert all(
        event.workflow_percent is None or event.workflow_percent <= 100.0
        for event in progress
    )


def test_run_excludes_partial_cached_nodes_from_remaining_work_progress(
    monkeypatch: MonkeyPatch,
) -> None:
    """Exclude cached work from remaining-work sampler projection."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={
            "1": {"class_type": "KSampler"},
            "2": {"class_type": "KSampler"},
        },
        messages=[
            json.dumps(
                {
                    "type": "execution_cached",
                    "data": {"prompt_id": "pid-1", "nodes": ["1"]},
                }
            ),
            json.dumps(
                {
                    "type": "progress",
                    "data": {"prompt_id": "pid-1", "node": "2", "value": 1, "max": 2},
                }
            ),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert [event.workflow_percent for event in progress] == [50.0, 100.0]


def test_run_clamps_sampler_progress_percent(monkeypatch: MonkeyPatch) -> None:
    """Clamp sampler percentages and reject zero-length telemetry."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={"1": {"class_type": "KSampler"}},
        messages=[
            json.dumps(
                {
                    "type": "progress",
                    "data": {
                        "prompt_id": "pid-1",
                        "node": "1",
                        "value": 120,
                        "max": 100,
                    },
                }
            ),
            json.dumps(
                {
                    "type": "progress",
                    "data": {
                        "prompt_id": "pid-1",
                        "node": "1",
                        "value": -1,
                        "max": 100,
                    },
                }
            ),
            json.dumps(
                {
                    "type": "progress",
                    "data": {"prompt_id": "pid-1", "node": "1", "value": 1, "max": 0},
                }
            ),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert [event.sampler_percent for event in progress[:3]] == [100.0, 0.0, None]
