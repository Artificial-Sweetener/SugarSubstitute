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

"""Run direct-output takeover fixtures against an isolated managed ComfyUI."""

from __future__ import annotations

import json
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Mapping, cast
from uuid import uuid4
from uuid import UUID

import requests
import websocket

from substitute.application.direct_workflows import DirectWorkflowExecutionProjector
from substitute.application.workflows.output_canvas_projection import (
    build_output_canvas_projection,
)
from substitute.application.ports.comfy_gateway import (
    ListenerOutputSource,
    OutputImageUpdate,
    OutputSavePlan,
)
from substitute.domain.comfy_workflow import (
    ComfyImageOutputDiscovery,
    DirectWorkflowGenerationPlan,
)
from substitute.domain.common import JsonObject
from substitute.domain.onboarding import ComfyEndpoint
from substitute.domain.workflow import ImageMeta, WorkflowState
from substitute.infrastructure.comfy.artifact_fetcher import ComfyArtifactFetcher
from substitute.infrastructure.comfy.final_image_event import FinalImageScene
from substitute.infrastructure.comfy.final_image_event_handler import (
    FinalImageEventHandler,
)
from substitute.infrastructure.comfy.output_image_persistence import (
    OutputImagePersistence,
)
from substitute.infrastructure.comfy.standard_executed_image_handler import (
    StandardExecutedImageContext,
    StandardExecutedImageHandler,
)
from tests.managed_comfy_harness_layout import ManagedComfyHarnessLayout


@dataclass(frozen=True, slots=True)
class RealComfyFixtureResult:
    """Summarize one real Comfy direct-output fixture execution."""

    name: str
    source_count: int
    image_count: int
    source_labels: tuple[str, ...]
    batch_indices: tuple[int, ...]


class ManagedComfyDirectOutputHarness:
    """Own an isolated Comfy process and model-free output fixture runs."""

    def __init__(self, repository_root: Path) -> None:
        """Resolve managed Comfy runtime paths without using the user's process."""

        self._layout = ManagedComfyHarnessLayout.resolve(repository_root)
        self._comfy_root = self._layout.comfy_root
        self._python = self._layout.python_executable
        self._port = _available_port()
        self._endpoint = ComfyEndpoint(host="127.0.0.1", port=self._port)
        self._temporary_directory: tempfile.TemporaryDirectory[str] | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._log_handle: BinaryIO | None = None
        self._root: Path | None = None

    def __enter__(self) -> "ManagedComfyDirectOutputHarness":
        """Start isolated managed Comfy and wait for its HTTP API."""

        temporary_directory = tempfile.TemporaryDirectory(
            prefix="substitute-direct-comfy-harness-"
        )
        self._temporary_directory = temporary_directory
        self._root = Path(temporary_directory.name)
        for directory_name in (
            "comfy-output",
            "comfy-temp",
            "comfy-input",
            "comfy-user",
        ):
            (self._root / directory_name).mkdir(parents=True, exist_ok=True)
        log_path = self._root / "comfy.log"
        log_handle = log_path.open("wb")
        self._log_handle = log_handle
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
                "--disable-metadata",
                "--output-directory",
                str(self._root / "comfy-output"),
                "--temp-directory",
                str(self._root / "comfy-temp"),
                "--input-directory",
                str(self._root / "comfy-input"),
                "--user-directory",
                str(self._root / "comfy-user"),
            ],
            cwd=self._comfy_root,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=self._layout.process_creation_flags(),
        )
        try:
            self._wait_until_ready()
        except Exception:
            self.__exit__()
            raise
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Stop isolated Comfy, validate startup logs, and remove temporary state."""

        _ = exc_info
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        log_handle = self._log_handle
        if log_handle is not None:
            log_handle.close()
        if self._root is not None:
            log_text = (self._root / "comfy.log").read_text(
                encoding="utf-8",
                errors="replace",
            )
            if (
                "IMPORT FAILED" in log_text
                or "Traceback (most recent call last)" in log_text
            ):
                raise AssertionError(
                    f"Managed Comfy reported import errors:\n{log_text}"
                )
        if self._temporary_directory is not None:
            self._temporary_directory.cleanup()

    def run_fixture(
        self,
        *,
        name: str,
        graph: dict[str, object],
        expected_source_count: int,
        expected_image_count: int,
    ) -> RealComfyFixtureResult:
        """Discover, instrument, execute, persist, and verify one real graph."""

        root = self._required_root()
        definitions = self.node_definitions()
        manifest = ComfyImageOutputDiscovery().discover(
            graph,
            node_definitions=definitions,
        )
        if len(manifest.sources) != expected_source_count:
            raise AssertionError(
                f"{name}: expected {expected_source_count} sources, "
                f"found {len(manifest.sources)}"
            )
        projection = DirectWorkflowExecutionProjector().project(
            DirectWorkflowGenerationPlan(
                authored_api_graph=graph,
                output_manifest=manifest,
            )
        )
        updates: list[OutputImageUpdate] = []
        substitute_output = root / "substitute-output" / name
        persistence = OutputImagePersistence(
            output_save_plan=OutputSavePlan(
                output_root=substitute_output,
                path_pattern="{workflow}_{source}_{index}",
                workflow_name=name,
                output_run_number=1,
                job_started_at=datetime.now().astimezone(),
            ),
            workflow_payload=projection.prompt,
            sugar_script="",
            cube_numbers_by_alias={},
        )
        client_id = f"substitute-harness-{uuid4().hex}"
        handler = StandardExecutedImageHandler(
            context=StandardExecutedImageContext(
                workflow_id=f"workflow-{name}",
                generation_run_id=f"run-{name}",
                prompt_id="pending",
                client_id=client_id,
                workflow_payload=projection.prompt,
                scene=FinalImageScene(),
            ),
            sources_by_node={
                recovery.recovery_node_id: ListenerOutputSource(
                    recovery.recovery_node_id,
                    recovery.source_key,
                    recovery.source_label,
                )
                for recovery in projection.recovery_outputs
            },
            final_image_handler=FinalImageEventHandler(
                artifact_fetcher=ComfyArtifactFetcher(endpoint=self._endpoint),
                output_persistence=persistence,
                on_output_image=updates.append,
            ),
        )
        prompt_id = self._queue_and_receive(
            client_id=client_id,
            projection=projection.prompt,
            execution_targets=projection.execution_targets,
            handler=handler,
        )
        if prompt_id is None:
            raise AssertionError(f"{name}: Comfy did not return a prompt id")
        if len(updates) != expected_image_count:
            raise AssertionError(
                f"{name}: expected {expected_image_count} persisted images, "
                f"received {len(updates)}"
            )
        authored_output_files = tuple((root / "comfy-output").rglob("*"))
        if any(path.is_file() for path in authored_output_files):
            raise AssertionError(
                f"{name}: authored SaveImage output was not suppressed"
            )
        if not all(
            update.file_path is not None and update.file_path.is_file()
            for update in updates
        ):
            raise AssertionError(f"{name}: Substitute persistence missed an image")
        image_ids = tuple(UUID(int=index + 1) for index in range(len(updates)))
        image_metadata = {
            image_id: ImageMeta(
                workflow_name=name,
                cube_name=update.source_label,
                image_number=index + 1,
                suffix="",
                path=str(update.file_path),
                source_key=update.source_key,
                source_label=update.source_label,
                node_id=update.node_id,
                generation_run_id=update.generation_run_id or "",
                prompt_id=update.prompt_id or "",
                client_id=update.client_id or "",
                list_index=update.list_index,
                batch_index=update.batch_index,
                width=update.artifact_width,
                height=update.artifact_height,
            )
            for index, (image_id, update) in enumerate(
                zip(image_ids, updates, strict=True)
            )
        }
        canvas_projection = build_output_canvas_projection(
            WorkflowState(output_image_uuids=list(image_ids)),
            image_metadata,
        )
        source_labels = tuple(source.label for source in canvas_projection.sources)
        if source_labels != tuple(
            str(index + 1) for index in range(expected_source_count)
        ):
            raise AssertionError(f"{name}: unstable source order {source_labels}")
        projected_image_count = sum(
            len(source.images_by_set) for source in canvas_projection.sources
        )
        if projected_image_count != expected_image_count:
            raise AssertionError(
                f"{name}: canvas projected {projected_image_count} of "
                f"{expected_image_count} images"
            )
        return RealComfyFixtureResult(
            name=name,
            source_count=len(manifest.sources),
            image_count=len(updates),
            source_labels=source_labels,
            batch_indices=tuple(cast(int, update.batch_index) for update in updates),
        )

    def _queue_and_receive(
        self,
        *,
        client_id: str,
        projection: JsonObject,
        execution_targets: tuple[str, ...],
        handler: StandardExecutedImageHandler,
    ) -> str | None:
        """Queue one prompt and route its real websocket image events."""

        websocket_connection = websocket.create_connection(
            self._endpoint.websocket_url(client_id),
            timeout=30,
        )
        try:
            response = requests.post(
                self._endpoint.prompt_url(),
                json=cast(
                    Any,
                    {
                        "prompt": projection,
                        "client_id": client_id,
                        "partial_execution_targets": list(execution_targets),
                    },
                ),
                timeout=30,
            )
            response.raise_for_status()
            prompt_id = response.json().get("prompt_id")
            if not isinstance(prompt_id, str):
                return None
            active_handler = replace(
                handler,
                context=replace(handler.context, prompt_id=prompt_id),
            )
            deadline = time.monotonic() + 45.0
            while time.monotonic() < deadline:
                message = websocket_connection.recv()
                if not isinstance(message, str):
                    continue
                payload = json.loads(message)
                if not isinstance(payload, Mapping):
                    continue
                data = payload.get("data")
                if not isinstance(data, Mapping) or data.get("prompt_id") != prompt_id:
                    continue
                message_type = payload.get("type")
                if message_type == "executed":
                    active_handler.handle(data)
                if message_type == "executing" and data.get("node") is None:
                    return prompt_id
            raise TimeoutError(f"Timed out waiting for Comfy prompt {prompt_id}")
        finally:
            websocket_connection.close()

    def node_definitions(self) -> Mapping[str, Mapping[str, object]]:
        """Return real live definitions from the isolated managed Comfy process."""

        response = requests.get(
            f"http://{self._endpoint.host}:{self._endpoint.port}/object_info",
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise TypeError("Comfy object_info did not return a mapping")
        return {
            str(class_type): definition
            for class_type, definition in payload.items()
            if isinstance(definition, Mapping)
        }

    def image_template_root(self) -> Path:
        """Return image workflow templates installed beside this Comfy runtime."""

        return self._layout.image_template_root()

    def _wait_until_ready(self) -> None:
        """Wait for isolated Comfy startup or surface its complete log."""

        deadline = time.monotonic() + 90.0
        url = self._endpoint.system_stats_url()
        while time.monotonic() < deadline:
            process = self._process
            if process is not None and process.poll() is not None:
                break
            try:
                response = requests.get(url, timeout=1)
                if response.ok:
                    return
            except requests.RequestException:
                pass
            time.sleep(0.25)
        root = self._required_root()
        log_text = (root / "comfy.log").read_text(
            encoding="utf-8",
            errors="replace",
        )
        raise RuntimeError(f"Managed Comfy failed to start:\n{log_text}")

    def _required_root(self) -> Path:
        """Return the active temporary root or reject use before startup."""

        if self._root is None:
            raise RuntimeError("The managed Comfy harness has not started.")
        return self._root


def _available_port() -> int:
    """Reserve and return an unused loopback TCP port."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _empty_image(
    node_id: str, *, batch_size: int = 1, color: int = 0
) -> dict[str, object]:
    """Return one model-free core Comfy image source node."""

    return {
        "class_type": "EmptyImage",
        "inputs": {
            "width": 32,
            "height": 24,
            "batch_size": batch_size,
            "color": color,
        },
        "_meta": {"title": f"Image {node_id}"},
    }


def run_real_comfy_harness(repository_root: Path) -> tuple[RealComfyFixtureResult, ...]:
    """Run deduplication, distinct-source, and batch fixtures against real Comfy."""

    with ManagedComfyDirectOutputHarness(repository_root) as harness:
        deduplicated_graph: dict[str, object] = {
            "image": _empty_image("image"),
            "save": {
                "class_type": "SaveImage",
                "inputs": {"images": ["image", 0], "filename_prefix": "authored"},
            },
            "preview": {
                "class_type": "PreviewImage",
                "inputs": {"images": ["image", 0]},
            },
        }
        distinct_graph: dict[str, object] = {
            "red": _empty_image("red", color=0xFF0000),
            "blue": _empty_image("blue", color=0x0000FF),
            "save-red": {
                "class_type": "SaveImage",
                "inputs": {"images": ["red", 0], "filename_prefix": "red"},
            },
            "save-blue": {
                "class_type": "SaveImage",
                "inputs": {"images": ["blue", 0], "filename_prefix": "blue"},
            },
        }
        batch_graph: dict[str, object] = {
            "batch": _empty_image("batch", batch_size=3, color=0x336699),
            "save-batch": {
                "class_type": "SaveImage",
                "inputs": {"images": ["batch", 0], "filename_prefix": "batch"},
            },
        }
        return (
            harness.run_fixture(
                name="deduplicated",
                graph=deduplicated_graph,
                expected_source_count=1,
                expected_image_count=1,
            ),
            harness.run_fixture(
                name="distinct",
                graph=distinct_graph,
                expected_source_count=2,
                expected_image_count=2,
            ),
            harness.run_fixture(
                name="batch",
                graph=batch_graph,
                expected_source_count=1,
                expected_image_count=3,
            ),
        )


if __name__ == "__main__":
    results = run_real_comfy_harness(Path(__file__).resolve().parents[1])
    for result in results:
        print(result)
