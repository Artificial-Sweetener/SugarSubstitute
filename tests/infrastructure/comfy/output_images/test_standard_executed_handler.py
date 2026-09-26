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

"""Verify standard Comfy executed-image takeover handling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from substitute.application.ports.comfy_gateway import (
    ListenerOutputSource,
    OutputImageUpdate,
)
from substitute.domain.output_media import OutputMediaKind
from substitute.infrastructure.comfy.final_image_event import (
    FinalImageEvent,
    FinalImageScene,
    FinalImageSource,
)
from substitute.infrastructure.comfy.final_image_event_handler import (
    FinalImageEventHandler,
)
from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
)
from substitute.infrastructure.comfy.prompt_history_output_recovery import (
    PromptHistoryOutputRecovery,
    PromptHistoryRecoveryContext,
)
from substitute.infrastructure.comfy.standard_executed_output_handler import (
    StandardExecutedOutputContext,
    StandardExecutedOutputHandler,
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


@dataclass
class _DiscardSink:
    """Discard final-output events outside the behavior under test."""

    def handle(self, event: FinalImageEvent) -> None:
        """Accept one event without side effects."""

        del event


@dataclass
class _RecordingSink:
    """Record neutral final-output events for routing assertions."""

    events: list[FinalImageEvent]

    def handle(self, event: FinalImageEvent) -> None:
        """Record one typed-media event."""

        self.events.append(event)


def test_standard_executed_images_share_final_handler_and_keep_batch_indices() -> None:
    """One PreviewImage event should publish every batch artifact independently."""

    fetched: list[ComfyImageArtifact] = []
    persisted: list[tuple[bytes, OutputSourceIdentity]] = []
    updates: list[OutputImageUpdate] = []
    handler = StandardExecutedOutputHandler(
        context=StandardExecutedOutputContext(
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
        final_video_handler=_DiscardSink(),
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
    handler = StandardExecutedOutputHandler(
        context=StandardExecutedOutputContext(
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
        final_video_handler=_DiscardSink(),
    )

    assert handler.handle({"prompt_id": "prompt", "node": "other"}) is False
    assert handler.handle({"prompt_id": "other", "node": "recover"}) is False
    assert updates == []


def test_standard_executed_video_routes_only_to_video_handler() -> None:
    """Parse a declared video envelope without treating its poster as an image."""

    image_events: list[FinalImageEvent] = []
    video_events: list[FinalImageEvent] = []
    handler = StandardExecutedOutputHandler(
        context=StandardExecutedOutputContext(
            workflow_id="wf",
            generation_run_id="run",
            prompt_id="prompt",
            client_id="client",
            workflow_payload={},
            scene=FinalImageScene(),
        ),
        sources_by_node={
            "video": ListenerOutputSource(
                "video",
                "direct:7:0",
                "Motion",
                OutputMediaKind.VIDEO,
            )
        },
        final_image_handler=_RecordingSink(image_events),
        final_video_handler=_RecordingSink(video_events),
    )

    handled = handler.handle(
        {
            "prompt_id": "prompt",
            "node": "video",
            "output": {
                "videos": [
                    {
                        "filename": "motion.webm",
                        "subfolder": "generated",
                        "type": "output",
                    }
                ]
            },
        }
    )

    assert handled
    assert image_events == []
    assert len(video_events) == 1
    assert video_events[0].artifacts[0].media_kind == "video"
    assert video_events[0].artifacts[0].filename == "motion.webm"


def test_shared_final_handler_deduplicates_transport_replays() -> None:
    """Cube-output and standard executed delivery may report the same artifact once."""

    fetched: list[ComfyImageArtifact] = []
    persisted: list[tuple[bytes, OutputSourceIdentity]] = []
    updates: list[OutputImageUpdate] = []
    final_handler = FinalImageEventHandler(
        artifact_fetcher=_Fetcher(fetched),
        output_persistence=_Persistence(persisted),
        on_output_image=updates.append,
    )
    handler = StandardExecutedOutputHandler(
        context=StandardExecutedOutputContext(
            workflow_id="wf",
            generation_run_id="run",
            prompt_id="prompt",
            client_id="client",
            workflow_payload={},
            scene=FinalImageScene(),
        ),
        sources_by_node={
            "recover": ListenerOutputSource("recover", "cube:cube-a", "Cube A")
        },
        final_image_handler=final_handler,
        final_video_handler=_DiscardSink(),
    )
    event = {
        "prompt_id": "prompt",
        "node": "recover",
        "output": {
            "images": [{"filename": "same.png", "subfolder": "", "type": "temp"}]
        },
    }

    assert handler.handle(event) is True
    assert handler.handle(event) is True
    assert len(fetched) == 1
    assert len(persisted) == 1
    assert len(updates) == 1


def test_shared_final_handler_deduplicates_conflicting_transport_source_labels() -> (
    None
):
    """One node artifact must survive transport disagreement as one final image."""

    fetched: list[ComfyImageArtifact] = []
    persisted: list[tuple[bytes, OutputSourceIdentity]] = []
    updates: list[OutputImageUpdate] = []
    handler = FinalImageEventHandler(
        artifact_fetcher=_Fetcher(fetched),
        output_persistence=_Persistence(persisted),
        on_output_image=updates.append,
    )
    artifact = ComfyImageArtifact(
        filename="same.png",
        subfolder="",
        type="temp",
        media_kind="image",
    )

    for source_key in ("direct:1:0", "cube:1"):
        handler.handle(
            FinalImageEvent(
                workflow_id="wf",
                generation_run_id="run",
                prompt_id="prompt",
                client_id="client",
                workflow_payload={},
                source=FinalImageSource(
                    node_id="recover",
                    source_key=source_key,
                    source_label="1",
                    cube_alias="1",
                ),
                artifacts=(artifact,),
                list_index=0,
                scene=FinalImageScene(),
            )
        )

    assert len(fetched) == 1
    assert len(persisted) == 1
    assert [update.source_key for update in updates] == ["direct:1:0"]


def test_live_and_history_delivery_share_one_artifact_identity() -> None:
    """History recovery must fill cached gaps without duplicating live finals."""

    fetched: list[ComfyImageArtifact] = []
    persisted: list[tuple[bytes, OutputSourceIdentity]] = []
    updates: list[OutputImageUpdate] = []
    final_handler = FinalImageEventHandler(
        artifact_fetcher=_Fetcher(fetched),
        output_persistence=_Persistence(persisted),
        on_output_image=updates.append,
    )
    source = ListenerOutputSource("recover", "cube:cube-a", "Cube A")
    handler = StandardExecutedOutputHandler(
        context=StandardExecutedOutputContext(
            workflow_id="wf",
            generation_run_id="run",
            prompt_id="prompt",
            client_id="client",
            workflow_payload={},
            scene=FinalImageScene(),
        ),
        sources_by_node={"recover": source},
        final_image_handler=final_handler,
        final_video_handler=_DiscardSink(),
    )
    output = {"images": [{"filename": "same.png", "subfolder": "", "type": "temp"}]}

    assert handler.handle({"prompt_id": "prompt", "node": "recover", "output": output})
    PromptHistoryOutputRecovery(
        history_reader=_StaticHistoryReader(
            {"prompt": {"outputs": {"recover": output}}}
        ),
        context=PromptHistoryRecoveryContext(
            workflow_id="wf",
            generation_run_id="run",
            prompt_id="prompt",
            client_id="client",
            workflow_payload={},
        ),
        output_node_ids=frozenset({"recover"}),
        source_resolver=lambda node_id: OutputSourceIdentity(
            node_id=node_id,
            source_key=source.source_key,
            source_label=source.source_label,
            cube_alias=source.source_label,
        ),
        final_image_handler=final_handler,
        final_video_handler=_DiscardSink(),
    ).recover()

    assert len(fetched) == 1
    assert len(persisted) == 1
    assert len(updates) == 1


@dataclass(frozen=True)
class _StaticHistoryReader:
    """Return one static prompt-history payload."""

    payload: dict[str, object]

    def read(self, prompt_id: str) -> dict[str, object]:
        """Return the configured payload for the expected prompt."""

        assert prompt_id == "prompt"
        return self.payload
