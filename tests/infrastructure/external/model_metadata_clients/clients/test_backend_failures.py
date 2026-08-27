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

"""Verify Substitute BackEnd failure handling and compatibility defaults."""

from __future__ import annotations

import logging

import pytest

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external import SubstituteBackendModelMetadataClient

from .support import _FakeResponse, _capabilities_payload


def test_backend_client_refresh_raises_when_model_catalog_unavailable() -> None:
    """Fresh model-catalog requests should fail instead of returning fake emptiness."""

    def fake_get(_url: str, **_kwargs: object) -> _FakeResponse:
        """Raise a transport-shaped error for the refresh call."""

        raise ValueError("backend unavailable")

    client = SubstituteBackendModelMetadataClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=fake_get,
    )

    assert client.list_models(("loras",)) == ()
    with pytest.raises(RuntimeError, match="model catalog refresh failed"):
        client.list_models(("loras",), refresh=True)


def test_backend_client_warns_once_for_repeated_get_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Repeated backend GET outages should not flood the warning log."""

    def fake_get(_url: str, **_kwargs: object) -> _FakeResponse:
        """Raise a transport-shaped error for each backend GET."""

        raise ValueError("backend unavailable")

    client = SubstituteBackendModelMetadataClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=fake_get,
    )

    with caplog.at_level(
        logging.DEBUG,
        logger=(
            "sugarsubstitute.infrastructure.external."
            "substitute_backend_model_metadata_client"
        ),
    ):
        assert client.get_capabilities() is None
        assert client.get_capabilities() is None

    failure_records = [
        record
        for record in caplog.records
        if record.message.startswith("Substitute BackEnd GET failed")
    ]
    assert [record.levelno for record in failure_records] == [
        logging.WARNING,
        logging.DEBUG,
    ]


def test_backend_client_defaults_missing_sugar_compile_capabilities() -> None:
    """Old Backends without Sugar compile facts should parse compatibly."""

    payload = _capabilities_payload()
    del payload["sugarCompile"]

    client = SubstituteBackendModelMetadataClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=lambda *_args, **_kwargs: _FakeResponse(payload),
    )

    capabilities = client.get_capabilities()

    assert capabilities is not None
    assert capabilities.sugar_compile.schema_version == 0
    assert capabilities.sugar_compile.sugar_dsl_version == ""


def test_backend_client_allows_missing_sugar_dsl_version() -> None:
    """Backends can advertise Sugar compile before exposing Sugar-DSL version."""

    payload = _capabilities_payload()
    sugar_compile = payload["sugarCompile"]
    assert isinstance(sugar_compile, dict)
    del sugar_compile["sugarDslVersion"]

    client = SubstituteBackendModelMetadataClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=lambda *_args, **_kwargs: _FakeResponse(payload),
    )

    capabilities = client.get_capabilities()

    assert capabilities is not None
    assert capabilities.sugar_compile.available is True
    assert capabilities.sugar_compile.sugar_dsl_version == ""
