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

"""Verify environment capabilities, status, and model-root mapping."""

from __future__ import annotations

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external import SubstituteBackendEnvironmentClient

from .support import (
    _FakeResponse,
    _capabilities_payload,
    _model_root_payload,
    _status_payload,
)


def test_environment_client_maps_capabilities_status_and_model_root() -> None:
    """Map host-owned status and persisted model-root routes exactly."""

    calls: list[tuple[str, object]] = []

    def get(url: str, **_kwargs: object) -> _FakeResponse:
        calls.append(("GET", url))
        payloads = {
            "/capabilities": _capabilities_payload(),
            "/status": _status_payload(),
            "/model-root": _model_root_payload(),
        }
        return _FakeResponse(
            next(
                payload for suffix, payload in payloads.items() if url.endswith(suffix)
            )
        )

    def put(url: str, **kwargs: object) -> _FakeResponse:
        calls.append(("PUT", kwargs["json"]))
        assert url.endswith("/model-root")
        return _FakeResponse(
            {
                **_model_root_payload(),
                "configuredModelRoot": "E:\\SharedModels",
                "activeModelRoot": "E:\\SharedModels",
                "usesDefault": False,
                "restartRequired": True,
            }
        )

    client = SubstituteBackendEnvironmentClient(
        ComfyEndpoint(host="10.0.0.2", port=8189), http_get=get, http_put=put
    )
    assert client.get_environment_capabilities().restart_supported is True  # type: ignore[union-attr]
    assert client.get_environment_status().python.version == "3.12.7"  # type: ignore[union-attr]
    assert client.get_model_root().uses_default is True  # type: ignore[union-attr]
    updated_root = client.update_model_root(use_default=False, path="E:\\SharedModels")
    assert updated_root is not None
    assert updated_root.restart_required is True
    assert calls[-1] == ("PUT", {"mode": "custom", "path": "E:\\SharedModels"})
