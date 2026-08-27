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

"""Verify CivitAI hash-lookup transport and response contracts."""

from __future__ import annotations

from substitute.domain.model_metadata import CivitaiLookupStatus
from substitute.infrastructure.external import CivitaiClient

from .support import _FakeResponse, _civitai_payload, _typed_headers


def test_civitai_client_parses_by_hash_response_and_uses_bearer_token() -> None:
    """CivitAI client should normalize by-hash model-version responses."""

    calls: list[tuple[str, dict[str, str]]] = []

    def fake_get(url: str, **kwargs: object) -> _FakeResponse:
        """Return one CivitAI by-hash payload."""

        calls.append((url, dict(_typed_headers(kwargs["headers"]))))
        return _FakeResponse(_civitai_payload())

    client = CivitaiClient(
        http_get=fake_get,
        api_key="secret-token",
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    result = client.lookup_model_version_by_hash("abc123")

    assert result.status is CivitaiLookupStatus.FOUND
    assert result.version is not None
    assert result.version.model_id == 100
    assert result.version.model_version_id == 200
    assert (
        result.version.model_page_url
        == "https://civitai.com/models/100?modelVersionId=200"
    )
    assert result.version.trained_words == ("trigger", "style")
    assert result.version.files[0].hashes["SHA256"] == "ABC123"
    assert (
        result.version.files[0].download_url
        == "https://civitai.com/api/download/models/200"
    )
    assert result.version.files[0].file_type == "Model"
    assert result.version.files[0].pickle_scan_result == "Success"
    assert result.version.files[0].virus_scan_result == "Success"
    assert result.version.images[0].url == "https://image.example/safe.jpg"
    assert calls == [
        (
            "https://civitai.com/api/v1/model-versions/by-hash/ABC123",
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "SugarSubstitute/1.0",
                "Authorization": "Bearer secret-token",
            },
        )
    ]


def test_civitai_client_returns_not_found_for_404() -> None:
    """CivitAI client should turn 404 responses into typed not-found results."""

    def fake_get(_url: str, **_kwargs: object) -> _FakeResponse:
        """Return one not-found response."""

        return _FakeResponse({}, status_code=404)

    result = CivitaiClient(http_get=fake_get).lookup_model_version_by_hash("ABC")

    assert result.status is CivitaiLookupStatus.NOT_FOUND
