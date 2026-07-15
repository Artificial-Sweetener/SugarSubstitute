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

"""Resolve missing recipe models by requesting verified backend downloads."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace
import time
from typing import cast

from substitute.application.civitai import normalize_base_model_bucket
from substitute.application.model_metadata.ports import BackendModelDownloadGateway
from substitute.application.recipes.inline_lora_parser import inline_lora_spans
from substitute.application.recipes.lora_prompt_names import (
    normalized_prompt_lora_name,
    prompt_lora_name_for_backend_value,
)
from substitute.application.recipes.model_load_resolution import (
    RecipeModelDownloadCandidate,
    RecipeModelResolutionRequired,
    RecipeModelResolutionSummary,
    RecipeModelUnresolvedReference,
    ResolvedRecipeModelScript,
)
from substitute.domain.model_metadata import (
    BackendModelDownloadJob,
    BackendModelDownloadResult,
    ModelDownloadStatus,
)
from substitute.domain.recipes import SugarBufferMap
from substitute.domain.workflow.override_keys import canonicalize_global_override_key
from substitute.domain.civitai import DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN


class RecipeModelDownloadResolutionError(ValueError):
    """Raised when missing recipe models cannot be downloaded and verified."""


@dataclass(frozen=True, slots=True)
class RecipeModelDownloadResolutionService:
    """Coordinate backend-verified downloads for unresolved recipe model references."""

    backend: BackendModelDownloadGateway
    api_key_provider: Callable[[], str | None]
    downloads_enabled: Callable[[], bool]
    download_path_pattern_provider: Callable[[], str] = lambda: (
        DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN
    )
    model_downloaded: (
        Callable[[BackendModelDownloadResult, RecipeModelDownloadCandidate], None]
        | None
    ) = None
    sleep: Callable[[float], None] = time.sleep
    poll_interval_seconds: float = 0.5
    poll_timeout_seconds: float = 600.0

    def download_and_resolve(
        self,
        required: RecipeModelResolutionRequired,
        *,
        api_key_override: str | None = None,
        progress_callback: Callable[[BackendModelDownloadJob], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ResolvedRecipeModelScript:
        """Download every unresolved model and return a rewritten parsed script."""

        if not self.downloads_enabled():
            raise RecipeModelDownloadResolutionError("CivitAI downloads are disabled.")
        buffers = cast(
            OrderedDict[str, object], deepcopy(required.partial_script.buffers)
        )
        global_overrides = deepcopy(required.partial_script.global_overrides)
        downloaded_values: dict[_DownloadCandidateKey, str] = {}
        for reference in required.references:
            candidate_key = _candidate_key(reference)
            value = downloaded_values.get(candidate_key)
            if value is None:
                value = self._download_reference(
                    reference,
                    api_key_override=api_key_override,
                    progress_callback=progress_callback,
                    should_cancel=should_cancel,
                )
                downloaded_values[candidate_key] = value
            if _rewrite_prompt_lora_reference(
                buffers,
                reference=reference,
                value=value,
            ):
                continue
            _set_model_value(
                buffers,
                alias=reference.alias,
                node_name=reference.node_name,
                input_key=reference.input_key,
                value=value,
            )
            _set_global_override_value(
                global_overrides,
                input_key=reference.input_key,
                value=value,
            )
        return ResolvedRecipeModelScript(
            parsed_script=replace(
                required.partial_script,
                buffers=cast(SugarBufferMap, buffers),
                global_overrides=global_overrides,
            ),
            summary=RecipeModelResolutionSummary(
                literal_matches=required.summary.literal_matches,
                hash_matches=required.summary.hash_matches + len(required.references),
                unresolved_hashes=0,
            ),
        )

    def _download_reference(
        self,
        reference: RecipeModelUnresolvedReference,
        *,
        api_key_override: str | None,
        progress_callback: Callable[[BackendModelDownloadJob], None] | None,
        should_cancel: Callable[[], bool] | None,
    ) -> str:
        """Download one unresolved recipe model and return its backend value."""

        candidate = reference.candidate
        if candidate is None:
            raise RecipeModelDownloadResolutionError(
                f"No verified CivitAI file is available for {reference.sha256[:12]}."
            )
        job = self.backend.start_civitai_model_download(
            kind=candidate.kind,
            sha256=candidate.sha256,
            download_url=candidate.download_url,
            file_name=candidate.name,
            file_type=candidate.file_type,
            metadata_format=candidate.metadata_format,
            pickle_scan_result=candidate.pickle_scan_result,
            virus_scan_result=candidate.virus_scan_result,
            download_path_pattern=self.download_path_pattern_provider(),
            download_path_tokens=_download_path_tokens(candidate),
            api_key=(
                api_key_override
                if api_key_override is not None
                else self.api_key_provider()
            ),
        )
        if job is None:
            raise RecipeModelDownloadResolutionError(
                "Backend download route is unavailable."
            )
        _emit_progress(progress_callback, job)
        deadline = time.monotonic() + self.poll_timeout_seconds
        current = job
        while time.monotonic() < deadline:
            if should_cancel is not None and should_cancel():
                cancelled = self.backend.cancel_model_download_job(current.job_id)
                if cancelled is not None:
                    _emit_progress(progress_callback, cancelled)
                raise RecipeModelDownloadResolutionError("Model download cancelled.")
            if current.status is ModelDownloadStatus.COMPLETE:
                if current.result is None:
                    raise RecipeModelDownloadResolutionError(
                        "Backend download completed without a model result."
                    )
                if self.model_downloaded is not None:
                    self.model_downloaded(current.result, candidate)
                return current.result.value
            if current.status is ModelDownloadStatus.FAILED:
                raise RecipeModelDownloadResolutionError(
                    current.error or "Backend download failed."
                )
            if current.status is ModelDownloadStatus.CANCELLED:
                raise RecipeModelDownloadResolutionError(
                    current.error or "Model download cancelled."
                )
            self.sleep(self.poll_interval_seconds)
            polled = self.backend.get_model_download_job(current.job_id)
            if polled is None:
                raise RecipeModelDownloadResolutionError(
                    "Backend download job disappeared before completion."
                )
            current = polled
            _emit_progress(progress_callback, current)
        raise RecipeModelDownloadResolutionError("Backend download timed out.")


def _set_model_value(
    buffers: OrderedDict[str, object],
    *,
    alias: str,
    node_name: str,
    input_key: str,
    value: str,
) -> None:
    """Rewrite one parsed model picker input value."""

    alias_buffer = cast(dict[str, object], buffers[alias])
    nodes = cast(dict[str, object], alias_buffer["nodes"])
    node = cast(dict[str, object], nodes[node_name])
    inputs = cast(dict[str, object], node["inputs"])
    inputs[input_key] = value


def _rewrite_prompt_lora_reference(
    buffers: OrderedDict[str, object],
    *,
    reference: RecipeModelUnresolvedReference,
    value: str,
) -> bool:
    """Rewrite an inline prompt LoRA token for one downloaded reference."""

    if reference.kind != "loras":
        return False
    inputs = _inputs_for_reference(buffers, reference)
    current_value = inputs.get(reference.input_key)
    if not isinstance(current_value, str) or "<lora:" not in current_value.casefold():
        return False
    target_name = normalized_prompt_lora_name(reference.value)
    replacement_name = prompt_lora_name_for_backend_value(value)
    rewritten = current_value
    changed = False
    for lora_span in sorted(
        inline_lora_spans(current_value),
        key=lambda span: span.name_start,
        reverse=True,
    ):
        if normalized_prompt_lora_name(lora_span.prompt_name) != target_name:
            continue
        rewritten = (
            rewritten[: lora_span.name_start]
            + replacement_name
            + rewritten[lora_span.name_end :]
        )
        changed = True
    if not changed:
        return False
    inputs[reference.input_key] = rewritten
    return True


def _inputs_for_reference(
    buffers: OrderedDict[str, object],
    reference: RecipeModelUnresolvedReference,
) -> dict[str, object]:
    """Return the mutable input mapping for one unresolved recipe reference."""

    alias_buffer = cast(dict[str, object], buffers[reference.alias])
    nodes = cast(dict[str, object], alias_buffer["nodes"])
    node = cast(dict[str, object], nodes[reference.node_name])
    return cast(dict[str, object], node["inputs"])


def _set_global_override_value(
    global_overrides: dict[str, dict[str, object]],
    *,
    input_key: str,
    value: str,
) -> None:
    """Rewrite a matching global override so it cannot restore the missing model."""

    override_key = canonicalize_global_override_key(input_key)
    override = global_overrides.get(override_key)
    if not isinstance(override, dict) or "value" not in override:
        return
    override["value"] = value


def _emit_progress(
    callback: Callable[[BackendModelDownloadJob], None] | None,
    job: BackendModelDownloadJob,
) -> None:
    """Emit one backend download job update when the caller requested progress."""

    if callback is not None:
        callback(job)


def _download_path_tokens(
    candidate: RecipeModelDownloadCandidate,
) -> dict[str, str]:
    """Return CivitAI download path token values for one candidate."""

    base_model = (
        normalize_base_model_bucket(candidate.base_model)
        or normalize_base_model_bucket(candidate.model_name)
        or "Unsorted"
    )
    file_name = candidate.name.strip() or "model.safetensors"
    return {
        "baseModel": base_model,
        "modelName": candidate.model_name.strip() or "Unsorted",
        "versionName": candidate.version_name.strip() or "Version",
        "creator": (candidate.creator or "").strip() or "Unknown Creator",
        "fileName": file_name,
    }


@dataclass(frozen=True, slots=True)
class _DownloadCandidateKey:
    """Identify one unique CivitAI download candidate within a recipe load."""

    kind: str
    sha256: str
    download_url: str
    file_name: str


def _candidate_key(reference: RecipeModelUnresolvedReference) -> _DownloadCandidateKey:
    """Return the de-duplication key for one unresolved reference."""

    candidate = reference.candidate
    if candidate is None:
        return _DownloadCandidateKey(
            kind=reference.kind,
            sha256=reference.sha256,
            download_url="",
            file_name="",
        )
    return _DownloadCandidateKey(
        kind=candidate.kind,
        sha256=candidate.sha256,
        download_url=candidate.download_url,
        file_name=candidate.name,
    )


__all__ = [
    "RecipeModelDownloadResolutionError",
    "RecipeModelDownloadResolutionService",
]
