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

"""Verify Danbooru wiki lookup contracts in prompt context menus."""

from __future__ import annotations

from typing import Any, cast

import pytest
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QWidget
from qfluentwidgets.components.widgets.menu import RoundMenu  # type: ignore[import-untyped]

from substitute.application.danbooru import DanbooruWikiContentService
from substitute.domain.prompt.features.models import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.interactions import (
    danbooru_dialog_runner as danbooru_dialog_runner_module,
)
from substitute.presentation.editor.prompt_editor.shell.prompt_text_menu import (
    PromptTextMenu,
)
from tests.presentation.editor.prompt_editor.context_menu.event_positions import (
    context_event_for_source_text,
)
from tests.presentation.editor.prompt_editor.context_menu.mounting import (
    create_prompt_editor,
    ensure_qapp,
    process_events,
)
from tests.support.execution import immediate_prompt_task_executor_factory
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
)


class _StubDanbooruWikiService:
    """Provide the minimal wiki lookup service surface for menu wiring tests."""

    def lookup_selection(self, selection_text: str) -> object:
        """Return an opaque value because dialog creation is monkeypatched in tests."""

        return selection_text

    def lookup_title(self, title: str) -> object:
        """Return an opaque value because dialog creation is monkeypatched in tests."""

        return title


def test_prompt_editor_context_menu_adds_danbooru_wiki_action_for_selection(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Selected prompt text should add a Danbooru wiki lookup action."""

    editor = create_prompt_editor(prompt_widgets)
    action_texts: list[str] = []
    triggered: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture the final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    menu_type = PromptTextMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        selected_prompt_text="long hair",
        lookup_danbooru_wiki=lambda: triggered.append("wiki"),
        danbooru_wiki_lookup_enabled=True,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    action = next(
        action
        for action in menu.menuActions()
        if action.text() == "Danbooru wiki lookup"
    )
    schedule_action = next(
        action for action in menu.menuActions() if action.text() == "Schedule LoRA"
    )
    action.trigger()

    assert "Danbooru wiki lookup" in action_texts
    assert action.icon().isNull() is False
    assert schedule_action.icon().isNull() is False
    assert triggered == ["wiki"]


def test_prompt_editor_context_menu_omits_danbooru_wiki_action_without_selection(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Danbooru wiki lookup should not appear when no prompt text is selected."""

    editor = create_prompt_editor(prompt_widgets)
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture the final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    menu_type = PromptTextMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        selected_prompt_text="",
        lookup_danbooru_wiki=lambda: None,
        danbooru_wiki_lookup_enabled=True,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    assert "Danbooru wiki lookup" not in action_texts


def test_phase24_1_context_menu_omits_disabled_danbooru_lookup(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """A selected prompt should not show wiki lookup when readiness is disabled."""

    editor = create_prompt_editor(prompt_widgets)
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    menu = PromptTextMenu(
        editor,
        schedule_lora=lambda: None,
        selected_prompt_text="long hair",
        lookup_danbooru_wiki=lambda: None,
        danbooru_wiki_lookup_enabled=False,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    assert "Danbooru wiki lookup" not in action_texts


def test_prompt_editor_danbooru_wiki_action_opens_native_dialog(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """The prompt editor should open the native Danbooru wiki dialog for selections."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(440, 220)
    dialog_calls: list[tuple[str, QWidget | None, bool]] = []

    class _FakeDialog:
        """Record dialog construction and execution for the menu callback."""

        def __init__(self, **kwargs: object) -> None:
            """Capture the selected text used for dialog creation."""

            dialog_calls.append(
                (
                    str(kwargs.get("selection_text", "")),
                    cast(QWidget | None, kwargs.get("parent")),
                    False,
                )
            )

        def exec(self) -> int:
            """Record that the native dialog would have been shown."""

            selection_text, parent, _executed = dialog_calls[-1]
            dialog_calls[-1] = (selection_text, parent, True)
            return 0

    monkeypatch.setattr(
        danbooru_dialog_runner_module, "DanbooruWikiDialog", _FakeDialog
    )

    editor = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        danbooru_wiki_service=cast(
            DanbooruWikiContentService, _StubDanbooruWikiService()
        ),
        prompt_feature_profile=PromptEditorFeatureProfile.enabled_profile(
            (PromptEditorFeature.DANBOORU_WIKI_LOOKUP,)
        ),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    editor.setGeometry(20, 20, 320, editor.minimumEditorHeight())
    host.show()
    editor.show()
    editor.setPlainText("long hair")
    process_events(app)
    prompt_widgets.extend([host, editor])

    cast(Any, editor)._danbooru_dialog_runner.open_wiki_for_selection("long hair")

    assert dialog_calls == [("long hair", host, True)]


def test_prompt_editor_danbooru_wiki_dialog_uses_top_level_window_parent(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Danbooru wiki browsing should parent to the top-level window, not EditorPanel."""

    app = ensure_qapp()

    class EditorPanel(QWidget):
        """Minimal widget whose class name matches the production editor panel."""

    shell = QWidget()
    shell.resize(520, 280)
    panel = EditorPanel(shell)
    panel.setGeometry(20, 20, 460, 220)
    nested_host = QWidget(panel)
    nested_host.setGeometry(0, 0, 420, 200)
    dialog_parents: list[QWidget | None] = []

    class _FakeDialog:
        """Record the parent used for the native Danbooru wiki dialog."""

        def __init__(self, **kwargs: object) -> None:
            """Capture the dialog parent without building a real modal."""

            dialog_parents.append(cast(QWidget | None, kwargs.get("parent")))

        def exec(self) -> int:
            """Accept the same interface as the real dialog."""

            return 0

    monkeypatch.setattr(
        danbooru_dialog_runner_module, "DanbooruWikiDialog", _FakeDialog
    )

    editor = PromptEditor(
        nested_host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        danbooru_wiki_service=cast(
            DanbooruWikiContentService, _StubDanbooruWikiService()
        ),
        prompt_feature_profile=PromptEditorFeatureProfile.enabled_profile(
            (PromptEditorFeature.DANBOORU_WIKI_LOOKUP,)
        ),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    editor.setGeometry(20, 20, 320, editor.minimumEditorHeight())
    shell.show()
    panel.show()
    nested_host.show()
    editor.show()
    process_events(app)
    prompt_widgets.extend([shell, panel, nested_host, editor])

    cast(Any, editor)._danbooru_dialog_runner.open_wiki_for_selection("long hair")

    assert dialog_parents == [shell]


def test_prompt_editor_context_menu_lookup_action_uses_selected_prompt_text(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Triggering the context-menu wiki action should use the captured selection."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(440, 220)
    dialog_calls: list[tuple[str, bool]] = []

    class _FakeDialog:
        """Record dialog construction and execution for the menu trigger."""

        def __init__(self, **kwargs: object) -> None:
            """Capture the selected prompt text passed into the dialog."""

            dialog_calls.append((str(kwargs.get("selection_text", "")), False))

        def exec(self) -> int:
            """Record that the dialog would have been shown."""

            selection_text, _executed = dialog_calls[-1]
            dialog_calls[-1] = (selection_text, True)
            return 0

    monkeypatch.setattr(
        danbooru_dialog_runner_module, "DanbooruWikiDialog", _FakeDialog
    )

    editor = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        danbooru_wiki_service=cast(
            DanbooruWikiContentService, _StubDanbooruWikiService()
        ),
        prompt_feature_profile=PromptEditorFeatureProfile.enabled_profile(
            (
                PromptEditorFeature.EMPHASIS,
                PromptEditorFeature.DANBOORU_WIKI_LOOKUP,
            )
        ),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    editor.setGeometry(20, 20, 320, editor.minimumEditorHeight())
    host.show()
    editor.show()
    editor.setFocus()
    editor.setPlainText("long hair, short hair")
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(9, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    process_events(app)
    prompt_widgets.extend([host, editor])

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Trigger the Danbooru wiki row without opening a visible popup."""

        action = next(
            action
            for action in self.menuActions()
            if action.text() == "Danbooru wiki lookup"
        )
        action.trigger()

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        context_event_for_source_text(editor, "long hair")
    )

    assert dialog_calls == [("long hair", True)]
