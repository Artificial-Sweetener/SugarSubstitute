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

"""Test inline LoRA metadata actions."""

from __future__ import annotations

from PySide6.QtCore import QPoint

from tests.presentation.editor.prompt_editor.interactions.inline_lora_menu.support import (
    InsertionExecutor,
    LoraMetadata,
    MetadataActionHandler,
    ShellMenu,
    actions,
    ensure_qapp,
    build_presenter,
    token,
)


def test_inline_lora_presenter_builds_refresh_action_for_backend_token() -> None:
    """Inline LoRA metadata actions should include refresh for local targets."""

    ensure_qapp()
    shell_menu = ShellMenu()
    metadata_handler = MetadataActionHandler()
    presenter = build_presenter(
        metadata=LoraMetadata(),
        shell_menu=shell_menu,
        insertion_executor=InsertionExecutor(),
        opened_urls=[],
        effective_prompt_text="portrait",
        finish_reasons=[],
        metadata_action_handler=metadata_handler,
    )

    presenter.show_lora_context_menu(
        token(model_page_url=None, trained_words=()),
        QPoint(1, 2),
    )

    assert len(shell_menu.calls) == 1
    _global_pos, trigger_action, metadata_menu_items = shell_menu.calls[0]
    assert trigger_action is None
    metadataactions = actions(metadata_menu_items)
    assert [action.label for action in metadataactions] == [
        "Refresh CivitAI metadata",
        "Set thumbnail from canvas",
    ]
    refresh_action = metadataactions[0]

    refresh_action.callback()

    assert len(metadata_handler.refresh_targets) == 1
    target = metadata_handler.refresh_targets[0]
    assert getattr(target, "backend_value") == "midna.safetensors"
    assert getattr(target, "model_kind") == "loras"
