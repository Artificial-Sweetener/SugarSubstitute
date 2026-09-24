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

"""Verify secure video transfer, persistence, and update publication."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from substitute.application.ports import OutputSavePlan, OutputVideoUpdate
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.artifact_fetcher import ComfyArtifactFetcher
from substitute.infrastructure.comfy.artifact_locator_validation import (
    validate_artifact_locator,
)
from substitute.infrastructure.comfy.final_image_event import (
    FinalImageEvent,
    FinalImageSource,
)
from substitute.infrastructure.comfy.final_video_event_handler import (
    FinalVideoEventHandler,
)
from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact
from substitute.infrastructure.comfy.output_destination_allocator import (
    OutputDestinationAllocator,
)
from substitute.application.ports.video import VideoProbeResult
from substitute.infrastructure.comfy.output_video_persistence import (
    OutputVideoPersistence,
)
from substitute.infrastructure.comfy.session_video_artifact_store import (
    SessionVideoArtifactStore,
)


def test_artifact_locator_rejects_paths_and_unknown_type() -> None:
    """Reject traversal, absolute names, device names, and unknown stores."""

    unsafe = (
        ComfyImageArtifact("../movie.mp4", "", "output", media_kind="video"),
        ComfyImageArtifact("movie.mp4", "../other", "output", media_kind="video"),
        ComfyImageArtifact("C:\\movie.mp4", "", "output", media_kind="video"),
        ComfyImageArtifact("CON", "", "output", media_kind="video"),
        ComfyImageArtifact("movie.mp4", "", "remote", media_kind="video"),
    )

    for artifact in unsafe:
        with pytest.raises(ValueError):
            validate_artifact_locator(artifact)


def test_streaming_enforces_size_and_removes_partial(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Delete incomplete transfers when streamed bytes exceed the bound."""

    response = _Response(chunks=(b"1234", b"5678"))
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.artifact_fetcher.requests.get",
        lambda *_args, **_kwargs: response,
    )
    destination = tmp_path / "movie.partial"
    fetcher = ComfyArtifactFetcher(endpoint=ComfyEndpoint("127.0.0.1", 8188))

    with pytest.raises(ValueError, match="size limit"):
        fetcher.stream_to(
            ComfyImageArtifact("movie.mp4", "clips", "output", media_kind="video"),
            destination,
            maximum_bytes=7,
            chunk_bytes=4,
        )

    assert not destination.exists()


def test_video_handler_promotes_transient_artifact_and_deduplicates(
    tmp_path: Path,
) -> None:
    """Publish one session-owned video only after streaming and probing succeed."""

    store = SessionVideoArtifactStore(tmp_path / "session")
    updates: list[OutputVideoUpdate] = []
    streamer = _Streamer(b"video-data")
    handler = FinalVideoEventHandler(
        artifact_streamer=streamer,
        output_persistence=OutputVideoPersistence(
            destination_allocator=_allocator(
                tmp_path,
                persisted_aliases=frozenset(),
            ),
            session_store=store,
        ),
        video_probe=_Probe(),
        on_output_video=updates.append,
    )
    event = _event()

    handler.handle(event)
    handler.handle(event)

    assert len(updates) == 1
    update = updates[0]
    assert update.temporary is True
    assert update.file_path.parent == store.root
    assert update.file_path.suffix == ".webm"
    assert update.file_path.read_bytes() == b"video-data"
    assert update.poster_bytes == b"poster"
    assert update.artifact_width == 320
    assert update.artifact_height == 180
    assert streamer.calls == 1
    store.close()


def test_video_handler_promotes_durable_artifact_atomically(tmp_path: Path) -> None:
    """Move a validated transfer into the normal output destination policy."""

    store = SessionVideoArtifactStore(tmp_path / "session")
    updates: list[OutputVideoUpdate] = []
    handler = FinalVideoEventHandler(
        artifact_streamer=_Streamer(b"video-data"),
        output_persistence=OutputVideoPersistence(
            destination_allocator=_allocator(tmp_path, persisted_aliases=None),
            session_store=store,
        ),
        video_probe=_Probe(),
        on_output_video=updates.append,
    )

    handler.handle(_event())

    assert updates[0].temporary is False
    assert updates[0].file_path == tmp_path / "output" / "001_main_1.webm"
    assert updates[0].file_path.read_bytes() == b"video-data"
    assert not tuple(store.root.glob("*.partial"))
    store.close()


def test_probe_failure_removes_partial_and_publishes_nothing(tmp_path: Path) -> None:
    """Treat failed decode validation as a clean artifact miss."""

    store = SessionVideoArtifactStore(tmp_path / "session")
    updates: list[OutputVideoUpdate] = []
    handler = FinalVideoEventHandler(
        artifact_streamer=_Streamer(b"invalid"),
        output_persistence=OutputVideoPersistence(
            destination_allocator=_allocator(tmp_path, persisted_aliases=None),
            session_store=store,
        ),
        video_probe=_FailingProbe(),
        on_output_video=updates.append,
    )

    with pytest.raises(ValueError, match="decode"):
        handler.handle(_event())

    assert updates == []
    assert not tuple(store.root.iterdir())
    store.close()


class _Response:
    """Provide the requests response surface used by streaming tests."""

    def __init__(self, *, chunks: tuple[bytes, ...]) -> None:
        """Store deterministic response chunks."""

        self.headers: dict[str, str] = {}
        self._chunks = chunks

    def __enter__(self) -> "_Response":
        """Return this response from a context manager."""

        return self

    def __exit__(self, *_args: object) -> None:
        """Close without suppressing errors."""

    def raise_for_status(self) -> None:
        """Represent a successful HTTP response."""

    def iter_content(self, *, chunk_size: int) -> tuple[bytes, ...]:
        """Return deterministic chunks independent of requested size."""

        del chunk_size
        return self._chunks


class _Streamer:
    """Write deterministic bytes to the requested partial path."""

    def __init__(self, payload: bytes) -> None:
        """Store payload and call count."""

        self._payload = payload
        self.calls = 0

    def stream_to(self, artifact: ComfyImageArtifact, destination: Path) -> int:
        """Write one fake downloaded artifact."""

        del artifact
        self.calls += 1
        destination.write_bytes(self._payload)
        return len(self._payload)


class _Probe:
    """Return deterministic validated video facts."""

    def probe(
        self,
        path: Path,
        *,
        artifact: ComfyImageArtifact,
    ) -> VideoProbeResult:
        """Validate that the stream exists before returning facts."""

        assert path.read_bytes()
        return VideoProbeResult(
            width=artifact.width or 320,
            height=artifact.height or 180,
            duration_seconds=2.5,
            mime_type="video/webm",
            poster_bytes=b"poster",
        )


class _FailingProbe:
    """Reject every staged artifact."""

    def probe(
        self,
        path: Path,
        *,
        artifact: ComfyImageArtifact,
    ) -> VideoProbeResult:
        """Raise the deterministic decode failure."""

        del path, artifact
        raise ValueError("decode failed")


def _allocator(
    tmp_path: Path,
    *,
    persisted_aliases: frozenset[str] | None,
) -> OutputDestinationAllocator:
    """Return a deterministic output allocator."""

    return OutputDestinationAllocator(
        output_save_plan=OutputSavePlan(
            output_root=tmp_path / "output",
            path_pattern="{run}_{source}_{set}",
            workflow_name="Workflow",
            output_run_number=1,
            job_started_at=datetime(2026, 9, 24),
            persisted_cube_aliases=persisted_aliases,
        ),
        cube_numbers_by_alias={},
    )


def _event() -> FinalImageEvent:
    """Return one deterministic generated video event."""

    return FinalImageEvent(
        workflow_id="workflow",
        generation_run_id="run",
        prompt_id="prompt",
        client_id="client",
        workflow_payload={},
        source=FinalImageSource(
            node_id="node",
            source_key="workflow:node",
            source_label="Main",
            cube_alias="Main",
        ),
        artifacts=(
            ComfyImageArtifact(
                filename="movie.webm",
                subfolder="clips",
                type="output",
                media_kind="video",
            ),
        ),
        list_index=0,
    )
