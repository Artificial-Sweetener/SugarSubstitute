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

"""Deterministic prompt editor benchmark service fakes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import cast

from substitute.application.danbooru import (
    DanbooruImportedPrompt,
    DanbooruPromptImportResult,
    DanbooruUrlClassification,
    DanbooruUrlImportService,
    DanbooruUrlKind,
    DanbooruWikiContentService,
)
from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.application.prompt_editor import (
    PromptLoraCatalogItem,
    PromptScheduledLora,
    PromptSpellcheckSnapshot,
    PromptSpellingIssue,
    PromptSpellingSuggestionSet,
)
from substitute.devtools.prompt_editor_performance.metrics import OperationCounter
from substitute.devtools.prompt_editor_performance.scenarios import (
    AutocompleteGatewayKind,
    DANBOORU_IMPORT_URL,
    LoraCatalogKind,
    Scenario,
    WildcardGatewayKind,
)
from substitute.domain.user_presets import GLOBAL_PRESET_ASSOCIATION
from substitute.presentation.editor.catalog.snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)


@dataclass(frozen=True, slots=True)
class _MeasuredPresetSaveScope:
    """Mirror save-scope fields without importing the Qt save dialog module."""

    title: str
    full_label: str
    association: object


@dataclass(frozen=True, slots=True)
class _MeasuredPromptSegmentPresetMenuItem:
    """Describe one deterministic saved prompt segment."""

    label: str
    text: str
    tooltip: str


@dataclass(frozen=True, slots=True)
class _MeasuredPromptSegmentPresetMenuSection:
    """Group deterministic prompt segment presets."""

    title: str
    presets: tuple[_MeasuredPromptSegmentPresetMenuItem, ...]


@dataclass(frozen=True, slots=True)
class _MeasuredPromptSegmentPresetMenuModel:
    """Mirror menu model fields consumed by the segment preset controller."""

    sections: tuple[_MeasuredPromptSegmentPresetMenuSection, ...]
    save_scopes: tuple[_MeasuredPresetSaveScope, ...]


@dataclass(frozen=True, slots=True)
class _MeasuredPromptSegmentPresetSourceSnapshot:
    """Mirror segment preset source snapshot fields consumed by the controller."""

    menu_model: _MeasuredPromptSegmentPresetMenuModel
    catalog_identity: CatalogSnapshotIdentity
    status: CatalogSnapshotStatus


class _StaticPromptAutocompleteGateway:
    """Return deterministic autocomplete suggestions without filesystem IO."""

    def __init__(self, counter: OperationCounter) -> None:
        """Store the measurement counter."""

        self._counter = counter

    def search(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return stable rows for compatible prefixes."""

        started_at = perf_counter()
        try:
            if not prefix.casefold().startswith(("ha", "hair")):
                return ()
            return (
                PromptAutocompleteSuggestion(tag="hair ornament", popularity=4100),
                PromptAutocompleteSuggestion(tag="hair ribbon", popularity=3800),
            )[:limit]
        finally:
            self._counter.record((perf_counter() - started_at) * 1000.0)


class _EmptyPromptAutocompleteGateway:
    """Return no autocomplete suggestions while preserving measurement counters."""

    def __init__(self, counter: OperationCounter) -> None:
        """Store the measurement counter."""

        self._counter = counter

    def search(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return an empty result set for every query."""

        _ = (prefix, limit)
        self._counter.record(0.0)
        return ()


class _MeasuredPromptWildcardCatalogGateway:
    """Return deterministic wildcard data while recording catalog searches."""

    def __init__(self, *, enabled: bool, counter: OperationCounter) -> None:
        """Store whether wildcard autocomplete rows should be returned."""

        self._enabled = enabled
        self._counter = counter

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return stable wildcard suggestions for compatible prefixes."""

        started_at = perf_counter()
        try:
            if not self._enabled:
                return ()
            if not prefix.casefold().startswith(("li", "lighting")):
                return ()
            return (
                PromptAutocompleteSuggestion(
                    tag="lighting/day",
                    source_label="wildcard",
                    source_kind="wildcard",
                ),
                PromptAutocompleteSuggestion(
                    tag="lighting/night",
                    source_label="wildcard",
                    source_kind="wildcard",
                ),
            )[:limit]
        finally:
            self._counter.record((perf_counter() - started_at) * 1000.0)

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Return successful wildcard metadata for every measured reference."""

        return tuple(
            PromptWildcardResolution(
                identifier=reference.identifier,
                wildcard_form=reference.wildcard_form,
                csv_column=reference.csv_column,
                exists=True,
            )
            for reference in references
        )


class _MeasuredPromptLoraCatalog:
    """Return deterministic LoRA rows while measuring catalog access."""

    def __init__(self, *, enabled: bool, counter: OperationCounter) -> None:
        """Store deterministic LoRA rows and the lookup counter."""

        self._counter = counter
        self._items = (lora_catalog_item(),) if enabled else ()

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return cached LoRA rows without simulating backend loading."""

        self._counter.record(0.0)
        return self._items

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return stable LoRA rows for autocomplete and picker scenarios."""

        started_at = perf_counter()
        try:
            return self._items
        finally:
            self._counter.record((perf_counter() - started_at) * 1000.0)

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return the stable LoRA row matching one prompt reference."""

        started_at = perf_counter()
        try:
            normalized = prompt_name.replace("\\", "/").casefold()
            for item in self._items:
                if item.prompt_name.replace("\\", "/").casefold() == normalized:
                    return item
            return None
        finally:
            self._counter.record((perf_counter() - started_at) * 1000.0)


class _MeasuredPromptSpellcheckService:
    """Return deterministic spelling diagnostics without backend IO."""

    def snapshot_for_text(self, text: str) -> PromptSpellcheckSnapshot:
        """Return a spelling issue for the known misspelled token."""

        word = "mispelled"
        start = text.find(word)
        issues = (
            (
                PromptSpellingIssue(
                    source_start=start,
                    source_end=start + len(word),
                    word=word,
                ),
            )
            if start >= 0
            else ()
        )
        return PromptSpellcheckSnapshot(
            source_text=text,
            language_tag="en_US",
            issues=issues,
        )

    def suggestions_for_word(
        self,
        word: str,
        *,
        limit: int = 8,
    ) -> PromptSpellingSuggestionSet:
        """Return deterministic spelling suggestions for context-menu actions."""

        _ = limit
        return PromptSpellingSuggestionSet(word=word, suggestions=("misspelled",))

    def dictionary_add_supported(self) -> bool:
        """Return whether persistent dictionary additions are supported."""

        return False

    def ignore_word_for_session(self, word: str) -> None:
        """Accept session-ignore requests without touching a backend."""

        _ = word

    def add_word_to_dictionary(self, word: str) -> bool:
        """Decline persistent dictionary writes for this deterministic fake."""

        _ = word
        return False


class _MeasuredDanbooruUrlImportService:
    """Return deterministic Danbooru paste/import outcomes for measurement."""

    def __init__(self) -> None:
        """Create the stable classification and prompt import result."""

        self._classification = DanbooruUrlClassification(
            url=DANBOORU_IMPORT_URL,
            kind=DanbooruUrlKind.POST,
            lookup_value="123456",
        )
        self._result = DanbooruPromptImportResult(
            imported_prompt=DanbooruImportedPrompt(
                display_text="imported_tag, imported_character",
                source_post_id=123456,
                included_tags=("imported_tag", "imported_character"),
                excluded_tags=(),
            ),
            classification=self._classification,
        )

    def classify_url(self, text: str) -> DanbooruUrlClassification | None:
        """Return a supported classification for the deterministic URL."""

        if text.strip() == DANBOORU_IMPORT_URL:
            return self._classification
        return None

    def import_prompt_from_url(self, text: str) -> DanbooruPromptImportResult:
        """Return the deterministic imported prompt result."""

        _ = text
        return self._result


class _ImmediateDanbooruImportDispatcher:
    """Run Danbooru paste/import lookups inline for deterministic measurement."""

    def submit(
        self,
        lookup: Callable[[], DanbooruPromptImportResult],
        *,
        completed: Callable[[DanbooruPromptImportResult], None],
        failed: Callable[[BaseException], None],
    ) -> None:
        """Execute the lookup immediately and report through callbacks."""

        try:
            completed(lookup())
        except BaseException as error:  # noqa: BLE001
            failed(error)


class _MeasuredDanbooruWikiService:
    """Provide inert Danbooru wiki lookup methods for menu readiness tests."""

    def lookup_selection(self, selection_text: str) -> object:
        """Return an opaque lookup result without network access."""

        return selection_text

    def lookup_title(self, title: str) -> object:
        """Return an opaque lookup result without network access."""

        return title


class _MeasuredPromptSegmentPresetSource:
    """Provide in-memory prompt segment presets for menu measurements."""

    def __init__(self) -> None:
        """Create one deterministic saved segment and global save scope."""

        self._scope = _MeasuredPresetSaveScope(
            title="Global",
            full_label="Global",
            association=GLOBAL_PRESET_ASSOCIATION,
        )
        self._model = _MeasuredPromptSegmentPresetMenuModel(
            sections=(
                _MeasuredPromptSegmentPresetMenuSection(
                    title="Global",
                    presets=(
                        _MeasuredPromptSegmentPresetMenuItem(
                            label="Detailed portrait",
                            text="detailed portrait",
                            tooltip="detailed portrait",
                        ),
                    ),
                ),
            ),
            save_scopes=(self._scope,),
        )

    def list_prompt_segment_presets(self) -> _MeasuredPromptSegmentPresetSourceSnapshot:
        """Return in-memory segment menu data."""

        return _MeasuredPromptSegmentPresetSourceSnapshot(
            menu_model=self._model,
            catalog_identity=CatalogSnapshotIdentity(source_revision=1),
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
        )

    def prompt_segment_save_scopes(self) -> tuple[_MeasuredPresetSaveScope, ...]:
        """Return the fake global save scope."""

        return (self._scope,)

    def save_prompt_segment(
        self,
        *,
        label: str,
        text: str,
        scope: _MeasuredPresetSaveScope,
    ) -> None:
        """Accept save requests without touching the filesystem."""

        _ = (label, text, scope)


def autocomplete_gateway(
    kind: AutocompleteGatewayKind,
    counter: OperationCounter,
) -> object:
    """Return the autocomplete gateway requested by a scenario."""

    if kind == "static":
        return _StaticPromptAutocompleteGateway(counter)
    return _EmptyPromptAutocompleteGateway(counter)


def wildcard_gateway(
    kind: WildcardGatewayKind,
    counter: OperationCounter,
) -> object:
    """Return the wildcard gateway requested by a scenario."""

    return _MeasuredPromptWildcardCatalogGateway(
        enabled=kind == "static",
        counter=counter,
    )


def lora_catalog(
    kind: LoraCatalogKind,
    counter: OperationCounter,
) -> object:
    """Return the LoRA catalog requested by a scenario."""

    return _MeasuredPromptLoraCatalog(enabled=kind == "static", counter=counter)


def spellcheck_service_for_scenario(scenario: Scenario) -> object | None:
    """Return deterministic spellcheck service when diagnostics are measured."""

    if scenario.spellcheck_enabled:
        return _MeasuredPromptSpellcheckService()
    return None


def scheduled_lora_resolver_for_scenario(
    scenario: Scenario,
) -> Callable[[str], tuple[PromptScheduledLora, ...]] | None:
    """Return deterministic scheduled-LoRA context when menu actions need it."""

    if not scenario.scheduled_lora_context_enabled:
        return None
    scheduled_lora = scheduled_lora_for_context_menu()
    return lambda _prompt_text: (scheduled_lora,)


def danbooru_wiki_service_for_scenario(
    scenario: Scenario,
) -> DanbooruWikiContentService | None:
    """Return an inert wiki service so Danbooru menu readiness can be measured."""

    if not scenario.danbooru_wiki_enabled:
        return None
    return cast(DanbooruWikiContentService, _MeasuredDanbooruWikiService())


def segment_preset_source_for_scenario(scenario: Scenario) -> object | None:
    """Return deterministic saved segment data for segment menu measurements."""

    if not scenario.segment_presets_enabled:
        return None
    return _MeasuredPromptSegmentPresetSource()


def danbooru_url_import_service() -> DanbooruUrlImportService:
    """Return the deterministic Danbooru URL import service."""

    return cast(DanbooruUrlImportService, _MeasuredDanbooruUrlImportService())


def immediate_danbooru_import_dispatcher() -> object:
    """Return the deterministic inline Danbooru import dispatcher."""

    return _ImmediateDanbooruImportDispatcher()


def scheduled_lora_for_context_menu() -> PromptScheduledLora:
    """Return one scheduled LoRA with trigger words for context-menu measurement."""

    return PromptScheduledLora(
        prompt_name="detail_booster",
        backend_value="detail_booster.safetensors",
        display_name="Detail Booster",
        trained_words=("detail", "texture"),
        source="cube_field",
    )


def lora_catalog_item() -> PromptLoraCatalogItem:
    """Return one deterministic LoRA catalog item for autocomplete scenarios."""

    return PromptLoraCatalogItem(
        display_name="Detail Booster",
        display_subtitle="local",
        prompt_name="detail_booster",
        backend_value="detail_booster.safetensors",
        relative_path="styles/detail_booster.safetensors",
        folder="styles",
        basename="detail_booster",
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="SDXL",
        trained_words=("detail", "texture"),
        tags=("style",),
        model_page_url=None,
        collision_key="detail_booster",
        collision_count=1,
        has_collision=False,
        search_text="detail booster styles detail texture",
    )
