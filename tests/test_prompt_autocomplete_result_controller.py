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

"""Verify Phase 27.4 autocomplete result/cache ownership."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptScheduledLora,
    PromptAutocompleteFallbackQuery,
    PromptAutocompleteQuery,
    effective_prompt_text_at_source_position,
    PromptLoraAutocompleteQuery,
    PromptLoraCatalogItem,
    PromptLoraThumbnailVariant,
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features.autocomplete_result_controller import (
    _AUTOCOMPLETE_RESULT_CACHE_LIMIT,
    PromptAutocompleteResultController,
    PromptAutocompleteTagContext,
    PromptAutocompleteTriggerWordResult,
)
from substitute.presentation.editor.prompt_editor.features.catalog_snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptFeatureProfileController,
    PromptWildcardFeatureController,
)
from substitute.presentation.editor.prompt_editor.projection.autocomplete_ghost_text import (
    PromptAutocompleteGhostTextPublisher,
    PromptAutocompleteGhostTextSourceSnapshot,
)
from substitute.presentation.editor.prompt_editor.features.wildcard_controller import (
    PromptWildcardAutocompleteQuerySnapshot,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession
from tests.prompt_autocomplete_test_helpers import build_test_autocomplete_coordinator
from tests.prompt_editor_controller_test_helpers import (
    AutocompleteEditorDouble,
    DeferredScheduledLoraContextProvider,
    EmptyAutocompleteGateway,
    FakeWildcardRequestChannel,
    MenuCursorDouble,
    TextAutocompleteEditorDouble,
    autocomplete_session_controller_with_session,
    import_autocomplete_module,
    prompt_lora_catalog_item,
    scene_feature,
)


class _Gateway:
    """Record autocomplete gateway searches and return configured rows."""

    cache_revision = 0

    def __init__(
        self,
        rows_by_prefix: dict[str, tuple[PromptAutocompleteSuggestion, ...]],
    ) -> None:
        """Store deterministic rows for result tests."""

        self.rows_by_prefix = rows_by_prefix
        self.calls: list[tuple[str, int]] = []

    def search(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return configured rows while recording lookup calls."""

        self.calls.append((prefix, limit))
        return self.rows_by_prefix.get(prefix, ())


class _TriggerProvider:
    """Return configured trigger rows and signatures."""

    def __init__(
        self,
        *,
        rows: tuple[PromptAutocompleteSuggestion, ...] = (),
        signature: tuple[tuple[str, str, str, tuple[str, ...], str], ...] = (),
    ) -> None:
        """Store deterministic trigger-word output."""

        self.rows = rows
        self.signature = signature
        self.calls: list[tuple[str, str, str, object | None, Hashable | None]] = []

    def trigger_word_suggestions(
        self,
        prefix: str,
        prompt_text: str,
        *,
        source_text: str,
        source_identity: object | None,
        query_identity: Hashable | None,
    ) -> PromptAutocompleteTriggerWordResult:
        """Return configured trigger rows and record context inputs."""

        self.calls.append(
            (prefix, prompt_text, source_text, source_identity, query_identity)
        )
        if self.rows and prefix != "1g":
            return PromptAutocompleteTriggerWordResult(
                suggestions=(),
                scheduled_lora_signature=(),
            )
        return PromptAutocompleteTriggerWordResult(
            suggestions=self.rows,
            scheduled_lora_signature=self.signature,
        )


@dataclass(slots=True)
class _WildcardProvider:
    """Return one configured wildcard snapshot."""

    snapshot: PromptWildcardAutocompleteQuerySnapshot

    def wildcard_autocomplete_snapshot(
        self,
        *,
        prefix: str,
        limit: int,
        source_identity: object | None = None,
        query_identity: Hashable | None = None,
        current_query_identity: Callable[[], Hashable | None] | None = None,
        refresh_current_query: Callable[[], None] | None = None,
    ) -> PromptWildcardAutocompleteQuerySnapshot:
        """Return the configured snapshot and ignore refresh callbacks."""

        _ = (
            prefix,
            limit,
            source_identity,
            query_identity,
            current_query_identity,
            refresh_current_query,
        )
        return self.snapshot


class _SceneProvider:
    """Return configured scene autocomplete rows."""

    def __init__(
        self,
        rows: tuple[PromptAutocompleteSuggestion, ...],
    ) -> None:
        """Store deterministic scene rows."""

        self.rows = rows

    def scene_autocomplete_suggestions(
        self,
        query: PromptSceneAutocompleteQuery,
        *,
        limit: int,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return scene rows up to the requested limit."""

        _ = query
        return self.rows[:limit]


class _LoraCatalog:
    """Return cached LoRA rows while rejecting foreground catalog loading."""

    cache_revision = 3

    def __init__(self, rows: tuple[PromptLoraCatalogItem, ...] | None) -> None:
        """Store cached rows and counters."""

        self.rows = rows
        self.cached_calls = 0
        self.list_calls = 0
        self.refresh_calls = 0

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return cached rows without loading."""

        self.cached_calls += 1
        return self.rows

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Fail if result refresh tries to load the catalog."""

        self.list_calls += 1
        raise AssertionError("LoRA autocomplete must not call list_loras().")

    def refresh_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Fail if result refresh tries to refresh the catalog."""

        self.refresh_calls += 1
        raise AssertionError("LoRA autocomplete must not call refresh_loras().")


class _FailingLoraCatalog:
    """Raise from cached LoRA access to verify fail-closed error state."""

    cache_revision = 4

    @staticmethod
    def cached_loras() -> tuple[PromptLoraCatalogItem, ...] | None:
        """Raise a cache access error."""

        raise RuntimeError("catalog cache unavailable")


class _TrackingLoraCatalog(_LoraCatalog):
    """Return cached LoRA rows while recording every catalog access path."""

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Record passive loads without forcing a backend refresh."""

        self.list_calls += 1
        if self.rows is None:
            return ()
        return self.rows

    def refresh_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Record refresh requests without reaching any external backend."""

        self.refresh_calls += 1
        if self.rows is None:
            return ()
        return self.rows


class _CountingThumbnailAssetRepository:
    """Count thumbnail asset reads for autocomplete thumbnail-loading guards."""

    def __init__(self) -> None:
        """Initialize read accounting."""

        self.reads = 0

    def read_thumbnail_asset(self, storage_key: str) -> None:
        """Record a thumbnail read and return no asset."""

        _ = storage_key
        self.reads += 1


def _source_identity(revision: int, length: int) -> PromptCommandSourceIdentity:
    """Return a command source identity for result freshness tests."""

    return PromptCommandSourceIdentity(source_revision=revision, source_length=length)


def _tag_query(prefix: str) -> PromptAutocompleteQuery:
    """Return a simple tag query for the supplied prefix."""

    return PromptAutocompleteQuery(
        prefix=prefix,
        word_start=0,
        word_end=len(prefix),
        active_tag_end=len(prefix),
    )


def _tag_context(
    text: str, *, effective_text: str | None = None
) -> PromptAutocompleteTagContext:
    """Return tag result context for tests."""

    return PromptAutocompleteTagContext(
        source_text=text,
        effective_prompt_text=text if effective_text is None else effective_text,
    )


def _lora_item() -> PromptLoraCatalogItem:
    """Return one deterministic LoRA catalog row."""

    return PromptLoraCatalogItem(
        display_name="Friendly Midna",
        display_subtitle=None,
        prompt_name="midna",
        backend_value="midna.safetensors",
        relative_path="midna.safetensors",
        folder="",
        basename="midna",
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=("midna helmet",),
        tags=(),
        model_page_url=None,
        collision_key="midna",
        collision_count=1,
        has_collision=False,
        search_text="midna friendly midna",
    )


def _coordinator_lora_item(
    *,
    display_name: str = "CivitAI Midna",
    basename: str = "raw_midna",
    prompt_name: str = r"illustrious\characters\raw_midna",
    thumbnail_variants: tuple[PromptLoraThumbnailVariant, ...] = (),
) -> PromptLoraCatalogItem:
    """Return the LoRA catalog row used by coordinator refresh tests."""

    return prompt_lora_catalog_item(
        display_name=display_name,
        basename=basename,
        prompt_name=prompt_name,
        thumbnail_variants=thumbnail_variants,
    )


def _lora_query() -> PromptLoraAutocompleteQuery:
    """Return a LoRA query that matches the deterministic catalog row."""

    return PromptLoraAutocompleteQuery(
        query_text="mid",
        token_start=0,
        token_end=10,
        name_start=6,
        name_end=9,
        replacement_start=0,
        replacement_end=10,
        typed_weight_text=None,
        has_closing_bracket=False,
    )


def _coordinator_lora_query() -> PromptLoraAutocompleteQuery:
    """Return a LoRA query that matches the coordinator catalog row."""

    return PromptLoraAutocompleteQuery(
        query_text="Civ",
        token_start=0,
        token_end=9,
        name_start=6,
        name_end=9,
        replacement_start=0,
        replacement_end=9,
        typed_weight_text=None,
        has_closing_bracket=False,
    )


def _thumbnail_variant(storage_key: str) -> PromptLoraThumbnailVariant:
    """Return one lightweight LoRA thumbnail variant reference."""

    return PromptLoraThumbnailVariant(
        size=128,
        storage_key=storage_key,
        width=85,
        height=128,
        content_format="sqthumb-qimage-argb32-premultiplied",
        byte_size=43520,
    )


def _mute_autocomplete_surfaces(coordinator: Any) -> Any:
    """Disable panel and ghost-text publication for focused result tests."""

    coordinator._present_panel = lambda: None
    coordinator._publish_inline_completion_preview = lambda: None
    return coordinator


def test_coordinator_retains_selected_suggestion_when_result_still_matches() -> None:
    """Coordinator tag refresh keeps the selected row when the tag still exists."""

    mod = import_autocomplete_module()
    suggestions = (
        PromptAutocompleteSuggestion("1girl", 5_889_398),
        PromptAutocompleteSuggestion("1girls", 3_424),
    )
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            suggestions=(PromptAutocompleteSuggestion("1girls", 3_424),),
            selected_index=0,
            word_start=0,
            word_end=3,
            active_tag_end=3,
            prefix="1gi",
        ),
    )
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_coordinator(
                SimpleNamespace(toPlainText=lambda: "1gi"),
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda _prefix, limit=10: suggestions
                ),
                autocomplete_session_controller=session_controller,
            ),
        )
    )

    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix="1gi",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text="1gi",
    )

    assert session_controller.session.suggestions == suggestions
    assert session_controller.session.selected_index == 1
    assert session_controller.session.word_start == 0
    assert session_controller.session.word_end == 3


def test_coordinator_clears_ghost_text_when_feature_disabled() -> None:
    """Disabling ghost text should keep autocomplete active and clear previews."""

    mod = import_autocomplete_module()
    editor = TextAutocompleteEditorDouble("1gi")
    publisher = PromptAutocompleteGhostTextPublisher(preview_sink=editor)
    source_snapshot = PromptAutocompleteGhostTextSourceSnapshot(
        source_revision=0,
        source_length=3,
        cursor_position=3,
        source_text="1gi",
    )
    seed_session = AutocompleteSession(
        suggestions=(PromptAutocompleteSuggestion("1girl", 5_889_398),),
        selected_index=0,
        word_start=0,
        word_end=3,
        active_tag_end=3,
        prefix="1gi",
    )
    publisher.publish_for_session(seed_session, source_snapshot=source_snapshot)
    session_controller = mod.PromptAutocompleteSessionController()
    coordinator = build_test_autocomplete_coordinator(
        editor,
        prompt_autocomplete_gateway=_Gateway(
            {"1gi": (PromptAutocompleteSuggestion("1girl", 5_889_398),)}
        ),
        autocomplete_ghost_text_publisher=publisher,
        autocomplete_ghost_text_enabled=False,
        autocomplete_session_controller=session_controller,
    )

    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix="1gi",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text="1gi",
        ghost_text_source_snapshot=source_snapshot,
    )

    assert editor.autocomplete_preview_updates[-1] is None
    assert session_controller.has_active_session()
    assert session_controller.session.suggestions == (
        PromptAutocompleteSuggestion("1girl", 5_889_398),
    )


def test_coordinator_uses_prepared_source_text_snapshot() -> None:
    """Coordinator tag refresh should not read editor text while preparing results."""

    class _CountingTextEditor:
        """Count prompt text reads for one autocomplete refresh."""

        def __init__(self) -> None:
            """Initialize the editor text read counter."""

            self.reads = 0

        def toPlainText(self) -> str:
            """Return fixed prompt text while recording one read."""

            self.reads += 1
            return "1gi"

    editor = _CountingTextEditor()
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_coordinator(
                editor,
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda _prefix, limit=10: (
                        PromptAutocompleteSuggestion("1girl", 5_889_398),
                    )
                ),
            ),
        )
    )

    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix="1gi",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text="1gi",
    )

    assert editor.reads == 0
    assert coordinator._sessions.session.suggestions == (
        PromptAutocompleteSuggestion("1girl", 5_889_398),
    )


def test_coordinator_falls_back_to_current_suffix_after_long_miss() -> None:
    """Long scene lines still complete the current tag when the full line misses."""

    source = "**scene\n" + ("background detail " * 10) + "1g"
    full_prefix = source[source.index("background") :]
    calls: list[str] = []
    suffix_suggestion = PromptAutocompleteSuggestion("1girl", 5_889_398)

    def search(
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return a suggestion only for the suffix fallback prefix."""

        calls.append(prefix)
        _ = limit
        return (suffix_suggestion,) if prefix == "1g" else ()

    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_coordinator(
                TextAutocompleteEditorDouble(source),
                prompt_autocomplete_gateway=SimpleNamespace(search=search),
            ),
        )
    )

    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix=full_prefix,
            word_start=source.index("background"),
            word_end=len(source),
            active_tag_end=len(source),
            fallback_query=PromptAutocompleteFallbackQuery(
                prefix="1g",
                word_start=source.rindex("1g"),
                word_end=len(source),
                active_tag_end=len(source),
            ),
        ),
        source_text=source,
    )

    assert calls == [full_prefix, "1g"]
    assert coordinator._sessions.session.suggestions == (suffix_suggestion,)
    assert coordinator._sessions.session.prefix == "1g"
    assert coordinator._sessions.session.word_start == source.rindex("1g")
    assert coordinator._sessions.session.word_end == len(source)
    assert coordinator._sessions.session.active_tag_end == len(source)


def test_coordinator_preserves_matching_multi_word_tag_prefix() -> None:
    """Suffix fallback must not steal valid multi-word tag completions."""

    source = "long h"
    calls: list[str] = []
    suggestion = PromptAutocompleteSuggestion("long hair", 4_000_000)

    def search(
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return a match for the full multi-word prefix only."""

        calls.append(prefix)
        _ = limit
        return (suggestion,) if prefix == "long h" else ()

    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_coordinator(
                TextAutocompleteEditorDouble(source),
                prompt_autocomplete_gateway=SimpleNamespace(search=search),
            ),
        )
    )

    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix="long h",
            word_start=0,
            word_end=len(source),
            active_tag_end=len(source),
        ),
        source_text=source,
    )

    assert calls == ["long h"]
    assert coordinator._sessions.session.suggestions == (suggestion,)
    assert coordinator._sessions.session.prefix == "long h"
    assert coordinator._sessions.session.word_start == 0


def test_coordinator_merges_lora_trigger_suggestions_before_static_tags() -> None:
    """Scheduled-LoRA trigger words are ranked before static tag matches."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("midna helmet",),
        source="inline_prompt",
    )
    provider = DeferredScheduledLoraContextProvider(lambda _text: (scheduled_lora,))
    provider.cache_prompt("mid")
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_coordinator(
                SimpleNamespace(toPlainText=lambda: "mid"),
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda _prefix, limit=10: (
                        PromptAutocompleteSuggestion("mid shot", 200),
                    )
                ),
                scheduled_lora_context_provider=provider,
            ),
        )
    )

    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text="mid",
    )

    assert [
        (suggestion.tag, suggestion.source_label, suggestion.source_kind)
        for suggestion in coordinator._sessions.session.suggestions
    ] == [
        ("midna helmet", "Friendly Midna", "lora_trigger"),
        ("mid shot", None, "tag"),
    ]


def test_coordinator_dedupes_static_tag_when_lora_trigger_matches() -> None:
    """Duplicate static tags collapse into the scheduled-LoRA trigger row."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("midna helmet",),
        source="inline_prompt",
    )
    provider = DeferredScheduledLoraContextProvider(lambda _text: (scheduled_lora,))
    provider.cache_prompt("mid")
    coordinator = _mute_autocomplete_surfaces(
        build_test_autocomplete_coordinator(
            TextAutocompleteEditorDouble("mid"),
            prompt_autocomplete_gateway=SimpleNamespace(
                search=lambda _prefix, limit=10: (
                    PromptAutocompleteSuggestion("midna_helmet", 200),
                )
            ),
            scheduled_lora_context_provider=provider,
        )
    )

    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text="mid",
    )

    assert coordinator._sessions.session.suggestions == (
        PromptAutocompleteSuggestion(
            "midna helmet",
            popularity=None,
            source_label="Friendly Midna",
            source_kind="lora_trigger",
        ),
    )


def test_coordinator_dedupes_static_tag_when_split_lora_trigger_matches() -> None:
    """Split CivitAI trigger parts still replace duplicate static tag rows."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="ranni",
        backend_value="ranni.safetensors",
        display_name="Ranni XL",
        trained_words=("ranni elden ring, witch hat",),
        source="inline_prompt",
    )
    provider = DeferredScheduledLoraContextProvider(lambda _text: (scheduled_lora,))
    provider.cache_prompt("witch")
    coordinator = _mute_autocomplete_surfaces(
        build_test_autocomplete_coordinator(
            TextAutocompleteEditorDouble("witch"),
            prompt_autocomplete_gateway=SimpleNamespace(
                search=lambda _prefix, limit=10: (
                    PromptAutocompleteSuggestion("witch_hat", 200),
                )
            ),
            scheduled_lora_context_provider=provider,
        )
    )

    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix="witch",
            word_start=0,
            word_end=5,
            active_tag_end=5,
        ),
        source_text="witch",
    )

    assert coordinator._sessions.session.suggestions == (
        PromptAutocompleteSuggestion(
            "witch hat",
            popularity=None,
            source_label="Ranni XL",
            source_kind="lora_trigger",
        ),
    )


def test_coordinator_uses_scene_effective_lora_trigger_context() -> None:
    """Scene-local trigger suggestions come from the active scene context."""

    global_lora = PromptScheduledLora(
        prompt_name="global",
        backend_value="global.safetensors",
        display_name="Global LoRA",
        trained_words=("midna global",),
        source="inline_prompt",
    )
    portrait_lora = PromptScheduledLora(
        prompt_name="portrait",
        backend_value="portrait.safetensors",
        display_name="Portrait LoRA",
        trained_words=("midna portrait",),
        source="inline_prompt",
    )
    source = "<lora:global:1>\n**portrait\n<lora:portrait:1>\nmid\n**cafe\nmid"
    resolver_calls: list[str] = []

    def resolve_scheduled_loras(
        prompt_text: str,
    ) -> tuple[PromptScheduledLora, ...]:
        """Return LoRAs visible from the effective prompt text."""

        resolver_calls.append(prompt_text)
        loras = [global_lora]
        if "<lora:portrait:1>" in prompt_text:
            loras.append(portrait_lora)
        return tuple(loras)

    provider = DeferredScheduledLoraContextProvider(resolve_scheduled_loras)
    portrait_mid = source.index("mid")
    cafe_mid = source.rindex("mid")
    provider.cache_prompt(
        effective_prompt_text_at_source_position(
            text=source,
            source_position=portrait_mid,
        )
    )
    provider.cache_prompt(
        effective_prompt_text_at_source_position(
            text=source,
            source_position=cafe_mid,
        )
    )
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_coordinator(
                TextAutocompleteEditorDouble(source),
                prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
                scene_feature=scene_feature(text=source, titles=()),
                scheduled_lora_context_provider=provider,
            ),
        )
    )

    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=portrait_mid,
            word_end=portrait_mid + 3,
            active_tag_end=portrait_mid + 3,
        ),
        source_text=source,
    )

    assert [
        suggestion.tag for suggestion in coordinator._sessions.session.suggestions
    ] == [
        "midna global",
        "midna portrait",
    ]

    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=cafe_mid,
            word_end=cafe_mid + 3,
            active_tag_end=cafe_mid + 3,
        ),
        source_text=source,
    )

    assert [
        suggestion.tag for suggestion in coordinator._sessions.session.suggestions
    ] == [
        "midna global",
    ]
    assert "<lora:portrait:1>" in resolver_calls[0]
    assert "<lora:portrait:1>" not in resolver_calls[1]


def test_coordinator_uses_static_tags_while_trigger_context_resolves() -> None:
    """Cold async trigger-word context does not block static tag autocomplete."""

    editor = TextAutocompleteEditorDouble("mid")
    resolver_calls: list[str] = []

    def resolve_scheduled_loras(prompt_text: str) -> tuple[PromptScheduledLora, ...]:
        """Record one resolver call while returning no LoRAs."""

        resolver_calls.append(prompt_text)
        return ()

    provider = DeferredScheduledLoraContextProvider(resolve_scheduled_loras)
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_coordinator(
                editor,
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda _prefix, limit=10: (
                        PromptAutocompleteSuggestion("mid shot", 200),
                    )
                ),
                scheduled_lora_context_provider=provider,
            ),
        )
    )

    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text=editor.text,
    )

    assert resolver_calls == []
    assert len(provider.jobs) == 1
    assert coordinator._sessions.session.suggestions == (
        PromptAutocompleteSuggestion("mid shot", 200),
    )


def test_coordinator_skips_duplicate_refresh_for_empty_async_trigger_context() -> None:
    """Empty async trigger-word results do not redraw unchanged tag suggestions."""

    editor = TextAutocompleteEditorDouble("mid")
    provider = DeferredScheduledLoraContextProvider(lambda _text: ())
    panel_updates = 0
    preview_updates = 0
    coordinator = cast(
        Any,
        build_test_autocomplete_coordinator(
            editor,
            prompt_autocomplete_gateway=SimpleNamespace(
                search=lambda _prefix, limit=10: (
                    PromptAutocompleteSuggestion("mid shot", 200),
                )
            ),
            scheduled_lora_context_provider=provider,
        ),
    )

    def record_panel_update() -> bool:
        """Record one panel refresh and report visible presentation."""

        nonlocal panel_updates
        panel_updates += 1
        return True

    def record_preview_update() -> None:
        """Record one inline preview refresh."""

        nonlocal preview_updates
        preview_updates += 1

    coordinator._present_panel = record_panel_update
    coordinator._publish_inline_completion_preview = record_preview_update

    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text=editor.text,
    )
    provider.complete()

    assert panel_updates == 1
    assert preview_updates == 1
    assert coordinator._sessions.session.suggestions == (
        PromptAutocompleteSuggestion("mid shot", 200),
    )


def test_coordinator_applies_async_trigger_words_for_current_query() -> None:
    """Completed async trigger-word context refreshes the current tag session."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("midna helmet",),
        source="inline_prompt",
    )
    editor = TextAutocompleteEditorDouble("mid")
    provider = DeferredScheduledLoraContextProvider(lambda _text: (scheduled_lora,))
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_coordinator(
                editor,
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda _prefix, limit=10: (
                        PromptAutocompleteSuggestion("mid shot", 200),
                    )
                ),
                scheduled_lora_context_provider=provider,
            ),
        )
    )

    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text=editor.text,
    )
    provider.complete()

    assert [
        (suggestion.tag, suggestion.source_label, suggestion.source_kind)
        for suggestion in coordinator._sessions.session.suggestions
    ] == [
        ("midna helmet", "Friendly Midna", "lora_trigger"),
        ("mid shot", None, "tag"),
    ]


def test_coordinator_discards_stale_async_trigger_words() -> None:
    """Older async trigger-word results must not replace the active tag query."""

    stale_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("midna helmet",),
        source="inline_prompt",
    )
    current_lora = PromptScheduledLora(
        prompt_name="ranni",
        backend_value="ranni.safetensors",
        display_name="Ranni XL",
        trained_words=("ranni hat",),
        source="inline_prompt",
    )
    editor = TextAutocompleteEditorDouble("mid")
    resolver_results = [(stale_lora,), (current_lora,)]

    def resolve_scheduled_loras(_text: str) -> tuple[PromptScheduledLora, ...]:
        """Return queued scheduled-LoRA results in request order."""

        return resolver_results.pop(0)

    provider = DeferredScheduledLoraContextProvider(resolve_scheduled_loras)
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_coordinator(
                editor,
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda prefix, limit=10: (
                        PromptAutocompleteSuggestion(f"{prefix} static", 200),
                    )
                ),
                scheduled_lora_context_provider=provider,
            ),
        )
    )

    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text=editor.text,
    )
    editor.text = "ran"
    editor.source_revision += 1
    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix="ran",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text=editor.text,
    )
    provider.complete(index=0)

    assert [
        suggestion.tag for suggestion in coordinator._sessions.session.suggestions
    ] == ["ran static"]

    provider.complete(index=0)

    assert [
        suggestion.tag for suggestion in coordinator._sessions.session.suggestions
    ] == [
        "ranni hat",
        "ran static",
    ]


def test_coordinator_uses_wildcard_catalog_gateway() -> None:
    """Wildcard autocomplete presents prepared wildcard catalog rows."""

    suggestions = (
        PromptAutocompleteSuggestion(
            "animal",
            source_label="TXT wildcard",
            source_kind="wildcard",
        ),
    )
    calls: list[tuple[str, int]] = []

    class _WildcardCatalogGateway:
        """Record wildcard searches and return deterministic suggestions."""

        def search_wildcards(
            self,
            prefix: str,
            limit: int = 10,
        ) -> tuple[PromptAutocompleteSuggestion, ...]:
            """Return configured wildcard suggestions for the requested prefix."""

            calls.append((prefix, limit))
            return suggestions

    request_channel = FakeWildcardRequestChannel()
    wildcard_feature = PromptWildcardFeatureController(
        feature_profile=PromptFeatureProfileController(
            PromptEditorFeatureProfile.enabled_profile(
                (PromptEditorFeature.WILDCARD_AUTOCOMPLETE,)
            )
        ),
        wildcard_catalog_gateway=cast(
            PromptWildcardCatalogGateway,
            _WildcardCatalogGateway(),
        ),
        request_channel=request_channel,
    )
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_coordinator(
                SimpleNamespace(toPlainText=lambda: "{"),
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda _prefix, limit=10: ()
                ),
                wildcard_feature=cast(Any, wildcard_feature),
            ),
        )
    )

    coordinator.refresh_for_wildcard_query(
        PromptWildcardAutocompleteQuery(
            prefix="",
            opener_start=0,
            content_start=1,
            cursor_position=1,
            replacement_end=1,
        )
    )

    assert calls == []
    assert coordinator._sessions.session.mode == "none"
    assert len(request_channel.handles) == 1

    request_channel.handles[-1].run_work()

    assert calls == [("", 10)]
    assert coordinator._sessions.session.mode == "wildcard"
    assert coordinator._sessions.session.suggestions == suggestions
    assert coordinator._sessions.session.word_start == 0


def test_coordinator_uses_authority_scene_titles() -> None:
    """Scene autocomplete searches workflow-provided authority scene names."""

    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_coordinator(
                SimpleNamespace(toPlainText=lambda: "**p"),
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda _prefix, limit=10: ()
                ),
                scene_feature=scene_feature(
                    text="**p",
                    titles=("portrait", "cafe interior"),
                ),
            ),
        )
    )

    coordinator.refresh_for_scene_query(
        PromptSceneAutocompleteQuery(
            prefix="p",
            marker_start=0,
            title_start=2,
            cursor_position=3,
            replacement_end=3,
        )
    )

    assert coordinator._sessions.session.mode == "scene"
    assert coordinator._sessions.session.suggestions == (
        PromptAutocompleteSuggestion(
            "portrait",
            popularity=None,
            source_label="Scene",
            source_kind="scene",
        ),
    )
    assert coordinator._sessions.session.word_start == 2


def test_coordinator_clears_scene_query_when_authority_titles_are_empty() -> None:
    """Scene autocomplete stays hidden when no reusable titles are configured."""

    coordinator = cast(
        Any,
        build_test_autocomplete_coordinator(
            SimpleNamespace(toPlainText=lambda: "**p"),
            prompt_autocomplete_gateway=SimpleNamespace(
                search=lambda _prefix, limit=10: ()
            ),
            scene_feature=scene_feature(
                text="**p",
                titles=(),
            ),
        ),
    )
    cleared: list[bool] = []
    coordinator.dismiss_autocomplete = lambda _reason: cleared.append(True)

    coordinator.refresh_for_scene_query(
        PromptSceneAutocompleteQuery(
            prefix="p",
            marker_start=0,
            title_start=2,
            cursor_position=3,
            replacement_end=3,
        )
    )

    assert cleared == [True]


def test_coordinator_filters_exact_scene_title_matches() -> None:
    """Scene autocomplete does not offer a no-op exact title replacement."""

    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_coordinator(
                SimpleNamespace(toPlainText=lambda: "**portrait"),
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda _prefix, limit=10: ()
                ),
                scene_feature=scene_feature(
                    text="**portrait",
                    titles=("portrait", "portrait close"),
                ),
            ),
        )
    )

    coordinator.refresh_for_scene_query(
        PromptSceneAutocompleteQuery(
            prefix="portrait",
            marker_start=0,
            title_start=2,
            cursor_position=10,
            replacement_end=10,
        )
    )

    assert coordinator._sessions.session.mode == "scene"
    assert [
        suggestion.tag for suggestion in coordinator._sessions.session.suggestions
    ] == ["portrait close"]


def test_coordinator_filters_noop_tag_suggestions_before_opening_session() -> None:
    """Coordinator refresh suppresses suggestions that already match the query slice."""

    coordinator = _mute_autocomplete_surfaces(
        build_test_autocomplete_coordinator(
            AutocompleteEditorDouble(
                MenuCursorDouble(text="looking at viewer", position=17)
            ),
            prompt_autocomplete_gateway=SimpleNamespace(
                search=lambda _prefix, limit=10: (
                    PromptAutocompleteSuggestion("looking_at_viewer", 500),
                )
            ),
        )
    )

    coordinator.refresh_for_query(
        PromptAutocompleteQuery(
            prefix="looking at viewer",
            word_start=0,
            word_end=17,
            active_tag_end=17,
        ),
        source_text="looking at viewer",
    )

    assert coordinator._sessions.session.suggestions == ()


def test_coordinator_builds_lora_session_without_tag_gateway() -> None:
    """LoRA autocomplete refresh ranks cached catalog rows through the LoRA path."""

    lora = _coordinator_lora_item()
    coordinator = _mute_autocomplete_surfaces(
        build_test_autocomplete_coordinator(
            AutocompleteEditorDouble(
                MenuCursorDouble(text="<lora:Civ", position=len("<lora:Civ"))
            ),
            prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
            prompt_lora_catalog_service=_LoraCatalog((lora,)),
            lora_thumbnail_cache_available=True,
        )
    )

    coordinator.refresh_for_lora_query(_coordinator_lora_query())

    assert coordinator._sessions.session.mode == "lora"
    assert coordinator._sessions.session.selected_index == 0
    assert coordinator._sessions.session.lora_candidates[0].item is lora
    assert (
        coordinator._sessions.session.lora_candidates[0].replacement_text
        == r"<lora:illustrious\characters\raw_midna:1.00>"
    )


def test_coordinator_uses_cached_loras_without_backend_reads() -> None:
    """LoRA autocomplete does not refresh or cold-load the catalog while typing."""

    lora = _coordinator_lora_item()
    catalog = _TrackingLoraCatalog((lora,))
    coordinator = _mute_autocomplete_surfaces(
        build_test_autocomplete_coordinator(
            AutocompleteEditorDouble(
                MenuCursorDouble(text="<lora:Civ", position=len("<lora:Civ"))
            ),
            prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
            prompt_lora_catalog_service=catalog,
            lora_thumbnail_cache_available=True,
        )
    )
    query = _coordinator_lora_query()

    coordinator.refresh_for_lora_query(query)
    coordinator.refresh_for_lora_query(query)

    assert catalog.refresh_calls == 0
    assert catalog.list_calls == 0
    assert catalog.cached_calls == 2
    assert coordinator._sessions.session.mode == "lora"


def test_coordinator_cold_lora_cache_returns_no_candidates() -> None:
    """Cold LoRA autocomplete cache does not block typing with backend reads."""

    catalog = _TrackingLoraCatalog(None)
    coordinator = _mute_autocomplete_surfaces(
        build_test_autocomplete_coordinator(
            AutocompleteEditorDouble(
                MenuCursorDouble(text="<lora:Civ", position=len("<lora:Civ"))
            ),
            prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
            prompt_lora_catalog_service=catalog,
            lora_thumbnail_cache_available=True,
        )
    )

    coordinator.refresh_for_lora_query(_coordinator_lora_query())

    assert catalog.refresh_calls == 0
    assert catalog.list_calls == 0
    assert catalog.cached_calls == 1
    assert coordinator._sessions.session.mode == "none"
    assert coordinator._sessions.session.lora_candidates == ()


def test_coordinator_lora_refresh_does_not_load_thumbnail_assets() -> None:
    """LoRA autocomplete refresh does not decode thumbnail assets while typing."""

    asset_repository = _CountingThumbnailAssetRepository()
    items = tuple(
        _coordinator_lora_item(
            display_name=f"CivitAI LoRA {index:03}",
            basename=f"lora_{index:03}",
            prompt_name=rf"illustrious\characters\lora_{index:03}",
            thumbnail_variants=(_thumbnail_variant(f"lora_{index:03}:128"),),
        )
        for index in range(200)
    )
    coordinator = _mute_autocomplete_surfaces(
        build_test_autocomplete_coordinator(
            AutocompleteEditorDouble(MenuCursorDouble(text="<lora:Civ", position=9)),
            prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
            prompt_lora_catalog_service=_LoraCatalog(items),
            lora_thumbnail_cache_available=True,
        )
    )

    coordinator.refresh_for_lora_query(_coordinator_lora_query())

    assert len(coordinator._sessions.session.lora_candidates) == 200
    assert asset_repository.reads == 0


def test_tag_results_preserve_cache_identity_and_eviction() -> None:
    """Tag result caching is source-aware and bounded."""

    gateway = _Gateway(
        {
            "ha": (PromptAutocompleteSuggestion("hair ornament", 100),),
            **{
                f"h{index}": (PromptAutocompleteSuggestion(f"h{index} completion", 1),)
                for index in range(_AUTOCOMPLETE_RESULT_CACHE_LIMIT + 2)
            },
        }
    )
    controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=gateway,
        limit=10,
    )

    first = controller.result_for_tag_query(
        _tag_query("ha"),
        context=_tag_context("ha"),
        source_identity=_source_identity(1, 2),
    )
    second = controller.result_for_tag_query(
        _tag_query("ha"),
        context=_tag_context("ha"),
        source_identity=_source_identity(1, 2),
    )
    changed_source = controller.result_for_tag_query(
        _tag_query("ha"),
        context=_tag_context("ha"),
        source_identity=_source_identity(2, 2),
    )

    assert gateway.calls[:2] == [("ha", 10), ("ha", 10)]
    assert first.cache_key == second.cache_key
    assert second.cache_key != changed_source.cache_key

    first_evicted_key = None
    for index in range(_AUTOCOMPLETE_RESULT_CACHE_LIMIT + 2):
        prefix = f"h{index}"
        result = controller.result_for_tag_query(
            _tag_query(prefix),
            context=_tag_context(prefix),
            source_identity=_source_identity(index + 10, len(prefix)),
        )
        if index == 0:
            first_evicted_key = result.cache_key

    assert controller.cached_tag_result_count == _AUTOCOMPLETE_RESULT_CACHE_LIMIT
    assert first_evicted_key not in controller.cached_tag_result_keys()


def test_tag_result_cache_misses_when_trigger_signature_changes() -> None:
    """Scheduled-LoRA trigger signatures participate in tag result cache identity."""

    gateway = _Gateway({"ha": (PromptAutocompleteSuggestion("hair ornament", 4100),)})
    trigger_provider = _TriggerProvider()
    controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=gateway,
        trigger_word_provider=trigger_provider,
        limit=10,
    )

    first = controller.result_for_tag_query(
        _tag_query("ha"),
        context=_tag_context("ha"),
        source_identity=_source_identity(8, 2),
    )
    second = controller.result_for_tag_query(
        _tag_query("ha"),
        context=_tag_context("ha"),
        source_identity=_source_identity(8, 2),
    )
    trigger_provider.signature = (
        ("inline_prompt", "midna", "Friendly Midna", ("midna helmet",), "midna"),
    )
    third = controller.result_for_tag_query(
        _tag_query("ha"),
        context=_tag_context("ha"),
        source_identity=_source_identity(8, 2),
    )

    assert gateway.calls == [("ha", 10), ("ha", 10)]
    assert first.cache_key == second.cache_key
    assert second.cache_key != third.cache_key


def test_tag_results_preserve_fallback_filtering_trigger_merge_and_signature() -> None:
    """Tag results preserve fallback, no-op filtering, trigger ordering, and signatures."""

    gateway = _Gateway(
        {
            "very long prompt 1g": (),
            "1g": (
                PromptAutocompleteSuggestion("1girl", 100),
                PromptAutocompleteSuggestion("1girls", 50),
            ),
        }
    )
    trigger_provider = _TriggerProvider(
        rows=(
            PromptAutocompleteSuggestion(
                "1girl",
                popularity=None,
                source_label="Trigger LoRA",
                source_kind="lora_trigger",
            ),
            PromptAutocompleteSuggestion("1g trigger", popularity=None),
        ),
        signature=(("lora", "backend", "Trigger LoRA", (), ""),),
    )
    controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=gateway,
        trigger_word_provider=trigger_provider,
        limit=10,
    )
    source_text = "very long prompt 1g"

    result = controller.result_for_tag_query(
        PromptAutocompleteQuery(
            prefix=source_text,
            word_start=0,
            word_end=len(source_text),
            active_tag_end=len(source_text),
            fallback_query=PromptAutocompleteFallbackQuery(
                prefix="1g",
                word_start=source_text.rindex("1g"),
                word_end=len(source_text),
                active_tag_end=len(source_text),
            ),
        ),
        context=_tag_context(source_text, effective_text="scene effective 1g"),
        source_identity=_source_identity(4, len(source_text)),
    )
    no_op_result = controller.result_for_tag_query(
        _tag_query("1girl"),
        context=_tag_context("1girl"),
        source_identity=_source_identity(5, len("1girl")),
    )

    assert gateway.calls == [(source_text, 10), ("1g", 10), ("1girl", 10)]
    assert [suggestion.tag for suggestion in result.suggestions] == [
        "1girl",
        "1g trigger",
        "1girls",
    ]
    assert result.prefix == "1g"
    assert result.had_candidates is True
    assert trigger_provider.calls[1][1] == "scene effective 1g"
    assert all(suggestion.tag != "1girl" for suggestion in no_op_result.suggestions)


def test_wildcard_and_scene_results_consume_prepared_feature_snapshots() -> None:
    """Wildcard and scene result paths adapt prepared feature rows into snapshots."""

    wildcard_query = PromptWildcardAutocompleteQuery(
        prefix="land",
        opener_start=0,
        content_start=1,
        cursor_position=5,
        replacement_end=6,
    )
    wildcard_snapshot = PromptWildcardAutocompleteQuerySnapshot(
        identity=CatalogSnapshotIdentity(query_identity=("wildcard", 1)),
        status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
        prefix="land",
        limit=10,
        suggestions=(PromptAutocompleteSuggestion("landscape", 30),),
    )
    scene_query = PromptSceneAutocompleteQuery(
        prefix="in",
        marker_start=0,
        title_start=8,
        cursor_position=10,
        replacement_end=10,
    )
    controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=_Gateway({}),
        wildcard_feature=_WildcardProvider(wildcard_snapshot),
        scene_feature=_SceneProvider((PromptAutocompleteSuggestion("intro", 1),)),
        limit=10,
    )

    wildcard_result = controller.result_for_wildcard_query(
        wildcard_query,
        source_identity=None,
    )
    scene_result = controller.result_for_scene_query(scene_query, source_identity=None)

    assert wildcard_result.status == "ready"
    assert wildcard_result.suggestions == (
        PromptAutocompleteSuggestion("landscape", 30),
    )
    assert wildcard_result.word_start == wildcard_query.opener_start
    assert scene_result.status == "ready"
    assert scene_result.suggestions == (PromptAutocompleteSuggestion("intro", 1),)
    assert scene_result.word_start == scene_query.title_start


def test_lora_results_use_cached_catalog_and_fail_closed() -> None:
    """LoRA result preparation consumes cached rows only and returns safe empty/error states."""

    catalog = _LoraCatalog((_lora_item(),))
    controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=_Gateway({}),
        prompt_lora_catalog_service=catalog,
        limit=10,
    )

    ready = controller.result_for_lora_query(
        _lora_query(),
        source_identity=None,
        enabled=True,
        thumbnail_cache_available=True,
    )
    disabled = controller.result_for_lora_query(
        _lora_query(),
        source_identity=None,
        enabled=False,
        thumbnail_cache_available=True,
    )
    no_thumbnail = controller.result_for_lora_query(
        _lora_query(),
        source_identity=None,
        enabled=True,
        thumbnail_cache_available=False,
    )
    failing = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=_Gateway({}),
        prompt_lora_catalog_service=_FailingLoraCatalog(),
        limit=10,
    ).result_for_lora_query(
        _lora_query(),
        source_identity=None,
        enabled=True,
        thumbnail_cache_available=True,
    )

    assert ready.status == "ready"
    assert ready.mode == "lora"
    assert ready.lora_candidates
    assert catalog.cached_calls == 1
    assert catalog.list_calls == 0
    assert catalog.refresh_calls == 0
    assert disabled.status == "empty"
    assert no_thumbnail.status == "empty"
    assert failing.status == "error"
    assert failing.error_reason == "lora_catalog_cache_error"
