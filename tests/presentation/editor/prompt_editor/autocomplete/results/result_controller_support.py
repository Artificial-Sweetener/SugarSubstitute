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

"""Shared deterministic support for autocomplete result-controller contracts."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Any

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
)
from substitute.application.prompt_editor.autocomplete.queries import (
    PromptAutocompleteQuery,
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from substitute.application.prompt_editor.lora.autocomplete import (
    PromptLoraAutocompleteQuery,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
    PromptLoraThumbnailVariant,
)
from substitute.presentation.editor.prompt_editor.features.autocomplete_result_controller import (
    PromptAutocompleteTagContext,
    PromptAutocompleteTriggerWordResult,
)
from substitute.presentation.editor.prompt_editor.features.wildcard_models import (
    PromptWildcardAutocompleteQuerySnapshot,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession
from tests.support.prompt_editor.autocomplete_support import (
    PromptAutocompleteTestStack,
    build_autocomplete_query_state,
)
from tests.support.prompt_editor.controller_support import (
    prompt_lora_catalog_item,
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


class _RecordingAutocompletePresenter:
    """Record real presenter requests without creating a Qt panel."""

    def __init__(self) -> None:
        """Initialize a visible presentation recorder."""

        self.presented_sessions: list[AutocompleteSession] = []

    @property
    def panel(self) -> None:
        """Return no concrete panel for this focused result test."""

        return None

    def present_session(self, session: AutocompleteSession) -> bool:
        """Record one production presentation request."""

        self.presented_sessions.append(session)
        return True

    def set_activation_handler(self, handler: Callable[[Any], None] | None) -> None:
        """Accept coordinator activation wiring without invoking it."""

        _ = handler

    def set_selection_changed_handler(
        self,
        handler: Callable[[int], None] | None,
    ) -> None:
        """Accept coordinator selection wiring without invoking it."""

        _ = handler

    def set_visibility_changed_handler(
        self,
        handler: Callable[[bool], None] | None,
    ) -> None:
        """Accept coordinator visibility wiring without invoking it."""

        _ = handler

    def panel_under_mouse(self) -> bool:
        """Report no pointer ownership for focus-retention checks."""

        return False

    def panel_visible(self) -> bool:
        """Report the panel as visible after a successful present request."""

        return bool(self.presented_sessions)

    def hide(self) -> None:
        """Accept a hide request without retaining Qt state."""

    def move_lora_selection(self, direction: str) -> int | None:
        """Expose no LoRA-wall selection movement in this result test."""

        _ = direction
        return None


def _source_identity(revision: int, length: int) -> PromptSourceIdentity:
    """Return a command source identity for result freshness tests."""

    return PromptSourceIdentity(source_revision=revision, source_length=length)


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


def _mute_autocomplete_surfaces(
    autocomplete_stack: PromptAutocompleteTestStack,
) -> PromptAutocompleteTestStack:
    """Disable session presentation while retaining real result publication."""

    return autocomplete_stack


def _refresh_tag_result(
    autocomplete_stack: PromptAutocompleteTestStack,
    query: PromptAutocompleteQuery | None,
    *,
    source_text: str,
    source_identity: object | None = None,
) -> None:
    """Send a prepared tag state to the real query/result lifecycle."""

    autocomplete_stack.query_result_lifecycle.refresh_results_for_query_state(
        build_autocomplete_query_state(
            source_text=source_text,
            source_identity=source_identity,
            tag_query=query,
        )
    )


def _refresh_wildcard_result(
    autocomplete_stack: PromptAutocompleteTestStack,
    query: PromptWildcardAutocompleteQuery | None,
    *,
    source_identity: object | None = None,
) -> None:
    """Send a prepared wildcard state to the real query/result lifecycle."""

    autocomplete_stack.query_result_lifecycle.refresh_results_for_query_state(
        build_autocomplete_query_state(
            source_identity=source_identity,
            wildcard_query=query,
        )
    )


def _refresh_scene_result(
    autocomplete_stack: PromptAutocompleteTestStack,
    query: PromptSceneAutocompleteQuery | None,
    *,
    source_identity: object | None = None,
) -> None:
    """Send a prepared scene state to the real query/result lifecycle."""

    autocomplete_stack.query_result_lifecycle.refresh_results_for_query_state(
        build_autocomplete_query_state(
            source_identity=source_identity,
            scene_query=query,
        )
    )


def _refresh_lora_result(
    autocomplete_stack: PromptAutocompleteTestStack,
    query: PromptLoraAutocompleteQuery | None,
    *,
    source_identity: object | None = None,
) -> None:
    """Send a prepared LoRA state to the real query/result lifecycle."""

    autocomplete_stack.query_result_lifecycle.refresh_results_for_query_state(
        build_autocomplete_query_state(
            source_identity=source_identity,
            lora_query=query,
        )
    )
