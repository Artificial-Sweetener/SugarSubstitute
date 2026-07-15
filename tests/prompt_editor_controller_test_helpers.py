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

"""Shared doubles and builders for prompt-editor controller tests."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Hashable
from types import SimpleNamespace
from typing import Any

from PySide6.QtCore import Qt

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptLoraCatalogItem,
    PromptScheduledLora,
    PromptTriggerWordIndex,
    PromptLoraThumbnailVariant,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptAutocompleteAcceptance,
    PromptCommandResult,
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptAutocompleteTriggerWordResult,
    PromptEditorTaskHandle,
    PromptScheduledLoraContextProvider,
    autocomplete_suggestion_from_trigger_word,
    scheduled_lora_signature,
)
from substitute.presentation.editor.prompt_editor.async_work.scheduled_lora_dispatcher import (
    PromptScheduledLoraCachedContextSnapshot,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptFeatureProfileController,
    PromptSceneFeatureController,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession


def import_autocomplete_module() -> Any:
    """Import the concrete prompt autocomplete interaction module."""

    return importlib.import_module(
        "substitute.presentation.editor.prompt_editor.interactions.autocomplete_controller"
    )


def import_autocomplete_acceptance_module() -> Any:
    """Import the prompt autocomplete acceptance interaction module."""

    return importlib.import_module(
        "substitute.presentation.editor.prompt_editor.interactions.autocomplete_acceptance"
    )


def import_autocomplete_ghost_text_module() -> Any:
    """Import the projection-owned autocomplete ghost-text module."""

    return importlib.import_module(
        "substitute.presentation.editor.prompt_editor.projection.autocomplete_ghost_text"
    )


def autocomplete_session_controller_with_session(
    autocomplete_module: Any,
    session: AutocompleteSession,
) -> Any:
    """Return a session controller seeded with one active autocomplete session."""

    session_controller = autocomplete_module.PromptAutocompleteSessionController()
    session_controller._state = autocomplete_module.PromptAutocompleteSessionState(
        lifecycle="active",
        session=session,
    )
    return session_controller


def key_event(
    key: int,
    *,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    text: str = "",
) -> Any:
    """Return the minimal key-event shape consumed by controller tests."""

    return SimpleNamespace(
        key=lambda: key,
        modifiers=lambda: modifiers,
        text=lambda: text,
    )


class SceneFeatureHost:
    """Provide source identity and text for scene feature controller tests."""

    def __init__(self, text: str) -> None:
        """Store the prompt text returned to the scene feature."""

        self._text = text

    def toPlainText(self) -> str:
        """Return the configured prompt text."""

        return self._text

    def prompt_command_source_identity(self) -> None:
        """Return no source identity for pure autocomplete tests."""

        return None


def scene_feature(
    *,
    text: str,
    titles: tuple[str, ...],
) -> PromptSceneFeatureController:
    """Return a scene feature owner with deterministic title state."""

    controller = PromptSceneFeatureController(
        host=SceneFeatureHost(text),
        feature_profile=PromptFeatureProfileController(
            PromptEditorFeatureProfile.enabled_profile(())
        ),
    )
    controller.set_scene_autocomplete_titles(titles)
    return controller


def autocomplete_ghost_text_source_snapshot(
    ghost_mod: Any,
    source_text: str,
    *,
    cursor_position: int | None = None,
    source_revision: int = 0,
    source_length: int | None = None,
) -> Any:
    """Return a prepared source snapshot for projection ghost-text tests."""

    return ghost_mod.PromptAutocompleteGhostTextSourceSnapshot(
        source_revision=source_revision,
        source_length=len(source_text) if source_length is None else source_length,
        cursor_position=len(source_text)
        if cursor_position is None
        else cursor_position,
        source_text=source_text,
    )


def prompt_lora_catalog_item(
    *,
    display_name: str = "CivitAI Midna",
    basename: str = "raw_midna",
    prompt_name: str = r"illustrious\characters\raw_midna",
    thumbnail_variants: tuple[PromptLoraThumbnailVariant, ...] = (),
) -> PromptLoraCatalogItem:
    """Return one deterministic LoRA catalog item for prompt-editor tests."""

    return PromptLoraCatalogItem(
        display_name=display_name,
        display_subtitle=None,
        prompt_name=prompt_name,
        backend_value=f"{prompt_name}.safetensors",
        relative_path=f"{prompt_name}.safetensors",
        folder=prompt_name.rsplit("\\", 1)[0] if "\\" in prompt_name else "",
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=thumbnail_variants,
        base_model="Illustrious",
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=" ".join((display_name, basename, prompt_name)).casefold(),
    )


class EmptyAutocompleteGateway:
    """Provide a deterministic empty autocomplete gateway for coordinator tests."""

    @staticmethod
    def search(
        _prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no suggestions for the supplied prefix."""

        _ = limit
        return ()


class MenuSelectionDouble:
    """Expose the minimal Qt selection API used by controller tests."""

    def __init__(self, cursor: "MenuCursorDouble") -> None:
        """Store the cursor that owns this selection."""

        self._cursor = cursor

    def isEmpty(self) -> bool:
        """Return whether the tracked selection is empty."""

        return self._cursor.selectionStart() == self._cursor.selectionEnd()


class MenuCursorDouble:
    """Provide the minimal cursor API used by prompt-controller tests."""

    def __init__(
        self,
        *,
        text: str,
        position: int,
        anchor: int | None = None,
    ) -> None:
        """Store the backing text and the current cursor anchors."""

        self._text = text
        self._position = position
        self._anchor = position if anchor is None else anchor
        self.moves: list[tuple[int, object | None]] = []
        self.selected_mode: object | None = None
        self.inserted_text = ""

    def sync_text(self, text: str) -> None:
        """Replace the backing text used for selection slices."""

        self._text = text

    def position(self) -> int:
        """Return the current cursor position."""

        return self._position

    def anchor(self) -> int:
        """Return the current cursor anchor."""

        return self._anchor

    def selection(self) -> MenuSelectionDouble:
        """Return the current selection wrapper."""

        return MenuSelectionDouble(self)

    def selectionStart(self) -> int:
        """Return the inclusive selection start."""

        return min(self._anchor, self._position)

    def selectionEnd(self) -> int:
        """Return the exclusive selection end."""

        return max(self._anchor, self._position)

    def selectedText(self) -> str:
        """Return the selected substring from the backing prompt text."""

        return self._text[self.selectionStart() : self.selectionEnd()]

    def hasSelection(self) -> bool:
        """Return whether the cursor currently tracks a non-empty selection."""

        return self.selectionStart() != self.selectionEnd()

    def setPosition(self, pos: int, mode: object | None = None) -> None:
        """Move or extend the tracked cursor selection."""

        self.moves.append((pos, mode))
        mode_name = "" if mode is None else str(mode)
        if mode == "keep" or mode_name.endswith("KeepAnchor"):
            self._position = pos
            return
        self._anchor = pos
        self._position = pos

    def select(self, mode: object) -> None:
        """Record fallback selection mode when no emphasis span matches."""

        self.selected_mode = mode

    def insertText(self, text: str) -> None:
        """Record inserted text for autocomplete replacement tests."""

        self.inserted_text = text


class AutocompleteEditorDouble:
    """Provide the minimal editor API used by autocomplete coordinator tests."""

    def __init__(
        self,
        cursor: object,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
        command_result: PromptCommandResult[object] | None = None,
    ) -> None:
        """Store cursor, source identity, and optional command result."""

        self._cursor = cursor
        self.source_identity = source_identity
        self.command_result = command_result
        self.cursor_updates = 0
        self.autocomplete_preview_state: object | None = object()
        self.lora_autocomplete_commit_calls = 0
        self.accepted_autocomplete: list[PromptAutocompleteAcceptance] = []

    def textCursor(self) -> object:
        """Return the tracked cursor."""

        return self._cursor

    def setTextCursor(self, cursor: object) -> None:
        """Persist the supplied cursor and record the update."""

        self._cursor = cursor
        self.cursor_updates += 1

    def set_autocomplete_preview_state(self, preview_state: object | None) -> None:
        """Record projection-owned autocomplete preview state."""

        self.autocomplete_preview_state = preview_state

    def commit_lora_autocomplete_replacement(self) -> None:
        """Record syntax commits after accepting LoRA autocomplete."""

        self.lora_autocomplete_commit_calls += 1

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return the configured source identity for freshness checks."""

        return self.source_identity

    def execute_autocomplete_acceptance(
        self,
        acceptance: PromptAutocompleteAcceptance,
    ) -> PromptCommandResult[object]:
        """Record the prepared autocomplete acceptance."""

        self.accepted_autocomplete.append(acceptance)
        if self.command_result is not None:
            return self.command_result
        return PromptCommandResult.completed("accept_autocomplete")


class DeferredScheduledLoraContextProvider(PromptScheduledLoraContextProvider):
    """Record scheduled-LoRA context jobs so tests control completion order."""

    def __init__(
        self,
        resolver: Callable[[str], tuple[PromptScheduledLora, ...]],
    ) -> None:
        """Initialize an empty scheduled job queue."""

        self._resolver = resolver
        self._cache: dict[str, tuple[PromptScheduledLora, ...]] = {}
        self._pending: set[str] = set()
        self.jobs: list[
            tuple[
                str,
                str | None,
                PromptCommandSourceIdentity | None,
                Callable[[], str] | None,
                Callable[[], PromptCommandSourceIdentity | None] | None,
                Callable[[], Hashable | None],
                Callable[[], None],
            ]
        ] = []

    def prewarm(self, prompt_text: str) -> bool:
        """Queue one prewarm request unless it is cached or pending."""

        if prompt_text in self._cache or prompt_text in self._pending:
            return False
        self._pending.add(prompt_text)
        self.jobs.append(
            (
                prompt_text,
                None,
                None,
                lambda: prompt_text,
                None,
                lambda: None,
                lambda: None,
            )
        )
        return True

    def cached_scheduled_loras(
        self,
        prompt_text: str,
    ) -> tuple[PromptScheduledLora, ...] | None:
        """Return cached scheduled LoRAs for one prompt snapshot."""

        return self._cache.get(prompt_text)

    def cached_context_snapshot(
        self,
        prompt_text: str,
    ) -> PromptScheduledLoraCachedContextSnapshot | None:
        """Return cached scheduled-LoRA context identity for one prompt snapshot."""

        cached = self._cache.get(prompt_text)
        if cached is None:
            return None
        return PromptScheduledLoraCachedContextSnapshot(
            cache_key=("test", prompt_text),
            prompt_context_token=("test", len(prompt_text), hash(prompt_text)),
            scheduled_loras=cached,
            signature=scheduled_lora_signature(cached),
        )

    def cache_prompt(self, prompt_text: str) -> None:
        """Populate one prompt context through the resolver without queueing."""

        self._cache[prompt_text] = self._resolver(prompt_text)

    def trigger_word_result(
        self,
        *,
        prefix: str,
        prompt_text: str,
        source_text: str,
        source_identity: PromptCommandSourceIdentity | None,
        query_identity: Hashable | None,
        current_source_text: Callable[[], str] | None,
        current_query_identity: Callable[[], Hashable | None],
        refresh_current_query: Callable[[], None],
        current_source_identity: Callable[[], PromptCommandSourceIdentity | None]
        | None = None,
    ) -> PromptAutocompleteTriggerWordResult:
        """Return cached trigger words and queue a cold context refresh."""

        _ = (source_identity, query_identity)
        cached = self._cache.get(prompt_text)
        if cached is not None:
            signature = scheduled_lora_signature(cached)
            trigger_word_index = PromptTriggerWordIndex.build(cached)
            return PromptAutocompleteTriggerWordResult(
                suggestions=tuple(
                    autocomplete_suggestion_from_trigger_word(trigger_word)
                    for trigger_word in trigger_word_index.search(prefix)
                ),
                scheduled_lora_signature=signature,
            )
        if prompt_text not in self._pending:
            self._pending.add(prompt_text)
            self.jobs.append(
                (
                    prompt_text,
                    source_text,
                    source_identity,
                    current_source_text,
                    current_source_identity,
                    current_query_identity,
                    refresh_current_query,
                )
            )
        return PromptAutocompleteTriggerWordResult(
            suggestions=(),
            scheduled_lora_signature=(),
        )

    def complete(self, index: int = 0) -> None:
        """Run and complete one queued lookup."""

        (
            prompt_text,
            source_text,
            source_identity,
            current_source_text,
            current_source_identity,
            current_query_identity,
            refresh_current_query,
        ) = self.jobs.pop(index)
        self._pending.discard(prompt_text)
        scheduled_loras = self._resolver(prompt_text)
        self._cache[prompt_text] = scheduled_loras
        if not scheduled_lora_signature(scheduled_loras):
            return
        live_source_identity = (
            None if current_source_identity is None else current_source_identity()
        )
        if (
            live_source_identity is not None
            and source_identity is not None
            and live_source_identity.source_revision != source_identity.source_revision
        ):
            return
        if (
            live_source_identity is None
            and source_text is not None
            and current_source_text is not None
            and current_source_text() != source_text
        ):
            return
        if current_query_identity() is None:
            return
        refresh_current_query()


class FakeWildcardTaskHandle(
    PromptEditorTaskHandle[tuple[PromptAutocompleteSuggestion, ...]]
):
    """Store one wildcard async request until a test completes it."""

    def __init__(
        self,
        request: PromptAsyncRequest[tuple[PromptAutocompleteSuggestion, ...]],
    ) -> None:
        """Store request and callback observations."""

        self.request = request
        self.callbacks: list[
            Callable[
                [PromptAsyncTaskOutcome[tuple[PromptAutocompleteSuggestion, ...]]],
                None,
            ]
        ] = []
        self.cancel_calls: list[str] = []
        self._outcome: (
            PromptAsyncTaskOutcome[tuple[PromptAutocompleteSuggestion, ...]] | None
        ) = None

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return the request identity."""

        return self.request.identity

    @property
    def is_finished(self) -> bool:
        """Return whether the fake task has completed."""

        return self._outcome is not None

    @property
    def outcome(
        self,
    ) -> PromptAsyncTaskOutcome[tuple[PromptAutocompleteSuggestion, ...]] | None:
        """Return the completed outcome when available."""

        return self._outcome

    def add_done_callback(
        self,
        callback: Callable[
            [PromptAsyncTaskOutcome[tuple[PromptAutocompleteSuggestion, ...]]],
            None,
        ],
        *,
        reason: str,
    ) -> None:
        """Record a completion callback."""

        _ = reason
        self.callbacks.append(callback)

    def cancel(self, *, reason: str) -> None:
        """Record cancellation without preventing test completion."""

        self.cancel_calls.append(reason)

    def run_work(self) -> None:
        """Execute request work and publish the fake outcome."""

        try:
            result = self.request.work(_Token())
        except BaseException as error:  # noqa: BLE001
            self.complete(error=error)
            return
        self.complete(result=result)

    def complete(
        self,
        *,
        result: tuple[PromptAutocompleteSuggestion, ...] | None = None,
        error: BaseException | None = None,
    ) -> None:
        """Publish one fake wildcard completion."""

        self._outcome = PromptAsyncTaskOutcome(
            identity=self.request.identity,
            context=self.request.context,
            result=result,
            error=error,
        )
        callbacks = tuple(self.callbacks)
        self.callbacks.clear()
        for callback in callbacks:
            callback(self._outcome)


class _Token:
    """Provide a never-cancelled token for prompt controller tests."""

    generation = 0
    is_cancelled = False
    reason: str | None = None


class FakeWildcardRequestChannel:
    """Record wildcard async requests and return controllable handles."""

    def __init__(self) -> None:
        """Initialize request storage."""

        self.handles: list[FakeWildcardTaskHandle] = []
        self.cancel_reasons: list[str] = []

    def submit_latest(
        self,
        request: PromptAsyncRequest[tuple[PromptAutocompleteSuggestion, ...]],
    ) -> FakeWildcardTaskHandle:
        """Store a wildcard request for deterministic completion."""

        handle = FakeWildcardTaskHandle(request)
        self.handles.append(handle)
        return handle

    def cancel_pending(self, *, reason: str) -> None:
        """Record cancellation requests."""

        self.cancel_reasons.append(reason)


class TextAutocompleteEditorDouble:
    """Provide mutable prompt text for autocomplete projection tests."""

    def __init__(self, text: str) -> None:
        """Initialize the prompt text returned by the editor double."""

        self.text = text
        self.source_revision = 0
        self.cursor_position: int | None = None
        self.autocomplete_preview_state: object | None = None
        self.autocomplete_preview_updates: list[object | None] = []

    def toPlainText(self) -> str:
        """Return the current prompt text."""

        return self.text

    def textCursor(self) -> object:
        """Return a cursor exposing the current source position."""

        position = (
            len(self.text) if self.cursor_position is None else self.cursor_position
        )
        return _CursorDouble(position=position)

    def set_autocomplete_preview_state(self, preview_state: object | None) -> None:
        """Record projection-owned autocomplete preview state."""

        self.autocomplete_preview_state = preview_state
        self.autocomplete_preview_updates.append(preview_state)

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
        """Return source identity for ghost-text freshness tests."""

        return PromptCommandSourceIdentity(
            source_revision=self.source_revision,
            source_length=len(self.text),
        )


class _CursorDouble:
    """Expose the cursor position API consumed by ghost-text publishing."""

    def __init__(self, *, position: int) -> None:
        """Store one deterministic cursor position."""

        self._position = position

    def position(self) -> int:
        """Return the configured cursor position."""

        return self._position
