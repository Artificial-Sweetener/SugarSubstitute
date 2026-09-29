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

"""Verify bounded workflow nodepack lookup through Comfy Registry."""

from __future__ import annotations

from email.message import Message
import io
import json
import ssl
from urllib.error import HTTPError

import pytest

from substitute.infrastructure.comfy.comfy_registry_nodepack_client import (
    ComfyRegistryNodepackClient,
    InvalidRegistryNodepackError,
)
from sugarsubstitute_shared.tls import SystemTrustTlsContext


def _payload() -> dict[str, object]:
    """Return one active Registry package response."""

    return {
        "id": "comfyui-impact-pack",
        "name": "ComfyUI Impact Pack",
        "repository": "https://github.com/ltdrdata/ComfyUI-Impact-Pack",
        "status": "NodeStatusActive",
        "latest_version": {
            "node_id": "comfyui-impact-pack",
            "version": "8.28.3",
            "status": "NodeVersionStatusActive",
        },
    }


def test_infers_active_pack_from_encoded_class_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the Registry's focused class-name endpoint and system trust."""

    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    observed: dict[str, object] = {}

    def fake_urlopen(
        request: object,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ) -> io.BytesIO:
        """Return one package while recording transport policy."""

        observed.update(request=request, timeout=timeout, context=context)
        return io.BytesIO(json.dumps(_payload()).encode("utf-8"))

    monkeypatch.setattr(SystemTrustTlsContext, "create", lambda: tls_context)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    nodepack = ComfyRegistryNodepackClient().infer_nodepack("SEGS Preview/+")

    assert getattr(observed["request"], "full_url") == (
        "https://api.comfy.org/comfy-nodes/SEGS%20Preview%2F%2B/node"
    )
    assert observed["context"] is tls_context
    assert nodepack is not None
    assert nodepack.identifier == "comfyui-impact-pack"
    assert nodepack.version == "8.28.3"


def test_get_by_id_rejects_response_identity_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit persisted CNR identity must not be redirected to another pack."""

    payload = _payload()
    payload["id"] = "different-pack"
    latest = payload["latest_version"]
    assert isinstance(latest, dict)
    latest["node_id"] = "different-pack"
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: io.BytesIO(json.dumps(payload).encode("utf-8")),
    )

    with pytest.raises(InvalidRegistryNodepackError):
        ComfyRegistryNodepackClient().get_nodepack("comfyui-impact-pack")


def test_returns_none_for_missing_or_inactive_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Absent and non-active packages must not become install candidates."""

    def missing(*args: object, **kwargs: object) -> io.BytesIO:
        """Raise the public response for an unknown class."""

        _ = args, kwargs
        raise HTTPError("https://api.comfy.org", 404, "missing", Message(), None)

    monkeypatch.setattr("urllib.request.urlopen", missing)
    assert ComfyRegistryNodepackClient().infer_nodepack("Unknown") is None

    payload = _payload()
    payload["status"] = "NodeStatusBanned"
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: io.BytesIO(json.dumps(payload).encode("utf-8")),
    )
    assert ComfyRegistryNodepackClient().get_nodepack("comfyui-impact-pack") is None


def test_rejects_oversized_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bound public metadata before JSON parsing."""

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: io.BytesIO(b"{" + b"x" * (256 * 1024)),
    )

    with pytest.raises(InvalidRegistryNodepackError, match="size limit"):
        ComfyRegistryNodepackClient().get_nodepack("comfyui-impact-pack")
