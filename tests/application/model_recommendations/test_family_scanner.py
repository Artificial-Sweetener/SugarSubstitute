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

"""Verify bounded, read-only existing-model family detection."""

from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import subprocess

import pytest

from substitute.application.model_recommendations import ExistingModelFamilyScanner
from substitute.domain.model_recommendations import (
    ModelFamilyEvidenceKind,
    ModelFamilyId,
    ModelFamilyScanStatus,
)


class _Cancellation:
    """Expose deterministic scanner cancellation state."""

    def __init__(self, cancelled: bool) -> None:
        """Store whether traversal should stop."""

        self._cancelled = cancelled

    @property
    def is_cancelled(self) -> bool:
        """Return the configured cancellation state."""

        return self._cancelled


def _write_safetensor(path: Path, header: dict[str, object]) -> None:
    """Write the minimum SafeTensor shape needed for header-only scanning."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(header).encode("utf-8")
    path.write_bytes(struct.pack("<Q", len(payload)) + payload)


def _sdxl_architecture_header() -> dict[str, object]:
    """Return tensor-shape evidence shared by SDXL, Pony, and Illustrious."""

    return {
        "model.diffusion_model.input_blocks.0.0.weight": {
            "dtype": "F16",
            "shape": [320, 4, 3, 3],
            "data_offsets": [0, 1],
        },
        "model.diffusion_model.label_emb.0.0.weight": {
            "dtype": "F16",
            "shape": [1280, 2816],
            "data_offsets": [1, 2],
        },
        "model.diffusion_model.input_blocks.4.1.transformer_blocks.0.attn2.to_k.weight": {
            "dtype": "F16",
            "shape": [640, 2048],
            "data_offsets": [2, 3],
        },
    }


def test_scan_detects_sdxl_and_anima_from_trusted_header_evidence(
    tmp_path: Path,
) -> None:
    """Mixed roots must report every confidently supported family."""

    _write_safetensor(
        tmp_path / "checkpoints" / "PORTRAIT.SAFETENSORS",
        {"__metadata__": {"modelspec.architecture": "SDXL 1.0"}},
    )
    _write_safetensor(
        tmp_path / "diffusion_models" / "anima.safetensors",
        {"model.diffusion_model.double_blocks.0.img_attn.qkv.weight": {}},
    )
    original = {path: path.read_bytes() for path in tmp_path.rglob("*.safetensors")}

    result = ExistingModelFamilyScanner().scan(tmp_path)

    assert result.status is ModelFamilyScanStatus.COMPLETED
    assert result.detected_families == {
        ModelFamilyId.SDXL,
        ModelFamilyId.ANIMA,
    }
    assert {item.evidence_kind for item in result.detected} == {
        ModelFamilyEvidenceKind.SAFETENSOR_METADATA,
        ModelFamilyEvidenceKind.TENSOR_SIGNATURE,
    }
    assert {path: path.read_bytes() for path in original} == original


def test_scan_treats_generic_sdxl_pony_and_illustrious_as_sdxl_compatible(
    tmp_path: Path,
) -> None:
    """Lineage must not prevent an SDXL-compatible checkpoint satisfying coverage."""

    for filename in (
        "generic.safetensors",
        "pony.safetensors",
        "illustrious.safetensors",
    ):
        _write_safetensor(
            tmp_path / "checkpoints" / filename,
            _sdxl_architecture_header(),
        )

    result = ExistingModelFamilyScanner().scan(tmp_path)

    assert result.status is ModelFamilyScanStatus.COMPLETED
    assert result.detected_families == {ModelFamilyId.SDXL}
    assert len(result.detected) == 3
    assert {item.evidence_kind for item in result.detected} == {
        ModelFamilyEvidenceKind.TENSOR_SIGNATURE
    }


def test_scan_reports_unknown_and_unreadable_without_filename_guessing(
    tmp_path: Path,
) -> None:
    """Names and folders alone must never become confident family evidence."""

    _write_safetensor(tmp_path / "anima" / "anima-sdxl.safetensors", {"weights": {}})
    (tmp_path / "broken.safetensors").write_bytes(b"not a header")

    result = ExistingModelFamilyScanner().scan(tmp_path)

    assert result.confidently_empty
    assert result.unknown_count == 1
    assert result.unreadable_count == 1


def test_scan_distinguishes_missing_root_limit_and_cancellation(tmp_path: Path) -> None:
    """Unreliable scans must not be projected as confidently empty."""

    missing = ExistingModelFamilyScanner().scan(tmp_path / "missing")
    assert missing.status is ModelFamilyScanStatus.FAILED
    assert not missing.confidently_empty

    _write_safetensor(tmp_path / "one.safetensors", {"weights": {}})
    _write_safetensor(tmp_path / "two.safetensors", {"weights": {}})
    limited = ExistingModelFamilyScanner(maximum_files=1).scan(tmp_path)
    assert limited.status is ModelFamilyScanStatus.INCOMPLETE
    assert limited.inspected_count == 1
    assert not limited.confidently_empty

    cancelled = ExistingModelFamilyScanner().scan(
        tmp_path,
        cancellation=_Cancellation(True),
    )
    assert cancelled.status is ModelFamilyScanStatus.CANCELLED
    assert cancelled.inspected_count == 0


def test_scan_handles_deep_unicode_and_case_variant_paths(tmp_path: Path) -> None:
    """Portable long and Unicode paths remain normal read-only inputs."""

    nested = tmp_path.joinpath(*(["模型-folder"] * 12))
    _write_safetensor(
        nested / "MODEL.SAFETENSORS",
        {"__metadata__": {"base_model": "stable diffusion xl"}},
    )

    result = ExistingModelFamilyScanner().scan(tmp_path)

    assert result.status is ModelFamilyScanStatus.COMPLETED
    assert result.detected_families == {ModelFamilyId.SDXL}


def test_scan_stops_at_deterministic_time_limit(tmp_path: Path) -> None:
    """Treat a bounded-time exit as incomplete instead of confidently empty."""

    _write_safetensor(tmp_path / "unknown.safetensors", {"weights": {}})
    clock_values = iter((0.0, 2.0))

    result = ExistingModelFamilyScanner(
        timeout_seconds=1.0,
        monotonic=lambda: next(clock_values),
    ).scan(tmp_path)

    assert result.status is ModelFamilyScanStatus.INCOMPLETE
    assert result.inspected_count == 0
    assert not result.confidently_empty


def test_scan_does_not_follow_directory_symlinks(tmp_path: Path) -> None:
    """Never traverse a linked tree outside the explicitly selected root."""

    external = tmp_path.parent / f"{tmp_path.name}-external"
    _write_safetensor(
        external / "linked.safetensors",
        {"__metadata__": {"base_model": "SDXL 1.0"}},
    )
    link = tmp_path / "linked-models"
    try:
        os.symlink(external, link, target_is_directory=True)
    except OSError as error:
        if os.name != "nt":
            pytest.fail(f"Host does not permit the required symlink fixture: {error}")
        junction_result = subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(link), str(external)],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if junction_result.returncode != 0:
            pytest.fail(
                f"Could not create a Windows junction fixture: {junction_result.stderr}"
            )

    result = ExistingModelFamilyScanner().scan(tmp_path)

    assert result.status is ModelFamilyScanStatus.COMPLETED
    assert result.inspected_count == 0
    assert result.detected_families == frozenset()
