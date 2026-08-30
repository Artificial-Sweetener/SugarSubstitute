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

"""Shared deterministic collaborators for LoRA metadata feature tests."""

from __future__ import annotations


from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
    PromptLoraThumbnailVariant,
)
from substitute.application.prompt_editor.lora.schedule import PromptLoraScheduleService
from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLora,
    PromptScheduledLoraService,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptEditorMainThreadDispatcher,
    scheduled_lora_signature,
)
from substitute.presentation.editor.prompt_editor.async_work.scheduled_lora_dispatcher import (
    PromptScheduledLoraCachedContextSnapshot,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptFeatureProfileController,
    PromptLoraMetadataPresentation,
    PromptLoraMetadataRefreshLifecycle,
    PromptLoraTriggerWordController,
)
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile


class _QueuedDispatcher:
    """Capture main-thread publications for LoRA metadata tests."""

    def __init__(self) -> None:
        """Initialize an empty callback queue."""

        self.callbacks: list[Callable[[], None]] = []

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Record one callback for explicit test execution."""

        _ = reason
        self.callbacks.append(callback)


class _LoraMetadataHost:
    """Provide the host protocol required by the LoRA metadata controller."""

    def __init__(self) -> None:
        """Initialize host state."""

        self.visible = True
        self.has_lora_spans = True
        self.refresh_calls = 0
        self.cached_context: PromptScheduledLoraCachedContextSnapshot | None = None
        self.cached_context_calls = 0
        self.prewarm_prompts: list[str] = []
        self.source_revision = 4

    def toPlainText(self) -> str:  # noqa: N802
        """Return current prompt text."""

        return "<lora:midna:1>"

    def isVisible(self) -> bool:  # noqa: N802
        """Return whether the host is visible."""

        return self.visible

    def prompt_command_source_identity(self) -> PromptSourceIdentity:
        """Return a stable source identity for snapshot tests."""

        return PromptSourceIdentity(
            source_revision=self.source_revision,
            source_length=len(self.toPlainText()),
        )

    def has_lora_spans_for_metadata(self) -> bool:
        """Return whether LoRA spans are present."""

        return self.has_lora_spans

    def refresh_lora_render_metadata_now(self, *, reason: str) -> bool:
        """Record one render metadata refresh."""

        assert reason == "lora_metadata"
        self.refresh_calls += 1
        return True

    def cached_context_snapshot(
        self,
        prompt_text: str,
    ) -> PromptScheduledLoraCachedContextSnapshot | None:
        """Return cached context through the neutral coordinator protocol."""

        _ = prompt_text
        self.cached_context_calls += 1
        return self.cached_context

    def cached_scheduled_loras(
        self,
        prompt_text: str,
    ) -> tuple[PromptScheduledLora, ...] | None:
        """Return scheduled rows from the cached context."""

        snapshot = self.cached_context_snapshot(prompt_text)
        return None if snapshot is None else snapshot.scheduled_loras

    def prewarm(self, prompt_text: str) -> bool:
        """Warm context through the neutral coordinator protocol."""

        self.prewarm_prompts.append(prompt_text)
        return True


class _LoraCatalog:
    """Record LoRA catalog calls and expose a mutable cache revision."""

    def __init__(
        self,
        items: tuple[PromptLoraCatalogItem, ...],
        *,
        fail: bool = False,
        cached: tuple[PromptLoraCatalogItem, ...] | None | object = (),
    ) -> None:
        """Store configured LoRA rows."""

        self.items = items
        self.fail = fail
        self.cached = items if cached == () else cached
        self.cache_revision = 1
        self.cached_calls = 0
        self.list_calls = 0
        self.refresh_calls = 0

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return configured LoRA rows or raise the configured failure."""

        self.list_calls += 1
        if self.fail:
            raise RuntimeError("catalog unavailable")
        return self.items

    def refresh_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return configured LoRA rows and advance the fake revision."""

        self.refresh_calls += 1
        if self.fail:
            raise RuntimeError("catalog unavailable")
        self.cache_revision += 1
        return self.items

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return configured rows without simulating a backend load."""

        self.cached_calls += 1
        if self.cached is None:
            return None
        return cast(tuple[PromptLoraCatalogItem, ...], self.cached)

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return the first item matching the requested prompt name."""

        for item in self.items:
            if item.prompt_name == prompt_name:
                return item
        return None


class _ImmediateDispatcher:
    """Publish prompt-editor async callbacks immediately for controller tests."""

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Run one callback synchronously while preserving the dispatcher protocol."""

        _ = reason
        callback()


@dataclass(frozen=True, slots=True)
class _LoraMetadataOwners:
    """Expose the independently owned LoRA metadata test composition."""

    presentation: PromptLoraMetadataPresentation
    refresh: PromptLoraMetadataRefreshLifecycle


def _metadata_owners(
    *,
    host: _LoraMetadataHost,
    dispatcher: _QueuedDispatcher,
    lora_catalog: _LoraCatalog | None = None,
    syntaxes: tuple[str, ...] = ("lora",),
) -> _LoraMetadataOwners:
    """Build the explicit presentation and refresh owners for one test."""

    feature_profile = PromptFeatureProfileController.from_legacy_syntax(
        prompt_syntax_profile(*syntaxes)
    )
    presentation = PromptLoraMetadataPresentation(
        identity_port=host,
        feature_profile=feature_profile,
        lora_catalog=lora_catalog,
        lora_schedule_service=PromptLoraScheduleService(),
        scheduled_lora_service=PromptScheduledLoraService(),
        thumbnail_repository_available=False,
    )
    refresh = PromptLoraMetadataRefreshLifecycle(
        host=host,
        presentation=presentation,
        dispatcher=cast(PromptEditorMainThreadDispatcher, dispatcher),
    )
    return _LoraMetadataOwners(presentation=presentation, refresh=refresh)


def _trigger_controller(
    *,
    host: _LoraMetadataHost,
    syntaxes: tuple[str, ...] = ("lora",),
    catalog_revision: Callable[[], object | None] = lambda: None,
) -> PromptLoraTriggerWordController:
    """Return the independently owned trigger-word controller for tests."""

    profile = PromptFeatureProfileController.from_legacy_syntax(
        prompt_syntax_profile(*syntaxes)
    )
    return PromptLoraTriggerWordController(
        host=host,
        scheduled_lora_service=PromptScheduledLoraService(),
        scheduled_lora_context=cast(Any, host),
        feature_profile_id=lambda: profile.identity.feature_profile_id,
        catalog_revision=catalog_revision,
        trigger_words_enabled=lambda: profile.lora_trigger_words_enabled,
        effective_prompts=lambda: (host.toPlainText(),),
    )


def _item(display_name: str) -> PromptLoraCatalogItem:
    """Return one deterministic LoRA catalog row."""

    return PromptLoraCatalogItem(
        display_name=display_name,
        display_subtitle=None,
        prompt_name=display_name.casefold(),
        backend_value=f"{display_name}.safetensors",
        relative_path=f"{display_name}.safetensors",
        folder="",
        basename=display_name,
        extension=".safetensors",
        thumbnail_variants=(
            PromptLoraThumbnailVariant(
                size=128,
                storage_key=f"{display_name}:128",
                width=128,
                height=128,
                content_format="sqthumb-qimage-argb32-premultiplied",
                byte_size=65536,
            ),
        ),
        base_model="Illustrious",
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=display_name.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=display_name.casefold(),
    )


def _raw_midna_item() -> PromptLoraCatalogItem:
    """Return the raw Midna LoRA row used by PromptEditor picker refresh tests."""

    return PromptLoraCatalogItem(
        display_name="CivitAI Midna",
        display_subtitle=None,
        prompt_name=r"illustrious\characters\raw_midna",
        backend_value=r"illustrious\characters\raw_midna.safetensors",
        relative_path=r"illustrious\characters\raw_midna.safetensors",
        folder=r"illustrious\characters",
        basename="raw_midna",
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key="raw_midna",
        collision_count=1,
        has_collision=False,
        search_text=(r"civitai midna raw_midna illustrious\characters\raw_midna"),
    )


def _cached_context(
    prompt_text: str,
    scheduled_loras: tuple[PromptScheduledLora, ...],
) -> PromptScheduledLoraCachedContextSnapshot:
    """Return a deterministic cached scheduled-LoRA context snapshot."""

    return PromptScheduledLoraCachedContextSnapshot(
        cache_key=("test", prompt_text),
        prompt_context_token=("test", len(prompt_text), hash(prompt_text)),
        scheduled_loras=scheduled_loras,
        signature=scheduled_lora_signature(scheduled_loras),
    )
