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

"""Tests for persisted managed Comfy process metadata ownership records."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.infrastructure.comfy.managed_process_metadata import (
    ManagedProcessMetadata,
)
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)


def test_managed_process_registry_round_trips_metadata(tmp_path: Path) -> None:
    """Registry save and load should preserve the managed ownership record."""

    registry = ManagedProcessRegistry(tmp_path)
    metadata = ManagedProcessMetadata(
        pid=42,
        host="127.0.0.1",
        port=8188,
        workspace_path=tmp_path / "comfyui",
        parent_pid=7,
        selected_install_target="windows_nvidia",
        selected_backend_policy="cuda_cu130",
        containment_mode="windows_job_object",
        owner_pid=99,
        job_name="substitute-job",
    )

    registry.save(metadata)

    assert registry.load() == metadata


def test_managed_process_registry_clears_only_matching_pid(tmp_path: Path) -> None:
    """Registry clear-if-match should not erase a newer record accidentally."""

    registry = ManagedProcessRegistry(tmp_path)
    metadata = ManagedProcessMetadata(
        pid=42,
        host="127.0.0.1",
        port=8188,
        workspace_path=tmp_path / "comfyui",
    )
    registry.save(metadata)

    registry.clear_if_pid_matches(99)

    assert registry.load() == metadata


def test_managed_process_registry_round_trips_posix_containment_metadata(
    tmp_path: Path,
) -> None:
    """Registry save and load should preserve POSIX guardian ownership fields."""

    registry = ManagedProcessRegistry(tmp_path)
    metadata = ManagedProcessMetadata(
        pid=84,
        host="127.0.0.1",
        port=8191,
        workspace_path=tmp_path / "comfyui",
        containment_mode="posix_guardian",
        owner_pid=314,
        process_group_id=2718,
        guardian_pipe_token="guardian-pipe",
    )

    registry.save(metadata)

    assert registry.load() == metadata


def test_managed_process_registry_loads_legacy_payload_without_containment_fields(
    tmp_path: Path,
) -> None:
    """Older registry payloads should deserialize into legacy containment mode."""

    payload = {
        "pid": 42,
        "host": "127.0.0.1",
        "port": 8188,
        "workspace_path": str(tmp_path / "comfyui"),
        "parent_pid": 7,
        "last_launched_at": "2026-03-24T00:00:00+00:00",
    }
    (tmp_path / "managed_comfy_process.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    metadata = ManagedProcessRegistry(tmp_path).load()

    assert metadata is not None
    assert metadata.containment_mode == "legacy_uncontained"
    assert metadata.owner_pid is None
    assert metadata.process_group_id is None


def test_registry_normalizes_legacy_linux_guardian_to_posix_owner(
    tmp_path: Path,
) -> None:
    """Persisted Linux-specific ownership should migrate to the POSIX mode."""

    payload = {
        "pid": 42,
        "host": "127.0.0.1",
        "port": 8188,
        "workspace_path": str(tmp_path / "comfyui"),
        "containment_mode": "linux_guardian",
        "owner_pid": 7,
        "process_group_id": 42,
    }
    (tmp_path / "managed_comfy_process.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    metadata = ManagedProcessRegistry(tmp_path).load()

    assert metadata is not None
    assert metadata.containment_mode == "posix_guardian"
