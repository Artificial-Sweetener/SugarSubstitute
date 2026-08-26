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

"""Provide shared headless infrastructure for real Comfy compatibility probes."""

from __future__ import annotations

from collections.abc import Sequence
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import threading
import time
from typing import Final, TextIO
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from substitute.domain.comfy_manager import ComfyManagerRuntime
from substitute.infrastructure.comfy.manager_environment import (
    manager_runtime_environment,
)
from tools.ci.loopback_port_lease import LoopbackPortLease

STARTUP_TIMEOUT_SECONDS: Final[float] = 420.0
REQUEST_TIMEOUT_SECONDS: Final[float] = 10.0
OUTPUT_LIMIT: Final[int] = 80_000


def prepare_environment(repository_root: Path, workspace: Path) -> Path:
    """Create workspace Python and install the checkout's real requirements."""

    windows = os.name == "nt"
    python_executable = (
        workspace / ".venv" / ("Scripts/python.exe" if windows else "bin/python")
    )
    repository_uv = (
        repository_root / ".venv" / ("Scripts/uv.exe" if windows else "bin/uv")
    )
    uv_executable = _resolve_uv_executable(repository_uv)
    if not python_executable.is_file():
        run_checked(
            [
                str(uv_executable),
                "venv",
                "--seed",
                "--python",
                "3.12",
                str(workspace / ".venv"),
            ],
            cwd=repository_root,
        )
    torch_command = [
        str(uv_executable),
        "pip",
        "install",
        "--python",
        str(python_executable),
        "--index-strategy",
        "unsafe-best-match",
    ]
    if sys.platform != "darwin":
        torch_command.extend(["--index-url", "https://download.pytorch.org/whl/cpu"])
    torch_command.extend(["torch", "torchvision", "torchaudio"])
    run_checked(torch_command, cwd=workspace)
    run_checked(
        [
            str(uv_executable),
            "pip",
            "install",
            "--python",
            str(python_executable),
            "--index-strategy",
            "unsafe-best-match",
            "--requirement",
            str(workspace / "requirements.txt"),
        ],
        cwd=workspace,
    )
    return python_executable


def _resolve_uv_executable(repository_uv: Path) -> Path:
    """Use the repository toolchain first and a CI-installed uv only as fallback."""

    if repository_uv.is_file():
        return repository_uv
    discovered = shutil.which("uv")
    if discovered is None:
        raise RuntimeError(
            "Comfy qualification requires uv in the repository .venv or PATH."
        )
    return Path(discovered).resolve()


def assert_manager_requirement(workspace: Path, expected_version: str) -> None:
    """Confirm the checkout owns the expected exact Manager pin."""

    requirement = (workspace / "manager_requirements.txt").read_text(encoding="utf-8")
    expected = f"comfyui_manager=={expected_version}"
    if expected not in requirement.splitlines():
        raise RuntimeError(
            f"{workspace.name} does not declare expected Manager pin {expected}."
        )


def assert_runtime(
    actual_version: str | None,
    actual_supports_pygit2: bool,
    expected_version: str,
    expected_supports_pygit2: bool,
) -> None:
    """Confirm runtime evidence matches the checkout-owned release contract."""

    if actual_version != expected_version:
        raise RuntimeError(
            f"Manager runtime is {actual_version!r}, expected {expected_version!r}."
        )
    if actual_supports_pygit2 is not expected_supports_pygit2:
        raise RuntimeError(
            "Manager optional pygit2 capability does not match upstream history."
        )


def probe_server(
    *,
    workspace: Path,
    python_executable: Path,
    runtime: ComfyManagerRuntime,
) -> dict[str, object]:
    """Launch Comfy headlessly, verify runtime APIs, and leave no child process."""

    with LoopbackPortLease.acquire() as endpoint_lease:
        port = endpoint_lease.port
        environment = manager_runtime_environment(
            workspace,
            os.environ,
            use_pygit2=runtime.uses_pygit2,
        )
        environment["SUGARSUBSTITUTE_SKIP_TTS_INSTALLER"] = "1"
        environment["PYTHONIOENCODING"] = "utf-8"
        command = [
            str(python_executable),
            str(workspace / "main.py"),
            "--listen",
            "127.0.0.1",
            "--port",
            str(port),
            "--cpu",
            *runtime.launch_arguments,
        ]
        endpoint_lease.release_for_handoff()
        process = subprocess.Popen(
            command,
            cwd=workspace,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
        )
    output: list[str] = []
    reader = threading.Thread(
        target=_drain_output,
        args=(process.stdout, output),
        daemon=True,
    )
    reader.start()
    base_url = f"http://127.0.0.1:{port}"
    try:
        object_info = _wait_for_json(process, f"{base_url}/object_info", output)
        if not isinstance(object_info, dict):
            raise RuntimeError("ComfyUI /object_info did not return an object.")
        expected_nodes = {"SugarCubes.CubeInput", "SugarCubes.CubeOutput"}
        missing_nodes = expected_nodes.difference(object_info)
        if missing_nodes:
            raise RuntimeError(
                f"Required SugarCubes nodes were not registered: {sorted(missing_nodes)}"
            )
        _require_json(f"{base_url}/substitute/v1/capabilities")
        _require_json(f"{base_url}/sugarcubes/list")
        installed = _require_json(f"{base_url}/v2/customnode/installed")
        if not isinstance(installed, (dict, list)):
            raise RuntimeError(
                "Integrated Manager installed endpoint returned invalid JSON."
            )
        return {
            "object_info": "passed",
            "required_node_registration": "passed",
            "substitute_backend_endpoint": "passed",
            "sugarcubes_endpoint": "passed",
            "manager_v4_endpoint": "passed",
        }
    finally:
        _terminate_process(process)
        reader.join(timeout=10)


def run_checked(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: float | None = None,
) -> None:
    """Run a logged command without opening a separate console window."""

    subprocess.run(
        command,
        cwd=cwd,
        check=True,
        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
        timeout=timeout_seconds,
    )


def git_output(workspace: Path, *arguments: str) -> str:
    """Return normalized output from a read-only Git query."""

    result = subprocess.run(
        ["git", *arguments],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
        timeout=30,
    )
    return result.stdout.strip()


def log(message: str) -> None:
    """Emit one production installer progress line in CI."""

    print(message, flush=True)


def _wait_for_json(
    process: subprocess.Popen[str],
    url: str,
    output: list[str],
) -> object:
    """Poll one startup endpoint until it responds or the process fails."""

    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    last_error = "server did not respond"
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"ComfyUI exited with {return_code} before startup. "
                f"{_output_excerpt(output)}"
            )
        try:
            return _require_json(url)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = repr(error)
            time.sleep(1)
    raise RuntimeError(
        f"ComfyUI startup timed out: {last_error}. {_output_excerpt(output)}"
    )


def _require_json(url: str) -> object:
    """Fetch and decode one bounded local ComfyUI JSON response."""

    with urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}.")
        return json.loads(response.read())


def _drain_output(stream: TextIO | None, output: list[str]) -> None:
    """Drain child output to prevent blocking while retaining diagnostics."""

    if stream is None:
        return
    for line in stream:
        output.append(line)
        while sum(len(item) for item in output) > OUTPUT_LIMIT and output:
            output.pop(0)


def _terminate_process(process: subprocess.Popen[str]) -> None:
    """Terminate the headless server and confirm no process remains."""

    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=30)
        raise RuntimeError("ComfyUI required forced termination after its probe.")


def _output_excerpt(output: Sequence[str]) -> str:
    """Return bounded recent child output for a failed probe."""

    return "".join(output)[-OUTPUT_LIMIT:]


__all__ = [
    "assert_manager_requirement",
    "assert_runtime",
    "git_output",
    "log",
    "prepare_environment",
    "probe_server",
    "run_checked",
]
