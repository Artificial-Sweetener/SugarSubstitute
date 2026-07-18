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

import requests

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.artifact_urls import artifact_view_url
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

        response = requests.get(
            artifact_view_url(self._endpoint, artifact),
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return bytes(response.content)
