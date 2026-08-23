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

"""Contract tests for strict live Output visual event boundaries."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from substitute.application.ports import OutputImageUpdate, PreviewImageUpdate
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    LivePreviewEvent,
    OutputSceneIdentity,
    SourceOnlyOutputIdentity,
)


def test_live_preview_event_preserves_identity_and_node_metadata() -> None:
    """Strict previews should retain backend identity and raw node metadata."""

    event = LivePreviewEvent.from_update(
        PreviewImageUpdate(
            workflow_id="wf",
            image="preview",
            generation_run_id="run",
            prompt_id="prompt",
            client_id="client",
            node_id="resolved-node",
            metadata_node_id="metadata-node",
            display_node_id="display-node",
            parent_node_id="parent-node",
            real_node_id="real-node",
            source_key="wf:save",
            source_label="Save",
        )
    )

    assert event is not None
    assert event.identity.source_key == "wf:save"
    assert isinstance(event.identity.scene, SourceOnlyOutputIdentity)
    assert event.node_identity.resolved_node_id == "resolved-node"
    assert event.node_identity.metadata_node_id == "metadata-node"
    assert event.node_identity.display_node_id == "display-node"
    assert event.node_identity.parent_node_id == "parent-node"
    assert event.node_identity.real_node_id == "real-node"


def test_live_preview_event_rejects_missing_identity_or_resolved_node() -> None:
    """Strict previews should fail closed before canvas preview ingress."""

    assert (
        LivePreviewEvent.from_update(
            PreviewImageUpdate(
                workflow_id="wf",
                image="preview",
                generation_run_id="run",
                prompt_id="prompt",
                client_id="client",
                node_id=None,
                source_key="wf:save",
                source_label="Save",
            )
        )
        is None
    )
    assert (
        LivePreviewEvent.from_update(
            PreviewImageUpdate(
                workflow_id="wf",
                image="preview",
                generation_run_id="run",
                prompt_id="prompt",
                client_id=None,
                node_id="resolved-node",
                source_key="wf:save",
                source_label="Save",
            )
        )
        is None
    )


def test_live_final_event_preserves_list_index_dimensions_and_scene_identity() -> None:
    """Strict final events should carry backend slot and complete scene identity."""

    event = LiveFinalOutputEvent.from_update(
        OutputImageUpdate(
            workflow_id="wf",
            workflow_payload={},
            file_path=Path("E:/out.png"),
            node_id="save",
            generation_run_id="run",
            prompt_id="prompt",
            client_id="client",
            source_key="wf:save",
            source_label="Save",
            list_index=3,
            artifact_width=640,
            artifact_height=480,
            scene_run_id="scene-run",
            scene_key="scene-a",
            scene_title="Scene A",
            scene_order=2,
            scene_count=4,
        )
    )

    assert event is not None
    assert event.node_id == "save"
    assert event.position.list_index == 3
    assert event.position.batch_index == 0
    assert event.artifact_width == 640
    assert event.artifact_height == 480
    assert event.identity.scene == OutputSceneIdentity(
        run_id="scene-run",
        key="scene-a",
        title="Scene A",
        order=2,
        count=4,
    )


def test_live_final_event_rejects_missing_slot_dimensions_or_partial_scene() -> None:
    """Strict final events should reject incomplete backend routing data."""

    base = OutputImageUpdate(
        workflow_id="wf",
        workflow_payload={},
        file_path=Path("E:/out.png"),
        node_id="save",
        generation_run_id="run",
        prompt_id="prompt",
        client_id="client",
        source_key="wf:save",
        source_label="Save",
        list_index=0,
        artifact_width=640,
        artifact_height=480,
    )

    assert LiveFinalOutputEvent.from_update(base) is not None
    assert LiveFinalOutputEvent.from_update(replace(base, list_index=None)) is None
    assert LiveFinalOutputEvent.from_update(replace(base, list_index=-1)) is None
    assert LiveFinalOutputEvent.from_update(replace(base, list_index=True)) is None
    assert LiveFinalOutputEvent.from_update(replace(base, artifact_width=None)) is None
    assert LiveFinalOutputEvent.from_update(replace(base, artifact_width=True)) is None
    assert LiveFinalOutputEvent.from_update(replace(base, artifact_height=0)) is None
    assert LiveFinalOutputEvent.from_update(replace(base, scene_key="scene-a")) is None


@pytest.mark.parametrize(
    "field_updates",
    (
        {"workflow_id": ""},
        {"generation_run_id": None},
        {"prompt_id": None},
        {"client_id": None},
        {"source_key": ""},
        {"source_label": ""},
        {"node_id": ""},
        {"list_index": None},
        {"artifact_width": None},
        {"artifact_height": None},
    ),
)
def test_live_final_event_rejects_every_required_identity_gap(
    field_updates: dict[str, object],
) -> None:
    """Missing backend visual identity should fail before live registration."""

    base = OutputImageUpdate(
        workflow_id="wf",
        workflow_payload={},
        file_path=Path("E:/out.png"),
        node_id="save",
        generation_run_id="run",
        prompt_id="prompt",
        client_id="client",
        source_key="wf:save",
        source_label="Save",
        list_index=0,
        artifact_width=640,
        artifact_height=480,
    )

    assert (
        LiveFinalOutputEvent.from_update(replace(base, **cast(Any, field_updates)))
        is None
    )
