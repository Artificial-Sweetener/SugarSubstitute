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

"""Protect Comfy image-artifact URL generation and byte transport."""

from __future__ import annotations

import types

import pytest

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.artifact_fetcher import ComfyArtifactFetcher
from substitute.infrastructure.comfy.artifact_urls import artifact_view_url
from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact


def test_artifact_view_url_encodes_query_values() -> None:
    """Artifact URLs should encode every Comfy view query value."""

    endpoint = ComfyEndpoint(host="127.0.0.1", port=8188)
    artifact = ComfyImageArtifact(
        filename="ComfyUI temp 00001.png",
        subfolder="nested folder",
        type="temp",
        media_kind="image",
    )

    assert artifact_view_url(endpoint, artifact) == (
        "http://127.0.0.1:8188/view?"
        "filename=ComfyUI+temp+00001.png&subfolder=nested+folder&type=temp"
    )


def test_artifact_fetcher_returns_response_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Artifact fetcher should request the encoded view URL and return bytes."""

    requested: list[tuple[str, float]] = []

    class Response:
        """Provide the bounded HTTP response surface consumed by the fetcher."""

        content = b"image-bytes"

        def raise_for_status(self) -> None:
            """Represent a successful artifact response."""

    def get(url: str, *, timeout: float) -> Response:
        """Capture one external artifact transport request."""

        requested.append((url, timeout))
        return Response()

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.artifact_fetcher.requests",
        types.SimpleNamespace(get=get),
    )
    fetcher = ComfyArtifactFetcher(
        endpoint=ComfyEndpoint(host="10.0.0.2", port=8190),
        timeout_seconds=3.5,
    )
    artifact = ComfyImageArtifact(
        filename="image.png",
        subfolder="",
        type="temp",
        media_kind="image",
    )

    assert fetcher.fetch(artifact) == b"image-bytes"
    assert requested == [
        ("http://10.0.0.2:8190/view?filename=image.png&subfolder=&type=temp", 3.5)
    ]
