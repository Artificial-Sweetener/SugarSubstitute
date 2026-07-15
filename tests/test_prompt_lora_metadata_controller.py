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

"""Tests for prompt-editor LoRA metadata feature ownership."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import QSize

from substitute.application.prompt_editor import (
    PromptLoraCatalogItem,
    PromptLoraScheduleService,
    PromptLoraThumbnailVariant,
    PromptScheduledLora,
    PromptScheduledLoraService,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptEditorMainThreadDispatcher,
    scheduled_lora_signature,
)
from substitute.presentation.editor.prompt_editor.async_work.scheduled_lora_dispatcher import (
    PromptScheduledLoraCachedContextSnapshot,
)
from substitute.presentation.editor.prompt_editor.features import (
    CatalogSnapshotReadiness,
    PromptFeatureProfileController,
    PromptLoraMetadataFeatureController,
    PromptLoraTriggerWordController,
    PromptLoraTokenContext,
)
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionThumbnailVariant,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
)
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile


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

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
        """Return a stable source identity for snapshot tests."""

        return PromptCommandSourceIdentity(
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


class _LoraMetadataInteractionControllerDouble:
    """Expose LoRA metadata refresh seams consumed by PromptEditor."""

    def __init__(
        self,
        *,
        has_lora_spans: bool = True,
        schedule_result: bool = True,
        schedule_error: Exception | None = None,
    ) -> None:
        """Store deterministic LoRA refresh behavior."""

        self._has_lora_spans = has_lora_spans
        self._schedule_result = schedule_result
        self._schedule_error = schedule_error
        self.schedule_calls = 0

    def has_lora_spans(self) -> bool:
        """Return whether the prompt currently contains LoRA spans."""

        return self._has_lora_spans

    def refresh_lora_render_metadata(self, *, reason: str) -> bool:
        """Record and return the configured metadata refresh result."""

        assert reason == "lora_metadata"
        self.schedule_calls += 1
        if self._schedule_error is not None:
            raise self._schedule_error
        return self._schedule_result


class _ImmediateDispatcher:
    """Publish prompt-editor async callbacks immediately for controller tests."""

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Run one callback synchronously while preserving the dispatcher protocol."""

        _ = reason
        callback()


class _FailingLoraPickerCatalog:
    """Raise when picker rows are refreshed."""

    cache_revision = 0

    def refresh_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Fail one active picker refresh."""

        raise RuntimeError("picker failed")

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Fail one passive picker load."""

        raise RuntimeError("picker failed")

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return no cached rows before explicit refresh."""

        return None


class _LoraThumbnailCacheDouble:
    """Expose thumbnail-cache behavior consumed by PromptEditor refresh tests."""

    def __init__(self, *, clear_error: Exception | None = None) -> None:
        """Store deterministic cache clear behavior."""

        self._clear_error = clear_error
        self.clear_calls = 0

    def clear(self) -> None:
        """Record and optionally fail a cache clear request."""

        self.clear_calls += 1
        if self._clear_error is not None:
            raise self._clear_error


class _PromptEditorLoraMetadataRefreshDouble:
    """Provide the PromptEditor attributes needed by metadata refresh tests."""

    def __init__(
        self,
        *,
        dirty: bool = True,
        visible: bool = True,
        picker_error: Exception | None = None,
        interaction_controller: _LoraMetadataInteractionControllerDouble | None = None,
        thumbnail_cache: _LoraThumbnailCacheDouble | None = None,
    ) -> None:
        """Store deterministic prompt-editor metadata refresh collaborators."""

        self._visible = visible
        self._interaction_controller = (
            interaction_controller or _LoraMetadataInteractionControllerDouble()
        )
        self._lora_thumbnail_cache = thumbnail_cache or _LoraThumbnailCacheDouble()
        self._lora_metadata_feature_controller = PromptLoraMetadataFeatureController(
            host=self,
            feature_profile=PromptFeatureProfileController.from_legacy_syntax(
                prompt_syntax_profile("lora")
            ),
            lora_catalog=(
                cast(Any, _FailingLoraPickerCatalog()) if picker_error else None
            ),
            lora_schedule_service=PromptLoraScheduleService(),
            scheduled_lora_service=PromptScheduledLoraService(),
            main_thread_dispatcher=cast(
                PromptEditorMainThreadDispatcher,
                _ImmediateDispatcher(),
            ),
        )
        if dirty:
            self._lora_metadata_feature_controller.mark_dirty()

    def isVisible(self) -> bool:  # noqa: N802
        """Return whether the fake editor is visible."""

        return self._visible

    def toPlainText(self) -> str:  # noqa: N802
        """Return empty source text for metadata-controller tests."""

        return ""

    def prompt_command_source_identity(self) -> None:
        """Return no source identity for metadata-controller tests."""

        return None

    def has_lora_spans_for_metadata(self) -> bool:
        """Return whether the fake editor currently has LoRA spans."""

        return self._interaction_controller.has_lora_spans()

    def refresh_lora_render_metadata_now(self, *, reason: str) -> bool:
        """Delegate render metadata refresh to the interaction double."""

        return self._interaction_controller.refresh_lora_render_metadata(reason=reason)


class _FailingThumbnailAssetRepository:
    """Raise while counting thumbnail asset reads."""

    def __init__(self) -> None:
        """Initialize read accounting."""

        self.reads = 0

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Record and fail one thumbnail asset read."""

        _ = storage_key
        self.reads += 1
        raise RuntimeError("thumbnail store unavailable")


class _InvalidThumbnailAssetRepository:
    """Return invalid thumbnail payloads while counting asset reads."""

    def __init__(self) -> None:
        """Initialize read accounting."""

        self.reads = 0

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Record one read and return undecodable payload data."""

        self.reads += 1
        return ThumbnailAsset(
            storage_key=storage_key,
            width=16,
            height=16,
            qt_format=-1,
            bytes_per_line=0,
            content_format="sqthumb-qimage-argb32-premultiplied",
            payload=b"not-image-data",
        )


def test_lora_thumbnail_cache_clear_drops_scaled_pixmaps() -> None:
    """LoRA metadata refresh can discard stale scaled pixmaps."""

    cache = PromptLoraThumbnailCache()
    pixmaps = cast(dict[object, object], cache._pixmaps)
    pixmaps[("storage", 16, 16, 128, 1.0)] = object()

    cache.clear()

    assert cache._pixmaps == {}


def test_lora_thumbnail_cache_handles_repository_failure() -> None:
    """Thumbnail repository failures queue asynchronously and return missing."""

    repository = _FailingThumbnailAssetRepository()
    cache = PromptLoraThumbnailCache(repository)
    variants = (_projection_thumbnail_variant("broken:banner:128"),)

    first_pixmap = cache.pixmap_for_variants(variants, QSize(32, 32))
    second_pixmap = cache.pixmap_for_variants(variants, QSize(32, 32))

    assert first_pixmap is None
    assert second_pixmap is None
    assert repository.reads <= 1


def test_lora_thumbnail_cache_handles_invalid_payload() -> None:
    """Invalid thumbnail payloads queue asynchronously and return missing."""

    repository = _InvalidThumbnailAssetRepository()
    cache = PromptLoraThumbnailCache(repository)
    variants = (_projection_thumbnail_variant("invalid:banner:128"),)

    first_pixmap = cache.pixmap_for_variants(variants, QSize(32, 32))
    second_pixmap = cache.pixmap_for_variants(variants, QSize(32, 32))

    assert first_pixmap is None
    assert second_pixmap is None
    assert repository.reads <= 1


def test_refresh_lora_metadata_keeps_dirty_flag_when_picker_refresh_fails() -> None:
    """Picker refresh failures do not block render metadata refresh."""

    mod = _import_prompt_editor_module()
    editor = _PromptEditorLoraMetadataRefreshDouble(
        picker_error=RuntimeError("picker failed")
    )

    refreshed = mod.PromptEditor.refresh_lora_metadata_if_visible(editor)

    assert refreshed is True
    assert editor._lora_metadata_feature_controller.dirty is False


def test_refresh_lora_metadata_keeps_dirty_flag_when_projection_queue_fails() -> None:
    """Projection queue failures leave visible LoRA metadata retryable."""

    mod = _import_prompt_editor_module()
    editor = _PromptEditorLoraMetadataRefreshDouble(
        interaction_controller=_LoraMetadataInteractionControllerDouble(
            schedule_error=RuntimeError("queue failed")
        )
    )

    refreshed = mod.PromptEditor.refresh_lora_metadata_if_visible(editor)

    assert refreshed is True
    assert editor._lora_metadata_feature_controller.dirty is True


def test_refresh_lora_metadata_keeps_dirty_flag_when_projection_not_queued() -> None:
    """A failed projection queue attempt does not consume dirty metadata."""

    mod = _import_prompt_editor_module()
    editor = _PromptEditorLoraMetadataRefreshDouble(
        interaction_controller=_LoraMetadataInteractionControllerDouble(
            schedule_result=False
        )
    )

    refreshed = mod.PromptEditor.refresh_lora_metadata_if_visible(editor)

    assert refreshed is True
    assert editor._lora_metadata_feature_controller.dirty is True


def test_refresh_lora_metadata_clears_dirty_flag_after_successful_queue() -> None:
    """A successfully queued metadata refresh consumes the dirty flag."""

    mod = _import_prompt_editor_module()
    editor = _PromptEditorLoraMetadataRefreshDouble()

    refreshed = mod.PromptEditor.refresh_lora_metadata_if_visible(editor)

    assert refreshed is True
    assert editor._lora_metadata_feature_controller.dirty is False
    assert editor._lora_thumbnail_cache.clear_calls == 0


def test_catalog_update_lora_metadata_refresh_preserves_thumbnail_cache() -> None:
    """Catalog metadata refresh does not drop existing LoRA thumbnail pixmaps."""

    mod = _import_prompt_editor_module()
    editor = _PromptEditorLoraMetadataRefreshDouble()

    refreshed = mod.PromptEditor._refresh_lora_render_metadata_after_catalog_update(
        editor
    )

    assert refreshed is True
    assert editor._lora_metadata_feature_controller.dirty is False
    assert editor._lora_thumbnail_cache.clear_calls == 0


def test_picker_refresh_updates_inline_lora_render_metadata() -> None:
    """A direct picker catalog refresh also refreshes visible LoRA chips."""

    class _PickerRefreshCatalog:
        """Expose a revision-changing LoRA picker refresh."""

        def __init__(self) -> None:
            """Initialize catalog rows and revision accounting."""

            self.cache_revision = 0

        def refresh_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
            """Return a LoRA row and advance the catalog revision."""

            self.cache_revision += 1
            return (_raw_midna_item(),)

        def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
            """Return no passive rows because this test exercises refresh."""

            return ()

        def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
            """Return no cached rows before the explicit refresh."""

            return None

    editor = _PromptEditorLoraMetadataRefreshDouble()
    editor._lora_metadata_feature_controller = PromptLoraMetadataFeatureController(
        host=editor,
        feature_profile=PromptFeatureProfileController.from_legacy_syntax(
            prompt_syntax_profile("lora")
        ),
        lora_catalog=cast(Any, _PickerRefreshCatalog()),
        lora_schedule_service=PromptLoraScheduleService(),
        scheduled_lora_service=PromptScheduledLoraService(),
        main_thread_dispatcher=cast(
            PromptEditorMainThreadDispatcher,
            _ImmediateDispatcher(),
        ),
    )

    result = editor._lora_metadata_feature_controller.refresh_lora_picker_snapshot_now(
        reason="test",
    )

    assert [item.prompt_name for item in result.snapshot.items] == [
        r"illustrious\characters\raw_midna"
    ]
    assert editor._interaction_controller.schedule_calls == 1


def test_lora_metadata_controller_coalesces_pending_render_refreshes() -> None:
    """Repeated metadata requests schedule one feature-controller refresh."""

    dispatcher = _QueuedDispatcher()
    editor = _PromptEditorLoraMetadataRefreshDouble()
    editor._lora_metadata_feature_controller = PromptLoraMetadataFeatureController(
        host=editor,
        feature_profile=PromptFeatureProfileController.from_legacy_syntax(
            prompt_syntax_profile("lora")
        ),
        lora_catalog=None,
        lora_schedule_service=PromptLoraScheduleService(),
        scheduled_lora_service=PromptScheduledLoraService(),
        main_thread_dispatcher=cast(PromptEditorMainThreadDispatcher, dispatcher),
    )
    controller = editor._lora_metadata_feature_controller

    assert controller.schedule_render_metadata_refresh(reason="lora_metadata") is True
    assert controller.schedule_render_metadata_refresh(reason="lora_metadata") is True
    assert len(dispatcher.callbacks) == 1

    dispatcher.callbacks.pop()()

    assert editor._interaction_controller.schedule_calls == 1


def test_lora_metadata_controller_coalesces_render_refresh() -> None:
    """Render refresh scheduling should be owned and coalesced by the feature."""

    dispatcher = _QueuedDispatcher()
    host = _LoraMetadataHost()
    controller = _controller(host=host, dispatcher=dispatcher)

    assert controller.schedule_render_metadata_refresh(reason="lora_metadata") is True
    assert controller.schedule_render_metadata_refresh(reason="lora_metadata") is True
    assert len(dispatcher.callbacks) == 1

    dispatcher.callbacks.pop()()

    assert host.refresh_calls == 1
    assert controller.dirty is False


def test_lora_metadata_controller_uses_matching_cached_action_snapshot() -> None:
    """Trigger-word actions should consume matching cached scheduled-LoRA context."""

    host = _LoraMetadataHost()
    controller = _trigger_controller(host=host)
    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Midna",
        trained_words=("imp princess",),
        source="cube_field",
    )
    prompt_text = "<lora:midna:1>"

    assert (
        controller.snapshot_for_prompt(
            prompt_text=prompt_text,
        ).trigger_word_actions
        == ()
    )
    host.cached_context = _cached_context(prompt_text, (scheduled_lora,))

    actions = controller.snapshot_for_prompt(
        prompt_text=prompt_text,
    ).trigger_word_actions

    assert len(actions) == 1
    assert actions[0].command_request is not None
    payload = actions[0].command_request.payload
    assert payload.insertion_text == "imp princess"
    assert payload.snapshot_identity is not None
    assert payload.snapshot_identity.source_revision == host.source_revision
    assert payload.snapshot_identity.prompt_context_token == (
        "test",
        len(prompt_text),
        hash(prompt_text),
    )
    assert payload.snapshot_identity.request_identity == scheduled_lora_signature(
        (scheduled_lora,)
    )


def test_lora_metadata_controller_projects_prompt_actions_from_context_cache() -> None:
    """Prompt actions should derive directly from authoritative cached context."""

    host = _LoraMetadataHost()
    controller = _trigger_controller(host=host)
    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Midna",
        trained_words=("imp princess",),
        source="cube_field",
    )
    prompt_text = "<lora:midna:1>"

    cold_snapshot = controller.snapshot_for_prompt(prompt_text=prompt_text)

    assert cold_snapshot.trigger_word_actions == ()
    assert cold_snapshot.status.readiness is CatalogSnapshotReadiness.COLD
    assert cold_snapshot.status.unavailable_reason is None
    assert host.cached_context_calls == 1

    host.cached_context = _cached_context(prompt_text, (scheduled_lora,))
    prepared_snapshot = controller.snapshot_for_prompt(
        prompt_text=prompt_text,
    )
    menu_snapshot = controller.snapshot_for_prompt(prompt_text=prompt_text)

    assert host.cached_context_calls == 3
    assert menu_snapshot == prepared_snapshot
    assert len(menu_snapshot.trigger_word_actions) == 1


def test_lora_metadata_controller_reprojects_actions_for_catalog_revision() -> None:
    """Catalog revisions should flow into newly projected action identities."""

    host = _LoraMetadataHost()
    catalog = _LoraCatalog((_item("Midna"),))
    metadata_controller = _controller(
        host=host,
        dispatcher=_QueuedDispatcher(),
        lora_catalog=catalog,
    )
    controller = _trigger_controller(
        host=host,
        catalog_revision=lambda: metadata_controller.snapshot.catalog_revision,
    )
    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Midna",
        trained_words=("imp princess",),
        source="cube_field",
    )
    prompt_text = "<lora:midna:1>"
    host.cached_context = _cached_context(prompt_text, (scheduled_lora,))
    controller.snapshot_for_prompt(
        prompt_text=prompt_text,
    )

    result = metadata_controller.refresh_lora_picker_snapshot_now(reason="test")
    snapshot = controller.snapshot_for_prompt(prompt_text=prompt_text)

    assert result.revision_changed is True
    assert len(snapshot.trigger_word_actions) == 1
    assert (
        snapshot.identity.catalog_revision
        == metadata_controller.snapshot.catalog_revision
    )


def test_lora_metadata_controller_projects_inline_token_action_without_cache() -> None:
    """Inline actions should derive purely from token-owned cached metadata."""

    host = _LoraMetadataHost()
    controller = _trigger_controller(host=host)
    token_context = PromptLoraTokenContext(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Midna",
        trained_words=("imp princess",),
        model_page_url=None,
    )
    prompt_text = "<lora:midna:1>"

    menu_action = controller.inline_action(
        token_context,
        prompt_text=prompt_text,
    )

    assert menu_action is not None
    assert host.cached_context_calls == 0


def test_lora_metadata_controller_rejects_stale_cached_action_snapshot() -> None:
    """Trigger-word actions should reject cache identity from another prompt."""

    host = _LoraMetadataHost()
    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Midna",
        trained_words=("imp princess",),
        source="cube_field",
    )
    host.cached_context = _cached_context("<lora:stale:1>", (scheduled_lora,))
    controller = _trigger_controller(host=host)

    snapshot = controller.snapshot_for_prompt(
        prompt_text="<lora:midna:1>",
    )

    assert snapshot.trigger_word_actions == ()
    assert snapshot.identity.stale is True
    assert snapshot.identity.unavailable_reason == "stale_scheduled_lora_context"


def test_lora_metadata_controller_omits_cold_cached_action_snapshot() -> None:
    """Cold scheduled-LoRA action context should produce an empty snapshot cheaply."""

    controller = _trigger_controller(host=_LoraMetadataHost())

    snapshot = controller.snapshot_for_prompt(
        prompt_text="<lora:midna:1>",
    )

    assert snapshot.trigger_word_actions == ()
    assert snapshot.consumable is False
    assert snapshot.status.readiness is CatalogSnapshotReadiness.COLD


def test_lora_metadata_controller_disables_trigger_word_action_snapshot() -> None:
    """Disabled LoRA trigger words should publish disabled action readiness."""

    controller = _trigger_controller(
        host=_LoraMetadataHost(),
        syntaxes=("wildcard",),
    )

    snapshot = controller.snapshot_for_prompt(
        prompt_text="<lora:midna:1>",
    )

    assert snapshot.trigger_word_actions == ()
    assert snapshot.consumable is False
    assert snapshot.status.readiness is CatalogSnapshotReadiness.DISABLED


def test_lora_trigger_controller_keeps_action_when_trigger_words_exist() -> None:
    """Prompt contents must not remove a scheduled LoRA from trigger actions."""

    prompt_text = "<lora:midna:1>, imp princess"
    host = _LoraMetadataHost()
    host.cached_context = _cached_context(
        prompt_text,
        (
            PromptScheduledLora(
                prompt_name="midna",
                backend_value="midna.safetensors",
                display_name="Midna",
                trained_words=("imp princess",),
                source="cube_field",
            ),
        ),
    )
    controller = _trigger_controller(host=host)

    snapshot = controller.snapshot_for_prompt(
        prompt_text=prompt_text,
    )

    assert snapshot.consumable is True
    assert len(snapshot.trigger_word_actions) == 1
    action = snapshot.trigger_word_actions[0]
    assert action.command_request is not None
    assert action.command_request.payload.insertion_text == "imp princess"


def test_lora_trigger_controller_keeps_full_action_for_partial_presence() -> None:
    """A partially present trained-word set should still insert its complete set."""

    prompt_text = "<lora:midna:1>, imp princess"
    host = _LoraMetadataHost()
    host.cached_context = _cached_context(
        prompt_text,
        (
            PromptScheduledLora(
                prompt_name="midna",
                backend_value="midna.safetensors",
                display_name="Midna",
                trained_words=("imp princess", "twili helmet"),
                source="cube_field",
            ),
        ),
    )
    snapshot = _trigger_controller(host=host).snapshot_for_prompt(
        prompt_text=prompt_text
    )

    assert len(snapshot.trigger_word_actions) == 1
    action = snapshot.trigger_word_actions[0]
    assert action.command_request is not None
    assert action.command_request.payload.insertion_text == (
        "imp princess, twili helmet"
    )


def test_trigger_word_controller_rejects_stale_source_profile_and_catalog() -> None:
    """Prepared actions should remain valid only while every owner identity matches."""

    prompt_text = "<lora:midna:1>"
    host = _LoraMetadataHost()
    host.cached_context = _cached_context(
        prompt_text,
        (
            PromptScheduledLora(
                prompt_name="midna",
                backend_value="midna.safetensors",
                display_name="Midna",
                trained_words=("imp princess",),
                source="cube_field",
            ),
        ),
    )
    current = {"profile": "profile-a", "catalog": "catalog-a"}
    controller = PromptLoraTriggerWordController(
        host=host,
        scheduled_lora_service=PromptScheduledLoraService(),
        scheduled_lora_context=cast(Any, host),
        feature_profile_id=lambda: current["profile"],
        catalog_revision=lambda: current["catalog"],
        trigger_words_enabled=lambda: True,
        effective_prompts=lambda: (host.toPlainText(),),
    )
    action = controller.snapshot_for_prompt(
        prompt_text=prompt_text
    ).trigger_word_actions[0]
    assert action.command_request is not None
    identity = action.command_request.identity

    assert controller.action_identity_is_current(identity) is True

    host.source_revision += 1
    assert controller.action_identity_is_current(identity) is False
    host.source_revision -= 1
    current["profile"] = "profile-b"
    assert controller.action_identity_is_current(identity) is False
    current["profile"] = "profile-a"
    current["catalog"] = "catalog-b"
    assert controller.action_identity_is_current(identity) is False


def test_trigger_word_controller_prewarms_raw_and_effective_scene_prompts() -> None:
    """Every committed source should warm all menu-visible scene contexts."""

    host = _LoraMetadataHost()
    controller = PromptLoraTriggerWordController(
        host=host,
        scheduled_lora_service=PromptScheduledLoraService(),
        scheduled_lora_context=cast(Any, host),
        feature_profile_id=lambda: "profile-a",
        catalog_revision=lambda: "catalog-a",
        trigger_words_enabled=lambda: True,
        effective_prompts=lambda: ("scene-a", "scene-b", "scene-a"),
    )

    controller.handle_source_changed()

    assert host.prewarm_prompts == [host.toPlainText(), "scene-a", "scene-b"]


def test_lora_metadata_controller_preserves_model_page_action_identity() -> None:
    """Model-page actions should carry prepared URL and source/catalog identity."""

    controller = _controller(host=_LoraMetadataHost(), dispatcher=_QueuedDispatcher())

    action = controller.model_page_action_for_token(
        PromptLoraTokenContext(
            prompt_name="midna",
            backend_value="midna.safetensors",
            display_name="Midna",
            trained_words=(),
            model_page_url="https://civitai.example/models/1",
        )
    )

    assert action is not None
    assert action.command_request is not None
    payload = action.command_request.payload
    assert payload.url == "https://civitai.example/models/1"
    assert payload.snapshot_identity is not None
    assert payload.snapshot_identity.query_identity == (
        "lora_model_page",
        "midna.safetensors",
    )


def test_lora_metadata_snapshot_publishes_warm_picker_rows() -> None:
    """Warm picker rows should publish from cached rows without catalog listing."""

    host = _LoraMetadataHost()
    catalog = _LoraCatalog((_item("Midna"),))
    controller = _controller(
        host=host,
        dispatcher=_QueuedDispatcher(),
        lora_catalog=catalog,
    )

    snapshot = controller.lora_picker_snapshot

    assert snapshot.items == (_item("Midna"),)
    assert snapshot.status.readiness is CatalogSnapshotReadiness.WARM
    assert catalog.cached_calls == 1
    assert catalog.list_calls == 0
    assert catalog.refresh_calls == 0
    assert controller.snapshot.picker_items == (_item("Midna"),)
    assert controller.snapshot.identity.source_revision == host.source_revision
    assert controller.snapshot.catalog_revision == 1
    assert controller.snapshot.unavailable_reason is None


def test_lora_metadata_snapshot_publishes_cold_picker_without_listing() -> None:
    """Cold picker rows should stay unavailable until explicit refresh runs."""

    catalog = _LoraCatalog((_item("Midna"),), cached=None)
    controller = _controller(
        host=_LoraMetadataHost(),
        dispatcher=_QueuedDispatcher(),
        lora_catalog=catalog,
    )

    snapshot = controller.lora_picker_snapshot

    assert snapshot.items == ()
    assert snapshot.status.readiness is CatalogSnapshotReadiness.COLD
    assert snapshot.consumable is False
    assert catalog.cached_calls == 1
    assert catalog.list_calls == 0
    assert catalog.refresh_calls == 0


def test_lora_metadata_snapshot_marks_dirty_state_stale() -> None:
    """Dirty LoRA metadata should publish a stale prepared snapshot."""

    controller = _controller(
        host=_LoraMetadataHost(),
        dispatcher=_QueuedDispatcher(),
        lora_catalog=_LoraCatalog((_item("Midna"),)),
    )

    controller.mark_dirty()

    assert controller.snapshot.stale is True
    assert controller.snapshot.identity.stale is True
    assert controller.lora_picker_snapshot.status.readiness is (
        CatalogSnapshotReadiness.STALE
    )
    assert controller.lora_picker_snapshot.items == (_item("Midna"),)
    assert controller.dirty is True


def test_lora_metadata_snapshot_records_refresh_failure() -> None:
    """Catalog refresh failure should produce an unavailable snapshot reason."""

    controller = _controller(
        host=_LoraMetadataHost(),
        dispatcher=_QueuedDispatcher(),
        lora_catalog=_LoraCatalog((), fail=True),
    )

    result = controller.refresh_lora_picker_snapshot_now(reason="test")

    assert result.rows_changed is False
    assert controller.lora_picker_snapshot.status.readiness is (
        CatalogSnapshotReadiness.REFRESH_FAILED
    )
    assert controller.snapshot.unavailable_reason == "refresh_failed"


def test_lora_metadata_snapshot_reflects_revision_change_on_refresh() -> None:
    """Explicit picker refresh should publish the newer catalog revision."""

    catalog = _LoraCatalog((_item("Mineru"),))
    dispatcher = _QueuedDispatcher()
    controller = _controller(
        host=_LoraMetadataHost(),
        dispatcher=dispatcher,
        lora_catalog=catalog,
    )

    result = controller.refresh_lora_picker_snapshot_now(reason="test")

    assert result.revision_changed is True
    assert catalog.refresh_calls == 1
    assert controller.snapshot.catalog_revision == 2
    assert controller.snapshot.picker_items == (_item("Mineru"),)


def test_lora_metadata_visible_picker_refresh_consumes_cached_snapshot_only() -> None:
    """Visible popup refresh should not refresh or list LoRA catalog rows."""

    catalog = _LoraCatalog((_item("Mineru"),), cached=(_item("Midna"),))
    controller = _controller(
        host=_LoraMetadataHost(),
        dispatcher=_QueuedDispatcher(),
        lora_catalog=catalog,
    )
    catalog.cached = (_item("Mineru"),)

    assert controller.refresh_visible_picker_data() is True

    assert catalog.cached_calls == 2
    assert catalog.refresh_calls == 0
    assert catalog.list_calls == 0
    assert controller.lora_picker_snapshot.items == (_item("Mineru"),)


def test_lora_metadata_snapshot_disables_picker_without_feature_gate() -> None:
    """Disabled LoRA picker feature should publish unavailable picker readiness."""

    controller = _controller(
        host=_LoraMetadataHost(),
        dispatcher=_QueuedDispatcher(),
        syntaxes=("wildcard",),
        lora_catalog=_LoraCatalog((_item("Midna"),)),
    )

    assert controller.lora_picker_ready is False
    assert controller.snapshot.action_ready is False
    assert controller.lora_picker_snapshot.status.readiness is (
        CatalogSnapshotReadiness.DISABLED
    )


def _controller(
    *,
    host: _LoraMetadataHost,
    dispatcher: _QueuedDispatcher,
    lora_catalog: _LoraCatalog | None = None,
    syntaxes: tuple[str, ...] = ("lora",),
) -> PromptLoraMetadataFeatureController:
    """Return a LoRA metadata controller for tests."""

    return PromptLoraMetadataFeatureController(
        host=host,
        feature_profile=PromptFeatureProfileController.from_legacy_syntax(
            prompt_syntax_profile(*syntaxes)
        ),
        lora_catalog=lora_catalog,
        lora_schedule_service=PromptLoraScheduleService(),
        scheduled_lora_service=PromptScheduledLoraService(),
        main_thread_dispatcher=cast(PromptEditorMainThreadDispatcher, dispatcher),
    )


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


def _import_prompt_editor_module() -> Any:
    """Import the prompt editor widget module."""

    return importlib.import_module(
        "substitute.presentation.editor.prompt_editor.widget"
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


def _projection_thumbnail_variant(storage_key: str) -> PromptProjectionThumbnailVariant:
    """Return one prepared projection thumbnail reference for cache tests."""

    return PromptProjectionThumbnailVariant(
        size=128,
        storage_key=storage_key,
        width=85,
        height=128,
        content_format="sqthumb-qimage-argb32-premultiplied",
        byte_size=43520,
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
