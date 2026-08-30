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

"""Provide typed backend compilation transport doubles."""

from __future__ import annotations

import requests


class FakeResponse:
    """Represent a configured requests response."""

    def __init__(self, payload: object, *, status_code: int = 200) -> None:
        """Store the response payload and status."""
        self._payload = payload
        self.status_code = status_code

    def json(self) -> object:
        """Return the configured payload."""
        return self._payload

    def raise_for_status(self) -> None:
        """Raise a requests error for a non-success response."""
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class RecordingTransport:
    """Record backend HTTP requests and return configured responses."""

    def __init__(
        self,
        *,
        compile_response: FakeResponse | None = None,
        capabilities_response: FakeResponse | None = None,
    ) -> None:
        """Configure response payloads for both backend calls."""
        self.get_calls: list[tuple[str, float]] = []
        self.post_calls: list[tuple[str, dict[str, object], float]] = []
        self._compile_response = compile_response or FakeResponse(
            {"prompt": {"1": {"class_type": "KSampler"}}, "workflow": {"nodes": []}}
        )
        self._capabilities_response = capabilities_response or FakeResponse(
            {
                "features": ["sugar-compile"],
                "sugarCompile": {
                    "schemaVersion": 1,
                    "available": True,
                    "compileRoute": "/substitute/v1/sugar/compile",
                    "liveNodeDefinitions": True,
                },
            }
        )

    def get(self, url: str, *, timeout: float) -> FakeResponse:
        """Record a GET request."""
        self.get_calls.append((url, timeout))
        return self._capabilities_response

    def post(
        self,
        url: str,
        *,
        json: dict[str, object],
        timeout: float,
    ) -> FakeResponse:
        """Record a POST request."""
        self.post_calls.append((url, json, timeout))
        return self._compile_response
