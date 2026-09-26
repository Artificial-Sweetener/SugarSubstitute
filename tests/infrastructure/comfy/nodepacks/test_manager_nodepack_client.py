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

"""Tests for authoritative legacy ComfyUI-Manager nodepack resolution."""

from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Self

import pytest

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    WorkflowNodepackSourceKind,
)
from substitute.infrastructure.comfy.comfy_manager_nodepack_client import (
    ComfyManagerNodepackClient,
    InvalidComfyManagerNodepackCatalogError,
)


class _Response:
    """Expose a bounded urllib response around one JSON fixture."""

    def __init__(self, payload: object) -> None:
        """Encode the response payload."""

        self._raw = json.dumps(payload).encode()

    def __enter__(self) -> Self:
        """Enter the fake response context."""

        return self

    def __exit__(self, *_args: object) -> None:
        """Leave the fake response context."""

    def read(self, _size: int) -> bytes:
        """Return the encoded fixture."""

        return self._raw


def _install_catalog(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mapping: Mapping[str, object],
    nodepacks: object,
) -> list[str]:
    """Install deterministic official-catalog responses and return request URLs."""

    calls: list[str] = []

    def fake_urlopen(request: object, **_kwargs: object) -> _Response:
        url = str(getattr(request, "full_url"))
        calls.append(url)
        return _Response(
            mapping if url.endswith("extension-node-map.json") else nodepacks
        )

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_nodepack_client.urllib.request.urlopen",
        fake_urlopen,
    )
    return calls


def test_resolves_exact_class_only_when_install_catalog_confirms_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mapped class should become a Git candidate only with install metadata."""

    repository = "https://github.com/blue-pen5805/ComfyUI-krea2-negpip"
    calls = _install_catalog(
        monkeypatch,
        mapping={
            repository: [
                ["ApplyKrea2NegPiP"],
                {"title_aux": "Fallback title"},
            ]
        },
        nodepacks={
            "custom_nodes": [
                {
                    "title": "ComfyUI-krea2-negpip",
                    "install_type": "git-clone",
                    "files": [repository],
                    "reference": repository,
                }
            ]
        },
    )

    client = ComfyManagerNodepackClient()
    nodepack = client.infer_nodepack("ApplyKrea2NegPiP")

    assert nodepack is not None
    assert nodepack.identifier == repository
    assert nodepack.display_name == "ComfyUI-krea2-negpip"
    assert nodepack.source_kind is WorkflowNodepackSourceKind.GIT_REPOSITORY
    assert nodepack.repository_url == repository
    assert nodepack.version is None
    assert client.infer_nodepack("ApplyKrea2NegPiP") == nodepack
    assert len(calls) == 2


def test_rejects_ambiguous_or_unconfirmed_class_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multiple owners and unsupported install mechanisms must fail closed."""

    first = "https://github.com/example/first"
    second = "https://github.com/example/second"
    _install_catalog(
        monkeypatch,
        mapping={
            first: [["Ambiguous", "Unsupported"], {}],
            second: [["Ambiguous"], {}],
        },
        nodepacks={
            "custom_nodes": [
                {
                    "title": "Unsupported",
                    "install_type": "copy",
                    "files": [first],
                }
            ]
        },
    )

    client = ComfyManagerNodepackClient()

    assert client.infer_nodepack("Ambiguous") is None
    assert client.infer_nodepack("Unsupported") is None


def test_rejects_non_github_and_credentialed_repository_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy installation should accept only credential-free GitHub sources."""

    _install_catalog(
        monkeypatch,
        mapping={
            "https://example.com/owner/repo": [["Foreign"], {}],
            "https://user:token@github.com/owner/repo": [["Credentialed"], {}],
        },
        nodepacks={"custom_nodes": []},
    )

    client = ComfyManagerNodepackClient()

    assert client.infer_nodepack("Foreign") is None
    assert client.infer_nodepack("Credentialed") is None


def test_rejects_malformed_or_oversized_official_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catalog transport must be bounded and structurally validated."""

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_nodepack_client.urllib.request.urlopen",
        lambda *_args, **_kwargs: _Response([]),
    )
    with pytest.raises(InvalidComfyManagerNodepackCatalogError, match="not an object"):
        ComfyManagerNodepackClient().infer_nodepack("Node")
