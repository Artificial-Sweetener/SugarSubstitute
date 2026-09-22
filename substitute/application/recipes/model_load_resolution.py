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

"""Resolve recipe model references before workflow materialization."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from enum import Enum
import time
from typing import cast

from substitute.application.model_metadata.ports import (
    BackendModelHashLookupGateway,
    BackendModelMetadataGateway,
    CivitaiMetadataGateway,
)
from substitute.application.recipes.inline_lora_parser import inline_lora_spans
from substitute.application.recipes.lora_prompt_names import (
    backend_value_candidates_for_prompt_lora_name,
    normalized_prompt_lora_name,
    prompt_lora_name_for_backend_value,
)
from substitute.application.model_metadata import model_kind_for_field
from substitute.application.recipes.model_resolution_index import (
    LocalRecipeModel,
    RecipeModelResolutionIndex,
)
from substitute.domain.model_metadata import (
    BackendHashLookupMatch,
    BackendHashLookupStatus,
    CivitaiLookupStatus,
    CivitaiThumbnailPolicy,
    JobStatus,
)
from substitute.domain.recipes import ParsedSugarScript, SugarBufferMap
from substitute.domain.workflow.override_keys import canonicalize_global_override_key

from .model_download_candidate import (
    RecipeModelDownloadCandidate,
    candidate_from_civitai_version,
    civitai_download_access,
)


class RecipeModelCivitaiState(str, Enum):
    """Describe CivitAI missing-model lookup state for one recipe reference."""

    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    NOT_FOUND = "not-found"
    FOUND = "found"
    NO_SAFE_FILE = "no-safe-file"


@dataclass(frozen=True, slots=True)
class RecipeModelUnresolvedReference:
    """Describe one recipe model reference that needs user action."""

    alias: str
    node_name: str
    input_key: str
    kind: str
    value: str
    sha256: str
    civitai_state: RecipeModelCivitaiState
    civitai_status: CivitaiLookupStatus | None = None
    civitai_error: str | None = None
    candidate: RecipeModelDownloadCandidate | None = None


class RecipeModelResolutionRequired(ValueError):
    """Raised when a recipe references missing hashed models requiring user action."""

    def __init__(
        self,
        *,
        references: tuple[RecipeModelUnresolvedReference, ...],
        partial_script: ParsedSugarScript,
        summary: RecipeModelResolutionSummary,
    ) -> None:
        """Store the structured unresolved state used by the resolver wizard."""

        missing = ", ".join(
            f"{reference.alias}.{reference.node_name}.{reference.input_key} "
            f"({reference.sha256[:12]})"
            for reference in references
        )
        super().__init__(
            f"Recipe references model hashes that are not installed locally: {missing}"
        )
        self.references = references
        self.partial_script = partial_script
        self.summary = summary


@dataclass(frozen=True, slots=True)
class RecipeModelResolutionSummary:
    """Summarize pre-materialization model resolution results."""

    literal_matches: int = 0
    hash_matches: int = 0
    unresolved_hashes: int = 0


@dataclass(frozen=True, slots=True)
class ResolvedRecipeModelScript:
    """Carry a parsed script plus model resolution summary."""

    parsed_script: ParsedSugarScript
    summary: RecipeModelResolutionSummary


@dataclass(frozen=True, slots=True)
class _PromptLoraNameReplacement:
    """Describe one prompt LoRA token-name rewrite by source offsets."""

    start: int
    end: int
    value: str


@dataclass(frozen=True, slots=True)
class _PromptLoraResolutionResult:
    """Summarize inline prompt LoRA resolution mutations."""

    literal_matches: int
    hash_matches: int
    unresolved: tuple[RecipeModelUnresolvedReference, ...]


class RecipeModelLoadResolver:
    """Resolve literal and cached-hash model references before materialization."""

    def __init__(
        self,
        index: RecipeModelResolutionIndex,
        *,
        backend: BackendModelHashLookupGateway | None = None,
        fingerprint_jobs: BackendModelMetadataGateway | None = None,
        civitai: CivitaiMetadataGateway | None = None,
        civitai_missing_model_lookup_enabled: Callable[[], bool] | None = None,
        thumbnail_policy_provider: Callable[[], CivitaiThumbnailPolicy] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        fingerprint_poll_interval_seconds: float = 0.5,
        fingerprint_poll_timeout_seconds: float = 120.0,
    ) -> None:
        """Store the fast local model index."""

        self._index = index
        self._backend = backend
        self._fingerprint_jobs = fingerprint_jobs
        self._civitai = civitai
        self._civitai_missing_model_lookup_enabled = (
            civitai_missing_model_lookup_enabled
        )
        self._thumbnail_policy_provider = thumbnail_policy_provider
        self._sleep = sleep
        self._fingerprint_poll_interval_seconds = fingerprint_poll_interval_seconds
        self._fingerprint_poll_timeout_seconds = fingerprint_poll_timeout_seconds

    def resolve(self, parsed_script: ParsedSugarScript) -> ResolvedRecipeModelScript:
        """Return a parsed script with local same-hash model values rewritten."""

        buffers = cast(OrderedDict[str, object], deepcopy(parsed_script.buffers))
        global_overrides = deepcopy(parsed_script.global_overrides)
        literal_matches = 0
        hash_matches = 0
        unresolved: list[RecipeModelUnresolvedReference] = []
        for alias, node_name, input_key, kind, value in _model_fields(buffers):
            literal_model = self._index.find_literal(kind=kind, value=value)
            sha256 = parsed_script.model_hashes_by_field.get(
                (alias, node_name, input_key)
            )
            if sha256 is None or self._backend is None:
                if literal_model is not None:
                    literal_matches += 1
                    continue
            if sha256 is None:
                continue
            hash_model = self._authoritative_hash_model(kind=kind, sha256=sha256)
            if hash_model is None:
                unresolved.append(
                    self._unresolved_reference(
                        alias=alias,
                        node_name=node_name,
                        input_key=input_key,
                        kind=kind,
                        value=value,
                        sha256=sha256,
                    )
                )
                continue
            _set_model_value(
                buffers,
                alias=alias,
                node_name=node_name,
                input_key=input_key,
                value=hash_model.backend_value,
            )
            _set_global_override_value(
                global_overrides,
                input_key=input_key,
                value=hash_model.backend_value,
            )
            hash_matches += 1
        prompt_lora_result = self._resolve_inline_prompt_loras(
            parsed_script=parsed_script,
            buffers=buffers,
        )
        literal_matches += prompt_lora_result.literal_matches
        hash_matches += prompt_lora_result.hash_matches
        unresolved.extend(prompt_lora_result.unresolved)
        summary = RecipeModelResolutionSummary(
            literal_matches=literal_matches,
            hash_matches=hash_matches,
            unresolved_hashes=len(unresolved),
        )
        if unresolved:
            partial_script = replace(
                parsed_script,
                buffers=cast(SugarBufferMap, buffers),
                global_overrides=global_overrides,
            )
            raise RecipeModelResolutionRequired(
                references=tuple(unresolved),
                partial_script=partial_script,
                summary=summary,
            )
        return ResolvedRecipeModelScript(
            parsed_script=replace(
                parsed_script,
                buffers=cast(SugarBufferMap, buffers),
                global_overrides=global_overrides,
            ),
            summary=summary,
        )

    def _unresolved_reference(
        self,
        *,
        alias: str,
        node_name: str,
        input_key: str,
        kind: str,
        value: str,
        sha256: str,
    ) -> RecipeModelUnresolvedReference:
        """Build one unresolved reference with optional CivitAI by-hash state."""

        normalized_sha256 = sha256.upper()
        if not self._is_civitai_lookup_enabled():
            return RecipeModelUnresolvedReference(
                alias=alias,
                node_name=node_name,
                input_key=input_key,
                kind=kind,
                value=value,
                sha256=normalized_sha256,
                civitai_state=RecipeModelCivitaiState.DISABLED,
            )
        civitai = self._civitai
        if civitai is None:
            return RecipeModelUnresolvedReference(
                alias=alias,
                node_name=node_name,
                input_key=input_key,
                kind=kind,
                value=value,
                sha256=normalized_sha256,
                civitai_state=RecipeModelCivitaiState.UNAVAILABLE,
                civitai_status=CivitaiLookupStatus.UNAVAILABLE,
            )
        result = civitai.lookup_model_version_by_hash(normalized_sha256)
        if result.status is not CivitaiLookupStatus.FOUND or result.version is None:
            return RecipeModelUnresolvedReference(
                alias=alias,
                node_name=node_name,
                input_key=input_key,
                kind=kind,
                value=value,
                sha256=normalized_sha256,
                civitai_state=(
                    RecipeModelCivitaiState.NOT_FOUND
                    if result.status is CivitaiLookupStatus.NOT_FOUND
                    else RecipeModelCivitaiState.UNAVAILABLE
                ),
                civitai_status=result.status,
                civitai_error=result.error,
            )
        candidate = candidate_from_civitai_version(
            kind=kind,
            sha256=normalized_sha256,
            version=result.version,
            thumbnail_policy=self._thumbnail_policy(),
            download_access=civitai_download_access(
                civitai,
                result.version.model_version_id,
            ),
        )
        return RecipeModelUnresolvedReference(
            alias=alias,
            node_name=node_name,
            input_key=input_key,
            kind=kind,
            value=value,
            sha256=normalized_sha256,
            civitai_state=(
                RecipeModelCivitaiState.FOUND
                if candidate is not None
                else RecipeModelCivitaiState.NO_SAFE_FILE
            ),
            civitai_status=result.status,
            candidate=candidate,
        )

    def _is_civitai_lookup_enabled(self) -> bool:
        """Return whether missing-model CivitAI lookup may run."""

        enabled = self._civitai_missing_model_lookup_enabled
        return True if enabled is None else enabled()

    def _thumbnail_policy(self) -> CivitaiThumbnailPolicy:
        """Return the active CivitAI thumbnail policy for resolver previews."""

        provider = self._thumbnail_policy_provider
        return CivitaiThumbnailPolicy() if provider is None else provider()

    def _resolve_hash_from_backend(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> LocalRecipeModel | None:
        """Ask Substitute BackEnd for current local hash evidence."""

        backend = self._backend
        if backend is None:
            return None
        deadline = time.monotonic() + self._fingerprint_poll_timeout_seconds
        while time.monotonic() < deadline:
            result = backend.lookup_model_by_hash(kind=kind, sha256=sha256)
            if result is None:
                return None
            if result.status is BackendHashLookupStatus.COMPLETE:
                return (
                    _model_from_backend_match(result.matches[0], sha256)
                    if result.matches
                    else None
                )
            if result.status not in {
                BackendHashLookupStatus.HASHING_REQUIRED,
                BackendHashLookupStatus.HASHING_RUNNING,
            }:
                return None
            if result.job_id is None:
                return None
            if self._fingerprint_jobs is None:
                return None
            self._wait_for_backend_hash_job(result.job_id, deadline=deadline)
        return None

    def _wait_for_backend_hash_job(self, job_id: str, *, deadline: float) -> None:
        """Wait for a targeted backend fingerprint job to settle."""

        fingerprint_jobs = self._fingerprint_jobs
        if fingerprint_jobs is None:
            return
        while time.monotonic() < deadline:
            job = fingerprint_jobs.get_fingerprint_job(job_id)
            if job is None or job.status not in {JobStatus.QUEUED, JobStatus.RUNNING}:
                return
            self._sleep(self._fingerprint_poll_interval_seconds)

    def _resolve_inline_prompt_loras(
        self,
        *,
        parsed_script: ParsedSugarScript,
        buffers: OrderedDict[str, object],
    ) -> "_PromptLoraResolutionResult":
        """Resolve inline prompt LoRA tokens by literal value or adjacent hashes."""

        literal_matches = 0
        hash_matches = 0
        unresolved: list[RecipeModelUnresolvedReference] = []
        unresolved_keys: set[tuple[str, str, str, str]] = set()
        for alias, node_name, input_key, prompt_text in _prompt_lora_fields(buffers):
            raw_hashes = parsed_script.prompt_lora_hashes_by_field.get(
                (alias, node_name, input_key),
                {},
            )
            hashes_by_name = _prompt_lora_hashes_by_normalized_name(raw_hashes)
            replacements: list[_PromptLoraNameReplacement] = []
            for lora_span in inline_lora_spans(prompt_text):
                literal_model = _find_literal_prompt_lora(
                    self._index,
                    lora_span.prompt_name,
                )
                hash_entry = hashes_by_name.get(
                    normalized_prompt_lora_name(lora_span.prompt_name)
                )
                if hash_entry is None or self._backend is None:
                    if literal_model is not None:
                        literal_matches += 1
                        continue
                if hash_entry is None:
                    continue
                _, sha256 = hash_entry
                hash_model = self._authoritative_hash_model(
                    kind="loras",
                    sha256=sha256,
                )
                if hash_model is None:
                    unresolved_key = (alias, node_name, input_key, sha256)
                    if unresolved_key not in unresolved_keys:
                        unresolved_keys.add(unresolved_key)
                        unresolved.append(
                            self._unresolved_reference(
                                alias=alias,
                                node_name=node_name,
                                input_key=input_key,
                                kind="loras",
                                value=lora_span.prompt_name,
                                sha256=sha256,
                            )
                        )
                    continue
                replacements.append(
                    _PromptLoraNameReplacement(
                        start=lora_span.name_start,
                        end=lora_span.name_end,
                        value=prompt_lora_name_for_backend_value(
                            hash_model.backend_value
                        ),
                    )
                )
                hash_matches += 1
            if replacements:
                _set_model_value(
                    buffers,
                    alias=alias,
                    node_name=node_name,
                    input_key=input_key,
                    value=_replace_prompt_lora_names(prompt_text, replacements),
                )
        return _PromptLoraResolutionResult(
            literal_matches=literal_matches,
            hash_matches=hash_matches,
            unresolved=tuple(unresolved),
        )

    def _authoritative_hash_model(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> LocalRecipeModel | None:
        """Use BackEnd hash evidence when available, otherwise use cached evidence."""

        if self._backend is not None:
            return self._resolve_hash_from_backend(kind=kind, sha256=sha256)
        return self._index.find_hash(kind=kind, sha256=sha256)


def _model_fields(
    buffers: Mapping[str, object],
) -> tuple[tuple[str, str, str, str, str], ...]:
    """Return model-picker string fields from parsed recipe buffers."""

    fields: list[tuple[str, str, str, str, str]] = []
    for alias, buffer in buffers.items():
        if not isinstance(buffer, Mapping):
            continue
        nodes = buffer.get("nodes")
        if not isinstance(nodes, Mapping):
            continue
        for node_name, node_data in nodes.items():
            if not isinstance(node_data, Mapping):
                continue
            class_type = node_data.get("class_type")
            inputs = node_data.get("inputs")
            if not isinstance(inputs, Mapping):
                continue
            class_type_text = class_type if isinstance(class_type, str) else ""
            for input_key, value in inputs.items():
                if not isinstance(input_key, str) or not isinstance(value, str):
                    continue
                kind = model_kind_for_field(
                    class_type=class_type_text,
                    input_key=input_key,
                )
                if kind is not None:
                    fields.append((alias, str(node_name), input_key, kind, value))
    return tuple(fields)


def _prompt_lora_fields(
    buffers: Mapping[str, object],
) -> tuple[tuple[str, str, str, str], ...]:
    """Return parsed string fields that contain inline LoRA prompt syntax."""

    fields: list[tuple[str, str, str, str]] = []
    for alias, buffer in buffers.items():
        if not isinstance(buffer, Mapping):
            continue
        nodes = buffer.get("nodes")
        if not isinstance(nodes, Mapping):
            continue
        for node_name, node_data in nodes.items():
            if not isinstance(node_data, Mapping):
                continue
            inputs = node_data.get("inputs")
            if not isinstance(inputs, Mapping):
                continue
            for input_key, value in inputs.items():
                if not isinstance(input_key, str) or not isinstance(value, str):
                    continue
                if "<lora:" in value.casefold():
                    fields.append((alias, str(node_name), input_key, value))
    return tuple(fields)


def _prompt_lora_hashes_by_normalized_name(
    raw_hashes: Mapping[str, str],
) -> OrderedDict[str, tuple[str, str]]:
    """Return inline LoRA hashes keyed by normalized prompt name."""

    normalized: OrderedDict[str, tuple[str, str]] = OrderedDict()
    for prompt_name, sha256 in raw_hashes.items():
        normalized.setdefault(
            normalized_prompt_lora_name(prompt_name),
            (prompt_name, sha256.upper()),
        )
    return normalized


def _find_literal_prompt_lora(
    index: RecipeModelResolutionIndex,
    prompt_name: str,
) -> LocalRecipeModel | None:
    """Return a local LoRA matching one inline prompt token name literally."""

    for candidate in backend_value_candidates_for_prompt_lora_name(prompt_name):
        model = index.find_literal(kind="loras", value=candidate)
        if model is not None:
            return model
    return None


def _replace_prompt_lora_names(
    prompt_text: str,
    replacements: list[_PromptLoraNameReplacement],
) -> str:
    """Rewrite parsed inline LoRA token names while preserving surrounding syntax."""

    rewritten = prompt_text
    for replacement in sorted(replacements, key=lambda item: item.start, reverse=True):
        rewritten = (
            rewritten[: replacement.start]
            + replacement.value
            + rewritten[replacement.end :]
        )
    return rewritten


def _set_model_value(
    buffers: Mapping[str, object],
    *,
    alias: str,
    node_name: str,
    input_key: str,
    value: str,
) -> None:
    """Rewrite one parsed model picker input value."""

    alias_buffer = cast(Mapping[str, object], buffers[alias])
    nodes = cast(Mapping[str, object], alias_buffer["nodes"])
    node = cast(Mapping[str, object], nodes[node_name])
    inputs = cast(dict[str, object], node["inputs"])
    inputs[input_key] = value


def _set_global_override_value(
    global_overrides: dict[str, dict[str, object]],
    *,
    input_key: str,
    value: str,
) -> None:
    """Rewrite a matching global override for the same model-picker field."""

    override_key = canonicalize_global_override_key(input_key)
    override = global_overrides.get(override_key)
    if not isinstance(override, dict) or "value" not in override:
        return
    override["value"] = value


def _model_from_backend_match(
    match: BackendHashLookupMatch,
    sha256: str,
) -> LocalRecipeModel:
    """Convert a backend hash match into a local recipe model."""

    return LocalRecipeModel(
        kind=match.kind,
        backend_value=match.value,
        display_name=match.display_name,
        relative_path=match.source.relative_path,
        sha256=sha256.upper(),
    )


__all__ = [
    "RecipeModelLoadResolver",
    "RecipeModelCivitaiState",
    "RecipeModelDownloadCandidate",
    "RecipeModelResolutionRequired",
    "RecipeModelResolutionSummary",
    "RecipeModelUnresolvedReference",
    "ResolvedRecipeModelScript",
]
