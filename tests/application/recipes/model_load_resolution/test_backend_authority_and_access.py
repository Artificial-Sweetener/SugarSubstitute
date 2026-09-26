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

"""Prove BackEnd model authority and legacy SugarScript recovery behavior."""

from __future__ import annotations

from typing import cast

import pytest

from substitute.application.recipes import (
    LocalRecipeModel,
    RecipeModelLoadResolver,
    RecipeModelResolutionIndex,
    RecipeModelResolutionRequired,
)
from substitute.domain.model_metadata import (
    BackendHashLookupMatch,
    BackendHashLookupResult,
    BackendHashLookupStatus,
    BackendModelFile,
    BackendModelSource,
    CivitaiDownloadAccess,
    CivitaiFile,
    CivitaiLookupResult,
    CivitaiLookupStatus,
    CivitaiModelVersion,
)
from substitute.domain.recipes import ParsedSugarScript
from substitute.domain.recipes.sugar_script_parser import parse_sugar_script_document


def test_backend_absence_overrules_stale_frontend_catalog_match() -> None:
    """Treat a complete BackEnd miss as authoritative over cached frontend data."""

    sha256 = "C" * 64
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(
            (
                LocalRecipeModel(
                    kind="checkpoints",
                    backend_value="stale.safetensors",
                    display_name="stale",
                    relative_path="stale.safetensors",
                    sha256=sha256,
                ),
            )
        ),
        backend=_BackendHashLookup(),
        civitai_missing_model_lookup_enabled=lambda: False,
    )

    with pytest.raises(RecipeModelResolutionRequired):
        resolver.resolve(_legacy_script(sha256))


def test_backend_transport_failure_falls_back_to_cached_hash_evidence() -> None:
    """Keep loading from cached hashes when the BackEnd cannot answer."""

    sha256 = "B" * 64
    backend = _UnavailableBackendHashLookup()
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(
            (
                LocalRecipeModel(
                    kind="checkpoints",
                    backend_value="Installed/cached.safetensors",
                    display_name="cached",
                    relative_path="Installed/cached.safetensors",
                    sha256=sha256,
                ),
            )
        ),
        backend=backend,
    )

    resolved = resolver.resolve(_legacy_script(sha256))

    assert _checkpoint_value(resolved.parsed_script) == "Installed/cached.safetensors"
    assert backend.lookups == [("checkpoints", sha256)]


def test_real_legacy_sugarscript_hash_resolves_through_backend() -> None:
    """Resolve an old SugarScript hash even without portable workflow metadata."""

    sha256 = "D" * 64
    backend = _BackendHashLookup(match_value="Installed/renamed.safetensors")

    resolved = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(()),
        backend=backend,
    ).resolve(_legacy_script(sha256))

    assert _checkpoint_value(resolved.parsed_script) == "Installed/renamed.safetensors"
    assert resolved.summary.hash_matches == 1
    assert backend.lookups == [("checkpoints", sha256)]


def test_civitai_candidate_reports_api_key_requirement() -> None:
    """Carry CivitAI access requirements into the user-facing candidate."""

    sha256 = "E" * 64
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(()),
        backend=_BackendHashLookup(),
        civitai=_CivitaiLookup(sha256),
    )

    with pytest.raises(RecipeModelResolutionRequired) as raised:
        resolver.resolve(_legacy_script(sha256))

    candidate = raised.value.references[0].candidate
    assert candidate is not None
    assert candidate.download_access is CivitaiDownloadAccess.API_KEY_REQUIRED


def _legacy_script(sha256: str) -> ParsedSugarScript:
    """Parse the original SugarScript field-hash representation."""

    return parse_sugar_script_document(
        "\n".join(
            (
                "use X as A",
                'set A.checkpoint.ckpt_name = "missing.safetensors"',
                f"# sha256 {sha256}",
                "",
            )
        )
    )


def _checkpoint_value(parsed_script: ParsedSugarScript) -> str:
    """Return the checkpoint value from the parsed legacy script."""

    buffer = cast(dict[str, object], parsed_script.buffers["A"])
    nodes = cast(dict[str, object], buffer["nodes"])
    checkpoint = cast(dict[str, object], nodes["checkpoint"])
    inputs = cast(dict[str, object], checkpoint["inputs"])
    return cast(str, inputs["ckpt_name"])


class _BackendHashLookup:
    """Return one authoritative BackEnd hash result."""

    def __init__(self, match_value: str | None = None) -> None:
        """Store the optional BackEnd match value."""

        self._match_value = match_value
        self.lookups: list[tuple[str, str]] = []

    def lookup_model_by_hash(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> BackendHashLookupResult:
        """Return a complete lookup and record the authoritative request."""

        self.lookups.append((kind, sha256))
        matches: tuple[BackendHashLookupMatch, ...] = ()
        if self._match_value is not None:
            matches = (
                BackendHashLookupMatch(
                    kind=kind,
                    value=self._match_value,
                    display_name="renamed",
                    source=BackendModelSource(
                        root_id=f"{kind}:0",
                        relative_path=self._match_value,
                    ),
                    file=BackendModelFile(
                        extension=".safetensors",
                        size_bytes=1,
                        modified_at="2026-09-22T00:00:00Z",
                        created_at=None,
                    ),
                ),
            )
        return BackendHashLookupResult(
            status=BackendHashLookupStatus.COMPLETE,
            kind=kind,
            sha256=sha256,
            matches=matches,
            job_id=None,
        )


class _UnavailableBackendHashLookup:
    """Represent a configured BackEnd whose transport is unavailable."""

    def __init__(self) -> None:
        """Create an empty lookup record."""

        self.lookups: list[tuple[str, str]] = []

    def lookup_model_by_hash(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> BackendHashLookupResult | None:
        """Return transport unavailability after recording the request."""

        self.lookups.append((kind, sha256))
        return None


class _CivitaiLookup:
    """Expose one exact safe CivitAI file that requires an API key."""

    def __init__(self, sha256: str) -> None:
        """Store the exact file hash."""

        self._sha256 = sha256

    def lookup_model_version_by_hash(self, sha256: str) -> CivitaiLookupResult:
        """Return metadata for the requested exact hash."""

        assert sha256 == self._sha256
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
                        pickle_scan_result="Success",
                        virus_scan_result="Success",
                        primary=True,
                        hashes={"SHA256": sha256},
                        metadata={"format": "SafeTensor"},
                    ),
                ),
                images=(),
                stats={},
                model_page_url="https://civitai.com/models/1?modelVersionId=2",
                source_url="https://civitai.com/api/v1/model-versions/by-hash/hash",
                fetched_at="2026-09-22T00:00:00Z",
                raw_provider_payload={},
            ),
        )

    def model_version_download_access(
        self,
        model_version_id: int,
    ) -> CivitaiDownloadAccess:
        """Report that downloads for this version require a CivitAI API key."""

        assert model_version_id == 2
        return CivitaiDownloadAccess.API_KEY_REQUIRED
