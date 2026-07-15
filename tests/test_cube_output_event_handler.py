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

"""Tests for Comfy cube-output artifact handling."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from substitute.application.ports.comfy_gateway import OutputImageUpdate
from substitute.infrastructure.comfy.cube_output_event import CubeOutputArtifact
from substitute.infrastructure.comfy.cube_output_event_handler import (
    CubeOutputEventHandler,
)
from substitute.infrastructure.comfy.cube_output_event_router import (
    CubeOutputDiagnostic,
    CubeOutputRouteContext,
)
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
)


def _payload(**updates: object) -> dict[str, object]:
    """Return a valid cube-output payload with optional top-level updates."""

    payload: dict[str, object] = {
        "version": 2,
        "prompt_id": "pid-1",
        "node_id": "output-node",
        "list_index": 5,
        "cube_id": "cube-1",
        "default_alias": "CubeA",
        "instance_alias": "CubeA",
        "instance_id": "instance-1",
        "media_kind": "image",
        "value_type": "image",
        "artifacts": [
            {
                "filename": "image.png",
                "subfolder": "",
                "type": "output",
                "media_kind": "image",
                "width": 320,
                "height": 240,
            }
        ],
        "substitute": {
            "schemaVersion": 1,
            "workflowId": "wf-1",
            "generationRunId": "run-1",
            "clientId": "client-1",
            "sourceKey": "wf-1:output-node",
            "sourceLabel": "CubeA",
            "sceneRunId": "scene-run-1",
            "sceneKey": "scene-a",
            "sceneTitle": "Scene A",
            "sceneOrder": 2,
            "sceneCount": 4,
        },
    }
    payload.update(updates)
    return payload


@dataclass
class _ArtifactFetcher:
    """Record fetched artifacts and return deterministic image bytes."""

    artifacts: list[CubeOutputArtifact]

    def fetch(self, artifact: CubeOutputArtifact) -> bytes:
        """Record one fetched artifact."""

        self.artifacts.append(artifact)
        return b"image-bytes"


@dataclass(frozen=True)
class _PersistedImage:
    """Describe a persisted fake image."""

    file_path: Path
    width: int
    height: int


@dataclass
class _OutputPersistence:
    """Record persisted bytes and source identities."""

    calls: list[tuple[bytes, OutputSourceIdentity]]

    def persist_output_image(
        self,
        *,
        image_bytes: bytes,
        source_identity: OutputSourceIdentity,
    ) -> _PersistedImage:
        """Record persistence input and return a deterministic output path."""

        self.calls.append((image_bytes, source_identity))
        return _PersistedImage(
            file_path=Path("out.png"),
            width=640,
            height=480,
        )


def _handler(
    *,
    fetcher: _ArtifactFetcher | None = None,
    persistence: _OutputPersistence | None = None,
    output_events: list[OutputImageUpdate] | None = None,
    diagnostics: list[CubeOutputDiagnostic] | None = None,
    identity_accepted: bool = True,
) -> CubeOutputEventHandler:
    """Build a cube-output handler with recording test doubles."""

    captured_output_events = output_events if output_events is not None else []
    captured_diagnostics = diagnostics if diagnostics is not None else []
    return CubeOutputEventHandler(
        context=CubeOutputRouteContext(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
        ),
        workflow_payload={"output-node": {"class_type": "SugarCubes.CubeOutput"}},
        artifact_fetcher=fetcher or _ArtifactFetcher([]),
        output_persistence=persistence or _OutputPersistence([]),
        identity_acceptor=lambda _identity, _prompt_id, _node_id: identity_accepted,
        on_output_image=captured_output_events.append,
        on_diagnostic=captured_diagnostics.append,
    )


def test_cube_output_event_handler_keeps_infrastructure_boundary() -> None:
    """Cube-output handling must not import Qt, presentation, or listener code."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "infrastructure"
        / "comfy"
        / "cube_output_event_handler.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_roots = {
        "PySide6",
        "qfluentwidgets",
        "qframelesswindow",
        "substitute.presentation",
        "substitute.infrastructure.comfy.websocket_listener",
    }

    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    assert not {
        module
        for module in imported_modules
        for forbidden in forbidden_roots
        if module == forbidden or module.startswith(f"{forbidden}.")
    }


def test_handler_fetches_persists_and_emits_output_image_update() -> None:
    """Valid image artifacts should be fetched, persisted, and emitted."""

    fetched_artifacts: list[CubeOutputArtifact] = []
    persisted_calls: list[tuple[bytes, OutputSourceIdentity]] = []
    output_events: list[OutputImageUpdate] = []
    handler = _handler(
        fetcher=_ArtifactFetcher(fetched_artifacts),
        persistence=_OutputPersistence(persisted_calls),
        output_events=output_events,
    )

    handler.handle(_payload())

    assert [artifact.filename for artifact in fetched_artifacts] == ["image.png"]
    assert persisted_calls == [
        (
            b"image-bytes",
            OutputSourceIdentity(
                node_id="output-node",
                source_key="wf-1:output-node",
                source_label="CubeA",
                cube_alias="CubeA",
            ),
        )
    ]
    assert output_events == [
        OutputImageUpdate(
            workflow_id="wf-1",
            workflow_payload={"output-node": {"class_type": "SugarCubes.CubeOutput"}},
            file_path=Path("out.png"),
            node_id="output-node",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
            source_key="wf-1:output-node",
            source_label="CubeA",
            list_index=5,
            artifact_width=320,
            artifact_height=240,
            scene_run_id="scene-run-1",
            scene_key="scene-a",
            scene_title="Scene A",
            scene_order=2,
            scene_count=4,
        )
    ]


def test_handler_uses_persisted_dimensions_when_artifact_dimensions_are_missing() -> (
    None
):
    """Persisted image dimensions should backfill missing artifact dimensions."""

    output_events: list[OutputImageUpdate] = []
    handler = _handler(output_events=output_events)
    payload = _payload(
        artifacts=[
            {
                "filename": "image.png",
                "subfolder": "",
                "type": "output",
                "media_kind": "image",
            }
        ]
    )

    handler.handle(payload)

    assert output_events[0].artifact_width == 640
    assert output_events[0].artifact_height == 480


def test_handler_skips_non_image_artifacts_inside_image_events() -> None:
    """Non-image artifacts should not be fetched or emitted."""

    fetched_artifacts: list[CubeOutputArtifact] = []
    output_events: list[OutputImageUpdate] = []
    handler = _handler(
        fetcher=_ArtifactFetcher(fetched_artifacts),
        output_events=output_events,
    )
    payload = _payload(
        artifacts=[
            {
                "filename": "metadata.json",
                "subfolder": "",
                "type": "output",
                "media_kind": "value",
            }
        ]
    )

    handler.handle(payload)

    assert fetched_artifacts == []
    assert output_events == []


def test_handler_emits_diagnostics_without_fetching_artifacts() -> None:
    """Invalid cube-output payloads should route diagnostics and stop."""

    diagnostics: list[CubeOutputDiagnostic] = []
    fetched_artifacts: list[CubeOutputArtifact] = []
    handler = _handler(
        fetcher=_ArtifactFetcher(fetched_artifacts),
        diagnostics=diagnostics,
    )

    handler.handle(_payload(prompt_id="other-prompt"))

    assert fetched_artifacts == []
    assert len(diagnostics) == 1
    assert diagnostics[0].message == "Ignoring cube-output event for different prompt"


def test_handler_suppresses_output_after_identity_rejection() -> None:
    """Rejected Substitute visual identity should not fetch or emit outputs."""

    fetched_artifacts: list[CubeOutputArtifact] = []
    output_events: list[OutputImageUpdate] = []
    handler = _handler(
        fetcher=_ArtifactFetcher(fetched_artifacts),
        output_events=output_events,
        identity_accepted=False,
    )

    handler.handle(_payload())

    assert fetched_artifacts == []
    assert output_events == []
