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

"""Contract tests for Cube Library icon asset HTTP fetching."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external import SubstituteBackendCubeIconAssetClient


@dataclass(frozen=True)
class _FakeResponse:
    """Provide the response surface used by the icon asset client."""

    content: bytes
    headers: dict[str, str]

    def raise_for_status(self) -> None:
        """Accept successful responses."""


def test_cube_icon_asset_client_fetches_target_relative_assets() -> None:
    """Client should root target-relative icon URLs at the active endpoint."""

    calls: list[tuple[str, float]] = []

    def fake_get(url: str, *, timeout: float) -> _FakeResponse:
        """Record the requested URL and return icon bytes."""

        calls.append((url, timeout))
        return _FakeResponse(b"png-bytes", {"content-type": "image/png; charset=utf-8"})

    client = SubstituteBackendCubeIconAssetClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=fake_get,
        timeout_seconds=1.5,
    )

    asset = client.fetch_icon_asset("/sugarcubes/assets/icon?cube_id=demo")

    assert asset is not None
    assert asset.content == b"png-bytes"
    assert asset.media_type == "image/png"
    assert calls == [("http://10.0.0.2:8189/sugarcubes/assets/icon?cube_id=demo", 1.5)]


def test_cube_icon_asset_client_rejects_external_or_malformed_urls() -> None:
    """Client should not fetch icon URLs outside the active target."""

    calls: list[str] = []

    def fake_get(url: str, *, timeout: float) -> _FakeResponse:
        """Record unexpected network calls."""

        del timeout
        calls.append(url)
        return _FakeResponse(b"png-bytes", {"content-type": "image/png"})

    client = SubstituteBackendCubeIconAssetClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=fake_get,
    )

    assert client.fetch_icon_asset("https://example.invalid/icon.png") is None
    assert client.fetch_icon_asset("//example.invalid/icon.png") is None
    assert client.fetch_icon_asset("/path with spaces/icon.png") is None
    assert calls == []
