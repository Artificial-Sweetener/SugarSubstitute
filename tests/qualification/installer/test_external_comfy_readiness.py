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

"""Qualify the continuously owned external Comfy readiness boundary."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request

import pytest

from substitute.application.backend_compatibility import (
    BackendCompatibilityService,
    RuntimeCompatibilityStatus,
)
from substitute.application.runtime_mode import (
    ApplicationRuntimeMode,
    ApplicationRuntimeModeService,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.substitute_backend_model_metadata_client import (
    SubstituteBackendModelMetadataClient,
)
from tools.ci.external_comfy_readiness_server import ExternalComfyReadinessServer
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


def test_external_comfy_server_proves_compatible_remote_target_contract() -> None:
    """Hold one endpoint and satisfy production readiness and compatibility policy."""

    with ExternalComfyReadinessServer() as server:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as contender:
            with pytest.raises(OSError):
                contender.bind((server.host, server.port))
        with urllib.request.urlopen(
            f"http://{server.host}:{server.port}/system_stats",
            timeout=5.0,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        compatibility = BackendCompatibilityService(
            capability_provider=SubstituteBackendModelMetadataClient(
                ComfyEndpoint(host=server.host, port=server.port)
            ),
            runtime_mode=ApplicationRuntimeModeService(ApplicationRuntimeMode.RELEASE),
        ).assess()
        server.require_qualification_probes()

    assert payload == {
        "system": {"comfyui_version": "installer-qualification-boundary"}
    }
    assert compatibility.status is RuntimeCompatibilityStatus.COMPATIBLE
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as successor:
        successor.settimeout(1.0)
        assert successor.connect_ex((server.host, server.port)) != 0


def test_external_comfy_server_rejects_missing_or_unrelated_probes() -> None:
    """Do not accept server liveness as evidence of application contracts."""

    with pytest.raises(InstallerLifecycleError, match="required external Comfy routes"):
        with ExternalComfyReadinessServer() as server:
            with pytest.raises(urllib.error.HTTPError) as captured:
                urllib.request.urlopen(
                    f"http://{server.host}:{server.port}/unrelated",
                    timeout=5.0,
                )
            assert captured.value.code == 404
            server.require_qualification_probes()
