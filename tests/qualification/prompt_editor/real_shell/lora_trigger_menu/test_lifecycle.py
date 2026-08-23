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

"""Verify LoRA trigger actions across prompt and workflow lifecycle changes."""

from __future__ import annotations

from pathlib import Path

from dataclasses import replace
from typing import Any, cast

from tests.support.prompt_editor.projection_surface_support import (
    StaticPromptLoraCatalog,
    lora_catalog_item_with_banner,
)
from tests.support.prompt_editor.real_shell.context_menu_probe import (
    cached_scheduled_loras,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_lora_trigger_probe_follows_direct_source_replacement(
    tmp_path: Path,
) -> None:
    """Trigger actions should follow source replaced through the public editor API."""

    items = tuple(
        replace(
            lora_catalog_item_with_banner(prompt_name=name),
            display_name=display_name,
            trained_words=(trigger_word,),
        )
        for name, display_name, trigger_word in (
            ("midna", "Midna", "imp princess"),
            ("zelda", "Zelda", "wise princess"),
        )
    )
    shell_harness = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items),
    )
    try:
        field = shell_harness.workflows.add_prompt_workflow(
            initial_text="<lora:midna:1>, portrait"
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        editor.setPlainText("<lora:zelda:1>, landscape")
        shell_harness.wait_for_queued_delivery()
        trace = shell_harness.context_menus.trace(
            field,
            clicked_text="landscape",
        )

        assert trace.trigger_action_full_labels == ("Trigger words: Zelda",)
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_can_insert_two_scheduled_loras_in_sequence(
    tmp_path: Path,
) -> None:
    """Inserting one LoRA's words should leave the other LoRA action usable."""

    items = tuple(
        replace(
            lora_catalog_item_with_banner(prompt_name=name),
            display_name=display_name,
            trained_words=(trigger_word,),
        )
        for name, display_name, trigger_word in (
            ("midna", "Midna", "imp princess"),
            ("zelda", "Zelda", "wise princess"),
        )
    )
    shell_harness = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items),
    )
    try:
        field = shell_harness.workflows.add_prompt_workflow(
            initial_text="<lora:midna:1>, <lora:zelda:1>, portrait"
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        first = shell_harness.context_menus.trace(
            field,
            clicked_text="portrait",
            trigger_lora_action_label="Trigger words: Midna",
        )
        second = shell_harness.context_menus.trace(
            field,
            clicked_text="port",
            trigger_lora_action_label="Trigger words: Zelda",
        )

        assert first.triggered_action_text == "Midna"
        assert second.triggered_action_text == "Zelda"
        assert "imp princess" in second.source_after
        assert "wise princess" in second.source_after
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_does_not_split_clicked_prompt_word(
    tmp_path: Path,
) -> None:
    """Trigger insertion should preserve the prompt token used to open the menu."""

    item = replace(
        lora_catalog_item_with_banner(prompt_name="midna"),
        trained_words=("imp princess",),
    )
    shell_harness = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_lora_catalog_service=StaticPromptLoraCatalog((item,)),
    )
    try:
        field = shell_harness.workflows.add_prompt_workflow(
            initial_text="<lora:midna:1>, portrait"
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        trace = shell_harness.context_menus.trace(
            field,
            clicked_text="portrait",
            trigger_first_lora_action=True,
        )

        assert "portrait" in trace.source_after
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_rejects_action_after_source_changes(
    tmp_path: Path,
) -> None:
    """An action captured for an old source revision should not mutate new source."""

    item = replace(
        lora_catalog_item_with_banner(prompt_name="midna"),
        trained_words=("imp princess",),
    )
    shell_harness = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_lora_catalog_service=StaticPromptLoraCatalog((item,)),
    )
    try:
        field = shell_harness.workflows.add_prompt_workflow(
            initial_text="<lora:midna:1>, portrait"
        )
        editor = field.editor
        replacement = "unrelated replacement prompt"
        shell_harness.wait_until(
            lambda: cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        trace = shell_harness.context_menus.trace(
            field,
            clicked_text="portrait",
            trigger_first_lora_action=True,
            before_trigger_lora_action=lambda: editor.setPlainText(replacement),
        )

        assert trace.source_after == replacement
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_recovers_after_explicit_rewarm(
    tmp_path: Path,
) -> None:
    """Explicitly warming changed source should restore remaining LoRA actions."""

    items = tuple(
        replace(
            lora_catalog_item_with_banner(prompt_name=name),
            display_name=display_name,
            trained_words=(trigger_word,),
        )
        for name, display_name, trigger_word in (
            ("midna", "Midna", "imp princess"),
            ("zelda", "Zelda", "wise princess"),
        )
    )
    shell_harness = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items),
    )
    try:
        field = shell_harness.workflows.add_prompt_workflow(
            initial_text="<lora:midna:1>, <lora:zelda:1>, portrait"
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )
        shell_harness.context_menus.trace(
            field,
            clicked_text="portrait",
            trigger_lora_action_label="Trigger words: Midna",
        )

        cast(
            Any,
            editor,
        )._lora_trigger_word_controller.prewarm_current_source()
        shell_harness.wait_until(
            lambda: cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )
        trace = shell_harness.context_menus.trace(
            field,
            clicked_text="port",
            trigger_lora_action_label="Trigger words: Zelda",
        )

        assert trace.triggered_action_text == "Zelda"
        assert "wise princess" in trace.source_after
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_recovers_remaining_action_after_workflow_switch(
    tmp_path: Path,
) -> None:
    """Switching away and back should restore actions after a trigger insertion."""

    items = tuple(
        replace(
            lora_catalog_item_with_banner(prompt_name=name),
            display_name=display_name,
            trained_words=(trigger_word,),
        )
        for name, display_name, trigger_word in (
            ("midna", "Midna", "imp princess"),
            ("zelda", "Zelda", "wise princess"),
        )
    )
    shell_harness = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items),
    )
    try:
        field = shell_harness.workflows.add_prompt_workflow(
            initial_text="<lora:midna:1>, <lora:zelda:1>, portrait"
        )
        shell_harness.wait_until(
            lambda: (
                cached_scheduled_loras(field.editor, field.editor.toPlainText())
                is not None
            )
        )
        first = shell_harness.context_menus.trace(
            field,
            clicked_text="portrait",
            trigger_lora_action_label="Trigger words: Midna",
        )

        returned_field = shell_harness.workflows.workflow_round_trip(field)
        trace = shell_harness.context_menus.trace(
            returned_field,
            clicked_text="port",
            trigger_lora_action_label="Trigger words: Zelda",
        )

        assert first.triggered_action_text == "Midna"
        assert trace.triggered_action_text == "Zelda"
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_survives_workflow_round_trip(
    tmp_path: Path,
) -> None:
    """Prepared trigger actions should survive switching away and back."""

    item = replace(
        lora_catalog_item_with_banner(prompt_name="midna"),
        trained_words=("imp princess",),
    )
    shell_harness = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_lora_catalog_service=StaticPromptLoraCatalog((item,)),
    )
    try:
        field = shell_harness.workflows.add_prompt_workflow(
            initial_text="<lora:midna:1>, portrait"
        )
        shell_harness.wait_until(
            lambda: (
                cached_scheduled_loras(field.editor, field.editor.toPlainText())
                is not None
            )
        )

        returned_field = shell_harness.workflows.workflow_round_trip(field)
        trace = shell_harness.context_menus.trace(
            returned_field,
            clicked_text="portrait",
            trigger_first_lora_action=True,
        )

        assert trace.triggered_action_text == "Midna"
        assert "imp princess" in trace.source_after
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_keeps_workflow_contexts_isolated(
    tmp_path: Path,
) -> None:
    """Each workflow should expose actions for its own scheduled LoRA."""

    items = tuple(
        replace(
            lora_catalog_item_with_banner(prompt_name=name),
            display_name=display_name,
            trained_words=(trigger_word,),
        )
        for name, display_name, trigger_word in (
            ("midna", "Midna", "imp princess"),
            ("zelda", "Zelda", "wise princess"),
        )
    )
    shell_harness = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items),
    )
    try:
        midna_field = shell_harness.workflows.add_prompt_workflow(
            "midna-workflow",
            initial_text="<lora:midna:1>, portrait",
        )
        zelda_field = shell_harness.workflows.add_prompt_workflow(
            "zelda-workflow",
            initial_text="<lora:zelda:1>, landscape",
        )
        shell_harness.wait_until(
            lambda: (
                cached_scheduled_loras(
                    zelda_field.editor,
                    zelda_field.editor.toPlainText(),
                )
                is not None
            )
        )

        zelda_trace = shell_harness.context_menus.trace(
            zelda_field,
            clicked_text="landscape",
        )
        shell_harness.workflows.activate_workflow("midna-workflow")
        midna_field = shell_harness.workflows.prompt_field("midna-workflow")
        shell_harness.wait_until(
            lambda: (
                cached_scheduled_loras(
                    midna_field.editor,
                    midna_field.editor.toPlainText(),
                )
                is not None
            )
        )
        midna_trace = shell_harness.context_menus.trace(
            midna_field,
            clicked_text="portrait",
        )

        assert zelda_trace.trigger_action_full_labels == ("Trigger words: Zelda",)
        assert midna_trace.trigger_action_full_labels == ("Trigger words: Midna",)
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_returns_after_undo(tmp_path: Path) -> None:
    """Undoing trigger insertion should make the trigger action available again."""

    item = replace(
        lora_catalog_item_with_banner(prompt_name="midna"),
        trained_words=("imp princess",),
    )
    shell_harness = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_lora_catalog_service=StaticPromptLoraCatalog((item,)),
    )
    try:
        field = shell_harness.workflows.add_prompt_workflow(
            initial_text="<lora:midna:1>, portrait"
        )
        editor = field.editor
        original_text = editor.toPlainText()
        shell_harness.wait_until(
            lambda: cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )
        shell_harness.context_menus.trace(
            field,
            clicked_text="portrait",
            trigger_first_lora_action=True,
        )

        editor.undo()
        shell_harness.wait_for_queued_delivery()
        trace = shell_harness.context_menus.trace(
            field,
            clicked_text="portrait",
        )

        assert editor.toPlainText() == original_text
        assert trace.trigger_action_full_labels == ("Trigger words: Midna",)
    finally:
        shell_harness.close()


def test_real_shell_inline_lora_trigger_probe_exposes_prepared_action(
    tmp_path: Path,
) -> None:
    """Right-clicking an inline LoRA token should expose its trigger action."""

    item = replace(
        lora_catalog_item_with_banner(prompt_name="midna"),
        trained_words=("imp princess",),
    )
    shell_harness = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_lora_catalog_service=StaticPromptLoraCatalog((item,)),
    )
    try:
        field = shell_harness.workflows.add_prompt_workflow(
            initial_text="<lora:midna:1>, portrait"
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        trace = shell_harness.context_menus.probe_inline_lora_menu(field)

        assert trace.trigger_action_full_labels == ("Trigger words: Midna",)
    finally:
        shell_harness.close()
