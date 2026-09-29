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

"""Fetch Comfy artifacts referenced by cube-output events."""

from __future__ import annotations

from pathlib import Path

import requests

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.artifact_urls import artifact_view_url
from substitute.infrastructure.comfy.artifact_locator_validation import (
    validate_artifact_locator,
)
from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact


class ComfyArtifactFetcher:
    """Fetch artifact bytes through Comfy's public ``/view`` endpoint."""

    def __init__(
        self,
        *,
        endpoint: ComfyEndpoint,
        timeout_seconds: float = 10.0,
    ) -> None:
        """Store endpoint and network timeout settings."""

        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds

    def fetch(self, artifact: ComfyImageArtifact) -> bytes:
        """Fetch one artifact and return its response body."""

        validate_artifact_locator(artifact)
        response = requests.get(
            artifact_view_url(self._endpoint, artifact),
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return bytes(response.content)

    def stream_to(
        self,
        artifact: ComfyImageArtifact,
        destination: Path,
        *,
        maximum_bytes: int = 2 * 1024 * 1024 * 1024,
        chunk_bytes: int = 1024 * 1024,
    ) -> int:
        """Stream one validated artifact into a new partial file."""

        validate_artifact_locator(artifact)
        if maximum_bytes <= 0 or chunk_bytes <= 0:
            raise ValueError("Video transfer bounds must be positive.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        try:
            with requests.get(
                artifact_view_url(self._endpoint, artifact),
                timeout=self._timeout_seconds,
                stream=True,
            ) as response:
                response.raise_for_status()
                content_length = response.headers.get("Content-Length")
                if content_length is not None and int(content_length) > maximum_bytes:
                    raise ValueError("Comfy video artifact exceeds the size limit.")
                with destination.open("xb") as output:
                    for chunk in response.iter_content(chunk_size=chunk_bytes):
                        if not chunk:
                            continue
                        written += len(chunk)
                        if written > maximum_bytes:
                            raise ValueError(
                                "Comfy video artifact exceeds the size limit."
                            )
                        output.write(chunk)
                    output.flush()
            if written == 0:
                raise ValueError("Comfy video artifact was empty.")
            return written
        except Exception:
            destination.unlink(missing_ok=True)
            raise
