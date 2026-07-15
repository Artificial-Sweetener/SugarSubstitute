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

"""Tests for Comfy extension metadata providers."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.comfy_manager_extension_metadata import (
    ComfyManagerExtensionMetadataProvider,
)
from substitute.infrastructure.comfy.local_custom_node_git_metadata import (
    LocalCustomNodeGitMetadataProvider,
)
from tests.repository_service_test_double import RecordingRepositoryService


class _Response:
    """Small requests response test double."""

    def __init__(
        self, payload: object, *, status_error: Exception | None = None
    ) -> None:
        """Store JSON payload and optional status error."""

        self._payload = payload
        self._status_error = status_error

    def raise_for_status(self) -> None:
        """Raise the configured HTTP status error."""

        if self._status_error is not None:
            raise self._status_error

    def json(self) -> object:
        """Return the configured JSON payload."""

        return self._payload


def test_manager_installed_aux_id_resolves_github_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manager installed aux_id metadata should become repository links."""

    def fake_get(url: str, *, timeout: float) -> _Response:
        assert timeout == 2.0
        assert url.endswith("/customnode/installed")
        return _Response(
            {
                "ComfyUI-GGUF-FantasyTalking": {
                    "ver": "48dd427",
                    "cnr_id": "",
                    "aux_id": "kael558/ComfyUI-GGUF-FantasyTalking",
                    "enabled": True,
                }
            }
        )

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_extension_metadata.requests.get",
        fake_get,
    )

    metadata = ComfyManagerExtensionMetadataProvider(
        host="127.0.0.1",
        port=8188,
    ).installed_extensions()

    extension = metadata["ComfyUI-GGUF-FantasyTalking"]
    assert extension.version == "48dd427"
    assert (
        extension.repository_url
        == "https://github.com/kael558/ComfyUI-GGUF-FantasyTalking"
    )
    assert (
        extension.issues_url
        == "https://github.com/kael558/ComfyUI-GGUF-FantasyTalking/issues"
    )
    assert extension.source == "manager_installed_aux_id"


def test_manager_catalog_resolves_cnr_only_installed_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manager catalog should fill repository links when installed lacks aux_id."""

    calls: list[str] = []

    def fake_get(url: str, *, timeout: float) -> _Response:
        del timeout
        calls.append(url)
        if url.endswith("/customnode/installed"):
            return _Response(
                {
                    "comfyui-impact-subpack": {
                        "ver": "1.3.5",
                        "cnr_id": "comfyui-impact-subpack",
                        "aux_id": None,
                    }
                }
            )
        return _Response(
            {
                "node_packs": {
                    "comfyui-impact-subpack": {
                        "id": "comfyui-impact-subpack",
                        "repository": "https://github.com/ltdrdata/ComfyUI-Impact-Subpack",
                        "version": "1.3.5",
                    }
                }
            }
        )

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_extension_metadata.requests.get",
        fake_get,
    )

    metadata = ComfyManagerExtensionMetadataProvider(
        host="127.0.0.1",
        port=8188,
    ).installed_extensions()

    assert len(calls) == 2
    extension = metadata["comfyui-impact-subpack"]
    assert (
        extension.repository_url == "https://github.com/ltdrdata/ComfyUI-Impact-Subpack"
    )
    assert (
        extension.issues_url
        == "https://github.com/ltdrdata/ComfyUI-Impact-Subpack/issues"
    )
    assert extension.source == "manager_catalog_repository"


def test_manager_catalog_response_can_be_json_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manager catalog payload may arrive as a JSON-encoded string."""

    def fake_get(url: str, *, timeout: float) -> _Response:
        del timeout
        if url.endswith("/customnode/installed"):
            return _Response(
                {
                    "comfyui-impact-subpack": {
                        "ver": "1.3.5",
                        "cnr_id": "comfyui-impact-subpack",
                    }
                }
            )
        return _Response(
            '{"node_packs":{"comfyui-impact-subpack":{"id":"comfyui-impact-subpack",'
            '"repository":"https://github.com/ltdrdata/ComfyUI-Impact-Subpack"}}}'
        )

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_extension_metadata.requests.get",
        fake_get,
    )

    metadata = ComfyManagerExtensionMetadataProvider(
        host="127.0.0.1",
        port=8188,
    ).installed_extensions()

    assert metadata["comfyui-impact-subpack"].repository_url == (
        "https://github.com/ltdrdata/ComfyUI-Impact-Subpack"
    )


def test_manager_endpoint_failure_returns_empty_metadata(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Manager endpoint failures should log optional metadata misses as info."""

    def fake_get(url: str, *, timeout: float) -> _Response:
        del url, timeout
        raise RuntimeError("manager unavailable")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_extension_metadata.requests.get",
        fake_get,
    )

    with caplog.at_level(
        logging.INFO,
        logger="sugarsubstitute.infrastructure.comfy.manager_extension_metadata",
    ):
        metadata = ComfyManagerExtensionMetadataProvider(
            host="127.0.0.1",
            port=8188,
        ).installed_extensions()

    assert metadata == {}
    assert "Failed to fetch ComfyUI-Manager extension metadata" in caplog.text
    assert caplog.records[0].levelno == logging.INFO


def test_manager_catalog_failure_returns_partial_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catalog failures should keep installed metadata that was already parsed."""

    def fake_get(url: str, *, timeout: float) -> _Response:
        del timeout
        if url.endswith("/customnode/installed"):
            return _Response({"pack": {"ver": "1.0", "cnr_id": "pack", "aux_id": None}})
        raise RuntimeError("catalog unavailable")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_extension_metadata.requests.get",
        fake_get,
    )

    metadata = ComfyManagerExtensionMetadataProvider(
        host="127.0.0.1",
        port=8188,
    ).installed_extensions()

    assert metadata["pack"].version == "1.0"
    assert metadata["pack"].repository_url is None


def test_local_git_provider_reads_origin_remote(
    tmp_path: Path,
) -> None:
    """Local Git fallback should read a repository URL from extension remotes."""

    extension_dir = tmp_path / "ComfyUI-GGUF-FantasyTalking"
    (extension_dir / ".git").mkdir(parents=True)

    metadata = LocalCustomNodeGitMetadataProvider(
        custom_nodes_dir=tmp_path,
        repositories=RecordingRepositoryService(
            remotes={
                "origin": ("https://github.com/kael558/ComfyUI-GGUF-FantasyTalking.git")
            }
        ),
    ).installed_extensions()

    extension = metadata["ComfyUI-GGUF-FantasyTalking"]
    assert (
        extension.repository_url
        == "https://github.com/kael558/ComfyUI-GGUF-FantasyTalking"
    )
    assert extension.issues_url is not None
    assert extension.source == "local_git_remote"
