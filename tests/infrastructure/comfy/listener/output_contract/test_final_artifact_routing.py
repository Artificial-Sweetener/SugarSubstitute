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

"""Verify final cube-output routing and strict artifact identity validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from _pytest.monkeypatch import MonkeyPatch

from tests.infrastructure.comfy.listener.output_contract_harness import (
    _cube_output_message,
    _mutated_cube_output_identity_message,
    _mutated_cube_output_message,
    _run_cube_output_visual_messages,
)


def test_run_preserves_cube_output_source_scene_and_list_index(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Preserve final routing, scene, and list-index metadata in output DTOs."""

    message: Any = json.loads(_cube_output_message(node_id="output-node"))
    message["data"]["list_index"] = 5
    message["data"]["substitute"]["sceneRunId"] = "scene-run-1"
    message["data"]["substitute"]["sceneKey"] = "scene-b"
    message["data"]["substitute"]["sceneTitle"] = "Scene B"
    message["data"]["substitute"]["sceneOrder"] = 2
    message["data"]["substitute"]["sceneCount"] = 4

    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            json.dumps(message),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert len(output_events) == 1
    assert output_events[0].source_key == "wf-1:output-node"
    assert output_events[0].source_label == "CubeA"
    assert output_events[0].scene_run_id == "scene-run-1"
    assert output_events[0].scene_key == "scene-b"
    assert output_events[0].scene_title == "Scene B"
    assert output_events[0].scene_order == 2
    assert output_events[0].scene_count == 4
    assert output_events[0].list_index == 5


def test_run_preserves_every_cube_output_batch_artifact(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Publish every final image artifact in backend batch order."""

    message: Any = json.loads(_cube_output_message(node_id="output-node"))
    second_artifact = dict(message["data"]["artifacts"][0])
    second_artifact["filename"] = "ComfyUI_temp_demo_00002_.png"
    message["data"]["artifacts"].append(second_artifact)
    fetched_artifacts: list[object] = []
    saved_paths: list[str] = []

    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            json.dumps(message),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        fetched_artifacts=fetched_artifacts,
        saved_paths=saved_paths,
    )

    assert failures == []
    assert len(completed) == 1
    assert [event.batch_index for event in output_events] == [0, 1]
    assert len(fetched_artifacts) == 2
    assert len(saved_paths) == 2
    assert saved_paths[0] != saved_paths[1]


@pytest.mark.parametrize(
    ("message", "case_name"),
    [
        (_cube_output_message(prompt_id="other-prompt"), "prompt"),
        (_cube_output_message(workflow_id="wf-other"), "workflow"),
        (_cube_output_message(generation_run_id="run-other"), "generation_run"),
        (_cube_output_message(client_id="client-other"), "client"),
    ],
)
def test_run_rejects_stale_and_mismatched_cube_output_identity(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    message: str,
    case_name: str,
) -> None:
    """Reject stale or mismatched final identity before fetching or persistence."""

    fetched_artifacts: list[object] = []
    saved_paths: list[str] = []
    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            message,
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        fetched_artifacts=fetched_artifacts,
        saved_paths=saved_paths,
    )

    assert failures == [], case_name
    assert len(completed) == 1
    assert output_events == []
    assert fetched_artifacts == []
    assert saved_paths == []


def test_run_hydrates_missing_artifact_dimensions_from_fetched_image_bytes(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Hydrate missing image dimensions before publishing strict output DTOs."""

    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            _cube_output_message(node_id="output-node"),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert output_events[0].artifact_width == 640
    assert output_events[0].artifact_height == 480


@pytest.mark.parametrize(
    ("message", "case_name"),
    [
        (_mutated_cube_output_message(list_index=None), "missing"),
        (_mutated_cube_output_message(list_index="0"), "non_integer"),
        (_mutated_cube_output_message(list_index=-1), "negative"),
    ],
)
def test_run_rejects_cube_output_without_list_index_before_registration(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    message: str,
    case_name: str,
) -> None:
    """Reject absent, non-integer, and negative final artifact indexes before IO."""

    fetched_artifacts: list[object] = []
    saved_paths: list[str] = []
    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            message,
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        fetched_artifacts=fetched_artifacts,
        saved_paths=saved_paths,
    )

    assert failures == [], case_name
    assert len(completed) == 1
    assert output_events == []
    assert fetched_artifacts == []
    assert saved_paths == []


def test_run_rejects_non_image_final_media_and_artifacts(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Reject non-image final media and artifacts without producing output images."""

    non_image_artifact: Any = json.loads(_cube_output_message())
    non_image_artifact["data"]["artifacts"][0]["media_kind"] = "text"
    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            _mutated_cube_output_message(media_kind="text"),
            json.dumps(non_image_artifact),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert output_events == []


def test_run_rejects_cube_output_without_required_v2_identity(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Reject final output events missing required Substitute v2 identity fields."""

    fetched_artifacts: list[object] = []
    saved_paths: list[str] = []
    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            _mutated_cube_output_message(substitute=None),
            _mutated_cube_output_identity_message(sourceKey=None),
            _mutated_cube_output_identity_message(sourceLabel=None),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        fetched_artifacts=fetched_artifacts,
        saved_paths=saved_paths,
    )

    assert failures == []
    assert len(completed) == 1
    assert output_events == []
    assert fetched_artifacts == []
    assert saved_paths == []
