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

"""Execute no-copy image and mask loading against a hidden real Comfy process."""

from __future__ import annotations

import argparse
import copy
import io
import json
import os
import socket
import subprocess
import tempfile
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, BinaryIO, cast

import requests
from PIL import Image

from substitute.application.generation import ComfyAssetStagingService
from substitute.domain.common import JsonObject
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy import LocalComfyAssetStager
from substitute.infrastructure.comfy.workspace_python_resolver import (
    attached_comfy_python_candidates,
)


@dataclass(frozen=True, slots=True)
class RealComfyInpaintAssetResult:
    """Summarize one real external image-and-mask execution."""

    image_node_class: str
    mask_node_class: str
    image_size: tuple[int, int]
    mask_size: tuple[int, int]
    authored_payload_preserved: bool
    copied_file_count: int


class RealComfyInpaintAssetHarness:
    """Own an isolated hidden Comfy process and hostile local asset fixture."""

    def __init__(self, *, repository_root: Path, comfy_root: Path) -> None:
        """Resolve runtime and reserve isolated process state."""

        self._repository_root = repository_root.resolve()
        self._comfy_root = comfy_root.resolve()
        candidates = attached_comfy_python_candidates(
            self._comfy_root,
            environment={},
        )
        self._python = next(
            (
                candidate.executable.resolve()
                for candidate in candidates
                if candidate.executable.is_file()
            ),
            None,
        )
        if self._python is None:
            raise RuntimeError(
                f"Comfy Python is unavailable beneath {self._comfy_root}"
            )
        self._port = _available_port()
        self._endpoint = ComfyEndpoint(host="127.0.0.1", port=self._port)
        self._workspace: tempfile.TemporaryDirectory[str] | None = None
        self._desktop_source: tempfile.TemporaryDirectory[str] | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._log_handle: BinaryIO | None = None
        self._root: Path | None = None

    def __enter__(self) -> RealComfyInpaintAssetHarness:
        """Start Comfy without opening a browser or visible console window."""

        build_root = self._repository_root / "build"
        build_root.mkdir(parents=True, exist_ok=True)
        self._workspace = tempfile.TemporaryDirectory(
            prefix="inpaint-local-asset-",
            dir=build_root,
        )
        self._desktop_source = tempfile.TemporaryDirectory(
            prefix="inpaint external source, (hostile) ",
        )
        self._root = Path(self._workspace.name)
        for name in ("input", "output", "temp", "user"):
            (self._root / name).mkdir(parents=True)
        log_path = self._root / "comfy.log"
        self._log_handle = log_path.open("wb")
        self._process = subprocess.Popen(
            [
                str(self._python),
                "main.py",
                "--listen",
                "127.0.0.1",
                "--port",
                str(self._port),
                "--cpu",
                "--disable-auto-launch",
                "--disable-all-custom-nodes",
                "--whitelist-custom-nodes",
                "Substitute-BackEnd",
                "--disable-metadata",
                "--input-directory",
                str(self._root / "input"),
                "--output-directory",
                str(self._root / "output"),
                "--temp-directory",
                str(self._root / "temp"),
                "--user-directory",
                str(self._root / "user"),
            ],
            cwd=self._comfy_root,
            stdin=subprocess.DEVNULL,
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
            creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
        )
        try:
            self._wait_until_ready()
        except Exception:
            self.__exit__()
            raise
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Stop Comfy and clean every isolated harness artifact."""

        _ = exc_info
        process = self._process
        if process is not None and process.poll() is None:
            _terminate_process_tree(process)
        if self._log_handle is not None:
            self._log_handle.close()
        if self._workspace is not None:
            self._workspace.cleanup()
        if self._desktop_source is not None:
            self._desktop_source.cleanup()

    def run(self) -> RealComfyInpaintAssetResult:
        """Authorize, validate, execute, and inspect external image and mask files."""

        root = self._required_root()
        desktop_source = self._required_desktop_source()
        workflow_name = "Hostile Inpaint " + ("long-workflow-" * 12)
        image_path = desktop_source / (
            "masterpiece, best quality, (external source) [never copied].png"
        )
        mask_path = (
            root
            / "projects"
            / workflow_name
            / "masks"
            / ("mask, (long project name) __ load_image_as_mask.png")
        )
        mask_path.parent.mkdir(parents=True)
        _write_image_fixture(image_path)
        _write_mask_fixture(mask_path)
        input_before = tuple((root / "input").rglob("*"))
        authored_payload = _authored_prompt(
            image_path=image_path,
            mask_name=mask_path.name,
        )
        original_payload = copy.deepcopy(authored_payload)
        staged = ComfyAssetStagingService.with_projects_dir(
            stager=LocalComfyAssetStager(endpoint=self._endpoint),
            projects_dir=root / "projects",
        ).stage_payload(
            workflow_payload=authored_payload,
            workflow_id="hostile-inpaint",
            workflow_name=workflow_name,
        )
        if staged.failures:
            raise AssertionError(f"Asset authorization failed: {staged.failures}")
        prompt = staged.workflow_payload
        _attach_observable_outputs(prompt)
        prompt_id = self._queue(prompt)
        history = self._wait_for_history(prompt_id)
        image_output = self._rendered_output(history, "3")
        mask_output = self._rendered_output(history, "5")
        _assert_rendered_fixtures(image_output=image_output, mask_output=mask_output)
        input_after = tuple((root / "input").rglob("*"))
        if input_after != input_before:
            raise AssertionError("Local execution copied files into Comfy input.")
        image_node = cast(dict[str, object], prompt["1"])
        mask_node = cast(dict[str, object], prompt["2"])
        return RealComfyInpaintAssetResult(
            image_node_class=str(image_node["class_type"]),
            mask_node_class=str(mask_node["class_type"]),
            image_size=image_output.size,
            mask_size=mask_output.size,
            authored_payload_preserved=authored_payload == original_payload,
            copied_file_count=len(input_after) - len(input_before),
        )

    def _wait_until_ready(self) -> None:
        """Wait for both Substitute execution nodes to appear in object-info."""

        deadline = time.monotonic() + 90.0
        url = f"http://127.0.0.1:{self._port}/object_info/SubstituteBackendLoadImage"
        while time.monotonic() < deadline:
            process = self._process
            if process is not None and process.poll() is not None:
                raise RuntimeError(self._startup_failure())
            try:
                response = requests.get(url, timeout=1.0)
                if response.status_code == 200:
                    payload = response.json()
                    if "SubstituteBackendLoadImage" in payload:
                        return
            except requests.RequestException:
                pass
            time.sleep(0.1)
        raise TimeoutError(self._startup_failure())

    def _queue(self, prompt: dict[str, object]) -> str:
        """Queue the staged prompt through Comfy's real validation boundary."""

        response = requests.post(
            self._endpoint.substitute_prompt_queue_url(),
            json=cast(
                Any,
                {"prompt": prompt, "client_id": "inpaint-local-asset-harness"},
            ),
            timeout=10.0,
        )
        payload = response.json()
        if response.status_code != 200:
            raise AssertionError(f"Comfy rejected the prompt: {payload}")
        prompt_id = payload.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise AssertionError(f"Comfy rejected the prompt: {payload}")
        return prompt_id

    def _wait_for_history(self, prompt_id: str) -> dict[str, object]:
        """Wait for model-free execution and return its history record."""

        deadline = time.monotonic() + 60.0
        while time.monotonic() < deadline:
            response = requests.get(
                self._endpoint.history_url(prompt_id),
                timeout=3.0,
            )
            response.raise_for_status()
            payload = response.json()
            record = payload.get(prompt_id)
            if isinstance(record, dict):
                status = record.get("status")
                if isinstance(status, dict) and status.get("status_str") == "error":
                    raise AssertionError(f"Comfy execution failed: {record}")
                if record.get("outputs"):
                    return cast(dict[str, object], record)
            time.sleep(0.1)
        raise TimeoutError("Comfy did not complete the local asset fixture.")

    def _rendered_output(
        self,
        history: dict[str, object],
        node_id: str,
    ) -> Image.Image:
        """Fetch one PreviewImage result and return a detached image."""

        outputs = history.get("outputs")
        node_output = outputs.get(node_id) if isinstance(outputs, dict) else None
        images = node_output.get("images") if isinstance(node_output, dict) else None
        descriptor = images[0] if isinstance(images, list) and images else None
        if not isinstance(descriptor, dict):
            raise AssertionError(
                f"Missing rendered output for node {node_id}: {history}"
            )
        response = requests.get(
            self._endpoint.view_url(),
            params=descriptor,
            timeout=10.0,
        )
        response.raise_for_status()
        with Image.open(io.BytesIO(response.content)) as opened:
            return opened.copy()

    def _startup_failure(self) -> str:
        """Return startup logs without retaining the temporary directory."""

        root = self._required_root()
        log_path = root / "comfy.log"
        if self._log_handle is not None:
            self._log_handle.flush()
        return log_path.read_text(encoding="utf-8", errors="replace")

    def _required_root(self) -> Path:
        """Return initialized workspace root."""

        if self._root is None:
            raise RuntimeError("Harness has not been started.")
        return self._root

    def _required_desktop_source(self) -> Path:
        """Return the external source directory on the host temp volume."""

        if self._desktop_source is None:
            raise RuntimeError("Harness has not been started.")
        return Path(self._desktop_source.name)


def _authored_prompt(*, image_path: Path, mask_name: str) -> JsonObject:
    """Build the inpaint loader portion that previously failed validation."""

    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": str(image_path)},
        },
        "2": {
            "class_type": "LoadImageMask",
            "inputs": {"image": mask_name, "channel": "red"},
        },
    }


def _attach_observable_outputs(prompt: dict[str, object]) -> None:
    """Attach model-free output nodes so Comfy executes both loader branches."""

    prompt.update(
        {
            "3": {
                "class_type": "PreviewImage",
                "inputs": {"images": ["1", 0]},
            },
            "4": {
                "class_type": "MaskToImage",
                "inputs": {"mask": ["2", 0]},
            },
            "5": {
                "class_type": "PreviewImage",
                "inputs": {"images": ["4", 0]},
            },
        }
    )


def _write_image_fixture(path: Path) -> None:
    """Write a non-square RGB source with hostile edge colors."""

    image = Image.new("RGB", (23, 17), (17, 93, 241))
    image.putpixel((0, 0), (255, 0, 127))
    image.putpixel((22, 16), (0, 255, 63))
    image.save(path)


def _write_mask_fixture(path: Path) -> None:
    """Write a non-square grayscale mask with boundary values."""

    image = Image.new("L", (23, 17), 0)
    image.putpixel((0, 0), 255)
    image.putpixel((11, 8), 127)
    image.putpixel((22, 16), 255)
    image.save(path)


def _assert_rendered_fixtures(
    *,
    image_output: Image.Image,
    mask_output: Image.Image,
) -> None:
    """Prove dimensions and hostile edge pixels survived real node execution."""

    image = image_output.convert("RGB")
    mask = mask_output.convert("RGB")
    if image.size != (23, 17) or mask.size != (23, 17):
        raise AssertionError(
            f"Rendered fixture sizes drifted: image={image.size}, mask={mask.size}"
        )
    if image.getpixel((0, 0)) != (255, 0, 127):
        raise AssertionError("External image boundary pixel was not decoded exactly.")
    if image.getpixel((22, 16)) != (0, 255, 63):
        raise AssertionError("External image far-edge pixel was not decoded exactly.")
    if mask.getpixel((0, 0)) != (255, 255, 255):
        raise AssertionError("Mask maximum boundary was not decoded from red.")
    center = cast(tuple[int, int, int], mask.getpixel((11, 8)))
    if any(abs(channel - 127) > 1 for channel in center):
        raise AssertionError(f"Mask midpoint was corrupted: {center}")
    if mask.getpixel((22, 16)) != (255, 255, 255):
        raise AssertionError("Mask far-edge maximum was not decoded from red.")


def _available_port() -> int:
    """Reserve and release one loopback TCP port."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    """Terminate the exact harness process tree without leaving log handles."""

    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse explicit Comfy checkout selection."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--comfy-root", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the hidden real-Comfy inpaint asset proof."""

    arguments = _parse_arguments(argv)
    repository_root = Path(__file__).resolve().parents[1]
    with RealComfyInpaintAssetHarness(
        repository_root=repository_root,
        comfy_root=arguments.comfy_root,
    ) as harness:
        print(json.dumps(asdict(harness.run()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "RealComfyInpaintAssetHarness",
    "RealComfyInpaintAssetResult",
    "main",
]
