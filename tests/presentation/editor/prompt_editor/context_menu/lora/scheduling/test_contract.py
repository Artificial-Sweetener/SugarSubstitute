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

"""Verify scheduled-LoRA context-menu availability and cached state."""

from __future__ import annotations

from __future__ import annotations
from __future__ import annotations
from typing import Any, cast
import pytest
from PySide6.QtWidgets import QWidget
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    RoundMenu,
)
from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLora,
)
from substitute.presentation.editor.prompt_editor.shell.context_menu_controller import (
    _PromptEditorTextEditMenu,
)
from tests.presentation.editor.prompt_editor.context_menu.mounting import (
    create_lora_prompt_editor,
    create_lora_prompt_editor_with_resolver,
    create_prompt_editor,
    ensure_qapp,
    process_events,
)
from tests.presentation.editor.prompt_editor.context_menu.event_positions import (
    context_event_for_source_text,
    prepared_context_event_for_source_text,
)


def test_lora_feature_prewarm_delegates_to_context_coordinator(
    prompt_widgets: list[QWidget],
) -> None:
    """LoRA feature prewarm should use current text without widget ownership."""

    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("cached prompt")
    calls: list[str] = []

    class _ContextCoordinator:
        """Record scheduled-LoRA prewarm requests."""

        def prewarm(self, prompt_text: str) -> bool:
            """Record one prewarm prompt snapshot."""

            calls.append(prompt_text)
            return True

    controller = cast(Any, editor)._lora_trigger_word_controller
    controller._scheduled_lora_context = _ContextCoordinator()

    assert controller.prewarm_current_source() is True
    assert calls == ["cached prompt"]
    assert editor.toPlainText() == "cached prompt"


def test_prompt_editor_context_menu_uses_cached_scheduled_loras(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Context menu should not synchronously resolve LoRAs when prewarm cached them."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("midna helmet",),
        source="cube_field",
    )
    resolver_calls: list[str] = []

    def resolve_no_loras(prompt_text: str) -> tuple[PromptScheduledLora, ...]:
        """Record resolver calls while returning no scheduled LoRAs."""

        resolver_calls.append(prompt_text)
        return ()

    editor = create_lora_prompt_editor_with_resolver(
        prompt_widgets,
        scheduled_lora_resolver=resolve_no_loras,
    )
    prompt_text = editor.toPlainText()
    lifecycle = cast(Any, editor)._autocomplete_refresh_controller._lifecycle_requester
    provider = lifecycle._result_controller._trigger_word_provider._context_provider
    assert provider is not None
    cache_key = provider.cache_key_for_prompt(prompt_text)
    provider.complete_for_tests(
        cache_key=cache_key,
        prompt_text=prompt_text,
        scheduled_loras=(scheduled_lora,),
    )
    cast(
        Any,
        editor,
    )._lora_trigger_word_controller.snapshot_for_prompt(
        prompt_text=prompt_text,
    )
    resolver_calls.clear()
    trigger_full_labels: list[object] = []

    def fake_exec(
        self: _PromptEditorTextEditMenu,
        *_args: object,
        **_kwargs: object,
    ) -> None:
        """Capture trigger rows from the lazily rendered submenu model."""

        trigger_full_labels.extend(_trigger_full_labels(self))

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        prepared_context_event_for_source_text(editor, "alpha")
    )

    assert resolver_calls == []
    assert "Trigger words: Friendly Midna" in trigger_full_labels


def test_prompt_editor_context_menu_omits_uncached_scheduled_lora_resolver(
    prompt_widgets: list[QWidget],
) -> None:
    """Context menu scheduled-LoRA lookup should not run a cold resolver."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("midna helmet",),
        source="cube_field",
    )
    resolver_calls: list[str] = []

    def resolve_scheduled_loras(prompt_text: str) -> tuple[PromptScheduledLora, ...]:
        """Record resolver calls while returning one scheduled LoRA."""

        resolver_calls.append(prompt_text)
        return (scheduled_lora,)

    editor = create_lora_prompt_editor_with_resolver(
        prompt_widgets,
        scheduled_lora_resolver=resolve_scheduled_loras,
    )
    resolver_calls.clear()
    prewarm_calls: list[str] = []

    class _ColdScheduledLoraContext:
        """Expose a cold cache while recording the requested async prewarm."""

        def cached_context_snapshot(self, _prompt_text: str) -> None:
            """Return no cached scheduled-LoRA context."""

            return None

        def prewarm(self, prompt_text: str) -> bool:
            """Record a non-blocking context request."""

            prewarm_calls.append(prompt_text)
            return True

    controller = cast(Any, editor)._lora_trigger_word_controller
    controller._scheduled_lora_context = _ColdScheduledLoraContext()

    assert (
        controller.snapshot_for_prompt(
            prompt_text=editor.toPlainText()
        ).trigger_word_actions
        == ()
    )
    assert resolver_calls == []
    assert prewarm_calls == [editor.toPlainText()]


def test_prompt_editor_context_menu_uses_scene_effective_lora_context(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Trigger-word actions should use universal text plus the clicked scene."""

    global_lora = PromptScheduledLora(
        prompt_name="global",
        backend_value="global.safetensors",
        display_name="Global LoRA",
        trained_words=("global trigger",),
        source="inline_prompt",
    )
    portrait_lora = PromptScheduledLora(
        prompt_name="portrait",
        backend_value="portrait.safetensors",
        display_name="Portrait LoRA",
        trained_words=("portrait trigger",),
        source="inline_prompt",
    )
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

    editor = create_lora_prompt_editor_with_resolver(
        prompt_widgets,
        scheduled_lora_resolver=resolve_scheduled_loras,
    )
    editor.setPlainText(
        "<lora:global:1>\n**portrait\n<lora:portrait:1>\nportrait text\n**cafe\ncafe text"
    )
    process_events(ensure_qapp())
    context_event = context_event_for_source_text(editor, "cafe text")
    source_position = cast(
        Any, editor
    )._shell_context_menu._source_position_for_global_pos(context_event.globalPos())
    assert source_position is not None
    context_prompt_snapshot = cast(
        Any,
        editor,
    )._scene_position_preparation.prepare_position_context(
        source_position,
        reason="test_context_menu_scene_position",
    )
    assert context_prompt_snapshot.context is not None
    context_prompt_text = context_prompt_snapshot.context.effective_prompt_text
    lifecycle = cast(Any, editor)._autocomplete_refresh_controller._lifecycle_requester
    provider = lifecycle._result_controller._trigger_word_provider._context_provider
    assert provider is not None
    cache_key = provider.cache_key_for_prompt(context_prompt_text)
    provider.complete_for_tests(
        cache_key=cache_key,
        prompt_text=context_prompt_text,
        scheduled_loras=(global_lora,),
    )
    cast(
        Any,
        editor,
    )._lora_trigger_word_controller.snapshot_for_prompt(
        prompt_text=context_prompt_text,
    )
    resolver_calls.clear()
    trigger_full_labels: list[object] = []

    def fake_exec(
        self: _PromptEditorTextEditMenu,
        *_args: object,
        **_kwargs: object,
    ) -> None:
        """Capture trigger rows from the lazily rendered submenu model."""

        trigger_full_labels.extend(_trigger_full_labels(self))

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(context_event)

    assert "Trigger words: Global LoRA" in trigger_full_labels
    assert "Trigger words: Portrait LoRA" not in trigger_full_labels
    assert resolver_calls == []


def _trigger_full_labels(menu: RoundMenu) -> tuple[object, ...]:
    """Return trigger labels through the rendered lazy submenu boundary."""

    submenu = next(
        candidate
        for candidate in cast(Any, menu)._subMenus
        if candidate.title() == "Insert trigger words"
    )
    getattr(submenu, "populate_if_needed")()
    return tuple(
        action.property("promptFullTriggerWordsLabel")
        for action in submenu.menuActions()
    )


def test_prompt_editor_lora_context_menu_hides_schedule_action_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Disabled LoRA picker support should remove Schedule LoRA from the menu."""

    editor = create_lora_prompt_editor(prompt_widgets)
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture the final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    menu_type = _PromptEditorTextEditMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        schedule_lora_enabled=False,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    assert "Cancel" not in action_texts
    assert "Select all" in action_texts
    assert "Schedule LoRA" not in action_texts
