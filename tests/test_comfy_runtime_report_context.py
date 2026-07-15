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

"""Contract tests for Comfy runtime context collection."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.runtime_info_client import fetch_comfy_runtime_info
from substitute.infrastructure.comfy.runtime_report_context import (
    fetch_runtime_report_context,
)


def test_fetch_runtime_report_context_maps_comfy_system_stats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime report context should use Comfy `/system_stats` values."""

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.runtime_info_client.requests.get",
        lambda *_args, **_kwargs: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "system": {
                    "comfyui_version": "0.3.1",
                    "argv": ["main.py", "--listen"],
                    "os": "Windows",
                    "python_version": "3.12.10",
                    "embedded_python": False,
                    "pytorch_version": "2.8.0+cu128",
                },
                "devices": [
                    {
                        "name": "NVIDIA GeForce RTX 5090",
                        "type": "cuda",
                        "index": 0,
                        "vram_total": 123,
                        "vram_free": 45,
                    }
                ],
            },
        ),
    )

    context = fetch_runtime_report_context(ComfyEndpoint(host="127.0.0.1", port=8188))

    assert context.comfy_version == "0.3.1"
    assert context.python_version == "3.12.10"
    assert context.embedded_python == "False"
    assert context.pytorch_version == "2.8.0+cu128"
    assert context.launch_args == ("main.py", "--listen")
    assert context.devices == (
        "NVIDIA GeForce RTX 5090 (cuda #0) [VRAM: 123, free: 45]",
    )


def test_fetch_comfy_runtime_info_maps_system_stats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shared runtime info reader should parse Comfy `/system_stats`."""

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.runtime_info_client.requests.get",
        lambda *_args, **_kwargs: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "system": {
                    "comfyui_version": "0.3.2",
                    "os": "Windows",
                    "python_version": "3.12.10",
                    "embedded_python": True,
                    "pytorch_version": "2.8.0+cu128",
                },
                "devices": [],
            },
        ),
    )

    runtime_info = fetch_comfy_runtime_info(ComfyEndpoint(host="127.0.0.1", port=8188))

    assert runtime_info is not None
    assert runtime_info.comfy_version == "0.3.2"
    assert runtime_info.embedded_python == "True"
