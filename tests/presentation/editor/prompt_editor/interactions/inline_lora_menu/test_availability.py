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

"""Test inline LoRA action availability."""

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


def test_inline_lora_presenter_suppresses_missing_url_and_empty_triggers() -> None:
    """Missing prepared actions should be passed to the passive shell as absent."""

    ensure_qapp()
    shell_menu = ShellMenu()
    presenter = build_presenter(
        metadata=LoraMetadata(),
        shell_menu=shell_menu,
        insertion_executor=InsertionExecutor(),
        opened_urls=[],
        effective_prompt_text="portrait",
        finish_reasons=[],
    )

    presenter.show_lora_context_menu(
        token(model_page_url="  ", trained_words=()),
        QPoint(1, 2),
    )

    assert len(shell_menu.calls) == 1
    _global_pos, trigger_action, metadata_menu_items = shell_menu.calls[0]
    assert trigger_action is None
    assert metadata_menu_items == ()


def test_phase24_1_inline_lora_presenter_ignores_non_projection_tokens() -> None:
    """Non-token menu requests should finish edits without opening a menu."""

    ensure_qapp()
    shell_menu = ShellMenu()
    finish_reasons: list[str] = []
    presenter = build_presenter(
        metadata=LoraMetadata(),
        shell_menu=shell_menu,
        insertion_executor=InsertionExecutor(),
        opened_urls=[],
        effective_prompt_text="portrait",
        finish_reasons=finish_reasons,
    )

    presenter.show_lora_context_menu(object(), QPoint(4, 8))

    assert finish_reasons == ["lora_context_menu"]
    assert shell_menu.calls == []


def test_phase24_1_inline_lora_presenter_passes_single_prepared_actions() -> None:
    """Inline LoRA menus should pass page-only or trigger-only state to shell."""

    ensure_qapp()
    shell_menu = ShellMenu()
    insertion_executor = InsertionExecutor()
    presenter = build_presenter(
        metadata=LoraMetadata(),
        shell_menu=shell_menu,
        insertion_executor=insertion_executor,
        opened_urls=[],
        effective_prompt_text="scene-local prompt",
        finish_reasons=[],
    )

    presenter.show_lora_context_menu(
        token(
            model_page_url="https://civitai.example/models/2",
            trained_words=(),
        ),
        QPoint(10, 20),
    )
    presenter.show_lora_context_menu(
        token(model_page_url=None, trained_words=("scene trigger",)),
        QPoint(30, 40),
    )

    assert len(shell_menu.calls) == 2
    _page_pos, page_trigger_action, page_metadata_items = shell_menu.calls[0]
    assert page_trigger_action is None
    page_action = actions(page_metadata_items)[0]
    assert page_action is not None
    _trigger_pos, trigger_action, trigger_metadata_items = shell_menu.calls[1]
    assert trigger_action is not None
    assert trigger_metadata_items == ()
    assert trigger_action.toolTip() == "Trigger words: Friendly Midna"
    trigger_action.trigger()
    assert insertion_executor.inserted == ["scene trigger"]
