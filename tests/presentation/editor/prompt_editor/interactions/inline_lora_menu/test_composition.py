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

"""Test inline LoRA menu composition."""

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


def test_inline_lora_presenter_builds_page_and_trigger_actions() -> None:
    """The presenter should adapt a projected token into shell menu actions."""

    ensure_qapp()
    opened_urls: list[str] = []
    metadata = LoraMetadata()
    shell_menu = ShellMenu()
    insertion_executor = InsertionExecutor()
    finish_reasons: list[str] = []
    presenter = build_presenter(
        metadata=metadata,
        shell_menu=shell_menu,
        insertion_executor=insertion_executor,
        opened_urls=opened_urls,
        effective_prompt_text="imp princess, portrait",
        finish_reasons=finish_reasons,
    )

    presenter.show_lora_context_menu(
        token(
            model_page_url="https://civitai.example/models/1",
            trained_words=("imp princess", "twili helmet"),
        ),
        QPoint(20, 40),
    )

    assert finish_reasons == ["lora_context_menu"]
    assert len(shell_menu.calls) == 1
    global_pos, trigger_action, metadata_menu_items = shell_menu.calls[0]
    assert global_pos == QPoint(20, 40)
    assert metadata.trigger_prompt_texts == ["imp princess, portrait"]
    assert trigger_action is not None
    assert trigger_action.toolTip() == "Trigger words: Friendly Midna"
    assert (
        trigger_action.property("promptFullTriggerWordsLabel")
        == "Trigger words: Friendly Midna"
    )
    trigger_action.trigger()
    assert insertion_executor.inserted == ["imp princess, twili helmet"]
    metadataactions = actions(metadata_menu_items)
    assert len(metadataactions) == 1
    page_action = metadataactions[0]
    assert page_action is not None
    assert page_action.label == "Go to CivitAI page"
    page_action.callback()
    assert opened_urls == ["https://civitai.example/models/1"]
