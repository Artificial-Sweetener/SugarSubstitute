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

"""Tests for backend-downloaded recipe model resolution."""

from __future__ import annotations

from collections import OrderedDict
from typing import cast

from substitute.application.recipes import (
    RecipeModelCivitaiState,
    RecipeModelDownloadCandidate,
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
from substitute.domain.recipes import ParsedSugarScript


def test_recipe_model_download_resolution_rewrites_downloaded_backend_value() -> None:
    """Verified backend downloads should rewrite unresolved model picker values."""

    backend = _DownloadBackend()
    downloaded: list[BackendModelDownloadResult] = []
    downloaded_candidates: list[RecipeModelDownloadCandidate] = []

    def record_download(
        result: BackendModelDownloadResult,
        candidate: RecipeModelDownloadCandidate,
    ) -> None:
        """Record the callback payload."""

        downloaded.append(result)
        downloaded_candidates.append(candidate)

    service = RecipeModelDownloadResolutionService(
        backend=backend,
        api_key_provider=lambda: "secret",
        downloads_enabled=lambda: True,
        model_downloaded=record_download,
        sleep=lambda _seconds: None,
    )

    resolved = service.download_and_resolve(_required())

    assert _checkpoint_value(resolved.parsed_script) == "Downloaded/model.safetensors"
    assert resolved.summary.hash_matches == 1
    assert resolved.summary.unresolved_hashes == 0
    assert backend.started_api_key == "secret"
    assert backend.started_download_path_pattern == "{base_model}\\{file_name}"
    assert backend.started_download_path_tokens == {
        "baseModel": "SDXL",
        "modelName": "Model",
        "versionName": "v1",
        "creator": "creator",
        "fileName": "model.safetensors",
    }
    assert downloaded[0].value == "Downloaded/model.safetensors"
    assert downloaded_candidates[0].model_name == "Model"


def test_recipe_model_download_resolution_rewrites_matching_global_override() -> None:
    """Downloaded models should not be overwritten by loaded global overrides."""

    backend = _DownloadBackend()
    service = RecipeModelDownloadResolutionService(
        backend=backend,
        api_key_provider=lambda: None,
        downloads_enabled=lambda: True,
        sleep=lambda _seconds: None,
    )
    required = _required()
    required.partial_script.global_overrides["ckpt_name"] = {
        "value": "missing.safetensors",
        "mode": "global",
    }

    resolved = service.download_and_resolve(required)

    override = resolved.parsed_script.global_overrides["ckpt_name"]
    assert isinstance(override, dict)
    assert override["value"] == "Downloaded/model.safetensors"


def test_recipe_model_download_resolution_rewrites_inline_prompt_lora() -> None:
    """Downloaded inline LoRAs should rewrite token names without changing weights."""

    backend = _DownloadBackend()
    service = RecipeModelDownloadResolutionService(
        backend=backend,
        api_key_provider=lambda: None,
        downloads_enabled=lambda: True,
        sleep=lambda _seconds: None,
    )

    resolved = service.download_and_resolve(_required_inline_lora())

    assert _prompt_value(resolved.parsed_script) == (
        "portrait <lora:Downloaded/model:0.80:1.00>, <lora:Downloaded/model:1.00>"
    )
    assert resolved.summary.hash_matches == 1
    assert resolved.summary.unresolved_hashes == 0


def test_recipe_model_download_resolution_deduplicates_same_candidate() -> None:
    """Duplicate missing references should share one backend download job."""

    backend = _DownloadBackend()
    service = RecipeModelDownloadResolutionService(
        backend=backend,
        api_key_provider=lambda: None,
        downloads_enabled=lambda: True,
        sleep=lambda _seconds: None,
    )

    resolved = service.download_and_resolve(_required_with_duplicate_reference())

    assert backend.start_count == 1
    assert _checkpoint_value(resolved.parsed_script) == "Downloaded/model.safetensors"
    assert _second_checkpoint_value(resolved.parsed_script) == (
        "Downloaded/model.safetensors"
    )


def test_recipe_model_download_resolution_prefers_one_shot_api_key() -> None:
    """Resolver wizard one-shot keys should override persisted credential lookup."""

    backend = _DownloadBackend()
    service = RecipeModelDownloadResolutionService(
        backend=backend,
        api_key_provider=lambda: "stored-secret",
        downloads_enabled=lambda: True,
        sleep=lambda _seconds: None,
    )

    service.download_and_resolve(_required(), api_key_override="typed-secret")

    assert backend.started_api_key == "typed-secret"


class _DownloadBackend:
    """Fake backend model download gateway."""

    def __init__(self) -> None:
        """Initialize fake backend state."""

        self.started_api_key: str | None = None
        self.started_download_path_pattern: str | None = None
        self.started_download_path_tokens: dict[str, str] | None = None
        self.start_count = 0
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
        download_path_tokens: object,
        api_key: str | None,
    ) -> BackendModelDownloadJob | None:
        """Return a queued download job."""

        assert kind in {"checkpoints", "loras"}
        assert sha256 == "A" * 64
        assert download_url == "https://civitai.com/api/download/models/2"
        assert file_name == "model.safetensors"
        assert file_type == "Model"
        assert metadata_format == "SafeTensor"
        assert pickle_scan_result == "Success"
        assert virus_scan_result == "Success"
        assert isinstance(download_path_tokens, dict)
        self.start_count += 1
        self.started_api_key = api_key
        self.started_download_path_pattern = download_path_pattern
        self.started_download_path_tokens = cast(dict[str, str], download_path_tokens)
        return BackendModelDownloadJob(
            job_id="download-1",
            status=ModelDownloadStatus.QUEUED,
            kind=kind,
            sha256=sha256,
            value=None,
            result=None,
            error=None,
        )

    def get_model_download_job(self, job_id: str) -> BackendModelDownloadJob | None:
        """Return a completed download job."""

        assert job_id == "download-1"
        result = BackendModelDownloadResult(
            kind="checkpoints",
            value="Downloaded/model.safetensors",
            display_name="model",
            source=BackendModelSource(
                root_id="checkpoints:0",
                relative_path="Downloaded/model.safetensors",
            ),
            sha256="A" * 64,
            file=BackendModelFile(
                extension=".safetensors",
                size_bytes=10,
                modified_at="2026-05-21T00:00:00Z",
                created_at=None,
            ),
        )
        return BackendModelDownloadJob(
            job_id=job_id,
            status=ModelDownloadStatus.COMPLETE,
            kind="checkpoints",
            sha256="A" * 64,
            value=result.value,
            result=result,
            error=None,
        )

    def cancel_model_download_job(self, job_id: str) -> BackendModelDownloadJob | None:
        """Record cancellation and return a cancelled download job."""

        self.cancelled_job_id = job_id
        return BackendModelDownloadJob(
            job_id=job_id,
            status=ModelDownloadStatus.CANCELLED,
            kind="checkpoints",
            sha256="A" * 64,
            value=None,
            result=None,
            error="Model download cancelled.",
        )


def _required() -> RecipeModelResolutionRequired:
    """Build one unresolved recipe model exception."""

    parsed = ParsedSugarScript(
        buffers=OrderedDict(
            {
                "A": OrderedDict(
                    {
                        "cube_id": "cube",
                        "nodes": {
                            "checkpoint": {
                                "inputs": {"ckpt_name": "missing.safetensors"},
                            }
                        },
                    }
                )
            }
        ),
        global_overrides={},
        global_override_selections={},
        field_control_states_by_alias={},
        override_control_states={},
        model_hashes_by_field={("A", "checkpoint", "ckpt_name"): "A" * 64},
        prompt_lora_hashes_by_field={},
        project_name=None,
    )
    return RecipeModelResolutionRequired(
        references=(
            RecipeModelUnresolvedReference(
                alias="A",
                node_name="checkpoint",
                input_key="ckpt_name",
                kind="checkpoints",
                value="missing.safetensors",
                sha256="A" * 64,
                civitai_state=RecipeModelCivitaiState.FOUND,
                candidate=RecipeModelDownloadCandidate(
                    kind="checkpoints",
                    sha256="A" * 64,
                    name="model.safetensors",
                    download_url="https://civitai.com/api/download/models/2",
                    size_kb=1.0,
                    model_id=1,
                    model_version_id=2,
                    model_name="Model",
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
            ),
        ),
        partial_script=parsed,
        summary=RecipeModelResolutionSummary(unresolved_hashes=1),
    )


def _required_with_duplicate_reference() -> RecipeModelResolutionRequired:
    """Build unresolved model state with the same candidate used twice."""

    required = _required()
    buffer = required.partial_script.buffers["A"]
    nodes = cast(dict[str, object], buffer["nodes"])
    nodes["checkpoint_b"] = {"inputs": {"ckpt_name": "also-missing.safetensors"}}
    first = required.references[0]
    second = RecipeModelUnresolvedReference(
        alias="A",
        node_name="checkpoint_b",
        input_key="ckpt_name",
        kind=first.kind,
        value="also-missing.safetensors",
        sha256=first.sha256,
        civitai_state=first.civitai_state,
        candidate=first.candidate,
    )
    return RecipeModelResolutionRequired(
        references=(first, second),
        partial_script=required.partial_script,
        summary=RecipeModelResolutionSummary(unresolved_hashes=2),
    )


def _required_inline_lora() -> RecipeModelResolutionRequired:
    """Build unresolved inline LoRA state for download resolution."""

    parsed = ParsedSugarScript(
        buffers=OrderedDict(
            {
                "A": OrderedDict(
                    {
                        "cube_id": "cube",
                        "nodes": {
                            "prompt": {
                                "inputs": {
                                    "text": (
                                        "portrait <lora:missing:0.80:1.00>, "
                                        "<lora:missing.safetensors:1.00>"
                                    )
                                },
                            }
                        },
                    }
                )
            }
        ),
        global_overrides={},
        global_override_selections={},
        field_control_states_by_alias={},
        override_control_states={},
        model_hashes_by_field={},
        prompt_lora_hashes_by_field={("A", "prompt", "text"): {"missing": "A" * 64}},
        project_name=None,
    )
    candidate = _required().references[0].candidate
    assert candidate is not None
    lora_candidate = RecipeModelDownloadCandidate(
        kind="loras",
        sha256=candidate.sha256,
        name=candidate.name,
        download_url=candidate.download_url,
        size_kb=candidate.size_kb,
        model_id=candidate.model_id,
        model_version_id=candidate.model_version_id,
        model_name=candidate.model_name,
        version_name=candidate.version_name,
        base_model=candidate.base_model,
        creator=candidate.creator,
        file_id=candidate.file_id,
        file_type=candidate.file_type,
        metadata_format=candidate.metadata_format,
        pickle_scan_result=candidate.pickle_scan_result,
        virus_scan_result=candidate.virus_scan_result,
        model_page_url=candidate.model_page_url,
        thumbnail_url=candidate.thumbnail_url,
    )
    return RecipeModelResolutionRequired(
        references=(
            RecipeModelUnresolvedReference(
                alias="A",
                node_name="prompt",
                input_key="text",
                kind="loras",
                value="missing",
                sha256="A" * 64,
                civitai_state=RecipeModelCivitaiState.FOUND,
                candidate=lora_candidate,
            ),
        ),
        partial_script=parsed,
        summary=RecipeModelResolutionSummary(unresolved_hashes=1),
    )


def _checkpoint_value(parsed_script: ParsedSugarScript) -> str:
    """Return the checkpoint input value from a parsed script."""

    buffer = cast(dict[str, object], parsed_script.buffers["A"])
    nodes = cast(dict[str, object], buffer["nodes"])
    checkpoint = cast(dict[str, object], nodes["checkpoint"])
    inputs = cast(dict[str, object], checkpoint["inputs"])
    value = inputs["ckpt_name"]
    assert isinstance(value, str)
    return value


def _prompt_value(parsed_script: ParsedSugarScript) -> str:
    """Return the prompt input value from a parsed script."""

    buffer = cast(dict[str, object], parsed_script.buffers["A"])
    nodes = cast(dict[str, object], buffer["nodes"])
    prompt = cast(dict[str, object], nodes["prompt"])
    inputs = cast(dict[str, object], prompt["inputs"])
    value = inputs["text"]
    assert isinstance(value, str)
    return value


def _second_checkpoint_value(parsed_script: ParsedSugarScript) -> str:
    """Return the second checkpoint input value from a parsed script."""

    buffer = cast(dict[str, object], parsed_script.buffers["A"])
    nodes = cast(dict[str, object], buffer["nodes"])
    checkpoint = cast(dict[str, object], nodes["checkpoint_b"])
    inputs = cast(dict[str, object], checkpoint["inputs"])
    value = inputs["ckpt_name"]
    assert isinstance(value, str)
    return value
