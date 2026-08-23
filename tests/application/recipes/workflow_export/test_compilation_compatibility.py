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

"""Verify workflow payload compilation compatibility."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from tests.application.recipes.workflow_export.support import build_service


def test_compile_workflow_payload_accepts_missing_output_directory(
    tmp_path: Path,
) -> None:
    """Avoid requiring the compiler boundary to create output directories."""
    service, _repository, compiler = build_service({"1": {"class_type": "KSampler"}})
    missing_output_dir = tmp_path / "missing-output-dir"

    workflow_payload = service.compile_workflow_payload(
        sugar_script_text="use Cube as txt",
        output_dir=missing_output_dir,
    )

    assert workflow_payload
    assert compiler.calls == [("use Cube as txt", missing_output_dir)]
    assert not missing_output_dir.exists()


def test_compile_workflow_payload_preserves_empty_latent_sampler_denoise() -> None:
    """Preserve sampler denoise for an empty latent source."""
    workflow_payload: dict[str, object] = {
        "latent": {"class_type": "EmptyLatentImage", "inputs": {}},
        "sampler": {
            "class_type": "CustomSamplerLike",
            "inputs": {"latent_image": ["latent", 0], "denoise": 0.25},
        },
    }
    service, _repository, _compiler = build_service(workflow_payload)

    payload = service.compile_workflow_payload(
        sugar_script_text="use Cube as A",
        output_dir=Path("projects"),
    )

    sampler = cast(dict[str, Any], payload["sampler"])
    assert sampler["inputs"]["denoise"] == 0.25


def test_compile_workflow_payload_preserves_wrapped_prompt_denoise() -> None:
    """Preserve nested denoise when the compiler returns a prompt wrapper."""
    workflow_payload: dict[str, object] = {
        "prompt": {
            "latent": {"class_type": "EmptyLatentImage", "inputs": {}},
            "sampler": {
                "class_type": "CustomSamplerLike",
                "inputs": {"latent_image": ["latent", 0], "denoise": 0.25},
            },
        },
        "client_id": "substitute",
    }
    service, _repository, _compiler = build_service(workflow_payload)

    payload = service.compile_workflow_payload(
        sugar_script_text="use Cube as A",
        output_dir=Path("projects"),
    )

    prompt = cast(dict[str, Any], payload["prompt"])
    sampler = cast(dict[str, Any], prompt["sampler"])
    assert sampler["inputs"]["denoise"] == 0.25


def test_compile_workflow_payload_preserves_encoded_latent_sampler_denoise() -> None:
    """Preserve denoise when sampler latents come from an encoder."""
    workflow_payload: dict[str, object] = {
        "encode": {"class_type": "VAEEncode", "inputs": {}},
        "sampler": {
            "class_type": "CustomSamplerLike",
            "inputs": {"latent_image": ["encode", 0], "denoise": 0.25},
        },
    }
    service, _repository, _compiler = build_service(workflow_payload)

    payload = service.compile_workflow_payload(
        sugar_script_text="use Cube as A",
        output_dir=Path("projects"),
    )

    sampler = cast(dict[str, Any], payload["sampler"])
    assert sampler["inputs"]["denoise"] == 0.25
