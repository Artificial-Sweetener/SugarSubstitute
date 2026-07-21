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

"""Tests for authoritative Comfy Registry metadata enrichment."""

from __future__ import annotations

from collections.abc import Sequence
import logging

import pytest

from substitute.application.ports.comfy_extension_metadata_provider import (
    ComfyExtensionMetadata,
)
from substitute.infrastructure.comfy import comfy_registry_metadata


class _Response:
    """Expose the requests response surface used by the registry client."""

    def __init__(self, payload: object) -> None:
        """Store one decoded response payload."""

        self._payload = payload

    def raise_for_status(self) -> None:
        """Accept the fixture response status."""

    def json(self) -> object:
        """Return the configured registry payload."""

        return self._payload


def test_registry_enriches_cnr_package_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CNR-only Manager metadata should resolve through api.comfy.org."""

    def fake_get(
        url: str,
        *,
        params: Sequence[tuple[str, str]],
        timeout: float,
    ) -> _Response:
        assert url == "https://api.comfy.org/nodes"
        assert ("node_id", "comfyui-impact-subpack") in params
        assert timeout == 2.0
        return _Response(
            {
                "nodes": [
                    {
                        "id": "comfyui-impact-subpack",
                        "repository": (
                            "https://github.com/ltdrdata/ComfyUI-Impact-Subpack"
                        ),
                        "latest_version": {"version": "1.3.5"},
                    }
                ]
            }
        )

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_registry_metadata.requests.get",
        fake_get,
    )

    result = comfy_registry_metadata.ComfyRegistryMetadataClient().enrich(
        {
            "comfyui-impact-subpack": ComfyExtensionMetadata(
                key="comfyui-impact-subpack",
                version=None,
                cnr_id="comfyui-impact-subpack",
                aux_id=None,
                repository_url=None,
                issues_url=None,
                source=None,
            )
        }
    )

    metadata = result["comfyui-impact-subpack"]
    assert metadata.version == "1.3.5"
    assert metadata.repository_url == (
        "https://github.com/ltdrdata/ComfyUI-Impact-Subpack"
    )
    assert metadata.source == "comfy_registry_repository"


def test_registry_failure_preserves_partial_manager_metadata(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Optional registry downtime should preserve installed Manager evidence."""

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_registry_metadata.requests.get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    installed = {
        "pack": ComfyExtensionMetadata(
            key="pack",
            version="1.0",
            cnr_id="pack",
            aux_id=None,
            repository_url=None,
            issues_url=None,
            source=None,
        )
    }

    with caplog.at_level(
        logging.INFO,
        logger="sugarsubstitute.infrastructure.comfy.registry_extension_metadata",
    ):
        result = comfy_registry_metadata.ComfyRegistryMetadataClient().enrich(installed)

    assert result == installed
    assert "Failed to fetch Comfy Registry extension metadata" in caplog.text
