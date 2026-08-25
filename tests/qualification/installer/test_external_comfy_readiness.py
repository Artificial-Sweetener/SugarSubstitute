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

from tools.ci.external_comfy_readiness_server import ExternalComfyReadinessServer
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


def test_external_comfy_server_retains_port_and_records_readiness() -> None:
    """Hold the endpoint for its whole lifetime and retain semantic probe proof."""

    with ExternalComfyReadinessServer() as server:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as contender:
            with pytest.raises(OSError):
                contender.bind((server.host, server.port))
        with urllib.request.urlopen(
            f"http://{server.host}:{server.port}/system_stats",
            timeout=5.0,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        server.require_readiness_probe()

    assert payload == {
        "system": {"comfyui_version": "installer-qualification-boundary"}
    }
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as successor:
        successor.bind((server.host, server.port))


def test_external_comfy_server_rejects_missing_or_unrelated_probe() -> None:
    """Do not accept server liveness as evidence of application readiness."""

    with pytest.raises(InstallerLifecycleError, match="never probed"):
        with ExternalComfyReadinessServer() as server:
            with pytest.raises(urllib.error.HTTPError) as captured:
                urllib.request.urlopen(
                    f"http://{server.host}:{server.port}/unrelated",
                    timeout=5.0,
                )
            assert captured.value.code == 404
            server.require_readiness_probe()
