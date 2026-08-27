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

"""Verify LoRA trigger context-menu actions through the real prompt shell."""

from __future__ import annotations

from pathlib import Path

from dataclasses import replace

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


def test_real_shell_traces_lora_trigger_context_menu(tmp_path: Path) -> None:
    """Trace a real right-click LoRA trigger action through the mounted editor."""

    item = replace(
        lora_catalog_item_with_banner(prompt_name="midna"),
        trained_words=("imp princess", "twili helmet"),
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
        trace_before_prepare = shell_harness.context_menus.trace(
            field,
            clicked_text="portrait",
        )
        assert trace_before_prepare.cached_scheduled_lora_count_before == 1
        assert trace_before_prepare.trigger_action_full_labels == (
            "Trigger words: Midna",
        )
        assert trace_before_prepare.trigger_action_texts == ("Midna",)
        assert "Midna" not in trace_before_prepare.menu_rows
        assert trace_before_prepare.submenu_rows == (
            ("Insert trigger words", ("Midna",)),
        )

        trace = shell_harness.context_menus.trace(
            field,
            clicked_text="portrait",
            trigger_first_lora_action=True,
        )

        assert trace.trigger_action_full_labels == ("Trigger words: Midna",)
        assert trace.triggered_action_text == "Midna"
        assert "imp princess, twili helmet" in trace.source_after
    finally:
        shell_harness.close()


def test_real_shell_trigger_submenu_keeps_all_loras_when_words_exist(
    tmp_path: Path,
) -> None:
    """Existing prompt words must not hide scheduled LoRAs or flatten the submenu."""

    control_name = (
        "Illustrious\\Concept\\[Malebolgia] CONTROL BANANA Experiment Illustrious"
    )
    peoples_name = "Anima\\style\\People'sWorks_v10_Animabasev1.0_test3-000008"
    items = (
        replace(
            lora_catalog_item_with_banner(prompt_name=control_name),
            display_name="CONTROL BANANA Experiment Illustrious",
            display_subtitle=None,
            trained_words=("controlbananas",),
        ),
        replace(
            lora_catalog_item_with_banner(prompt_name=peoples_name),
            display_name="People's Works: Anima",
            display_subtitle="v10 Animabase",
            trained_words=("ppw",),
        ),
    )
    prompt = (
        "best quality, controlbananas, ppw, masterpiece\n\n"
        f"<lora:{control_name}:1.00>\n\n<lora:{peoples_name}:1.00>"
    )
    shell_harness = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items),
    )
    try:
        field = shell_harness.workflows.add_prompt_workflow(initial_text=prompt)
        shell_harness.wait_until(
            lambda: (
                cached_scheduled_loras(field.editor, field.editor.toPlainText())
                is not None
            )
        )

        trace = shell_harness.context_menus.trace(
            field,
            clicked_text="masterpiece",
        )

        assert trace.cached_scheduled_lora_count_before == 2
        assert trace.trigger_action_full_labels == (
            "Trigger words: CONTROL BANANA Experiment Illustrious",
            "Trigger words: People's Works: Anima - v10 Animabase",
        )
        assert len(trace.trigger_action_texts) == 2
        assert trace.submenu_rows == (
            ("Insert trigger words", trace.trigger_action_texts),
        )
        assert not set(trace.trigger_action_texts).intersection(trace.menu_rows)

        inserted = shell_harness.context_menus.trace(
            field,
            clicked_text="masterpiece",
            trigger_lora_action_label=(
                "Trigger words: CONTROL BANANA Experiment Illustrious"
            ),
        )
        assert inserted.source_after.count("controlbananas") == 2
        shell_harness.wait_until(
            lambda: (
                cached_scheduled_loras(field.editor, field.editor.toPlainText())
                is not None
            )
        )
        reopened = shell_harness.context_menus.trace(
            field,
            clicked_text="masterpiece",
        )
        assert reopened.trigger_action_full_labels == trace.trigger_action_full_labels
        assert reopened.submenu_rows == (
            ("Insert trigger words", reopened.trigger_action_texts),
        )
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_survives_unrelated_prompt_edit(
    tmp_path: Path,
) -> None:
    """Trigger actions should follow the current source after ordinary typing."""

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

        shell_harness.input.move_cursor_to_end(field)
        shell_harness.input.type_text(field, ", dramatic lighting")
        trace = shell_harness.context_menus.trace(
            field,
            clicked_text="portrait",
        )

        assert trace.trigger_action_full_labels == ("Trigger words: Midna",)
        assert trace.cached_scheduled_lora_count_before == 1
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_survives_repeated_menu_openings(
    tmp_path: Path,
) -> None:
    """Opening and cancelling the menu repeatedly should preserve trigger actions."""

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

        traces = tuple(
            shell_harness.context_menus.trace(
                field,
                clicked_text="portrait",
            )
            for _index in range(10)
        )

        assert all(
            trace.trigger_action_full_labels == ("Trigger words: Midna",)
            for trace in traces
        )
        assert all(trace.source_after == trace.source_before for trace in traces)
    finally:
        shell_harness.close()


def test_real_shell_lora_trigger_probe_selects_last_of_many_actions(
    tmp_path: Path,
) -> None:
    """A named action should remain usable at the end of a populated submenu."""

    item_count = 24
    items = tuple(
        replace(
            lora_catalog_item_with_banner(prompt_name=f"lora_{index}"),
            display_name=f"LoRA {index}",
            trained_words=(f"trigger {index}",),
        )
        for index in range(item_count)
    )
    shell_harness = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items),
    )
    try:
        field = shell_harness.workflows.add_prompt_workflow(
            initial_text=(
                "portrait, "
                + ", ".join(f"<lora:lora_{index}:1>" for index in range(item_count))
            )
        )
        editor = field.editor
        shell_harness.wait_until(
            lambda: cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        trace = shell_harness.context_menus.trace(
            field,
            clicked_text="portrait",
            trigger_lora_action_label=f"Trigger words: LoRA {item_count - 1}",
        )

        assert trace.captured_action_count == item_count
        assert trace.triggered_action_text == f"LoRA {item_count - 1}"
        assert f"trigger {item_count - 1}" in trace.source_after
    finally:
        shell_harness.close()
