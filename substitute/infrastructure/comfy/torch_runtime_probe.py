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

"""Probe the installed Torch runtime without coupling results to install policy."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Protocol


class RuntimeCommandRunner(Protocol):
    """Run one managed-environment command for the Torch probe."""

    def __call__(
        self,
        command: list[str],
        *,
        cwd: Path,
        check: bool = True,
        timeout_seconds: float = 60,
    ) -> subprocess.CompletedProcess[str]:
        """Run the supplied command and return its captured result."""


@dataclass(frozen=True)
class TorchRuntimeDetails:
    """Describe backend availability and actual device execution from Torch."""

    torch_version: str | None = None
    cuda: bool = False
    xpu: bool = False
    mps: bool = False
    hip: str | None = None
    device_operation: bool = False
    device_name: str | None = None
    device_error: str | None = None
    probe_error: str | None = None


_TORCH_RUNTIME_PROBE = """
import json

payload = {
    "torch_version": None,
    "cuda": False,
    "xpu": False,
    "mps": False,
    "hip": None,
    "device_operation": False,
    "device_name": None,
    "device_error": None,
}
import torch

payload["torch_version"] = getattr(torch, "__version__", None)
payload["cuda"] = bool(getattr(torch.cuda, "is_available", lambda: False)())
payload["xpu"] = bool(
    getattr(getattr(torch, "xpu", None), "is_available", lambda: False)()
)
payload["mps"] = bool(
    getattr(
        getattr(getattr(torch, "backends", None), "mps", None),
        "is_available",
        lambda: False,
    )()
)
payload["hip"] = getattr(getattr(torch, "version", None), "hip", None)

device = None
if payload["hip"]:
    if payload["cuda"]:
        device = "cuda"
    else:
        payload["device_error"] = "ROCm Torch found no available HIP device."
elif payload["cuda"]:
    device = "cuda"
elif payload["xpu"]:
    device = "xpu"
elif payload["mps"]:
    device = "mps"
else:
    device = "cpu"

if device is not None:
    try:
        value = torch.ones(1, device=device).add(1).item()
        payload["device_operation"] = value == 2
        if device == "cuda":
            payload["device_name"] = torch.cuda.get_device_name(0)
        elif device == "xpu":
            payload["device_name"] = torch.xpu.get_device_name(0)
        elif device == "mps":
            payload["device_name"] = "Apple MPS"
        else:
            payload["device_name"] = "CPU"
    except Exception as error:
        payload["device_error"] = f"{type(error).__name__}: {error}"

print(json.dumps(payload))
"""


def query_torch_runtime(
    *,
    python_executable: Path,
    workspace: Path,
    run_command: RuntimeCommandRunner,
) -> TorchRuntimeDetails:
    """Return normalized Torch runtime details from one managed interpreter."""

    try:
        result = run_command(
            [str(python_executable), "-c", _TORCH_RUNTIME_PROBE],
            cwd=workspace,
        )
        payload = json.loads(result.stdout or "{}") if result.stdout else {}
    except (RuntimeError, json.JSONDecodeError) as error:
        return TorchRuntimeDetails(probe_error=str(error))
    if not isinstance(payload, dict):
        return TorchRuntimeDetails(probe_error="Torch probe returned invalid output.")
    return TorchRuntimeDetails(
        torch_version=_optional_string(payload.get("torch_version")),
        cuda=bool(payload.get("cuda")),
        xpu=bool(payload.get("xpu")),
        mps=bool(payload.get("mps")),
        hip=_optional_string(payload.get("hip")),
        device_operation=bool(payload.get("device_operation")),
        device_name=_optional_string(payload.get("device_name")),
        device_error=_optional_string(payload.get("device_error")),
    )


def _optional_string(value: object) -> str | None:
    """Normalize one optional runtime detail string value."""

    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


__all__ = ["RuntimeCommandRunner", "TorchRuntimeDetails", "query_torch_runtime"]
