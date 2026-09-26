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

"""Verify bounded exact-release access to the public Comfy Registry."""

from __future__ import annotations

from email.message import Message
import io
import json
import ssl
from urllib.error import HTTPError

import pytest

from substitute.infrastructure.comfy.comfy_registry_release_client import (
    ComfyRegistryReleaseClient,
    InvalidRegistryReleaseError,
    RegistryReleaseUnavailableError,
)
from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS
from sugarsubstitute_shared.tls import SystemTrustTlsContext


def test_resolves_exact_identity_from_fixed_registry_and_cdn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Accept an identity-matched descriptor from the trusted Comfy CDN."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    observed: dict[str, object] = {}
    payload = {
        "node_id": nodepack.registry_id,
        "version": nodepack.required_version,
        "status": "NodeVersionStatusActive",
        "downloadUrl": "https://cdn.comfy.org/publisher/node/version/node.zip",
    }

    def fake_urlopen(
        request: object,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ) -> io.BytesIO:
        """Return exact metadata while recording transport policy."""

        observed.update(request=request, timeout=timeout, context=context)
        return io.BytesIO(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(SystemTrustTlsContext, "create", lambda: tls_context)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    release = ComfyRegistryReleaseClient().resolve_exact(nodepack)

    request = observed["request"]
    assert getattr(request, "full_url") == (
        "https://api.comfy.org/nodes/substitute-backend/install?version=1.10.0"
    )
    assert observed["context"] is tls_context
    assert release.node_id == nodepack.registry_id
    assert release.version == nodepack.required_version
    assert release.archive_url == payload["downloadUrl"]


@pytest.mark.parametrize(
    "payload",
    (
        {
            "node_id": "different-node",
            "version": "1.10.0",
            "status": "NodeVersionStatusActive",
            "downloadUrl": "https://cdn.comfy.org/publisher/node/version/node.zip",
        },
        {
            "node_id": "substitute-backend",
            "version": "0.0.1",
            "status": "NodeVersionStatusActive",
            "downloadUrl": "https://cdn.comfy.org/publisher/node/version/node.zip",
        },
        {
            "node_id": "substitute-backend",
            "version": "1.10.0",
            "status": "NodeVersionStatusActive",
            "downloadUrl": "https://attacker.example/node.zip",
        },
        {
            "node_id": "substitute-backend",
            "version": "1.10.0",
            "downloadUrl": "https://cdn.comfy.org/publisher/node/version/node.zip",
        },
    ),
)
def test_rejects_identity_version_or_archive_origin_changes(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, str],
) -> None:
    """Fail closed when Registry metadata changes the trusted exact request."""

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: io.BytesIO(json.dumps(payload).encode("utf-8")),
    )

    with pytest.raises(InvalidRegistryReleaseError):
        ComfyRegistryReleaseClient().resolve_exact(CORE_COMFY_NODEPACKS[0])


@pytest.mark.parametrize(
    "status",
    ("NodeVersionStatusFlagged", "NodeVersionStatusPending"),
)
def test_classifies_non_active_exact_release_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    """Route non-active releases through the trusted pinned-source fallback."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    payload = {
        "node_id": nodepack.registry_id,
        "version": nodepack.required_version,
        "status": status,
        "downloadUrl": "https://cdn.comfy.org/publisher/node/version/node.zip",
    }
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: io.BytesIO(json.dumps(payload).encode("utf-8")),
    )

    with pytest.raises(RegistryReleaseUnavailableError, match="is not active"):
        ComfyRegistryReleaseClient().resolve_exact(nodepack)


def test_classifies_missing_exact_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expose a Registry 404 as version unavailability rather than corruption."""

    def missing(*args: object, **kwargs: object) -> io.BytesIO:
        """Raise the public API response for an absent exact version."""

        _ = args, kwargs
        raise HTTPError("https://api.comfy.org", 404, "missing", Message(), None)

    monkeypatch.setattr("urllib.request.urlopen", missing)

    with pytest.raises(RegistryReleaseUnavailableError):
        ComfyRegistryReleaseClient().resolve_exact(CORE_COMFY_NODEPACKS[0])
