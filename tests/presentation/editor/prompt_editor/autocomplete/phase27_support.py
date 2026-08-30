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

"""Baseline Phase 27 autocomplete behavior before SOC extraction."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor.autocomplete.queries import (
    PromptAutocompleteQuery,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)
from substitute.application.prompt_editor.lora.scheduled import PromptScheduledLora
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorCancellationToken,
    PromptEditorTaskHandle,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteResultSnapshot,
)


class _Cursor:
    """Provide the minimal cursor API used by autocomplete timing tests."""

    def __init__(self, *, position: int, has_selection: bool = False) -> None:
        """Store deterministic cursor state."""

        self._position = position
        self._has_selection = has_selection

    def position(self) -> int:
        """Return the cursor position."""

        return self._position

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether this cursor carries a selection."""

        return self._has_selection


class _QueryEditor:
    """Expose source and cursor state to the autocomplete timing controller."""

    def __init__(self, text: str, *, has_selection: bool = False) -> None:
        """Store mutable source state."""

        self.text = text
        self.cursor_position = len(text)
        self.has_selection = has_selection
        self.source_revision = 0
        self.text_reads = 0

    def toPlainText(self) -> str:  # noqa: N802
        """Return source text while recording one read."""

        self.text_reads += 1
        return self.text

    def textCursor(self) -> _Cursor:  # noqa: N802
        """Return current cursor state."""

        return _Cursor(
            position=self.cursor_position,
            has_selection=self.has_selection,
        )

    def prompt_command_source_identity(self) -> PromptSourceIdentity:
        """Return source identity for stale-safe query snapshots."""

        return PromptSourceIdentity(
            source_revision=self.source_revision,
            source_length=len(self.text),
        )


class _TimingPublication:
    """Record lifecycle publications without a session or Qt presentation surface."""

    def __init__(self) -> None:
        """Initialize immutable publication and dismissal accounting."""

        self.published: list[tuple[PromptAutocompleteResultSnapshot, object]] = []
        self.dismissed: list[str] = []

    def has_active_session(self) -> bool:
        """Report no active session during timer-driven result publication."""

        return False

    def retarget_from_query_state(self, _query_state: object) -> bool:
        """Reject retargeting because this timing fixture has no live session."""

        return False

    def publish_result(
        self,
        result: PromptAutocompleteResultSnapshot,
        query_state: object,
    ) -> None:
        """Record the prepared result and its matching query state."""

        self.published.append((result, query_state))

    def dismiss_autocomplete(self, reason: str) -> None:
        """Record one lifecycle dismissal."""

        self.dismissed.append(reason)


class _TimingResultController:
    """Build ready tag results for timing-to-lifecycle integration coverage."""

    def result_for_tag_query(
        self, *, query: PromptAutocompleteQuery, **_kwargs: Any
    ) -> PromptAutocompleteResultSnapshot:
        """Return one ready tag result for the prepared query."""

        return PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(PromptAutocompleteSuggestion("timing", 1),),
            tag_query=query,
        )

    def safe_tag_query_identity(
        self,
        query: PromptAutocompleteQuery,
    ) -> tuple[str, str]:
        """Return a stable identity when scheduled context asks for a refresh."""

        return ("tag", query.prefix)


class _TimingSceneContextController:
    """Supply the tag context shape consumed by the result lifecycle."""

    def context_for_tag_query(self, _query: object, **_kwargs: Any) -> object:
        """Return a context without accessing a workflow or Qt state."""

        return SimpleNamespace(tag_context=None)


class _FakeTimerSignal:
    """Expose a Qt-like signal connect method for fake timers."""

    def __init__(self, timer: "_FakeTimer") -> None:
        """Store the owning fake timer."""

        self._timer = timer

    def connect(self, callback: Callable[[], None]) -> None:
        """Record the timeout callback."""

        self._timer.callback = callback


class _FakeTimer:
    """Provide deterministic timer behavior for debounce tests."""

    def __init__(self) -> None:
        """Initialize timer state."""

        self.timeout = _FakeTimerSignal(self)
        self.callback: Callable[[], None] | None = None
        self.started_delays: list[int] = []
        self.stop_calls = 0
        self.single_shot = False

    def setSingleShot(self, single_shot: bool) -> None:  # noqa: N802
        """Record whether the timer is single-shot."""

        self.single_shot = single_shot

    def start(self, delay_ms: int) -> None:
        """Record one scheduled delay."""

        self.started_delays.append(delay_ms)

    def stop(self) -> None:
        """Record one cancellation."""

        self.stop_calls += 1

    def fire(self) -> None:
        """Run the recorded timeout callback."""

        if self.callback is not None:
            self.callback()


class _ScheduledLoraTaskHandle(PromptEditorTaskHandle[tuple[PromptScheduledLora, ...]]):
    """Store a scheduled-LoRA async request for deterministic completion."""

    def __init__(
        self,
        request: PromptAsyncRequest[tuple[PromptScheduledLora, ...]],
    ) -> None:
        """Store request state."""

        self.request = request
        self.callbacks: list[
            Callable[
                [PromptAsyncTaskOutcome[tuple[PromptScheduledLora, ...]]],
                None,
            ]
        ] = []
        self._outcome: (
            PromptAsyncTaskOutcome[tuple[PromptScheduledLora, ...]] | None
        ) = None

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return the request identity."""

        return self.request.identity

    @property
    def is_finished(self) -> bool:
        """Return whether this task has completed."""

        return self._outcome is not None

    @property
    def outcome(self) -> PromptAsyncTaskOutcome[tuple[PromptScheduledLora, ...]] | None:
        """Return the completed outcome when available."""

        return self._outcome

    def add_done_callback(
        self,
        callback: Callable[
            [PromptAsyncTaskOutcome[tuple[PromptScheduledLora, ...]]],
            None,
        ],
        *,
        reason: str,
    ) -> None:
        """Record one completion callback."""

        _ = reason
        self.callbacks.append(callback)

    def cancel(self, *, reason: str) -> None:
        """Accept cancellation without changing explicit test completion."""

        _ = reason

    def complete(
        self,
        *,
        result: tuple[PromptScheduledLora, ...] | None = None,
        error: BaseException | None = None,
    ) -> None:
        """Publish a deterministic task outcome."""

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


class _ScheduledLoraExecutor:
    """Record scheduled-LoRA async requests."""

    def __init__(self) -> None:
        """Initialize submitted handle storage."""

        self.handles: list[_ScheduledLoraTaskHandle] = []

    def submit(
        self,
        request: PromptAsyncRequest[tuple[PromptScheduledLora, ...]],
        *,
        cancellation: PromptEditorCancellationToken,
    ) -> PromptEditorTaskHandle[tuple[PromptScheduledLora, ...]]:
        """Record one async request."""

        _ = cancellation
        handle = _ScheduledLoraTaskHandle(request)
        self.handles.append(handle)
        return handle


class _Token:
    """Provide a never-cancelled token for scheduled-LoRA test work."""

    generation = 0
    is_cancelled = False
    reason: str | None = None


class _ScheduledLoraResolver:
    """Resolve scheduled LoRAs while exposing a stable context token."""

    scheduled_lora_context_token = "phase27-token"

    def __init__(self, result: tuple[PromptScheduledLora, ...]) -> None:
        """Store deterministic resolver output."""

        self._result = result
        self.calls: list[str] = []

    def __call__(self, prompt_text: str) -> tuple[PromptScheduledLora, ...]:
        """Record one resolver call and return configured scheduled LoRAs."""

        self.calls.append(prompt_text)
        return self._result


class _PromptLoraCatalog:
    """Expose cached LoRA rows while failing blocking foreground reads."""

    def __init__(
        self,
        rows: tuple[PromptLoraCatalogItem, ...] | None,
    ) -> None:
        """Store cached row state."""

        self.rows = rows
        self.cached_calls = 0
        self.list_calls = 0
        self.refresh_calls = 0

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return cached rows."""

        self.cached_calls += 1
        return self.rows

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return a cached LoRA row matching one prompt name."""

        if self.rows is None:
            return None
        normalized_prompt_name = prompt_name.replace("\\", "/").casefold()
        for row in self.rows:
            if row.prompt_name.replace("\\", "/").casefold() == normalized_prompt_name:
                return row
        return None

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Fail if autocomplete attempts passive catalog loading."""

        self.list_calls += 1
        raise AssertionError("LoRA autocomplete must not call list_loras().")

    def refresh_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Fail if autocomplete attempts foreground refresh."""

        self.refresh_calls += 1
        raise AssertionError("LoRA autocomplete must not call refresh_loras().")


def _autocomplete_module() -> Any:
    """Import the transitional autocomplete interaction module."""

    import importlib

    return importlib.import_module(
        "substitute.presentation.editor.prompt_editor.interactions.autocomplete_controller"
    )


def _key_event(key: Qt.Key) -> QKeyEvent:
    """Return a key event suitable for autocomplete key-path tests."""

    return QKeyEvent(
        QKeyEvent.Type.KeyPress,
        int(key),
        Qt.KeyboardModifier.NoModifier,
    )


def _lora_item(*, prompt_name: str = "midna") -> PromptLoraCatalogItem:
    """Return one deterministic LoRA catalog item."""

    return PromptLoraCatalogItem(
        display_name="Midna",
        display_subtitle=None,
        prompt_name=prompt_name,
        backend_value=f"{prompt_name}.safetensors",
        relative_path=f"{prompt_name}.safetensors",
        folder="",
        basename=prompt_name,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=prompt_name,
        collision_count=1,
        has_collision=False,
        search_text="midna",
    )
