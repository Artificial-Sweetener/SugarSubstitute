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

"""Tests for Substitute BackEnd preview asset HTTP client."""

from __future__ import annotations

from substitute.domain.generation import TaesdPreviewAssetState
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external import SubstituteBackendPreviewAssetsClient


class _FakeResponse:
    """Provide the response surface used by the HTTP client."""

    def __init__(self, payload: object) -> None:
        """Store the response payload."""

        self._payload = payload

    def raise_for_status(self) -> None:
        """Accept successful responses."""

    def json(self) -> object:
        """Return the configured payload."""

        return self._payload


def test_preview_assets_client_builds_urls_and_parses_payloads() -> None:
    """Preview asset client should call active backend routes and parse DTOs."""

    calls: list[tuple[str, str, object | None]] = []

    def fake_get(url: str, **_kwargs: object) -> _FakeResponse:
        """Return route-specific fake GET payloads."""

        calls.append(("GET", url, None))
        assert url.endswith("/substitute/v1/preview-assets/taesd/status")
        return _FakeResponse(_status_payload(ready=False))

    def fake_post(url: str, **kwargs: object) -> _FakeResponse:
        """Return route-specific fake POST payloads."""

        calls.append(("POST", url, kwargs.get("json")))
        assert url.endswith("/substitute/v1/preview-assets/taesd/ensure")
        return _FakeResponse(_status_payload(ready=True))

    client = SubstituteBackendPreviewAssetsClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=fake_get,
        http_post=fake_post,
    )

    status = client.get_taesd_status()
    ensure = client.ensure_taesd_assets()

    assert status is not None
    assert status.ready is False
    assert status.assets[0].status is TaesdPreviewAssetState.MISSING
    assert ensure is not None
    assert ensure.ready is True
    assert calls == [
        (
            "GET",
            "http://10.0.0.2:8189/substitute/v1/preview-assets/taesd/status",
            None,
        ),
        (
            "POST",
            "http://10.0.0.2:8189/substitute/v1/preview-assets/taesd/ensure",
            {},
        ),
    ]


def test_preview_assets_client_returns_none_for_invalid_payload() -> None:
    """Invalid backend payloads should fail closed."""

    client = SubstituteBackendPreviewAssetsClient(
        ComfyEndpoint(host="127.0.0.1", port=8188),
        http_get=lambda *_args, **_kwargs: _FakeResponse({"assets": "bad"}),
    )

    assert client.get_taesd_status() is None


def _status_payload(*, ready: bool) -> dict[str, object]:
    """Return a minimal preview asset status payload."""

    return {
        "schemaVersion": 1,
        "destinationRoot": "E:\\ComfyUI\\models\\vae_approx",
        "ready": ready,
        "installedCount": 4 if ready else 0,
        "missingCount": 0 if ready else 4,
        "downloadsAttempted": ready,
        "assets": [
            {
                "id": "taesd",
                "filename": "taesd_decoder.pth",
                "url": "https://github.com/madebyollin/taesd/raw/main/taesd_decoder.pth",
                "status": "installed" if ready else "missing",
                "path": "E:\\ComfyUI\\models\\vae_approx\\taesd_decoder.pth",
                "sizeBytes": 123 if ready else None,
            }
        ],
    }
