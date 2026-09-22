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

"""Verify multi-model acquisition, cancellation, and credential recovery."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from typing import cast

import pytest

from substitute.application.recipes import (
    RecipeModelCivitaiState,
    RecipeModelDownloadCandidate,
    RecipeModelDownloadResolutionError,
    RecipeModelDownloadResolutionService,
    RecipeModelResolutionRequired,
    RecipeModelResolutionSummary,
    RecipeModelUnresolvedReference,
)
from substitute.domain.model_metadata import (
    BackendModelDownloadJob,
    BackendModelDownloadResult,
    BackendModelFile,
    BackendModelSource,
    ModelDownloadStatus,
)
from substitute.domain.recipes import ParsedSugarScript, SugarBufferMap


def test_distinct_models_complete_as_distinct_backend_jobs() -> None:
    """Download and rewrite every approved exact-hash model independently."""

    backend = _Backend()
    resolved = _service(backend).download_and_resolve(_required(two_models=True))

    assert backend.started_hashes == ["A" * 64, "B" * 64]
    assert _field_value(resolved.parsed_script, "A", "checkpoint", "ckpt_name") == (
        "Downloaded/checkpoint-model.safetensors"
    )
    assert _field_value(resolved.parsed_script, "B", "lora", "lora_name") == (
        "Downloaded/style-lora.safetensors"
    )
    assert resolved.summary.hash_matches == 2
    assert resolved.summary.unresolved_hashes == 0


def test_cancellation_cancels_the_active_backend_job() -> None:
    """Propagate user cancellation to BackEnd and keep the failure recoverable."""

    backend = _Backend()

    with pytest.raises(RecipeModelDownloadResolutionError, match="cancelled"):
        _service(backend).download_and_resolve(
            _required(),
            should_cancel=lambda: True,
        )

    assert backend.cancelled_job_id == "download-A"


def test_invalid_api_key_error_reaches_the_recovery_surface() -> None:
    """Preserve BackEnd's actionable CivitAI credential failure message."""

    backend = _Backend(failure="CivitAI API key was rejected.")

    with pytest.raises(
        RecipeModelDownloadResolutionError,
        match="CivitAI API key was rejected",
    ):
        _service(backend, api_key="invalid-key").download_and_resolve(_required())

    assert backend.started_api_keys == ["invalid-key"]


def _service(
    backend: _Backend,
    *,
    api_key: str | None = None,
) -> RecipeModelDownloadResolutionService:
    """Build a deterministic download service around the BackEnd fake."""

    return RecipeModelDownloadResolutionService(
        backend=backend,
        api_key_provider=lambda: api_key,
        downloads_enabled=lambda: True,
        sleep=lambda _seconds: None,
    )


def _required(*, two_models: bool = False) -> RecipeModelResolutionRequired:
    """Build one or two unresolved exact-hash model references."""

    buffers = cast(
        SugarBufferMap,
        OrderedDict(
            {
                "A": OrderedDict(
                    {
                        "cube_id": "cube-a",
                        "nodes": {
                            "checkpoint": {
                                "inputs": {
                                    "ckpt_name": "missing-checkpoint.safetensors"
                                }
                            }
                        },
                    }
                )
            }
        ),
    )
    references = [_reference("A", "checkpoint", "ckpt_name", "checkpoints", "A")]
    hashes = {("A", "checkpoint", "ckpt_name"): "A" * 64}
    if two_models:
        buffers["B"] = OrderedDict(
            {
                "cube_id": "cube-b",
                "nodes": {
                    "lora": {"inputs": {"lora_name": "missing-lora.safetensors"}}
                },
            }
        )
        references.append(_reference("B", "lora", "lora_name", "loras", "B"))
        hashes[("B", "lora", "lora_name")] = "B" * 64
    parsed = ParsedSugarScript(
        buffers=buffers,
        global_overrides={},
        global_override_selections={},
        field_control_states_by_alias={},
        override_control_states={},
        model_hashes_by_field=hashes,
        prompt_lora_hashes_by_field={},
        project_name=None,
    )
    return RecipeModelResolutionRequired(
        references=tuple(references),
        partial_script=parsed,
        summary=RecipeModelResolutionSummary(unresolved_hashes=len(references)),
    )


def _reference(
    alias: str,
    node_name: str,
    input_key: str,
    kind: str,
    marker: str,
) -> RecipeModelUnresolvedReference:
    """Build one safe exact-hash CivitAI candidate."""

    sha256 = marker * 64
    file_name = (
        "checkpoint-model.safetensors"
        if kind == "checkpoints"
        else "style-lora.safetensors"
    )
    return RecipeModelUnresolvedReference(
        alias=alias,
        node_name=node_name,
        input_key=input_key,
        kind=kind,
        value=f"missing-{marker}.safetensors",
        sha256=sha256,
        civitai_state=RecipeModelCivitaiState.FOUND,
        candidate=RecipeModelDownloadCandidate(
            kind=kind,
            sha256=sha256,
            name=file_name,
            download_url=f"https://civitai.com/api/download/models/{marker}",
            size_kb=1.0,
            model_id=1,
            model_version_id=2,
            model_name=file_name.removesuffix(".safetensors"),
            version_name="v1",
            base_model="SDXL 1.0",
            creator="creator",
            file_id=3,
            file_type="Model",
            metadata_format="SafeTensor",
            pickle_scan_result="Success",
            virus_scan_result="Success",
            model_page_url="https://civitai.com/models/1?modelVersionId=2",
        ),
    )


def _field_value(
    parsed: ParsedSugarScript,
    alias: str,
    node_name: str,
    input_key: str,
) -> str:
    """Return one rewritten model value."""

    buffer = cast(dict[str, object], parsed.buffers[alias])
    nodes = cast(dict[str, object], buffer["nodes"])
    node = cast(dict[str, object], nodes[node_name])
    inputs = cast(dict[str, object], node["inputs"])
    return cast(str, inputs[input_key])


class _Backend:
    """Complete, fail, or cancel deterministic BackEnd download jobs."""

    def __init__(self, *, failure: str | None = None) -> None:
        """Store optional provider failure behavior."""

        self._failure = failure
        self._jobs: dict[str, tuple[str, str, str]] = {}
        self.started_hashes: list[str] = []
        self.started_api_keys: list[str | None] = []
        self.cancelled_job_id: str | None = None

    def start_civitai_model_download(
        self,
        *,
        kind: str,
        sha256: str,
        download_url: str,
        file_name: str,
        file_type: str | None,
        metadata_format: str | None,
        pickle_scan_result: str | None,
        virus_scan_result: str | None,
        download_path_pattern: str,
        download_path_tokens: Mapping[str, str],
        api_key: str | None,
    ) -> BackendModelDownloadJob:
        """Create one queued job and retain its verification inputs."""

        _ = (
            download_url,
            file_type,
            metadata_format,
            pickle_scan_result,
            virus_scan_result,
            download_path_pattern,
            download_path_tokens,
        )
        self.started_hashes.append(sha256)
        self.started_api_keys.append(api_key)
        job_id = f"download-{sha256[0]}"
        self._jobs[job_id] = (kind, sha256, file_name)
        return self._job(job_id, ModelDownloadStatus.QUEUED)

    def get_model_download_job(self, job_id: str) -> BackendModelDownloadJob:
        """Return the configured terminal job state."""

        if self._failure is not None:
            return self._job(job_id, ModelDownloadStatus.FAILED, error=self._failure)
        kind, sha256, file_name = self._jobs[job_id]
        value = f"Downloaded/{file_name}"
        result = BackendModelDownloadResult(
            kind=kind,
            value=value,
            display_name=file_name.removesuffix(".safetensors"),
            source=BackendModelSource(
                root_id=f"{kind}:0",
                relative_path=value,
            ),
            sha256=sha256,
            file=BackendModelFile(
                extension=".safetensors",
                size_bytes=10,
                modified_at="2026-09-22T00:00:00Z",
                created_at=None,
            ),
        )
        return self._job(
            job_id,
            ModelDownloadStatus.COMPLETE,
            value=value,
            result=result,
        )

    def cancel_model_download_job(self, job_id: str) -> BackendModelDownloadJob:
        """Record cancellation and return a terminal cancelled job."""

        self.cancelled_job_id = job_id
        return self._job(
            job_id,
            ModelDownloadStatus.CANCELLED,
            error="Model download cancelled.",
        )

    def _job(
        self,
        job_id: str,
        status: ModelDownloadStatus,
        *,
        value: str | None = None,
        result: BackendModelDownloadResult | None = None,
        error: str | None = None,
    ) -> BackendModelDownloadJob:
        """Build one job from retained kind and hash identity."""

        kind, sha256, _file_name = self._jobs[job_id]
        return BackendModelDownloadJob(
            job_id=job_id,
            status=status,
            kind=kind,
            sha256=sha256,
            value=value,
            result=result,
            error=error,
        )
