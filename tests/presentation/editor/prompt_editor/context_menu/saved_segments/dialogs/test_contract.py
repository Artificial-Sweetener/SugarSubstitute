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

"""Verify saved-segment dialog, selection, and insertion contracts."""

from __future__ import annotations

from __future__ import annotations
from __future__ import annotations
from typing import Any, cast
import pytest
from PySide6.QtGui import QTextCursor
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QWidget
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    RoundMenu,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.interactions import (
    prompt_menu_presenter as prompt_menu_presenter_module,
)
from substitute.presentation.editor.prompt_editor.shell.context_menu_controller import (
    _PromptEditorTextEditMenu,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetMenuItem,
    PromptSegmentPresetMenuModel,
    PromptSegmentPresetMenuSection,
)
from substitute.presentation.widgets.save_preset_dialog import PresetSaveScope
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from tests.support.execution import immediate_prompt_task_executor_factory
from tests.presentation.editor.prompt_editor.context_menu.mounting import (
    create_prompt_editor,
    ensure_qapp,
    process_events,
)
from tests.presentation.editor.prompt_editor.context_menu.saved_segments.mounting import (
    _PromptSegmentPresetSource,
    _trigger_save_prompt_segment,
    create_prompt_editor_with_segments,
)


def test_prompt_editor_save_segment_dialog_flow_preserves_selected_text(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Saving should pass exact text and use the fallback window parent."""

    source = _PromptSegmentPresetSource()
    editor = create_prompt_editor_with_segments(prompt_widgets, source)
    cursor = editor.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(10, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    dialog_parents: list[QWidget] = []

    class _FakeSavePresetDialog:
        """Record save dialog construction without creating a real modal."""

        def __init__(
            self,
            *,
            parent: QWidget,
            title: str,
            scopes: tuple[PresetSaveScope, ...],
        ) -> None:
            """Capture the dialog parent and available scopes."""

            dialog_parents.append(parent)
            self.title = title
            self.scopes = scopes

    monkeypatch.setattr(
        prompt_menu_presenter_module,
        "SavePresetDialog",
        _FakeSavePresetDialog,
    )
    monkeypatch.setattr(
        prompt_menu_presenter_module,
        "preset_dialog_result",
        lambda _dialog: ("Segment name", source.scope),
    )

    _trigger_save_prompt_segment(
        editor,
        source_position=6,
        selected_text="beta",
        selection_snapshot=(6, 10, "beta"),
    )

    assert source.saved == [("Segment name", "beta", source.scope)]
    assert dialog_parents == [editor.window()]
    assert dialog_parents[0] is not editor


def test_prompt_editor_save_segment_dialog_parents_to_editor_panel(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Panel-hosted prompt editors should center save modals on the editor panel."""

    app = ensure_qapp()

    class EditorPanel(QWidget):
        """Minimal widget whose class name matches the production editor panel."""

    panel = EditorPanel()
    panel.resize(440, 220)
    nested_host = QWidget(panel)
    nested_host.setGeometry(0, 0, 420, 200)
    source = _PromptSegmentPresetSource()
    editor = PromptEditor(
        nested_host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        prompt_segment_preset_source=source,
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    editor.setGeometry(20, 20, 320, editor.minimumEditorHeight())
    panel.show()
    nested_host.show()
    editor.show()
    editor.setPlainText("alpha beta gamma")
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    process_events(app)
    prompt_widgets.extend([panel, nested_host, editor])
    dialog_parents: list[QWidget] = []

    class _FakeSavePresetDialog:
        """Record save dialog construction without creating a real modal."""

        def __init__(
            self,
            *,
            parent: QWidget,
            title: str,
            scopes: tuple[PresetSaveScope, ...],
        ) -> None:
            """Capture the dialog parent and available scopes."""

            dialog_parents.append(parent)
            self.title = title
            self.scopes = scopes

    monkeypatch.setattr(
        prompt_menu_presenter_module,
        "SavePresetDialog",
        _FakeSavePresetDialog,
    )
    monkeypatch.setattr(
        prompt_menu_presenter_module,
        "preset_dialog_result",
        lambda _dialog: ("Segment name", source.scope),
    )

    _trigger_save_prompt_segment(
        editor,
        source_position=0,
        selected_text="alpha",
        selection_snapshot=(0, 5, "alpha"),
    )

    assert source.saved == [("Segment name", "alpha", source.scope)]
    assert dialog_parents == [panel]


def test_prompt_editor_save_segment_dialog_preserves_selected_newline(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Saving should keep intentionally selected newline characters exact."""

    source = _PromptSegmentPresetSource()
    editor = create_prompt_editor_with_segments(prompt_widgets, source)
    editor.setPlainText("alpha\nbeta")
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(6, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    class _FakeSavePresetDialog:
        """Provide a fake accepted dialog for exact selected-text assertions."""

        def __init__(
            self,
            *,
            parent: QWidget,
            title: str,
            scopes: tuple[PresetSaveScope, ...],
        ) -> None:
            """Accept the same construction contract as the real dialog."""

            _ = (parent, title)
            self.scopes = scopes

    monkeypatch.setattr(
        prompt_menu_presenter_module,
        "SavePresetDialog",
        _FakeSavePresetDialog,
    )
    monkeypatch.setattr(
        prompt_menu_presenter_module,
        "preset_dialog_result",
        lambda _dialog: ("Segment name", source.scope),
    )

    _trigger_save_prompt_segment(
        editor,
        source_position=0,
        selected_text="alpha\n",
        selection_snapshot=(0, 6, "alpha\n"),
    )

    assert source.saved == [("Segment name", "alpha\n", source.scope)]


def test_prompt_editor_save_segment_uses_pre_context_click_selection_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Save segment should not read a selection expanded by menu click side effects."""

    source = _PromptSegmentPresetSource()
    editor = create_prompt_editor_with_segments(prompt_widgets, source)
    editor.setPlainText("art, detailed")
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(3, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    cast(Any, editor)._set_context_menu_selection_state_for_tests(
        had_selection=True,
        selection_snapshot=(0, 3, "art"),
    )

    class _FakeSavePresetDialog:
        """Provide a fake accepted dialog for menu-trigger save assertions."""

        def __init__(
            self,
            *,
            parent: QWidget,
            title: str,
            scopes: tuple[PresetSaveScope, ...],
        ) -> None:
            """Accept the same construction contract as the real dialog."""

            _ = (parent, title, scopes)

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Mutate the live editor selection before triggering the save action."""

        expanded_cursor = editor.textCursor()
        expanded_cursor.setPosition(0)
        expanded_cursor.setPosition(4, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(expanded_cursor)
        action = next(
            action
            for action in self.menuActions()
            if action.text() == "Save segment as..."
        )
        action.trigger()

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)
    monkeypatch.setattr(
        prompt_menu_presenter_module,
        "SavePresetDialog",
        _FakeSavePresetDialog,
    )
    monkeypatch.setattr(
        prompt_menu_presenter_module,
        "preset_dialog_result",
        lambda _dialog: ("Segment name", source.scope),
    )

    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        editor.rect().center(),
        editor.mapToGlobal(editor.rect().center()),
    )
    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(event)

    assert source.saved == [("Segment name", "art", source.scope)]
    assert editor.textCursor().selectedText() == "art"


def test_prompt_editor_saved_segment_action_inserts_text(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Saved segment insert actions should use the prompt editor insertion path."""

    editor = create_prompt_editor(prompt_widgets)
    inserted: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Avoid opening a popup while preserving built menu state."""

        _ = self

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    menu_type = _PromptEditorTextEditMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        prompt_segment_model=PromptSegmentPresetMenuModel(
            sections=(
                PromptSegmentPresetMenuSection(
                    title="Global",
                    presets=(
                        PromptSegmentPresetMenuItem(
                            label="Blue eyes",
                            text="blue eyes",
                            tooltip="blue eyes",
                        ),
                    ),
                ),
            ),
        ),
        insert_prompt_segment=inserted.append,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    submenu = cast(Any, menu)._subMenus[0]
    populate = getattr(submenu, "populate_if_needed")
    populate()
    submenu.menuActions()[0].trigger()

    assert inserted == ["blue eyes"]
