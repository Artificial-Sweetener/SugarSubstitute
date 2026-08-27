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

"""Tests for pre-materialization recipe model resolution."""

from __future__ import annotations

from collections import OrderedDict
from typing import cast

import pytest

from substitute.application.recipes import (
    LocalRecipeModel,
    RecipeModelCivitaiState,
    RecipeModelLoadResolver,
    RecipeModelResolutionIndex,
    RecipeModelResolutionRequired,
)
from substitute.domain.recipes import ParsedSugarScript
from substitute.domain.recipes.sugar_script_parser import parse_sugar_script_document
from substitute.domain.model_metadata import (
    BackendFingerprintJob,
    BackendCapabilities,
    BackendHashLookupMatch,
    BackendHashLookupResult,
    BackendHashLookupStatus,
    BackendModelFile,
    BackendModelCatalogEntry,
    BackendModelSource,
    CivitaiFile,
    CivitaiImage,
    CivitaiLookupResult,
    CivitaiLookupStatus,
    CivitaiModelVersion,
    CivitaiThumbnailPolicy,
    JobStatus,
)
from substitute.domain.civitai import CivitaiThumbnailSafetyPolicy


def test_recipe_model_load_resolver_keeps_literal_local_model() -> None:
    """Literal model values that exist locally should not be rewritten."""

    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(
            (
                LocalRecipeModel(
                    kind="checkpoints",
                    backend_value="base.safetensors",
                    display_name="base",
                    relative_path="base.safetensors",
                    sha256="A" * 64,
                ),
            )
        )
    )

    resolved = resolver.resolve(_parsed(value="base.safetensors", sha256="A" * 64))

    assert _checkpoint_value(resolved.parsed_script) == "base.safetensors"
    assert resolved.summary.literal_matches == 1
    assert resolved.summary.hash_matches == 0


def test_recipe_model_load_resolver_rewrites_same_hash_local_model() -> None:
    """Missing literal values should resolve to the user's same-hash local path."""

    sha256 = "ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789"
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(
            (
                LocalRecipeModel(
                    kind="checkpoints",
                    backend_value="Installed/renamed.safetensors",
                    display_name="renamed",
                    relative_path="Installed/renamed.safetensors",
                    sha256=sha256,
                ),
            )
        )
    )

    resolved = resolver.resolve(_parsed(value="missing.safetensors", sha256=sha256))

    assert _checkpoint_value(resolved.parsed_script) == "Installed/renamed.safetensors"
    assert resolved.summary.hash_matches == 1


def test_recipe_model_load_resolver_rewrites_matching_global_override() -> None:
    """Hash resolution should update global overrides for the same picker field."""

    sha256 = "ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789"
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(
            (
                LocalRecipeModel(
                    kind="checkpoints",
                    backend_value="Installed/renamed.safetensors",
                    display_name="renamed",
                    relative_path="Installed/renamed.safetensors",
                    sha256=sha256,
                ),
            )
        )
    )
    parsed = _parsed(value="missing.safetensors", sha256=sha256)
    parsed.global_overrides["ckpt_name"] = {
        "value": "missing.safetensors",
        "mode": "global",
    }

    resolved = resolver.resolve(parsed)

    override = resolved.parsed_script.global_overrides["ckpt_name"]
    assert isinstance(override, dict)
    assert override["value"] == "Installed/renamed.safetensors"


def test_recipe_model_load_resolver_blocks_unresolved_hash() -> None:
    """Unresolved hashed model references should block materialization."""

    resolver = RecipeModelLoadResolver(RecipeModelResolutionIndex(()))

    with pytest.raises(RecipeModelResolutionRequired):
        resolver.resolve(_parsed(value="missing.safetensors", sha256="A" * 64))


def test_recipe_model_load_resolver_rewrites_backend_hash_match() -> None:
    """Backend local hash lookup fills cache misses before materialization."""

    sha256 = "B" * 64
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(()),
        backend=_BackendHashLookup(match_value="RecentlyAdded/model.safetensors"),
    )

    resolved = resolver.resolve(_parsed(value="missing.safetensors", sha256=sha256))

    assert (
        _checkpoint_value(resolved.parsed_script) == "RecentlyAdded/model.safetensors"
    )
    assert resolved.summary.hash_matches == 1


def test_recipe_model_load_resolver_rewrites_real_parsed_recipe_hash() -> None:
    """Real Sugar text without class_type should resolve by confident field key."""

    sha256 = "D" * 64
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(
            (
                LocalRecipeModel(
                    kind="checkpoints",
                    backend_value="Installed/renamed.safetensors",
                    display_name="renamed",
                    relative_path="Installed/renamed.safetensors",
                    sha256=sha256,
                ),
            )
        )
    )
    parsed = parse_sugar_script_document(
        "\n".join(
            (
                "use X as A",
                'set A.checkpoint.ckpt_name = "missing.safetensors"',
                f"# sha256 {sha256}",
                "",
            )
        )
    )

    resolved = resolver.resolve(parsed)

    assert _checkpoint_value(resolved.parsed_script) == "Installed/renamed.safetensors"
    assert resolved.summary.hash_matches == 1


def test_recipe_model_load_resolver_keeps_literal_inline_prompt_lora() -> None:
    """Inline LoRA tokens already installed locally should not be rewritten."""

    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(
            (
                LocalRecipeModel(
                    kind="loras",
                    backend_value="characters/midna.safetensors",
                    display_name="midna",
                    relative_path="characters/midna.safetensors",
                    sha256="A" * 64,
                ),
            )
        )
    )

    resolved = resolver.resolve(
        _parsed_prompt_lora(
            prompt_text="<lora:characters/midna:0.80>",
            prompt_name="characters/midna",
            sha256="A" * 64,
        )
    )

    assert _prompt_value(resolved.parsed_script) == "<lora:characters/midna:0.80>"
    assert resolved.summary.literal_matches == 1
    assert resolved.summary.hash_matches == 0


def test_recipe_model_load_resolver_rewrites_inline_prompt_lora_by_hash() -> None:
    """Missing inline LoRA literals should resolve to same-hash local prompt names."""

    sha256 = "A" * 64
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(
            (
                LocalRecipeModel(
                    kind="loras",
                    backend_value="Installed/renamed.safetensors",
                    display_name="renamed",
                    relative_path="Installed/renamed.safetensors",
                    sha256=sha256,
                ),
            )
        )
    )

    resolved = resolver.resolve(
        _parsed_prompt_lora(
            prompt_text="portrait <lora:missing:0.80:1.00>, cinematic",
            prompt_name="missing",
            sha256=sha256,
        )
    )

    assert (
        _prompt_value(resolved.parsed_script)
        == "portrait <lora:Installed/renamed:0.80:1.00>, cinematic"
    )
    assert resolved.summary.hash_matches == 1


def test_recipe_model_load_resolver_rewrites_duplicate_inline_prompt_loras() -> None:
    """One inline LoRA hash entry should rewrite duplicate matching prompt tokens."""

    sha256 = "A" * 64
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(
            (
                LocalRecipeModel(
                    kind="loras",
                    backend_value="Installed/renamed.safetensors",
                    display_name="renamed",
                    relative_path="Installed/renamed.safetensors",
                    sha256=sha256,
                ),
            )
        )
    )

    resolved = resolver.resolve(
        _parsed_prompt_lora(
            prompt_text="<lora:missing:0.80>, <lora:missing.safetensors:1.00>",
            prompt_name="missing",
            sha256=sha256,
        )
    )

    assert (
        _prompt_value(resolved.parsed_script)
        == "<lora:Installed/renamed:0.80>, <lora:Installed/renamed:1.00>"
    )
    assert resolved.summary.hash_matches == 2


def test_recipe_model_load_resolver_keeps_unmatched_inline_lora_metadata() -> None:
    """Metadata for one inline LoRA should not rewrite another prompt token."""

    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(
            (
                LocalRecipeModel(
                    kind="loras",
                    backend_value="Installed/renamed.safetensors",
                    display_name="renamed",
                    relative_path="Installed/renamed.safetensors",
                    sha256="A" * 64,
                ),
            )
        )
    )

    resolved = resolver.resolve(
        _parsed_prompt_lora(
            prompt_text="<lora:other:1.00>",
            prompt_name="missing",
            sha256="A" * 64,
        )
    )

    assert _prompt_value(resolved.parsed_script) == "<lora:other:1.00>"
    assert resolved.summary.hash_matches == 0


def test_recipe_model_load_resolver_reports_unresolved_inline_prompt_lora() -> None:
    """Unresolved inline LoRA hashes should use the existing missing-model flow."""

    sha256 = "2" * 64
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(()),
        civitai=_CivitaiLookup(_civitai_result(sha256=sha256)),
    )

    with pytest.raises(RecipeModelResolutionRequired) as raised:
        resolver.resolve(
            _parsed_prompt_lora(
                prompt_text="<lora:missing:1.00>",
                prompt_name="missing",
                sha256=sha256,
            )
        )

    reference = raised.value.references[0]
    assert reference.kind == "loras"
    assert reference.value == "missing"
    assert reference.sha256 == sha256
    assert reference.civitai_state is RecipeModelCivitaiState.FOUND


def test_recipe_model_load_resolver_blocks_real_parsed_unresolved_hash() -> None:
    """Real Sugar text with an unresolved hashed model should block materialization."""

    parsed = parse_sugar_script_document(
        "\n".join(
            (
                "use X as A",
                'set A.checkpoint.ckpt_name = "missing.safetensors"',
                f"# sha256 {'E' * 64}",
                "",
            )
        )
    )

    with pytest.raises(RecipeModelResolutionRequired):
        RecipeModelLoadResolver(RecipeModelResolutionIndex(())).resolve(parsed)


def test_recipe_model_load_resolver_retries_after_backend_hash_job() -> None:
    """Backend hashing-required responses are polled then looked up again."""

    backend = _BackendHashLookup(match_value="RecentlyAdded/model.safetensors")
    backend.first_lookup_status = BackendHashLookupStatus.HASHING_REQUIRED
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(()),
        backend=backend,
        fingerprint_jobs=backend,
        sleep=lambda _seconds: None,
    )

    resolved = resolver.resolve(_parsed(value="missing.safetensors", sha256="C" * 64))

    assert (
        _checkpoint_value(resolved.parsed_script) == "RecentlyAdded/model.safetensors"
    )
    assert backend.polled_job_ids == ["job-1"]


def test_recipe_model_load_resolver_handles_sequential_backend_hash_jobs() -> None:
    """Backend hash lookup should keep retrying through multiple hash jobs."""

    backend = _SequentialBackendHashLookup(
        statuses=(
            BackendHashLookupStatus.HASHING_RUNNING,
            BackendHashLookupStatus.HASHING_REQUIRED,
            BackendHashLookupStatus.COMPLETE,
        ),
        match_value="RecentlyAdded/model.safetensors",
    )
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(()),
        backend=backend,
        fingerprint_jobs=backend,
        sleep=lambda _seconds: None,
    )

    resolved = resolver.resolve(_parsed(value="missing.safetensors", sha256="F" * 64))

    assert (
        _checkpoint_value(resolved.parsed_script) == "RecentlyAdded/model.safetensors"
    )
    assert backend.polled_job_ids == ["job-1", "job-2"]


def test_recipe_model_load_resolver_blocks_after_backend_hash_timeout() -> None:
    """Backend hash lookup timeout should leave the model unresolved."""

    backend = _SequentialBackendHashLookup(
        statuses=(BackendHashLookupStatus.HASHING_RUNNING,),
        match_value="RecentlyAdded/model.safetensors",
    )
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(()),
        backend=backend,
        fingerprint_jobs=backend,
        sleep=lambda _seconds: None,
        fingerprint_poll_timeout_seconds=0.0,
    )

    with pytest.raises(RecipeModelResolutionRequired):
        resolver.resolve(_parsed(value="missing.safetensors", sha256="1" * 64))


def test_recipe_model_load_resolver_reports_civitai_download_candidate() -> None:
    """CivitAI lookup should expose only safe exact-hash download candidates."""

    sha256 = "2" * 64
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(()),
        civitai=_CivitaiLookup(_civitai_result(sha256=sha256)),
    )

    with pytest.raises(RecipeModelResolutionRequired) as raised:
        resolver.resolve(_parsed(value="missing.safetensors", sha256=sha256))

    reference = raised.value.references[0]
    assert reference.civitai_state is RecipeModelCivitaiState.FOUND
    assert reference.candidate is not None
    assert (
        reference.candidate.download_url == "https://civitai.com/api/download/models/2"
    )
    assert reference.candidate.sha256 == sha256
    assert reference.candidate.thumbnail_url == "https://image.example/sfw.jpg"


def test_recipe_model_load_resolver_respects_disabled_thumbnail_policy() -> None:
    """Missing-model thumbnails should obey the CivitAI thumbnail setting."""

    sha256 = "6" * 64
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(()),
        civitai=_CivitaiLookup(_civitai_result(sha256=sha256)),
        thumbnail_policy_provider=lambda: CivitaiThumbnailPolicy(
            CivitaiThumbnailSafetyPolicy.DISABLED
        ),
    )

    with pytest.raises(RecipeModelResolutionRequired) as raised:
        resolver.resolve(_parsed(value="missing.safetensors", sha256=sha256))

    candidate = raised.value.references[0].candidate
    assert candidate is not None
    assert candidate.thumbnail_url is None


def test_recipe_model_load_resolver_respects_allow_all_thumbnail_policy() -> None:
    """Allow-all thumbnail settings should allow the first provider image."""

    sha256 = "7" * 64
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(()),
        civitai=_CivitaiLookup(_civitai_result(sha256=sha256)),
        thumbnail_policy_provider=lambda: CivitaiThumbnailPolicy(
            CivitaiThumbnailSafetyPolicy.ALLOW_ALL
        ),
    )

    with pytest.raises(RecipeModelResolutionRequired) as raised:
        resolver.resolve(_parsed(value="missing.safetensors", sha256=sha256))

    candidate = raised.value.references[0].candidate
    assert candidate is not None
    assert candidate.thumbnail_url == "https://image.example/nsfw.jpg"


def test_recipe_model_load_resolver_reports_disabled_civitai_lookup() -> None:
    """Disabled missing-model lookup should not call CivitAI."""

    civitai = _CivitaiLookup(_civitai_result(sha256="3" * 64))
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(()),
        civitai=civitai,
        civitai_missing_model_lookup_enabled=lambda: False,
    )

    with pytest.raises(RecipeModelResolutionRequired) as raised:
        resolver.resolve(_parsed(value="missing.safetensors", sha256="3" * 64))

    assert raised.value.references[0].civitai_state is RecipeModelCivitaiState.DISABLED
    assert civitai.calls == []


def test_recipe_model_load_resolver_rejects_pickletensor_civitai_file() -> None:
    """PickleTensor files should not be offered for recipe model downloads."""

    sha256 = "4" * 64
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(()),
        civitai=_CivitaiLookup(
            _civitai_result(sha256=sha256, file_format="PickleTensor")
        ),
    )

    with pytest.raises(RecipeModelResolutionRequired) as raised:
        resolver.resolve(_parsed(value="missing.safetensors", sha256=sha256))

    assert (
        raised.value.references[0].civitai_state is RecipeModelCivitaiState.NO_SAFE_FILE
    )
    assert raised.value.references[0].candidate is None


def test_recipe_model_load_resolver_rejects_missing_civitai_scan_metadata() -> None:
    """Missing CivitAI scan metadata should fail closed for downloads."""

    sha256 = "5" * 64
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(()),
        civitai=_CivitaiLookup(
            _civitai_result(
                sha256=sha256,
                pickle_scan_result=None,
                virus_scan_result="Success",
            )
        ),
    )

    with pytest.raises(RecipeModelResolutionRequired) as raised:
        resolver.resolve(_parsed(value="missing.safetensors", sha256=sha256))

    assert (
        raised.value.references[0].civitai_state is RecipeModelCivitaiState.NO_SAFE_FILE
    )
    assert raised.value.references[0].candidate is None


def _parsed(*, value: str, sha256: str) -> ParsedSugarScript:
    """Build one parsed recipe with a checkpoint field hash."""

    return ParsedSugarScript(
        buffers=OrderedDict(
            {
                "A": OrderedDict(
                    {
                        "cube_id": "cube",
                        "nodes": {
                            "checkpoint": {
                                "class_type": "CheckpointLoaderSimple",
                                "inputs": {"ckpt_name": value},
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
        model_hashes_by_field={("A", "checkpoint", "ckpt_name"): sha256},
        prompt_lora_hashes_by_field={},
        project_name=None,
    )


def _parsed_prompt_lora(
    *,
    prompt_text: str,
    prompt_name: str,
    sha256: str,
) -> ParsedSugarScript:
    """Build one parsed recipe with an inline prompt LoRA hash."""

    return ParsedSugarScript(
        buffers=OrderedDict(
            {
                "A": OrderedDict(
                    {
                        "cube_id": "cube",
                        "nodes": {
                            "prompt": {
                                "class_type": "CLIPTextEncode",
                                "inputs": {"text": prompt_text},
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
        prompt_lora_hashes_by_field={("A", "prompt", "text"): {prompt_name: sha256}},
        project_name=None,
    )


def _checkpoint_value(parsed_script: ParsedSugarScript) -> str:
    """Return the checkpoint input value from a test parsed script."""

    buffer = cast(dict[str, object], parsed_script.buffers["A"])
    nodes = cast(dict[str, object], buffer["nodes"])
    checkpoint = cast(dict[str, object], nodes["checkpoint"])
    inputs = cast(dict[str, object], checkpoint["inputs"])
    value = inputs["ckpt_name"]
    assert isinstance(value, str)
    return value


def _prompt_value(parsed_script: ParsedSugarScript) -> str:
    """Return the prompt input value from a test parsed script."""

    buffer = cast(dict[str, object], parsed_script.buffers["A"])
    nodes = cast(dict[str, object], buffer["nodes"])
    prompt = cast(dict[str, object], nodes["prompt"])
    inputs = cast(dict[str, object], prompt["inputs"])
    value = inputs["text"]
    assert isinstance(value, str)
    return value


class _BackendHashLookup:
    """Fake backend hash lookup gateway for resolver tests."""

    def __init__(self, *, match_value: str) -> None:
        """Store one backend match value."""

        self._match_value = match_value
        self.first_lookup_status = BackendHashLookupStatus.COMPLETE
        self._lookup_count = 0
        self.polled_job_ids: list[str] = []

    def lookup_model_by_hash(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> BackendHashLookupResult | None:
        """Return a queued state once, then a backend match."""

        self._lookup_count += 1
        if self._lookup_count == 1 and self.first_lookup_status in {
            BackendHashLookupStatus.HASHING_REQUIRED,
            BackendHashLookupStatus.HASHING_RUNNING,
        }:
            return BackendHashLookupResult(
                status=self.first_lookup_status,
                kind=kind,
                sha256=sha256,
                matches=(),
                job_id="job-1",
            )
        return BackendHashLookupResult(
            status=BackendHashLookupStatus.COMPLETE,
            kind=kind,
            sha256=sha256,
            matches=(
                BackendHashLookupMatch(
                    kind=kind,
                    value=self._match_value,
                    display_name="model",
                    source=BackendModelSource(
                        root_id="checkpoints:0",
                        relative_path=self._match_value,
                    ),
                    file=BackendModelFile(
                        extension=".safetensors",
                        size_bytes=1,
                        modified_at="2026-05-21T00:00:00Z",
                        created_at=None,
                    ),
                ),
            ),
            job_id=None,
        )

    def get_fingerprint_job(self, job_id: str) -> BackendFingerprintJob | None:
        """Return a completed hash job."""

        self.polled_job_ids.append(job_id)
        return BackendFingerprintJob(
            job_id=job_id, status=JobStatus.COMPLETE, entries=()
        )

    def get_capabilities(self) -> BackendCapabilities | None:
        """Return no capabilities because resolver tests do not use them."""

        return None

    def list_models(
        self,
        kinds: tuple[str, ...],
        *,
        refresh: bool = False,
    ) -> tuple[BackendModelCatalogEntry, ...]:
        """Return no catalog entries because resolver tests do not use them."""

        _ = (kinds, refresh)
        return ()

    def refresh_fingerprints(
        self,
        entries: tuple[BackendModelCatalogEntry, ...],
    ) -> BackendFingerprintJob:
        """Return a complete empty job because resolver tests do not use refresh."""

        _ = entries
        return BackendFingerprintJob(
            job_id="job-1", status=JobStatus.COMPLETE, entries=()
        )


class _SequentialBackendHashLookup(_BackendHashLookup):
    """Fake backend that returns several hashing states before a match."""

    def __init__(
        self,
        *,
        statuses: tuple[BackendHashLookupStatus, ...],
        match_value: str,
    ) -> None:
        """Store ordered lookup statuses."""

        super().__init__(match_value=match_value)
        self._statuses = list(statuses)

    def lookup_model_by_hash(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> BackendHashLookupResult | None:
        """Return the next configured lookup status."""

        if not self._statuses:
            return super().lookup_model_by_hash(kind=kind, sha256=sha256)
        status = self._statuses.pop(0)
        if status is BackendHashLookupStatus.COMPLETE:
            return super().lookup_model_by_hash(kind=kind, sha256=sha256)
        job_number = len(self.polled_job_ids) + 1
        return BackendHashLookupResult(
            status=status,
            kind=kind,
            sha256=sha256,
            matches=(),
            job_id=f"job-{job_number}",
        )


class _CivitaiLookup:
    """Fake CivitAI lookup gateway for resolver tests."""

    def __init__(self, result: CivitaiLookupResult) -> None:
        """Store one lookup result."""

        self._result = result
        self.calls: list[str] = []

    def lookup_model_version_by_hash(self, sha256: str) -> CivitaiLookupResult:
        """Record the lookup and return the configured response."""

        self.calls.append(sha256)
        return self._result


def _civitai_result(
    *,
    sha256: str,
    file_format: str = "SafeTensor",
    pickle_scan_result: str | None = "Success",
    virus_scan_result: str | None = "Success",
) -> CivitaiLookupResult:
    """Build one CivitAI found response with an exact hash file."""

    return CivitaiLookupResult(
        status=CivitaiLookupStatus.FOUND,
        version=CivitaiModelVersion(
            model_id=1,
            model_version_id=2,
            model_name="Model",
            model_type="Checkpoint",
            version_name="v1",
            base_model=None,
            trained_words=(),
            description=None,
            version_description=None,
            tags=(),
            creator_username=None,
            creator_image=None,
            nsfw=None,
            nsfw_level=None,
            availability=None,
            files=(
                CivitaiFile(
                    file_id=3,
                    name="model.safetensors",
                    size_kb=1.0,
                    file_type="Model",
                    download_url="https://civitai.com/api/download/models/2",
                    pickle_scan_result=pickle_scan_result,
                    virus_scan_result=virus_scan_result,
                    primary=True,
                    hashes={"SHA256": sha256},
                    metadata={"format": file_format},
                ),
            ),
            images=(
                CivitaiImage(
                    image_id=10,
                    url="https://image.example/nsfw.jpg",
                    image_type="image",
                    nsfw=True,
                    nsfw_level="Explicit",
                    width=512,
                    height=768,
                    meta=None,
                ),
                CivitaiImage(
                    image_id=11,
                    url="https://image.example/sfw.jpg",
                    image_type="image",
                    nsfw=False,
                    nsfw_level="None",
                    width=512,
                    height=768,
                    meta=None,
                ),
            ),
            stats={},
            model_page_url="https://civitai.com/models/1?modelVersionId=2",
            source_url="https://civitai.com/api/v1/model-versions/by-hash/hash",
            fetched_at="2026-05-21T00:00:00Z",
            raw_provider_payload={},
        ),
    )
