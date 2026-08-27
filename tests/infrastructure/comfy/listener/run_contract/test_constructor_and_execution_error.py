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

"""Verify listener construction and terminal execution-error publication."""

from __future__ import annotations

import json
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.domain.common import JsonObject
from tests.infrastructure.comfy.listener.contract_harness import (
    _build_callbacks,
    _build_request,
    _import_listener_module,
    _run_listener_messages,
)


def test_runnable_collects_cube_output_nodes(monkeypatch: MonkeyPatch) -> None:
    """Collect every SugarCubes output node while constructing the listener."""

    module = _import_listener_module(monkeypatch)
    callbacks, *_ = _build_callbacks()
    workflow: JsonObject = {
        "1": {"class_type": "SugarCubes.CubeOutput"},
        "2": {"class_type": "KSampler"},
        "3": {"class_type": "SugarCubes.CubeOutput"},
    }
    runnable = module.ComfyWebsocketListener(
        request=_build_request(output_dir=Path("."), workflow_payload=workflow),
        callbacks=callbacks,
    )

    assert runnable.cube_output_node_ids == {"1", "3"}


def test_runnable_reports_execution_error_detail(monkeypatch: MonkeyPatch) -> None:
    """Publish structured Comfy execution errors before completing the session."""

    workflow: JsonObject = {"1": {"class_type": "KSampler"}}
    _progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload=workflow,
        messages=[
            json.dumps(
                {
                    "type": "execution_error",
                    "data": {
                        "prompt_id": "pid-1",
                        "exception_type": "ModuleNotFoundError",
                        "exception_message": "No module named 'xformers'",
                        "node_id": "12",
                        "node_type": "KSampler",
                        "executed": ["1", "2"],
                        "traceback": ["Traceback line 1", "Traceback line 2"],
                        "current_inputs": {"seed": 123},
                        "current_outputs": {"samples": []},
                    },
                }
            )
        ],
    )

    assert len(failures) == 1
    assert failures[0].error == "ModuleNotFoundError: No module named 'xformers'"
    assert failures[0].detail == "Traceback line 1\nTraceback line 2"
    assert failures[0].error_report is not None
    assert render_source_application_text(failures[0].error_report.title) == (
        "KSampler failed"
    )
    assert failures[0].error_report.runtime.comfy_version == "0.3.1"
    assert failures[0].error_report.runtime.pytorch_version == "2.8.0"
    assert failures[0].error_report.runtime.devices == (
        "NVIDIA GeForce RTX 5090 (cuda #0)",
    )
    assert failures[0].error_report.node is not None
    assert failures[0].error_report.node.node_id == "12"
    assert failures[0].error_report.node.current_inputs == {"seed": 123}
    assert completed[0].prompt_id == "pid-1"
