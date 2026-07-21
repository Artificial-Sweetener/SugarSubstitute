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

"""Exercise installer and launch contracts against one real upstream tag."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from typing import Final, TextIO, cast
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from substitute.infrastructure.comfy.core_nodepack_reconciler import (
    ensure_core_comfy_nodepacks,
)
from substitute.infrastructure.comfy.manager_environment import (
    manager_runtime_environment,
)
from substitute.infrastructure.comfy.manager_provisioner import (
    ensure_attached_workspace_manager,
    ensure_managed_workspace_manager,
)
from substitute.infrastructure.comfy.manager_runtime_probe import (
    detect_workspace_manager_runtime,
)
from tools.ci.comfy_support_matrix import matrix_entry

_COMFYUI_REPOSITORY: Final[str] = "https://github.com/Comfy-Org/ComfyUI.git"
_STARTUP_TIMEOUT_SECONDS: Final[float] = 420.0
_REQUEST_TIMEOUT_SECONDS: Final[float] = 10.0
_OUTPUT_LIMIT: Final[int] = 80_000


def main(argv: Sequence[str] | None = None) -> int:
    """Run one exact-tag compatibility probe and report structured evidence."""

    arguments = _parse_arguments(argv)
    entry = matrix_entry(arguments.comfyui_tag)
    repository_root = Path.cwd().resolve()
    workspace = (
        arguments.workspace.resolve()
        if arguments.workspace is not None
        else repository_root / "build" / "comfy-compatibility" / entry.comfyui_tag
    )
    _prepare_checkout(workspace, entry.comfyui_tag)
    python_executable = _prepare_environment(repository_root, workspace)
    original_head = _git_output(workspace, "rev-parse", "HEAD")
    _assert_manager_requirement(workspace, entry.manager_version)

    managed_runtime = ensure_managed_workspace_manager(
        workspace,
        python_executable=python_executable,
        on_log=_log,
    )
    _assert_runtime(
        managed_runtime.version,
        managed_runtime.supports_pygit2,
        entry.manager_version,
        entry.supports_pygit2,
    )
    ensure_core_comfy_nodepacks(
        workspace,
        python_executable=python_executable,
        on_log=_log,
    )

    preservation_marker = workspace / "custom_nodes" / "User-Owned-Node" / "data.txt"
    preservation_marker.parent.mkdir(parents=True, exist_ok=True)
    preservation_marker.write_text("preserve attached content", encoding="utf-8")
    attached_runtime = ensure_attached_workspace_manager(
        workspace,
        python_executable=python_executable,
        on_log=_log,
    )
    ensure_core_comfy_nodepacks(
        workspace,
        python_executable=python_executable,
        on_log=_log,
    )
    if preservation_marker.read_text(encoding="utf-8") != "preserve attached content":
        raise RuntimeError(
            "Attached provisioning modified user-owned custom-node data."
        )
    if _git_output(workspace, "rev-parse", "HEAD") != original_head:
        raise RuntimeError(
            "Attached provisioning changed the ComfyUI checkout revision."
        )
    if _git_output(workspace, "diff", "--name-only"):
        raise RuntimeError("Installer modified tracked files in the attached checkout.")
    if attached_runtime.kind is not managed_runtime.kind:
        raise RuntimeError(
            "Managed and attached probes selected different Manager kinds."
        )

    launch_runtime = detect_workspace_manager_runtime(
        workspace,
        python_executable=python_executable,
    )
    evidence = _probe_server(
        workspace=workspace,
        python_executable=python_executable,
        runtime=launch_runtime,
    )
    print(
        json.dumps(
            {
                "comfyui_tag": entry.comfyui_tag,
                "manager_version": launch_runtime.version,
                "manager_supports_pygit2": launch_runtime.supports_pygit2,
                "manager_uses_pygit2": launch_runtime.uses_pygit2,
                "managed_flow": "passed",
                "attached_flow": "passed",
                "tracked_checkout_preserved": True,
                **evidence,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse the exact upstream tag and optional prepared workspace."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--comfyui-tag", required=True)
    parser.add_argument("--workspace", type=Path)
    return parser.parse_args(argv)


def _prepare_checkout(workspace: Path, tag: str) -> None:
    """Clone the exact immutable upstream tag unless a matching checkout exists."""

    if workspace.is_dir():
        actual_tag = _git_output(workspace, "describe", "--tags", "--exact-match")
        if actual_tag != tag:
            raise RuntimeError(
                f"Existing compatibility workspace is {actual_tag!r}, expected {tag!r}."
            )
        return
    workspace.parent.mkdir(parents=True, exist_ok=True)
    _run_checked(
        [
            "git",
            "clone",
            "--branch",
            tag,
            "--depth",
            "1",
            "--filter=blob:none",
            _COMFYUI_REPOSITORY,
            str(workspace),
        ],
        cwd=workspace.parent,
    )


def _prepare_environment(repository_root: Path, workspace: Path) -> Path:
    """Create a workspace-local Python and install ComfyUI's real requirements."""

    windows = os.name == "nt"
    python_executable = (
        workspace / ".venv" / ("Scripts/python.exe" if windows else "bin/python")
    )
    uv_executable = (
        repository_root / ".venv" / ("Scripts/uv.exe" if windows else "bin/uv")
    )
    if not python_executable.is_file():
        _run_checked(
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
    _run_checked(torch_command, cwd=workspace)
    _run_checked(
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


def _assert_manager_requirement(workspace: Path, expected_version: str) -> None:
    """Confirm the checked-out Comfy tag owns the expected exact Manager pin."""

    requirement = (workspace / "manager_requirements.txt").read_text(encoding="utf-8")
    expected = f"comfyui_manager=={expected_version}"
    if expected not in requirement.splitlines():
        raise RuntimeError(
            f"{workspace.name} does not declare expected Manager pin {expected}."
        )


def _assert_runtime(
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


def _probe_server(
    *,
    workspace: Path,
    python_executable: Path,
    runtime: object,
) -> dict[str, object]:
    """Launch Comfy headlessly, verify runtime APIs, and leave no child process."""

    from substitute.domain.comfy_manager import ComfyManagerRuntime

    manager_runtime = cast("ComfyManagerRuntime", runtime)
    port = _available_loopback_port()
    environment = manager_runtime_environment(
        workspace,
        os.environ,
        use_pygit2=manager_runtime.uses_pygit2,
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
        *manager_runtime.launch_arguments,
    ]
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


def _wait_for_json(
    process: subprocess.Popen[str],
    url: str,
    output: list[str],
) -> object:
    """Poll one startup endpoint until it responds or the process fails."""

    deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
    last_error = "server did not respond"
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"ComfyUI exited with {return_code} before startup. {_output_excerpt(output)}"
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

    with urlopen(url, timeout=_REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}.")
        return json.loads(response.read())


def _available_loopback_port() -> int:
    """Reserve and release one currently available loopback port."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _drain_output(stream: TextIO | None, output: list[str]) -> None:
    """Drain child output to prevent blocking while retaining diagnostics."""

    if stream is None:
        return
    for line in stream:
        output.append(line)
        while sum(len(item) for item in output) > _OUTPUT_LIMIT and output:
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


def _run_checked(command: Sequence[str], *, cwd: Path) -> None:
    """Run one visible-log command without opening a separate console window."""

    subprocess.run(
        command,
        cwd=cwd,
        check=True,
        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
    )


def _git_output(workspace: Path, *arguments: str) -> str:
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
    )
    return result.stdout.strip()


def _output_excerpt(output: Sequence[str]) -> str:
    """Return bounded recent child output for a failed probe."""

    return "".join(output)[-_OUTPUT_LIMIT:]


def _log(message: str) -> None:
    """Emit one production installer progress line in CI."""

    print(message, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
