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

"""Verify listener progress is bounded to its prompt identity and workflow."""

from __future__ import annotations

import json

from _pytest.monkeypatch import MonkeyPatch

from substitute.domain.common import JsonObject
from tests.infrastructure.comfy.listener.contract_harness import _run_listener_messages


def test_run_uses_wrapped_prompt_nodes_for_workflow_progress(
    monkeypatch: MonkeyPatch,
) -> None:
    """Keep the complete workflow denominator for wrapped prompt payloads."""

    workflow: JsonObject = {
        "prompt": {
            "1": {"class_type": "KSampler"},
            "2": {"class_type": "KSampler"},
        }
    }
    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload=workflow,
        messages=[
            json.dumps(
                {
                    "type": "execution_cached",
                    "data": {"prompt_id": "pid-1", "nodes": ["1", "2"]},
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": None, "prompt_id": "pid-1"},
                }
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert progress
    assert all(
        event.workflow_percent is None or event.workflow_percent <= 100.0
        for event in progress
    )
    assert [(event.workflow_percent, event.sampler_percent) for event in progress] == [
        (100.0, None)
    ]
    assert progress[0].workflow_id == "wf-1"
    assert progress[0].generation_run_id == "run-1"
    assert progress[0].prompt_id == "pid-1"
    assert progress[0].client_id == "client"


def test_run_ignores_other_prompt_cached_progress(monkeypatch: MonkeyPatch) -> None:
    """Ignore cached-node events for a different prompt."""

    workflow: JsonObject = {
        "1": {"class_type": "KSampler"},
        "2": {"class_type": "KSampler"},
    }
    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload=workflow,
        messages=[
            json.dumps(
                {
                    "type": "execution_cached",
                    "data": {"prompt_id": "other", "nodes": ["1", "2", "3"]},
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": None, "prompt_id": "pid-1"},
                }
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert [(event.workflow_percent, event.sampler_percent) for event in progress] == [
        (100.0, None)
    ]


def test_run_ignores_other_prompt_sampler_progress(monkeypatch: MonkeyPatch) -> None:
    """Ignore sampler progress for a different prompt."""

    workflow: JsonObject = {"1": {"class_type": "KSampler"}}
    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload=workflow,
        messages=[
            json.dumps(
                {
                    "type": "progress",
                    "data": {
                        "prompt_id": "other",
                        "node": "1",
                        "value": 1,
                        "max": 2,
                    },
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": None, "prompt_id": "pid-1"},
                }
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert [(event.workflow_percent, event.sampler_percent) for event in progress] == [
        (100.0, None)
    ]


def test_run_marks_previous_executing_node_complete_on_next_node(
    monkeypatch: MonkeyPatch,
) -> None:
    """Advance workflow completion when the next node begins execution."""

    workflow: JsonObject = {
        "1": {"class_type": "KSampler"},
        "2": {"class_type": "KSampler"},
    }
    progress, failures, completed = _run_listener_messages(
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
    )

    assert failures == []
    assert len(completed) == 1
    assert [event.workflow_percent for event in progress] == [0.0, 50.0, 100.0]
