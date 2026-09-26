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

"""Materialize validated generated videos under durable or session policy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from substitute.application.ports.video import VideoProbeResult
from substitute.infrastructure.comfy.output_destination_allocator import (
    OutputDestinationAllocator,
)
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
)
from substitute.infrastructure.comfy.session_video_artifact_store import (
    SessionVideoArtifactStore,
)


@dataclass(frozen=True, slots=True)
class PersistedOutputVideo:
    """Describe one promoted video artifact and validated media facts."""

    file_path: Path
    temporary: bool
    probe: VideoProbeResult


class OutputVideoPersistence:
    """Own staging, validation, and atomic promotion for generated videos."""

    def __init__(
        self,
        *,
        destination_allocator: OutputDestinationAllocator,
        session_store: SessionVideoArtifactStore,
    ) -> None:
        """Store destination and temporary-lifetime owners."""

        self._destination_allocator = destination_allocator
        self._session_store = session_store

    def materialize(
        self,
        *,
        source_identity: OutputSourceIdentity,
        suffix: str,
        stream: Callable[[Path], object],
        probe: Callable[[Path], VideoProbeResult],
    ) -> PersistedOutputVideo:
        """Stream, validate, and atomically promote one generated video."""

        partial_path = self._session_store.allocate_partial()
        try:
            stream(partial_path)
            probe_result = probe(partial_path)
            if not isinstance(probe_result, VideoProbeResult):
                raise TypeError("Video probe returned an invalid result.")
            durable_path = self._destination_allocator.allocate(
                source_identity=source_identity,
                width=probe_result.width,
                height=probe_result.height,
                suffix=suffix,
            )
            if durable_path is None:
                final_path = self._session_store.promote(
                    partial_path,
                    suffix=suffix,
                )
                return PersistedOutputVideo(
                    file_path=final_path,
                    temporary=True,
                    probe=probe_result,
                )
            partial_path.replace(durable_path)
            self._session_store.release(partial_path)
            return PersistedOutputVideo(
                file_path=durable_path,
                temporary=False,
                probe=probe_result,
            )
        except Exception:
            self._session_store.release(partial_path)
            raise


__all__ = ["OutputVideoPersistence", "PersistedOutputVideo"]
