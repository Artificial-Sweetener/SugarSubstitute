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

"""Own bounded process-lifetime reuse of pure prompt syntax render plans."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Hashable
from dataclasses import dataclass
import hashlib
from itertools import count
from threading import RLock
from weakref import ReferenceType, ref

from substitute.application.ports import PromptWildcardCatalogGateway
from substitute.application.prompt_editor.document.semantics import (
    PromptDocumentSemantics,
)
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogLookup,
)
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptSyntaxRenderPlan,
)

_PROMPT_SCENE_PARSING_VERSION = "prompt-scene-v1"
_DEFAULT_RENDER_PLAN_CACHE_LIMIT = 512


@dataclass(frozen=True, slots=True)
class PromptProjectionInputCacheKey:
    """Identify pure prompt projection inputs independent of widget geometry."""

    source_text_hash: str
    source_text_length: int
    syntax_profile_identity: tuple[str, ...]
    wildcard_catalog_revision: str
    lora_model_metadata_revision: str
    scene_parsing_version: str
    document_semantics_identity: Hashable


class PromptSyntaxRenderPlanCache:
    """Own bounded render-plan reuse and collaborator revision identities."""

    def __init__(self, *, limit: int = _DEFAULT_RENDER_PLAN_CACHE_LIMIT) -> None:
        """Create an empty cache with a positive entry limit."""

        if limit <= 0:
            raise ValueError("Prompt syntax render-plan cache limit must be positive.")
        self._limit = limit
        self._plans: OrderedDict[
            PromptProjectionInputCacheKey,
            PromptSyntaxRenderPlan,
        ] = OrderedDict()
        self._lock = RLock()
        self._identity_sequence = count(1)
        self._identity_references: dict[
            int,
            tuple[ReferenceType[object], int],
        ] = {}

    @property
    def limit(self) -> int:
        """Return the maximum retained render-plan count."""

        return self._limit

    @property
    def size(self) -> int:
        """Return the current retained render-plan count."""

        with self._lock:
            return len(self._plans)

    def values(self) -> tuple[PromptSyntaxRenderPlan, ...]:
        """Return an immutable snapshot of retained plans for diagnostics."""

        with self._lock:
            return tuple(self._plans.values())

    def key_for(
        self,
        document_view: PromptDocumentView,
        syntax_profile: PromptSyntaxProfile,
        *,
        wildcard_catalog: PromptWildcardCatalogGateway,
        lora_catalog: PromptLoraCatalogLookup | None,
        document_semantics: PromptDocumentSemantics,
    ) -> PromptProjectionInputCacheKey:
        """Build the complete projection-input identity for one render request."""

        source_text = document_view.source_text
        syntax_identity = tuple(syntax_profile.enabled_syntaxes)
        return PromptProjectionInputCacheKey(
            source_text_hash=hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            source_text_length=len(source_text),
            syntax_profile_identity=syntax_identity,
            wildcard_catalog_revision=self.revision_for(wildcard_catalog),
            lora_model_metadata_revision=self.revision_for(lora_catalog),
            scene_parsing_version=_PROMPT_SCENE_PARSING_VERSION,
            document_semantics_identity=document_semantics.identity,
        )

    def lookup(
        self,
        key: PromptProjectionInputCacheKey,
    ) -> tuple[PromptSyntaxRenderPlan | None, int]:
        """Return and promote one cached plan plus the current cache size."""

        with self._lock:
            plan = self._plans.get(key)
            if plan is not None:
                self._plans.move_to_end(key)
            return plan, len(self._plans)

    def install(
        self,
        key: PromptProjectionInputCacheKey,
        plan: PromptSyntaxRenderPlan,
    ) -> tuple[PromptSyntaxRenderPlan, int]:
        """Install one plan or retain the plan won by a concurrent builder."""

        with self._lock:
            installed = self._plans.get(key)
            if installed is None:
                installed = plan
                self._plans[key] = installed
                while len(self._plans) > self._limit:
                    self._plans.popitem(last=False)
            self._plans.move_to_end(key)
            return installed, len(self._plans)

    def revision_for(self, value: object | None) -> str:
        """Return a stable cache revision for a catalog-like collaborator."""

        if value is None:
            return "none"
        for attribute_name in ("cache_revision", "revision", "version"):
            raw_revision = getattr(value, attribute_name, None)
            if isinstance(raw_revision, str | int):
                return str(raw_revision)
        return self._identity_revision(value)

    def clear(self) -> None:
        """Discard all retained render plans without changing identities."""

        with self._lock:
            self._plans.clear()

    def _identity_revision(self, value: object) -> str:
        """Assign a collision-free lifetime identity to an unversioned object."""

        object_id = id(value)

        def release(released_reference: ReferenceType[object]) -> None:
            """Release this object's registered identity token."""

            self._release_identity_revision(object_id, released_reference)

        with self._lock:
            existing = self._identity_references.get(object_id)
            if existing is not None and existing[0]() is value:
                return f"identity:{existing[1]}"
            revision = next(self._identity_sequence)
            try:
                value_reference = ref(value, release)
            except TypeError:
                return f"uncacheable:{revision}"
            self._identity_references[object_id] = (value_reference, revision)
            return f"identity:{revision}"

    def _release_identity_revision(
        self,
        object_id: int,
        released_reference: ReferenceType[object],
    ) -> None:
        """Forget an identity token only after its exact object is released."""

        with self._lock:
            existing = self._identity_references.get(object_id)
            if existing is not None and existing[0] is released_reference:
                del self._identity_references[object_id]


_SHARED_RENDER_PLAN_CACHE = PromptSyntaxRenderPlanCache()


def shared_prompt_syntax_render_plan_cache() -> PromptSyntaxRenderPlanCache:
    """Return the process-wide prompt syntax render-plan cache owner."""

    return _SHARED_RENDER_PLAN_CACHE


def clear_prompt_syntax_render_plan_cache() -> None:
    """Clear process-wide pure prompt syntax render-plan cache entries."""

    _SHARED_RENDER_PLAN_CACHE.clear()


__all__ = [
    "PromptProjectionInputCacheKey",
    "PromptSyntaxRenderPlanCache",
    "clear_prompt_syntax_render_plan_cache",
    "shared_prompt_syntax_render_plan_cache",
]
