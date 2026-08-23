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

"""Verify listener rejects malformed and inflated progress-state telemetry."""

from __future__ import annotations

import json

from _pytest.monkeypatch import MonkeyPatch

from tests.infrastructure.comfy.listener.contract_harness import _run_listener_messages


def test_run_ignores_malformed_progress_state_entries(
    monkeypatch: MonkeyPatch,
) -> None:
    """Ignore malformed state records without losing terminal completion."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={"1": {"class_type": "KSampler"}},
        messages=[
            json.dumps(
                {
                    "type": "progress_state",
                    "data": {
                        "prompt_id": "pid-1",
                        "nodes": {
                            "1": {"state": "finished", "value": "bad", "max": 1},
                            "2": "bad",
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
    assert [(event.workflow_percent, event.sampler_percent) for event in progress] == [
        (100.0, None),
    ]


def test_run_progress_state_cannot_exceed_one_hundred_percent(
    monkeypatch: MonkeyPatch,
) -> None:
    """Ignore unknown completed nodes that would inflate workflow completion."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={"1": {"class_type": "KSampler"}},
        messages=[
            json.dumps(
                {
                    "type": "progress_state",
                    "data": {
                        "prompt_id": "pid-1",
                        "nodes": {
                            "1": {"state": "finished", "value": 1, "max": 1},
                            "2": {"state": "finished", "value": 1, "max": 1},
                            "2.0.0.1": {"state": "finished", "value": 1, "max": 1},
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
    assert [event.workflow_percent for event in progress] == [100.0, 100.0]
    assert all(
        event.workflow_percent is None or event.workflow_percent <= 100.0
        for event in progress
    )
