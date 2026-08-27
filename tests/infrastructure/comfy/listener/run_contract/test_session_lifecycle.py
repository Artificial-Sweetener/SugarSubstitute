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

"""Verify listener session cleanup for malformed and disconnected transports."""

from __future__ import annotations

import json
import logging

from _pytest.monkeypatch import MonkeyPatch
from _pytest.logging import LogCaptureFixture

from substitute.domain.common import JsonObject
from tests.infrastructure.comfy.listener.contract_harness import _run_listener_messages


def test_run_emits_failure_and_completion_when_recv_raises(
    monkeypatch: MonkeyPatch,
) -> None:
    """Publish one failure and completion while closing a failed transport."""

    closed: list[bool] = []
    _progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={"1": {"class_type": "KSampler"}},
        messages=[],
        receive_error=RuntimeError("network down"),
        close_events=closed,
    )

    assert closed == [True]
    assert len(failures) == 1
    assert failures[0].workflow_id == "wf-1"
    assert len(completed) == 1
    assert completed[0].workflow_id == "wf-1"
    assert completed[0].prompt_id == "pid-1"


def test_run_handles_malformed_json_and_still_completes(
    monkeypatch: MonkeyPatch,
) -> None:
    """Report malformed text data and complete the listener session safely."""

    closed: list[bool] = []
    _progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={"1": {"class_type": "KSampler"}},
        messages=["{not-json"],
        close_events=closed,
    )

    assert closed == [True]
    assert len(failures) == 1
    assert len(completed) == 1
    assert completed[0].workflow_id == "wf-1"
    assert completed[0].prompt_id == "pid-1"


def test_run_ignores_short_binary_frame_and_completes(
    monkeypatch: MonkeyPatch,
) -> None:
    """Ignore truncated binary data while preserving terminal cleanup."""

    workflow: JsonObject = {"N1": {"class_type": "SugarCubes.CubeOutput"}}
    closed: list[bool] = []
    _progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload=workflow,
        messages=[
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": "N1", "prompt_id": "pid-1"},
                }
            ),
            b"\x00\x01",
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        close_events=closed,
    )

    assert closed == [True]
    assert failures == []
    assert len(completed) == 1
    assert completed[0].workflow_id == "wf-1"
    assert completed[0].prompt_id == "pid-1"


def test_run_reports_connection_reset_without_exception_traceback(
    monkeypatch: MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    """Report remote resets without publishing an exception traceback."""

    closed: list[bool] = []
    caplog.set_level(
        logging.WARNING,
        logger="sugarsubstitute.infrastructure.comfy.websocket_listener",
    )
    _progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={"1": {"class_type": "KSampler"}},
        messages=[],
        receive_error=ConnectionResetError(
            10054,
            "An existing connection was forcibly closed by the remote host",
        ),
        close_events=closed,
    )

    assert closed == [True]
    assert len(failures) == 1
    assert failures[0].error == (
        "Comfy websocket connection closed before generation completed."
    )
    assert len(completed) == 1
    assert completed[0].workflow_id == "wf-1"
    assert "reason=websocket_disconnected" in caplog.text
