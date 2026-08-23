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

"""Test inline LoRA scene freshness handling."""

from __future__ import annotations

from PySide6.QtCore import QPoint

from tests.presentation.editor.prompt_editor.interactions.inline_lora_menu.support import (
    InsertionExecutor,
    LoraMetadata,
    ShellMenu,
    actions,
    ensure_qapp,
    build_presenter,
    token,
)


def test_phase24_5_inline_lora_presenter_omits_stale_scene_trigger_action() -> None:
    """Inline LoRA menus should not compute trigger words from stale scene context."""

    ensure_qapp()
    metadata = LoraMetadata()
    shell_menu = ShellMenu()
    presenter = build_presenter(
        metadata=metadata,
        shell_menu=shell_menu,
        insertion_executor=InsertionExecutor(),
        opened_urls=[],
        effective_prompt_text="stale scene prompt",
        finish_reasons=[],
        scene_ready=False,
    )

    presenter.show_lora_context_menu(
        token(
            model_page_url="https://civitai.example/models/2",
            trained_words=("scene trigger",),
        ),
        QPoint(30, 40),
    )

    assert metadata.trigger_prompt_texts == []
    assert len(shell_menu.calls) == 1
    _trigger_pos, trigger_action, metadata_menu_items = shell_menu.calls[0]
    assert trigger_action is None
    page_action = actions(metadata_menu_items)[0]
    assert page_action is not None
