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

"""Verify deferred LoRA trigger-menu population in the production shell."""

from __future__ import annotations

from pathlib import Path

from dataclasses import replace

from tests.support.prompt_editor.real_shell.context_menu_probe import (
    cached_scheduled_loras,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)
from tests.support.prompt_editor.projection_surface_support import (
    StaticPromptLoraCatalog,
    lora_catalog_item_with_banner,
)


def test_real_shell_lora_trigger_menu_defers_lazy_submenu_population(
    tmp_path: Path,
) -> None:
    """Leave trigger rows unbuilt until their submenu is explicitly opened."""

    item_count = 50
    items = tuple(
        replace(
            lora_catalog_item_with_banner(prompt_name=f"midna_{index}"),
            display_name=f"Midna {index}",
            trained_words=(f"imp princess {index}",),
        )
        for index in range(item_count)
    )
    real_shell_scenario = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_lora_catalog_service=StaticPromptLoraCatalog(items),
    )
    try:
        field = real_shell_scenario.workflows.add_prompt_workflow(
            initial_text=(
                "portrait, "
                + ", ".join(f"<lora:midna_{index}:1>" for index in range(item_count))
            )
        )
        editor = field.editor
        real_shell_scenario.wait_until(
            lambda: cached_scheduled_loras(editor, editor.toPlainText()) is not None
        )

        trace = real_shell_scenario.context_menus.trace(
            field,
            clicked_text="portrait",
            populate_lazy_submenus=False,
        )

        assert trace.captured_action_count == 0
        assert trace.captured_submenu_row_count == 0
        assert ("Insert trigger words", ()) in trace.submenu_rows
        assert trace.cached_scheduled_lora_count_before == item_count
    finally:
        real_shell_scenario.close()
