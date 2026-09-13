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

"""Verify provider routing, compatibility, deduplication, and acquisition."""

from __future__ import annotations

from pathlib import Path

from substitute.application.model_suggestions import (
    ModelSuggestionEngine,
    ModelSuggestionService,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import ModelFamilyId
from substitute.domain.model_suggestions import (
    ModelSuggestion,
    ModelSuggestionAccess,
    ModelSuggestionAccessPolicy,
    ModelSuggestionContext,
    ModelSuggestionReference,
)
from sugarsubstitute_shared.model_acquisition import AcquisitionResult
from sugarsubstitute_shared.model_discovery import (
    ModelArtifactDestinationPolicy,
    ModelArtifactKind,
)


class _Provider:
    """Expose deterministic suggestions through the provider protocol."""

    def __init__(
        self,
        provider_id: str,
        suggestions: tuple[ModelSuggestion, ...],
        *,
        supported: bool = True,
    ) -> None:
        """Store provider identity, results, and capability state."""

        self.provider_id = provider_id
        self.suggestions = suggestions
        self.supported = supported
        self.requests: list[
            tuple[ModelSuggestionContext, ModelSuggestionAccessPolicy]
        ] = []

    def supports(self, context: ModelSuggestionContext) -> bool:
        """Return configured capability."""

        _ = context
        return self.supported

    def suggest(
        self,
        context: ModelSuggestionContext,
        *,
        access_policy: ModelSuggestionAccessPolicy,
        limit: int,
        excluded_sha256: frozenset[str],
    ) -> tuple[ModelSuggestion, ...]:
        """Return unexcluded results up to the requested limit."""

        self.requests.append((context, access_policy))
        return tuple(
            item
            for item in self.suggestions
            if item.sha256.casefold() not in excluded_sha256
        )[:limit]

    def browse_url(self, context: ModelSuggestionContext) -> str:
        """Return a provider-owned browse route."""

        return f"https://{self.provider_id}.example/{context.family_id.value}"

    def fetch_thumbnail(self, suggestion: ModelSuggestion) -> ThumbnailAsset:
        """Reject unused thumbnail work."""

        raise AssertionError(suggestion)

    def acquire(
        self,
        suggestion: ModelSuggestion,
        *,
        destination: Path,
        cancellation: object | None,
    ) -> AcquisitionResult:
        """Return a deterministic provider-owned acquisition result."""

        _ = cancellation
        return AcquisitionResult(
            destination / suggestion.file_name,
            suggestion.sha256,
            suggestion.size_bytes,
            False,
        )


def _suggestion(
    context: ModelSuggestionContext,
    *,
    provider_id: str,
    sha256: str,
    rank: int,
) -> ModelSuggestion:
    """Build one provider-neutral suggestion."""

    return ModelSuggestion(
        reference=ModelSuggestionReference(
            provider_id,
            provider_id.title(),
            f"model-{rank}",
            f"version-{rank}",
        ),
        context=context,
        model_name=f"Model {rank}",
        version_name=f"v{rank}",
        creator=None,
        file_name=f"model-{rank}.safetensors",
        size_bytes=rank,
        sha256=sha256,
        download_url=f"https://{provider_id}.example/download/{rank}",
        model_page_url=f"https://{provider_id}.example/models/{rank}",
        thumbnail_url=None,
        provider_rank=rank,
        access=ModelSuggestionAccess.PUBLIC,
    )


def test_engine_routes_by_capability_and_deduplicates_provider_hashes() -> None:
    """Multiple providers should compose without incompatible or duplicate cards."""

    context = ModelSuggestionContext(
        ModelArtifactKind.DIFFUSION_MODELS,
        ModelFamilyId.ANIMA,
    )
    first = _suggestion(context, provider_id="first", sha256="a" * 64, rank=1)
    duplicate = _suggestion(context, provider_id="second", sha256="a" * 64, rank=1)
    second = _suggestion(context, provider_id="second", sha256="b" * 64, rank=2)
    ignored = _Provider("ignored", (second,), supported=False)
    engine = ModelSuggestionEngine(
        (
            _Provider("first", (first,)),
            _Provider("second", (duplicate, second)),
            ignored,
        )
    )

    suggestions = engine.suggest(
        context,
        access_policy=ModelSuggestionAccessPolicy.CURRENT_USER,
        limit=8,
    )

    assert suggestions == (first, second)
    assert ignored.requests == []
    assert engine.browse_urls(context) == (
        ("first", "https://first.example/anima"),
        ("second", "https://second.example/anima"),
    )


def test_empty_picker_service_uses_authenticated_access_and_exact_provider(
    tmp_path: Path,
) -> None:
    """Picker recovery should allow credentialed cards and preserve provider routing."""

    root = tmp_path / "synthetic-model-root"
    context = ModelSuggestionContext(
        ModelArtifactKind.CHECKPOINTS,
        ModelFamilyId.SDXL,
    )
    suggestion = _suggestion(context, provider_id="provider", sha256="c" * 64, rank=1)
    provider = _Provider("provider", (suggestion,))
    service = ModelSuggestionService(
        destinations=ModelArtifactDestinationPolicy(root),
        engine=ModelSuggestionEngine((provider,)),
    )

    plan = service.plan_empty_picker(context)
    selected, result = service.acquire(plan, suggestion.identity)

    assert provider.requests == [(context, ModelSuggestionAccessPolicy.CURRENT_USER)]
    assert selected is suggestion
    assert result.path == root / "checkpoints" / suggestion.file_name


def test_engine_rejects_duplicate_provider_identities() -> None:
    """Provider registration must not permit ambiguous acquisition ownership."""

    provider = _Provider("same", ())

    try:
        ModelSuggestionEngine((provider, provider))
    except ValueError as error:
        assert "unique" in str(error)
    else:
        raise AssertionError("Duplicate provider identities were accepted.")


def test_engine_rejects_provider_identity_spoofing() -> None:
    """A provider must never make another provider own its returned suggestion."""

    context = ModelSuggestionContext(
        ModelArtifactKind.CHECKPOINTS,
        ModelFamilyId.SDXL,
    )
    forged = _suggestion(context, provider_id="other", sha256="d" * 64, rank=1)
    provider = _Provider("registered", (forged,))

    try:
        ModelSuggestionEngine((provider,)).suggest(
            context,
            access_policy=ModelSuggestionAccessPolicy.CURRENT_USER,
            limit=1,
        )
    except ValueError as error:
        assert "another provider" in str(error)
    else:
        raise AssertionError("Provider identity spoofing was accepted.")
