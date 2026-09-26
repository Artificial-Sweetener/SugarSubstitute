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

"""Verify bounded concurrent enrichment of missing recipe model references."""

from __future__ import annotations

from threading import Event, Lock
from typing import cast

from substitute.application.model_metadata.ports import CivitaiMetadataGateway
from substitute.application.recipes.model_missing_reference_resolution import (
    MissingRecipeModelReference,
    RecipeModelMissingReferenceResolver,
)
from substitute.application.recipes.model_resolution_models import (
    RecipeModelCivitaiState,
)
from substitute.domain.model_metadata import (
    CivitaiLookupResult,
    CivitaiLookupStatus,
    CivitaiThumbnailPolicy,
)


def test_missing_hashes_are_looked_up_concurrently_and_keep_workflow_order() -> None:
    """Independent network lookups must share one external timeout window."""

    hashes = tuple(str(index) * 64 for index in range(1, 4))
    civitai = _ConcurrentNotFoundCivitai(expected_calls=len(hashes))
    references = tuple(
        _reference(sha256, node_name=f"model-{index}")
        for index, sha256 in enumerate(hashes)
    )

    resolved = RecipeModelMissingReferenceResolver(
        civitai=cast(CivitaiMetadataGateway, civitai),
        civitai_lookup_enabled=True,
        thumbnail_policy=CivitaiThumbnailPolicy(),
        recovery_gateways=(),
    ).resolve(references)

    assert civitai.calls == set(hashes)
    assert [reference.node_name for reference in resolved] == [
        "model-0",
        "model-1",
        "model-2",
    ]
    assert all(
        reference.civitai_state is RecipeModelCivitaiState.NOT_FOUND
        for reference in resolved
    )


def test_duplicate_hashes_share_one_civitai_lookup() -> None:
    """Repeated workflow fields must reuse one provider result."""

    sha256 = "A" * 64
    civitai = _ConcurrentNotFoundCivitai(expected_calls=1)

    resolved = RecipeModelMissingReferenceResolver(
        civitai=cast(CivitaiMetadataGateway, civitai),
        civitai_lookup_enabled=True,
        thumbnail_policy=CivitaiThumbnailPolicy(),
        recovery_gateways=(),
    ).resolve(
        (
            _reference(sha256, node_name="first"),
            _reference(sha256, node_name="second"),
        )
    )

    assert civitai.calls == {sha256}
    assert [reference.node_name for reference in resolved] == ["first", "second"]


def _reference(sha256: str, *, node_name: str) -> MissingRecipeModelReference:
    """Build one missing model field for provider enrichment."""

    return MissingRecipeModelReference(
        alias="Workflow",
        node_name=node_name,
        input_key="model_name",
        kind="checkpoints",
        value="missing.safetensors",
        sha256=sha256,
    )


class _ConcurrentNotFoundCivitai:
    """Require every expected lookup to enter before allowing any to return."""

    def __init__(self, *, expected_calls: int) -> None:
        """Create bounded concurrency coordination for the expected call count."""

        self._expected_calls = expected_calls
        self._lock = Lock()
        self._all_started = Event()
        self.calls: set[str] = set()

    def lookup_model_version_by_hash(self, sha256: str) -> CivitaiLookupResult:
        """Return not-found only after all unique hashes are in flight."""

        with self._lock:
            self.calls.add(sha256)
            if len(self.calls) == self._expected_calls:
                self._all_started.set()
        if not self._all_started.wait(timeout=5.0):
            raise AssertionError("CivitAI hashes were looked up serially")
        return CivitaiLookupResult(status=CivitaiLookupStatus.NOT_FOUND)
