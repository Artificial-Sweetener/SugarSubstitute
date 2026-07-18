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

"""Tests for standard Comfy executed-image takeover handling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from substitute.application.ports.comfy_gateway import (
    ListenerOutputSource,
    OutputImageUpdate,
)
from substitute.infrastructure.comfy.final_image_event import FinalImageScene
from substitute.infrastructure.comfy.final_image_event_handler import (
    FinalImageEventHandler,
)
from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
)
from substitute.infrastructure.comfy.standard_executed_image_handler import (
    StandardExecutedImageContext,
    StandardExecutedImageHandler,
)


@dataclass
class _Fetcher:
    """Record fetched standard artifacts."""

    artifacts: list[ComfyImageArtifact]

    def fetch(self, artifact: ComfyImageArtifact) -> bytes:
        """Record the artifact and return deterministic bytes."""

        self.artifacts.append(artifact)
        return artifact.filename.encode()


@dataclass(frozen=True)
class _Persisted:
    """Describe one fake persisted image."""

    file_path: Path
    width: int = 64
    height: int = 32


@dataclass
class _Persistence:
    """Record shared final-image persistence calls."""

    calls: list[tuple[bytes, OutputSourceIdentity]]

    def persist_output_image(
        self,
        *,
        image_bytes: bytes,
        source_identity: OutputSourceIdentity,
    ) -> _Persisted:
        """Record a persistence call and return a unique path."""

        self.calls.append((image_bytes, source_identity))
        return _Persisted(Path(f"{len(self.calls)}.png"))


def test_standard_executed_images_share_final_handler_and_keep_batch_indices() -> None:
    """One PreviewImage event should publish every batch artifact independently."""

    fetched: list[ComfyImageArtifact] = []
    persisted: list[tuple[bytes, OutputSourceIdentity]] = []
    updates: list[OutputImageUpdate] = []
    handler = StandardExecutedImageHandler(
        context=StandardExecutedImageContext(
            workflow_id="wf",
            generation_run_id="run",
            prompt_id="prompt",
            client_id="client",
            workflow_payload={"recover": {"class_type": "PreviewImage"}},
            scene=FinalImageScene(
                run_id="scene-run",
                key="scene-a",
                title="Scene A",
                order=0,
                count=2,
            ),
        ),
        sources_by_node={
            "recover": ListenerOutputSource(
                node_id="recover",
                source_key="direct:12:0",
                source_label="1",
            )
        },
        final_image_handler=FinalImageEventHandler(
            artifact_fetcher=_Fetcher(fetched),
            output_persistence=_Persistence(persisted),
            on_output_image=updates.append,
        ),
    )

    handled = handler.handle(
        {
            "prompt_id": "prompt",
            "node": "recover",
            "output": {
                "images": [
                    {"filename": "a.png", "subfolder": "", "type": "temp"},
                    {"filename": "b.png", "subfolder": "", "type": "temp"},
                ]
            },
        }
    )

    assert handled is True
    assert [artifact.filename for artifact in fetched] == ["a.png", "b.png"]
    assert [update.batch_index for update in updates] == [0, 1]
    assert [update.list_index for update in updates] == [0, 0]
    assert {update.source_key for update in updates} == {"direct:12:0"}
    assert {update.scene_key for update in updates} == {"scene-a"}


def test_standard_handler_ignores_foreign_nodes_and_prompts() -> None:
    """Only the exact recovery node and prompt may become final output."""

    updates: list[OutputImageUpdate] = []
    handler = StandardExecutedImageHandler(
        context=StandardExecutedImageContext(
            workflow_id="wf",
            generation_run_id="run",
            prompt_id="prompt",
            client_id="client",
            workflow_payload={},
            scene=FinalImageScene(),
        ),
        sources_by_node={"recover": ListenerOutputSource("recover", "direct:1:0", "1")},
        final_image_handler=FinalImageEventHandler(
            artifact_fetcher=_Fetcher([]),
            output_persistence=_Persistence([]),
            on_output_image=updates.append,
        ),
    )

    assert handler.handle({"prompt_id": "prompt", "node": "other"}) is False
    assert handler.handle({"prompt_id": "other", "node": "recover"}) is False
    assert updates == []
