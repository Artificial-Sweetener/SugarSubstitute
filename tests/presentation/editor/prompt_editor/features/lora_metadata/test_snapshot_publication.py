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

"""Contracts for prompt-editor LoRA metadata snapshot publication."""

from __future__ import annotations


from substitute.presentation.editor.prompt_editor.features import (
    CatalogSnapshotReadiness,
    PromptLoraTokenContext,
)

from .support import (
    _LoraCatalog,
    _LoraMetadataHost,
    _QueuedDispatcher,
    _item,
    _metadata_owners,
)


def test_lora_metadata_controller_preserves_model_page_action_identity() -> None:
    """Model-page actions should carry prepared URL and source/catalog identity."""

    controller = _metadata_owners(
        host=_LoraMetadataHost(), dispatcher=_QueuedDispatcher()
    ).presentation

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
    controller = _metadata_owners(
        host=host,
        dispatcher=_QueuedDispatcher(),
        lora_catalog=catalog,
    ).presentation

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
    owners = _metadata_owners(
        host=_LoraMetadataHost(),
        dispatcher=_QueuedDispatcher(),
        lora_catalog=catalog,
    )
    controller = owners.presentation

    snapshot = controller.lora_picker_snapshot

    assert snapshot.items == ()
    assert snapshot.status.readiness is CatalogSnapshotReadiness.COLD
    assert snapshot.consumable is False
    assert catalog.cached_calls == 1
    assert catalog.list_calls == 0
    assert catalog.refresh_calls == 0


def test_lora_metadata_snapshot_marks_dirty_state_stale() -> None:
    """Dirty LoRA metadata should publish a stale prepared snapshot."""

    owners = _metadata_owners(
        host=_LoraMetadataHost(),
        dispatcher=_QueuedDispatcher(),
        lora_catalog=_LoraCatalog((_item("Midna"),)),
    )
    controller = owners.presentation

    owners.refresh.mark_dirty()

    assert controller.snapshot.stale is True
    assert controller.snapshot.identity.stale is True
    assert controller.lora_picker_snapshot.status.readiness is (
        CatalogSnapshotReadiness.STALE
    )
    assert controller.lora_picker_snapshot.items == (_item("Midna"),)
    assert owners.refresh.dirty is True


def test_lora_metadata_snapshot_records_refresh_failure() -> None:
    """Catalog refresh failure should produce an unavailable snapshot reason."""

    owners = _metadata_owners(
        host=_LoraMetadataHost(),
        dispatcher=_QueuedDispatcher(),
        lora_catalog=_LoraCatalog((), fail=True),
    )
    controller = owners.presentation

    result = owners.refresh.refresh_lora_picker_snapshot_now(reason="test")

    assert result.rows_changed is False
    assert controller.lora_picker_snapshot.status.readiness is (
        CatalogSnapshotReadiness.REFRESH_FAILED
    )
    assert controller.snapshot.unavailable_reason == "refresh_failed"


def test_lora_metadata_snapshot_reflects_revision_change_on_refresh() -> None:
    """Explicit picker refresh should publish the newer catalog revision."""

    catalog = _LoraCatalog((_item("Mineru"),))
    dispatcher = _QueuedDispatcher()
    owners = _metadata_owners(
        host=_LoraMetadataHost(),
        dispatcher=dispatcher,
        lora_catalog=catalog,
    )
    controller = owners.presentation

    result = owners.refresh.refresh_lora_picker_snapshot_now(reason="test")

    assert result.revision_changed is True
    assert catalog.refresh_calls == 1
    assert controller.snapshot.catalog_revision == 2
    assert controller.snapshot.picker_items == (_item("Mineru"),)


def test_lora_metadata_visible_picker_refresh_consumes_cached_snapshot_only() -> None:
    """Visible popup refresh should not refresh or list LoRA catalog rows."""

    catalog = _LoraCatalog((_item("Mineru"),), cached=(_item("Midna"),))
    controller = _metadata_owners(
        host=_LoraMetadataHost(),
        dispatcher=_QueuedDispatcher(),
        lora_catalog=catalog,
    ).presentation
    catalog.cached = (_item("Mineru"),)

    assert controller.refresh_picker_from_cache() is True

    assert catalog.cached_calls == 2
    assert catalog.refresh_calls == 0
    assert catalog.list_calls == 0
    assert controller.lora_picker_snapshot.items == (_item("Mineru"),)


def test_lora_metadata_snapshot_disables_picker_without_feature_gate() -> None:
    """Disabled LoRA picker feature should publish unavailable picker readiness."""

    controller = _metadata_owners(
        host=_LoraMetadataHost(),
        dispatcher=_QueuedDispatcher(),
        syntaxes=("wildcard",),
        lora_catalog=_LoraCatalog((_item("Midna"),)),
    ).presentation

    assert controller.lora_picker_ready is False
    assert controller.snapshot.action_ready is False
    assert controller.lora_picker_snapshot.status.readiness is (
        CatalogSnapshotReadiness.DISABLED
    )
