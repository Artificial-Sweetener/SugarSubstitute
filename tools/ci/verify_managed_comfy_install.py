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

"""Provision pinned managed Comfy and prove its runtime and HTTP API."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from collections.abc import Sequence
from urllib.error import URLError
from urllib.request import urlopen


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from substitute.infrastructure.comfy.standalone_environment.layout import (  # noqa: E402
    ManagedStandaloneLayout,
)
from substitute.infrastructure.comfy.standalone_environment.models import (  # noqa: E402
    StandaloneVariantId,
)
from substitute.infrastructure.comfy.standalone_environment.pinned_catalog import (  # noqa: E402
    PinnedStandaloneEnvironmentCatalog,
)
from substitute.infrastructure.comfy.standalone_environment.provisioner import (  # noqa: E402
    StandaloneEnvironmentProvisioner,
)


_DEFAULT_TIMEOUT_SECONDS = 600.0
_CORE_NODE_CLASS = "CheckpointLoaderSimple"


class ManagedComfyVerificationError(RuntimeError):
    """Report a pinned environment that cannot run its expected Comfy API."""


def verify_managed_comfy_install(
    *,
    workspace: Path,
    cache_root: Path,
    variant: StandaloneVariantId,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> None:
    """Provision one exact pin, launch it on CPU, and verify core API behavior."""

    release = PinnedStandaloneEnvironmentCatalog.load_default().resolve(variant)
    virtual_python = StandaloneEnvironmentProvisioner().provision(
        workspace=workspace,
        variant=variant,
        cache_root=cache_root,
        on_log=lambda message: print(f"MANAGED_COMFY_INSTALL {message}", flush=True),
    )
    layout = ManagedStandaloneLayout(workspace, variant)
    _verify_runtime_versions(
        virtual_python=virtual_python,
        workspace=workspace,
        expected_torch_version=release.torch_version,
    )
    metadata = json.loads(layout.manifest.read_text(encoding="utf-8"))
    if (
        metadata.get("id") != variant.value
        or metadata.get("version") != release.release_tag
    ):
        raise ManagedComfyVerificationError(
            "Installed standalone metadata does not match the repository pin."
        )

    port = _available_loopback_port()
    log_path = workspace.parent / "managed-comfy-startup.log"
    command = [
        str(virtual_python),
        str(workspace / "main.py"),
        "--listen",
        "127.0.0.1",
        "--port",
        str(port),
        "--disable-auto-launch",
        "--cpu",
    ]
    environment = dict(os.environ)
    environment["PYTHONNOUSERSITE"] = "1"
    with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
        process = subprocess.Popen(  # noqa: S603
            command,
            cwd=workspace,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            shell=False,
        )
    try:
        base_url = f"http://127.0.0.1:{port}"
        _wait_for_comfy_api(
            process=process,
            url=f"{base_url}/system_stats",
            log_path=log_path,
            timeout_seconds=timeout_seconds,
        )
        object_info = _read_json(f"{base_url}/object_info")
        if _CORE_NODE_CLASS not in object_info:
            raise ManagedComfyVerificationError(
                f"Comfy API omitted core node class {_CORE_NODE_CLASS}."
            )
        print(
            "MANAGED_COMFY_READY "
            f"variant={variant.value} release={release.release_tag} "
            f"comfy={release.comfyui_version} commit={release.comfyui_commit}",
            flush=True,
        )
    finally:
        _stop_process(process)


def _verify_runtime_versions(
    *,
    virtual_python: Path,
    workspace: Path,
    expected_torch_version: str,
) -> None:
    """Verify that the hydrated runtime imports its bundled Torch build."""

    result = subprocess.run(  # noqa: S603
        [
            str(virtual_python),
            "-c",
            "import json, torch; print(json.dumps({'torch': torch.__version__}))",
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise ManagedComfyVerificationError(
            "Pinned managed runtime could not import Torch: " + result.stderr.strip()
        )
    reported = json.loads(result.stdout.strip())
    if reported.get("torch") != expected_torch_version:
        raise ManagedComfyVerificationError(
            "Pinned managed runtime Torch version does not match the catalog: "
            f"{reported.get('torch')} != {expected_torch_version}."
        )


def _wait_for_comfy_api(
    *,
    process: subprocess.Popen[bytes],
    url: str,
    log_path: Path,
    timeout_seconds: float,
) -> None:
    """Wait for the real Comfy API or report bounded process diagnostics."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise ManagedComfyVerificationError(
                f"Managed Comfy exited with {return_code} before readiness. "
                + _log_tail(log_path)
            )
        try:
            _read_json(url)
            return
        except (OSError, URLError, json.JSONDecodeError):
            time.sleep(0.25)
    raise ManagedComfyVerificationError(
        "Managed Comfy did not expose its API before timeout. " + _log_tail(log_path)
    )


def _read_json(url: str) -> dict[str, object]:
    """Read one loopback JSON object through the production HTTP surface."""

    with urlopen(url, timeout=5) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise ManagedComfyVerificationError(
            f"Comfy API returned non-object JSON: {url}"
        )
    return {str(key): value for key, value in payload.items()}


def _available_loopback_port() -> int:
    """Reserve and return one currently available loopback TCP port."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    """Stop the verified Comfy process before the CI workspace is removed."""

    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=15)


def _log_tail(path: Path, *, maximum_lines: int = 80) -> str:
    """Return bounded Comfy startup output for actionable CI failures."""

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return f"Startup log: {path}."
    return "Startup log tail:\n" + "\n".join(lines[-maximum_lines:])


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse managed Comfy verification inputs."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument(
        "--variant",
        choices=tuple(variant.value for variant in StandaloneVariantId),
        required=True,
    )
    parser.add_argument(
        "--timeout-seconds", type=float, default=_DEFAULT_TIMEOUT_SECONDS
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run pinned managed Comfy verification from CI."""

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    verify_managed_comfy_install(
        workspace=args.workspace,
        cache_root=args.cache_root,
        variant=StandaloneVariantId(args.variant),
        timeout_seconds=args.timeout_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
