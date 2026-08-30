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

"""Contracts for prompt-editor LoRA trigger-word action projection."""

from __future__ import annotations


from typing import Any, cast

from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLora,
    PromptScheduledLoraService,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    scheduled_lora_signature,
)
from substitute.presentation.editor.prompt_editor.features import (
    CatalogSnapshotReadiness,
    PromptLoraTokenContext,
    PromptLoraTriggerWordController,
)

from .support import (
    _LoraCatalog,
    _LoraMetadataHost,
    _QueuedDispatcher,
    _cached_context,
    _item,
    _metadata_owners,
    _trigger_controller,
)


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
    metadata_owners = _metadata_owners(
        host=host,
        dispatcher=_QueuedDispatcher(),
        lora_catalog=catalog,
    )
    controller = _trigger_controller(
        host=host,
        catalog_revision=lambda: metadata_owners.presentation.snapshot.catalog_revision,
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

    result = metadata_owners.refresh.refresh_lora_picker_snapshot_now(reason="test")
    snapshot = controller.snapshot_for_prompt(prompt_text=prompt_text)

    assert result.revision_changed is True
    assert len(snapshot.trigger_word_actions) == 1
    assert (
        snapshot.identity.catalog_revision
        == metadata_owners.presentation.snapshot.catalog_revision
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
