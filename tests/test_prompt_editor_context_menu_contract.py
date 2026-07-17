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

"""Contract tests for prompt-editor context-menu ownership and routing."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFontMetrics, QTextCursor
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import TextEdit as QFluentTextEdit  # type: ignore[import-untyped]
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    RoundMenu,
    TextEditMenu,
)

from substitute.application.prompt_editor import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptLoraCatalogItem,
    PromptScheduledLora,
    PromptScheduledLoraService,
    PromptWildcardDiagnosticProvider,
)
from substitute.application.danbooru import DanbooruWikiContentService
from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.interactions import (
    danbooru_dialog_runner as danbooru_dialog_runner_module,
)
from substitute.presentation.editor.prompt_editor.interactions import (
    PromptTriggerWordActionAdapter,
    prompt_menu_presenter as prompt_menu_presenter_module,
)
from substitute.presentation.editor.prompt_editor.features import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
    PromptContextMenuAction,
    PromptFeatureActionState,
    PromptFeatureCommandRequest,
    PromptFeatureSnapshotIdentity,
    PromptLoraTriggerWordsPayload,
)
from substitute.presentation.editor.prompt_editor.shell.context_menu_controller import (
    _PromptEditorTextEditMenu,
)
from substitute.presentation.editor.prompt_editor.shell import (
    PromptShellContextMenuOpening,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetMenuItem,
    PromptSegmentPresetMenuModel,
    PromptSegmentPresetMenuSection,
    PromptSegmentPresetSourceSnapshot,
)
from substitute.presentation.widgets.save_preset_dialog import PresetSaveScope
from substitute.domain.user_presets import GLOBAL_PRESET_ASSOCIATION
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from tests.execution_test_helpers import immediate_prompt_task_executor_factory

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real PromptEditor context-menu tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


@dataclass(frozen=True, slots=True)
class _ContextMenuCall:
    """Capture one delegated host context-menu call for assertions."""

    widget: QFluentTextEdit
    local_pos: QPoint
    global_pos: QPoint
    reason: QContextMenuEvent.Reason


class _RecordingWildcardCatalogGateway:
    """Record wildcard resolution requests from prompt-editor diagnostics."""

    def __init__(self) -> None:
        """Initialize request recording."""

        self.calls: list[tuple[PromptWildcardReference, ...]] = []

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Record one batch and return missing wildcard metadata."""

        self.calls.append(references)
        return tuple(
            PromptWildcardResolution(
                identifier=reference.identifier,
                wildcard_form=reference.wildcard_form,
                csv_column=reference.csv_column,
                exists=False,
            )
            for reference in references
        )

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no autocomplete suggestions."""

        _ = (prefix, limit)
        return ()


class _RecordingClipboardActions:
    """Record prompt clipboard action calls from context-menu rows."""

    def __init__(self) -> None:
        """Initialize empty action recording."""

        self.calls: list[str] = []

    def copy(self) -> None:
        """Record a copy request."""

        self.calls.append("copy")

    def cut(self) -> None:
        """Record a cut request."""

        self.calls.append("cut")

    def paste(self) -> None:
        """Record a paste request."""

        self.calls.append("paste")

    def select_all(self) -> None:
        """Record a select-all request."""

        self.calls.append("select_all")


def ensure_qapp() -> QApplication:
    """Return a running Qt application for prompt-editor widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def process_events(app: QApplication, cycles: int = 5) -> None:
    """Flush a few event-loop turns so prompt-editor state settles deterministically."""

    for _ in range(cycles):
        app.processEvents()


@pytest.fixture()
def prompt_widgets() -> Iterator[list[QWidget]]:
    """Track widgets created during one context-menu contract test."""

    widgets: list[QWidget] = []
    yield widgets
    app = ensure_qapp()
    for widget in reversed(widgets):
        widget.close()
        widget.deleteLater()
    process_events(app)


def create_prompt_editor(prompt_widgets: list[QWidget]) -> PromptEditor:
    """Create and show one live prompt editor in a stable geometry state."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(440, 220)
    editor = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_feature_profile=PromptEditorFeatureProfile.enabled_profile(
            (
                PromptEditorFeature.EMPHASIS,
                PromptEditorFeature.WILDCARD_SYNTAX,
                PromptEditorFeature.WILDCARD_AUTOCOMPLETE,
            )
        ),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    editor.setGeometry(20, 20, 320, editor.minimumEditorHeight())
    host.show()
    editor.show()
    editor.setFocus()
    editor.replaceBaselineSourceText("alpha beta gamma")
    process_events(app)
    prompt_widgets.extend([host, editor])
    return editor


class _EmptyLoraCatalog:
    """Provide the prompt editor with a no-op LoRA catalog for menu tests."""

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return no LoRA rows."""

        return ()

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return no cached LoRA rows."""

        return ()

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return no LoRA match for an empty catalog."""

        _ = prompt_name
        return None


class _StubDanbooruWikiService:
    """Provide the minimal wiki lookup service surface for menu wiring tests."""

    def lookup_selection(self, selection_text: str) -> object:
        """Return an opaque value because dialog creation is monkeypatched in tests."""

        return selection_text

    def lookup_title(self, title: str) -> object:
        """Return an opaque value because dialog creation is monkeypatched in tests."""

        return title


class _PromptSegmentPresetSource:
    """Provide deterministic saved prompt segment data for context-menu tests."""

    def __init__(
        self,
        model: PromptSegmentPresetMenuModel | None = None,
    ) -> None:
        """Store menu model and saved calls."""

        self.scope = PresetSaveScope(
            title="Global",
            full_label="Global",
            association=GLOBAL_PRESET_ASSOCIATION,
        )
        self.model = model or PromptSegmentPresetMenuModel(
            save_scopes=(self.scope,),
        )
        self.saved: list[tuple[str, str, PresetSaveScope]] = []
        self.list_calls = 0

    def list_prompt_segment_presets(self) -> PromptSegmentPresetSourceSnapshot:
        """Return saved prompt segment insert actions."""

        self.list_calls += 1
        return PromptSegmentPresetSourceSnapshot(
            menu_model=self.model,
            catalog_identity=CatalogSnapshotIdentity(
                catalog_revision=self.list_calls,
                prompt_context_token=("checkpoint", "test"),
            ),
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
        )

    def save_prompt_segment(
        self,
        *,
        label: str,
        text: str,
        scope: PresetSaveScope,
    ) -> None:
        """Record one save request."""

        self.saved.append((label, text, scope))


def create_lora_prompt_editor(prompt_widgets: list[QWidget]) -> PromptEditor:
    """Create one prompt editor configured with LoRA catalog support."""

    return create_lora_prompt_editor_with_resolver(prompt_widgets)


def create_lora_prompt_editor_with_resolver(
    prompt_widgets: list[QWidget],
    scheduled_lora_resolver: Callable[[str], tuple[PromptScheduledLora, ...]]
    | None = None,
) -> PromptEditor:
    """Create one LoRA-aware prompt editor with an optional scheduled-LoRA resolver."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(440, 220)
    editor = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard", "lora"),
        prompt_lora_catalog_service=_EmptyLoraCatalog(),
        scheduled_lora_resolver=scheduled_lora_resolver,
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    editor.setGeometry(20, 20, 320, editor.minimumEditorHeight())
    host.show()
    editor.show()
    editor.setFocus()
    editor.replaceBaselineSourceText("alpha beta gamma")
    process_events(app)
    prompt_widgets.extend([host, editor])
    return editor


def create_prompt_editor_with_segments(
    prompt_widgets: list[QWidget],
    source: _PromptSegmentPresetSource,
) -> PromptEditor:
    """Create one prompt editor configured with prompt segment preset support."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(440, 220)
    editor = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        prompt_segment_preset_source=source,
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    editor.setGeometry(20, 20, 320, editor.minimumEditorHeight())
    host.show()
    editor.show()
    editor.setFocus()
    editor.replaceBaselineSourceText("alpha beta gamma")
    process_events(app)
    prompt_widgets.extend([host, editor])
    return editor


def test_prompt_editor_context_menu_select_all_selects_full_source(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Context-menu Select all should use the projection-backed source selection."""

    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha,\n\nbeta")
    process_events(ensure_qapp())
    cursor = editor.textCursor()
    cursor.setPosition(6)
    editor.setTextCursor(cursor)
    QApplication.clipboard().clear()

    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)

    menu_type = _PromptEditorTextEditMenu
    menu = menu_type(editor, schedule_lora=lambda: None)
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    select_all_action = next(
        action for action in menu.menuActions() if action.text() == "Select all"
    )
    select_all_action.trigger()

    assert editor.textCursor().selectedText() == "alpha,\n\nbeta"


def test_prompt_editor_context_menu_owns_clipboard_rows_without_qfluent_text_menu() -> (
    None
):
    """Prompt clipboard rows should not inherit QFluent's text-edit menu behavior."""

    assert issubclass(_PromptEditorTextEditMenu, RoundMenu)
    assert not issubclass(_PromptEditorTextEditMenu, TextEditMenu)


def test_prompt_editor_context_menu_clipboard_rows_use_shared_controller(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Context-menu clipboard rows should bypass legacy parent-method wiring."""

    app = ensure_qapp()
    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha beta")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    QApplication.clipboard().setText("omega")
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)

    def fail_parent_clipboard_method(self: PromptEditor) -> None:
        """Fail if a menu row still routes through the parent widget method."""

        _ = self
        raise AssertionError("context menu used parent clipboard method")

    monkeypatch.setattr(PromptEditor, "copy", fail_parent_clipboard_method)
    monkeypatch.setattr(PromptEditor, "cut", fail_parent_clipboard_method)
    monkeypatch.setattr(PromptEditor, "paste", fail_parent_clipboard_method)
    monkeypatch.setattr(PromptEditor, "selectAll", fail_parent_clipboard_method)

    menu = _PromptEditorTextEditMenu(editor, schedule_lora=lambda: None)
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    actions = {action.text(): action for action in menu.menuActions()}

    actions["Copy"].trigger()
    assert QApplication.clipboard().text() == "alpha"

    QApplication.clipboard().setText("omega")
    actions["Paste"].trigger()
    process_events(app)
    assert editor.toPlainText() == "omega beta"

    editor.setPlainText("alpha beta")
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    actions["Cut"].trigger()
    process_events(app)
    assert QApplication.clipboard().text() == "alpha"
    assert editor.toPlainText() == " beta"

    editor.setPlainText("alpha beta")
    actions["Select all"].trigger()
    assert editor.textCursor().selectedText() == "alpha beta"


@pytest.mark.parametrize(
    ("row_text", "expected_call"),
    (
        ("Copy", "copy"),
        ("Cut", "cut"),
        ("Paste", "paste"),
        ("Select all", "select_all"),
    ),
)
def test_prompt_editor_context_menu_clipboard_row_clicks_call_the_shared_actions(
    row_text: str,
    expected_call: str,
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Clicking a clipboard menu row should invoke the same owner as QAction.trigger."""

    app = ensure_qapp()
    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha beta")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    QApplication.clipboard().setText("omega")
    clipboard_actions = _RecordingClipboardActions()
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)
    menu = _PromptEditorTextEditMenu(
        editor,
        schedule_lora=lambda: None,
        clipboard_actions=clipboard_actions,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    action = next(action for action in menu.menuActions() if action.text() == row_text)
    item = next(
        menu.view.item(index)
        for index in range(menu.view.count())
        if menu.view.item(index).data(Qt.ItemDataRole.UserRole) is action
    )
    monkeypatch.setattr(menu, "_hideMenu", lambda *_args, **_kwargs: None)

    action.trigger()
    cast(Any, menu)._onItemClicked(item)

    assert clipboard_actions.calls == [expected_call, expected_call]


@pytest.mark.parametrize(
    ("row_text", "method_name", "shortcut_key"),
    (
        ("Copy", "copy", Qt.Key.Key_C),
        ("Cut", "cut", Qt.Key.Key_X),
        ("Paste", "paste", Qt.Key.Key_V),
        ("Select all", "select_all", Qt.Key.Key_A),
    ),
)
def test_prompt_editor_context_menu_clipboard_click_and_shortcut_share_controller(
    row_text: str,
    method_name: str,
    shortcut_key: Qt.Key,
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Context-menu and Ctrl clipboard entrypoints should call one controller method."""

    app = ensure_qapp()
    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha beta")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    editor.setFocus()
    QApplication.clipboard().setText("omega")
    calls: list[str] = []
    controller_type = type(cast(Any, editor)._clipboard_history_controller)

    def record_controller_call(self: object) -> None:
        """Record one clipboard controller action invocation."""

        _ = self
        calls.append(method_name)

    monkeypatch.setattr(controller_type, method_name, record_controller_call)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)
    menu = _PromptEditorTextEditMenu(editor, schedule_lora=lambda: None)
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    action = next(action for action in menu.menuActions() if action.text() == row_text)
    item = next(
        menu.view.item(index)
        for index in range(menu.view.count())
        if menu.view.item(index).data(Qt.ItemDataRole.UserRole) is action
    )
    monkeypatch.setattr(menu, "_hideMenu", lambda *_args, **_kwargs: None)

    cast(Any, menu)._onItemClicked(item)
    QTest.keyClick(editor, shortcut_key, Qt.KeyboardModifier.ControlModifier)
    process_events(app)

    assert calls == [method_name, method_name]


def _capture_host_context_menu_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> list[_ContextMenuCall]:
    """Patch the QFluent host entry point and collect delegated calls."""

    calls: list[_ContextMenuCall] = []

    def fake_context_menu_event(
        self: QFluentTextEdit,
        event: QContextMenuEvent,
    ) -> None:
        """Record one delegated context-menu event without opening a popup."""

        calls.append(
            _ContextMenuCall(
                widget=self,
                local_pos=event.pos(),
                global_pos=event.globalPos(),
                reason=event.reason(),
            )
        )
        event.accept()

    monkeypatch.setattr(QFluentTextEdit, "contextMenuEvent", fake_context_menu_event)
    return calls


def _trap_surface_context_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> list[QPoint]:
    """Fail fast if the projection surface still owns context-menu handling."""

    surface_calls: list[QPoint] = []

    if "contextMenuEvent" not in PromptProjectionSurface.__dict__:
        return surface_calls

    def fail_context_menu_event(
        self: PromptProjectionSurface,
        event: QContextMenuEvent,
    ) -> None:
        """Record the stale surface route without entering the old menu loop."""

        _ = self
        surface_calls.append(event.globalPos())
        event.accept()

    monkeypatch.setattr(
        PromptProjectionSurface,
        "contextMenuEvent",
        fail_context_menu_event,
    )
    return surface_calls


def _send_context_menu_event(target: QWidget) -> QPoint:
    """Send one mouse-originated context-menu event to the supplied widget."""

    app = ensure_qapp()
    local_pos = target.rect().center()
    global_pos = target.mapToGlobal(local_pos)
    QApplication.sendEvent(
        target,
        QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            local_pos,
            global_pos,
        ),
    )
    process_events(app)
    return global_pos


def _shell_viewport(editor: PromptEditor) -> QWidget:
    """Return the host QFluent viewport watched by the prompt-editor event filter."""

    return cast(QWidget, getattr(editor, "_shell_viewport")())


def _context_event_for_source_text(
    editor: PromptEditor,
    source_text: str,
) -> QContextMenuEvent:
    """Build a context-menu event centered on visible source text."""

    cast(Any, editor)._shell_context_menu.record_context_menu_press()
    source_start = editor.toPlainText().index(source_text)
    fragment = editor.source_range_fragments(
        start=source_start,
        end=source_start + len(source_text),
    )[0]
    global_pos = editor.viewport().mapToGlobal(fragment.center().toPoint())
    return QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        editor.mapFromGlobal(global_pos),
        global_pos,
    )


def _prepared_context_event_for_source_text(
    editor: PromptEditor,
    source_text: str,
) -> QContextMenuEvent:
    """Prepare scene-position context for the exact test context-click position."""

    event = _context_event_for_source_text(editor, source_text)
    source_position = cast(
        Any, editor
    )._shell_context_menu._source_position_for_global_pos(event.globalPos())
    assert source_position is not None
    cast(Any, editor)._scene_feature_controller.prepare_position_context(
        source_position,
        reason="test_context_menu_scene_position",
    )
    return event


def _prepare_context_menu_scene_position(
    editor: PromptEditor,
    source_text: str,
) -> None:
    """Prepare scene-position context for tests that build their event separately."""

    _ = _prepared_context_event_for_source_text(editor, source_text)


def _menu_visual_rows(menu: RoundMenu) -> list[str]:
    """Return visible menu row labels, including separator sentinels."""

    rows: list[str] = []
    for row in range(menu.view.count()):
        item = menu.view.item(row)
        if item.data(Qt.ItemDataRole.DecorationRole) == "seperator":
            rows.append("<separator>")
            continue
        action = item.data(Qt.ItemDataRole.UserRole)
        if hasattr(action, "text"):
            rows.append(str(action.text()))
        else:
            rows.append(item.text().strip())
    return rows


def _trigger_save_prompt_segment(
    editor: PromptEditor,
    *,
    source_position: int,
    selected_text: str,
    selection_snapshot: tuple[int, int, str] | None,
) -> None:
    """Trigger the prompt-menu presenter's save-segment callback."""

    cast(Any, editor)._prompt_menu_presenter.prepare_prompt_menu_selection(
        selected_text=selected_text,
        selection_snapshot=selection_snapshot,
        reason="test_trigger_save_prompt_segment",
    )
    request = cast(Any, editor)._prompt_menu_presenter.prepared_prompt_menu_request(
        PromptShellContextMenuOpening(
            source_position=source_position,
            selected_text=selected_text,
            selection_snapshot=selection_snapshot,
        )
    )
    assert request.save_prompt_segment is not None
    request.save_prompt_segment()


def _adapt_trigger_words_action_for_lora(
    editor: PromptEditor,
    scheduled_lora: PromptScheduledLora,
    *,
    prompt_text: str,
) -> Any:
    """Return a trigger-word action through the extracted interaction adapter."""

    insertion_text = (
        PromptScheduledLoraService().configured_trigger_words_for_insertion(
            scheduled_lora
        )
    )
    full_label = f"Trigger words: {scheduled_lora.display_name}"
    prepared_action = PromptFeatureActionState(
        action_id=f"lora.trigger_words:{scheduled_lora.backend_value}",
        label=full_label,
        ready=True,
        command_request=PromptFeatureCommandRequest(
            command_name="lora_insert_trigger_words",
            identity=PromptFeatureSnapshotIdentity(
                source_revision=editor.prompt_command_source_identity().source_revision
            ),
            payload=PromptLoraTriggerWordsPayload(
                insertion_text=insertion_text,
                display_name=scheduled_lora.display_name,
                full_label=full_label,
            ),
        ),
    )
    return PromptTriggerWordActionAdapter(
        action_parent=editor,
        text_insertion_executor=cast(Any, editor)._command_adapter,
        identity_validator=lambda _identity: True,
    ).action_for_trigger_words(prepared_action)


def test_prompt_editor_projection_viewport_context_menu_uses_prompt_menu(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Projection viewport right-clicks should use the prompt-owned QFluent menu."""

    editor = create_prompt_editor(prompt_widgets)
    host_calls = _capture_host_context_menu_calls(monkeypatch)
    _trap_surface_context_menu(monkeypatch)
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture the prompt menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    _send_context_menu_event(editor.viewport())

    assert host_calls == []
    assert "Rich prompt rendering" in action_texts
    assert "Cancel" not in action_texts
    assert "Undo" not in action_texts


def test_prompt_editor_shell_viewport_context_menu_uses_prompt_menu(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Shell viewport context menus should use the same prompt menu path."""

    editor = create_prompt_editor(prompt_widgets)
    host_calls = _capture_host_context_menu_calls(monkeypatch)
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture the prompt menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    _send_context_menu_event(_shell_viewport(editor))

    assert host_calls == []
    assert "Rich prompt rendering" in action_texts


def test_prompt_editor_context_menu_path_does_not_use_surface_or_plain_host_menu(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Projection viewport menus should avoid stale surface and plain host paths."""

    editor = create_prompt_editor(prompt_widgets)
    host_calls = _capture_host_context_menu_calls(monkeypatch)
    surface_calls = _trap_surface_context_menu(monkeypatch)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)

    _send_context_menu_event(editor.viewport())

    assert host_calls == []
    assert surface_calls == []


def test_prompt_editor_host_facade_text_history_and_signal_contract(
    prompt_widgets: list[QWidget],
) -> None:
    """Phase 20.1 baselines public text/history methods and signal emissions."""

    app = ensure_qapp()
    editor = create_prompt_editor(prompt_widgets)
    text_changed_count = 0
    cursor_changed_count = 0
    undo_available: list[bool] = []
    redo_available: list[bool] = []

    def record_text_changed() -> None:
        """Record one public textChanged emission."""

        nonlocal text_changed_count
        text_changed_count += 1

    def record_cursor_changed() -> None:
        """Record one public cursorPositionChanged emission."""

        nonlocal cursor_changed_count
        cursor_changed_count += 1

    editor.textChanged.connect(record_text_changed)
    editor.cursorPositionChanged.connect(record_cursor_changed)
    editor.undoAvailableChanged.connect(undo_available.append)
    editor.redoAvailableChanged.connect(redo_available.append)

    editor.setSourceText("alpha")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(len(editor.toPlainText()))
    editor.setTextCursor(cursor)
    QTest.keyClicks(editor, "x")
    cast(Any, editor)._edit_controller.finish_pending_key_edit_block(reason="phase20_1")
    process_events(app)

    assert editor.toPlainText() == "alphax"
    assert editor.canUndo() is True
    assert text_changed_count > 0
    assert cursor_changed_count > 0
    assert True in undo_available

    editor.undo()
    process_events(app)
    assert editor.toPlainText() == "alpha"
    assert editor.canRedo() is True
    assert True in redo_available

    editor.redo()
    process_events(app)
    assert editor.toPlainText() == "alphax"


def test_prompt_editor_host_facade_read_only_blocks_edits_but_allows_copy(
    prompt_widgets: list[QWidget],
) -> None:
    """Phase 20.1 baselines read-only source editing and selection behavior."""

    app = ensure_qapp()
    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha beta")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    QApplication.clipboard().clear()

    editor.setReadOnly(True)
    QTest.keyClicks(editor, "x")
    editor.copy()
    process_events(app)

    assert editor.toPlainText() == "alpha beta"
    assert QApplication.clipboard().text() == "alpha"


def test_prompt_editor_host_facade_context_insert_preserves_focus_target(
    prompt_widgets: list[QWidget],
) -> None:
    """Phase 20.1 baselines menu insertion focus restoration behavior."""

    app = ensure_qapp()
    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha")
    editor.setFocus()
    process_events(app)
    cast(Any, editor)._set_context_menu_insert_state_for_tests(insert_position=5)

    cast(Any, editor)._command_adapter.insert_context_menu_text(
        ", beta",
        command_name="lora_insert_trigger_words",
    )
    process_events(app)

    assert editor.toPlainText() == "alpha, beta"
    assert editor.hasFocus()


def test_prompt_editor_lora_context_menu_preserves_qfluent_text_actions(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """LoRA support should append to QFluent's text menu instead of using Qt's menu."""

    editor = create_lora_prompt_editor(prompt_widgets)
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture the final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    menu_type = _PromptEditorTextEditMenu
    menu = menu_type(editor, schedule_lora=lambda: None)
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    assert "Cancel" not in action_texts
    assert "Select all" in action_texts
    assert "Rich prompt rendering" in action_texts
    assert "Schedule LoRA" in action_texts
    assert action_texts.index("Rich prompt rendering") > action_texts.index(
        "Select all"
    )
    visual_rows = _menu_visual_rows(menu)
    rich_row = visual_rows.index("Rich prompt rendering")
    schedule_row = visual_rows.index("Schedule LoRA")
    assert visual_rows[schedule_row - 2] == "Select all"
    assert visual_rows[schedule_row - 1] == "<separator>"
    assert visual_rows[schedule_row + 1] == "<separator>"
    assert rich_row == schedule_row + 2


def test_prompt_editor_context_menu_undo_redo_follow_custom_stack(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Undo and redo menu rows should reflect the custom prompt history."""

    editor = create_prompt_editor(prompt_widgets)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)
    menu_type = _PromptEditorTextEditMenu

    clean_menu = menu_type(editor, schedule_lora=lambda: None)
    clean_menu.exec(editor.mapToGlobal(editor.rect().center()))
    clean_actions = [action.text() for action in clean_menu.menuActions()]

    assert "Undo" not in clean_actions
    assert "Redo" not in clean_actions
    assert "Cancel" not in clean_actions

    QTest.keyClicks(editor, "x")
    cast(Any, editor)._edit_controller.finish_pending_key_edit_block(reason="test_menu")
    undo_menu = menu_type(editor, schedule_lora=lambda: None)
    undo_menu.exec(editor.mapToGlobal(editor.rect().center()))
    undo_actions = [action.text() for action in undo_menu.menuActions()]

    assert "Undo" in undo_actions
    assert "Redo" not in undo_actions

    editor.undo()
    redo_menu = menu_type(editor, schedule_lora=lambda: None)
    redo_menu.exec(editor.mapToGlobal(editor.rect().center()))
    redo_actions = [action.text() for action in redo_menu.menuActions()]

    assert "Undo" not in redo_actions
    assert "Redo" in redo_actions


def test_prompt_editor_context_menu_adds_checked_rich_rendering_action(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Plain prompt editors should expose rich rendering in the icon column."""

    editor = create_prompt_editor(prompt_widgets)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)

    menu_type = _PromptEditorTextEditMenu
    menu = menu_type(editor, schedule_lora=lambda: None)
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    action = next(
        action
        for action in menu.menuActions()
        if action.text() == "Rich prompt rendering"
    )
    assert action.isCheckable() is True
    assert action.isChecked() is True
    assert action.icon().isNull() is False
    assert cast(Any, action.property("item")).icon().isNull() is False
    assert menu.view.itemDelegate().__class__.__name__ == "ShortcutMenuItemDelegate"

    unchecked_menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        rich_prompt_rendering_enabled=False,
    )
    unchecked_menu.exec(editor.mapToGlobal(editor.rect().center()))
    unchecked_action = next(
        action
        for action in unchecked_menu.menuActions()
        if action.text() == "Rich prompt rendering"
    )
    assert unchecked_action.isChecked() is False
    assert unchecked_action.icon().isNull() is False
    assert cast(Any, unchecked_action.property("item")).icon().isNull() is False


def test_prompt_editor_context_menu_adds_disabled_diagnostic_explainer(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Diagnostic explainers should appear before normal text-editing rows."""

    editor = create_prompt_editor(prompt_widgets)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)

    menu_type = _PromptEditorTextEditMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        diagnostic_actions=(
            PromptContextMenuAction(
                label="Wildcard not found",
                callback=None,
                enabled=False,
            ),
        ),
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    action = next(
        action for action in menu.menuActions() if action.text() == "Wildcard not found"
    )
    visual_rows = _menu_visual_rows(menu)

    assert action.isEnabled() is False
    assert action.icon().isNull() is False
    assert cast(Any, action.property("item")).icon().isNull() is False
    assert visual_rows[0] == "Wildcard not found"
    assert visual_rows[1] == "<separator>"
    assert "Cancel" not in visual_rows
    assert "Select all" in visual_rows


def test_prompt_editor_context_menu_aligns_enabled_diagnostic_actions(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Enabled diagnostic rows should reserve the same icon column."""

    editor = create_prompt_editor(prompt_widgets)
    triggered: list[str] = []
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)

    menu_type = _PromptEditorTextEditMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        diagnostic_actions=(
            PromptContextMenuAction(
                label="teh",
                callback=lambda: triggered.append("teh"),
            ),
        ),
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    action = next(action for action in menu.menuActions() if action.text() == "teh")
    visual_rows = _menu_visual_rows(menu)

    assert action.isEnabled() is True
    assert action.icon().isNull() is False
    assert cast(Any, action.property("item")).icon().isNull() is False
    assert visual_rows[0] == "teh"
    assert visual_rows[1] == "<separator>"
    assert "Cancel" not in visual_rows
    assert "Select all" in visual_rows

    action.trigger()

    assert triggered == ["teh"]


def test_prompt_editor_context_menu_rich_rendering_action_toggles_editor(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Triggering the rich rendering action should update the editor mode."""

    editor = create_prompt_editor(prompt_widgets)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)
    menu_type = _PromptEditorTextEditMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        rich_prompt_rendering_enabled=editor.richPromptRenderingEnabled(),
        toggle_rich_prompt_rendering=editor.setRichPromptRenderingEnabled,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    action = next(
        action
        for action in menu.menuActions()
        if action.text() == "Rich prompt rendering"
    )

    action.trigger()

    assert editor.richPromptRenderingEnabled() is False

    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        rich_prompt_rendering_enabled=editor.richPromptRenderingEnabled(),
        toggle_rich_prompt_rendering=editor.setRichPromptRenderingEnabled,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    action = next(
        action
        for action in menu.menuActions()
        if action.text() == "Rich prompt rendering"
    )
    action.trigger()

    assert editor.richPromptRenderingEnabled() is True


def test_prompt_editor_context_menu_rich_rendering_action_preserves_selection(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Toggling rich rendering from the menu should preserve source selection."""

    editor = create_prompt_editor(prompt_widgets)
    cursor = editor.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(10, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)
    menu_type = _PromptEditorTextEditMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        rich_prompt_rendering_enabled=editor.richPromptRenderingEnabled(),
        toggle_rich_prompt_rendering=editor.setRichPromptRenderingEnabled,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    action = next(
        action
        for action in menu.menuActions()
        if action.text() == "Rich prompt rendering"
    )

    action.trigger()

    assert editor.textCursor().selectionStart() == 6
    assert editor.textCursor().selectionEnd() == 10
    assert editor.toPlainText() == "alpha beta gamma"


def test_prompt_editor_context_menu_copy_restores_exclusive_selection_end(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """QFluent menu actions should restore prompt selections without a +1 drift."""

    app = ensure_qapp()
    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("see-through dress, sparkling")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(len("see-through dres"), QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)
    menu_type = _PromptEditorTextEditMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    copy_action = next(
        action for action in menu.menuActions() if action.text() == "Copy"
    )
    copy_item = next(
        menu.view.item(index)
        for index in range(menu.view.count())
        if menu.view.item(index).data(Qt.ItemDataRole.UserRole) is copy_action
    )
    monkeypatch.setattr(menu, "_hideMenu", lambda *_args, **_kwargs: None)

    cast(Any, menu)._onItemClicked(copy_item)

    assert QApplication.clipboard().text() == "see-through dres"
    assert editor.textCursor().selectionStart() == 0
    assert editor.textCursor().selectionEnd() == len("see-through dres")


def test_prompt_editor_segment_source_uses_custom_qfluent_menu(
    prompt_widgets: list[QWidget],
) -> None:
    """Saved prompt segment support should route through the custom QFluent menu."""

    editor = create_prompt_editor_with_segments(
        prompt_widgets,
        _PromptSegmentPresetSource(),
    )

    assert cast(Any, editor)._prompt_menu_requires_custom_actions()


def test_prompt_editor_wildcard_diagnostics_activate_from_wildcard_feature(
    prompt_widgets: list[QWidget],
) -> None:
    """Wildcard syntax support should install the missing-wildcard diagnostic provider."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(440, 220)
    gateway = _RecordingWildcardCatalogGateway()
    editor = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=gateway,
        prompt_feature_profile=PromptEditorFeatureProfile.enabled_profile(
            (PromptEditorFeature.WILDCARD_SYNTAX,)
        ),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    editor.setGeometry(20, 20, 320, editor.minimumEditorHeight())
    host.show()
    editor.show()
    editor.setPlainText("{missing}")
    process_events(app)
    prompt_widgets.extend([host, editor])

    controller = cast(Any, editor)._diagnostics_feature_controller
    assert controller.can_activate()

    controller.activate()
    service = cast(Any, controller)._service

    assert any(
        isinstance(provider, PromptWildcardDiagnosticProvider)
        for provider in cast(Any, service)._providers
    )


def test_prompt_editor_context_menu_adds_save_segment_for_selection(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Selected prompt text should get a first-layer save action."""

    editor = create_prompt_editor(prompt_widgets)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    menu_type = _PromptEditorTextEditMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        prompt_segment_model=PromptSegmentPresetMenuModel(),
        save_prompt_segment=lambda: None,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    assert "Save segment as..." in action_texts


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

    menu_type = _PromptEditorTextEditMenu
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


def test_prompt_editor_context_menu_groups_prompt_utilities_before_rich_rendering(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Save, Danbooru wiki lookup, and Schedule LoRA should share one section."""

    editor = create_prompt_editor(prompt_widgets)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)

    menu_type = _PromptEditorTextEditMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        selected_prompt_text="long hair",
        save_prompt_segment=lambda: None,
        lookup_danbooru_wiki=lambda: None,
        danbooru_wiki_lookup_enabled=True,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    visual_rows = _menu_visual_rows(menu)
    save_row = visual_rows.index("Save segment as...")
    lookup_row = visual_rows.index("Danbooru wiki lookup")
    schedule_row = visual_rows.index("Schedule LoRA")
    rich_row = visual_rows.index("Rich prompt rendering")
    save_action = next(
        action for action in menu.menuActions() if action.text() == "Save segment as..."
    )
    schedule_action = next(
        action for action in menu.menuActions() if action.text() == "Schedule LoRA"
    )

    assert lookup_row == save_row + 1
    assert schedule_row == lookup_row + 1
    assert visual_rows[schedule_row + 1] == "<separator>"
    assert rich_row == schedule_row + 2
    assert save_action.icon().isNull() is False
    assert schedule_action.icon().isNull() is False


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

    menu_type = _PromptEditorTextEditMenu
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

    menu = _PromptEditorTextEditMenu(
        editor,
        schedule_lora=lambda: None,
        selected_prompt_text="long hair",
        lookup_danbooru_wiki=lambda: None,
        danbooru_wiki_lookup_enabled=False,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    assert "Danbooru wiki lookup" not in action_texts


def test_phase24_1_context_menu_read_only_suppresses_mutation_rows(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Read-only menus should keep native read actions and omit mutations."""

    editor = create_prompt_editor(prompt_widgets)
    editor.setReadOnly(True)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    visual_rows: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture final menu rows without opening a popup."""

        visual_rows.extend(_menu_visual_rows(self))

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    menu = _PromptEditorTextEditMenu(
        editor,
        schedule_lora=lambda: None,
        trigger_word_actions=(
            _adapt_trigger_words_action_for_lora(
                editor,
                PromptScheduledLora(
                    prompt_name="midna",
                    backend_value="midna.safetensors",
                    display_name="Friendly Midna",
                    trained_words=("trigger",),
                    source="cube_field",
                ),
                prompt_text=editor.toPlainText(),
            ),
        ),
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
        selected_prompt_text="alpha",
        save_prompt_segment=lambda: None,
        lookup_danbooru_wiki=lambda: None,
        danbooru_wiki_lookup_enabled=True,
        insert_prompt_segment=lambda _text: None,
        queue_scene_key="portrait",
        queue_scene=lambda _key: None,
        diagnostic_actions=(PromptContextMenuAction(label="Fix typo"),),
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    assert "Copy" in visual_rows
    assert "Select all" in visual_rows
    assert "Rich prompt rendering" in visual_rows
    assert "Fix typo" not in visual_rows
    assert "Queue this scene" not in visual_rows
    assert "Insert saved segment" not in visual_rows
    assert "Trigger words: Friendly Midna" not in visual_rows
    assert "Save segment as..." not in visual_rows
    assert "Danbooru wiki lookup" not in visual_rows
    assert "Schedule LoRA" not in visual_rows


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
        _context_event_for_source_text(editor, "long hair")
    )

    assert dialog_calls == [("long hair", True)]


def test_prompt_editor_context_menu_adds_queue_scene_for_queueable_scene(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Right-clicking a queueable scene block should add a scene queue action."""

    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("quality\n**portrait\nportrait text\n**cafe\ncafe text")
    editor.set_queueable_scene_keys(frozenset({"portrait", "cafe"}))
    process_events(ensure_qapp())
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        _prepared_context_event_for_source_text(editor, "portrait text")
    )

    assert "Queue this scene" in action_texts


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
    autocomplete = cast(Any, editor)._autocomplete
    provider = autocomplete._scheduled_lora_context._context_provider
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

        trigger_full_labels.extend(
            item.properties.get("promptFullTriggerWordsLabel")
            for item in self._trigger_word_entries()
        )

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        _prepared_context_event_for_source_text(editor, "alpha")
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
    context_event = _context_event_for_source_text(editor, "cafe text")
    source_position = cast(
        Any, editor
    )._shell_context_menu._source_position_for_global_pos(context_event.globalPos())
    assert source_position is not None
    context_prompt_snapshot = cast(
        Any,
        editor,
    )._scene_feature_controller.prepare_position_context(
        source_position,
        reason="test_context_menu_scene_position",
    )
    assert context_prompt_snapshot.context is not None
    context_prompt_text = context_prompt_snapshot.context.effective_prompt_text
    autocomplete = cast(Any, editor)._autocomplete
    provider = autocomplete._scheduled_lora_context._context_provider
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

        trigger_full_labels.extend(
            item.properties.get("promptFullTriggerWordsLabel")
            for item in self._trigger_word_entries()
        )

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(context_event)

    assert "Trigger words: Global LoRA" in trigger_full_labels
    assert "Trigger words: Portrait LoRA" not in trigger_full_labels
    assert resolver_calls == []


def test_prompt_editor_context_menu_omits_queue_scene_for_universal_text(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Right-clicking universal text should not offer scene queueing."""

    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("quality\n**portrait\nportrait text")
    editor.set_queueable_scene_keys(frozenset({"portrait"}))
    process_events(ensure_qapp())
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        _context_event_for_source_text(editor, "quality")
    )

    assert "Queue this scene" not in action_texts


def test_prompt_editor_context_menu_omits_queue_scene_for_nonqueueable_scene(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Scene syntax should not be enough when workflow analysis rejects the key."""

    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("quality\n**portrait\nportrait text\n**cafe\ncafe text")
    editor.set_queueable_scene_keys(frozenset({"cafe"}))
    process_events(ensure_qapp())
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        _prepared_context_event_for_source_text(editor, "portrait text")
    )

    assert "Queue this scene" not in action_texts


def test_prompt_editor_queue_scene_action_emits_normalized_scene_key(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Triggering the scene queue action should emit the normalized scene key."""

    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("**Portrait Scene\nportrait text")
    editor.set_queueable_scene_keys(frozenset({"portrait scene"}))
    process_events(ensure_qapp())
    emitted_keys: list[str] = []
    editor.sceneQueueRequested.connect(emitted_keys.append)

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Trigger the queue action without opening a popup."""

        action = next(
            action
            for action in self.menuActions()
            if action.text() == "Queue this scene"
        )
        action.trigger()

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        _prepared_context_event_for_source_text(editor, "portrait text")
    )

    assert emitted_keys == ["portrait scene"]


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


def test_phase24_1_shell_menu_open_records_context_insert_state(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Shell menu open should capture insertion or replacement state cheaply."""

    editor = create_prompt_editor(prompt_widgets)
    observed_insert_states: list[tuple[int | None, bool | None]] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture insert state after shell prepares the prompt menu."""

        _ = self
        insert_state = cast(
            Any, editor
        )._shell_context_menu.consume_context_insert_state()
        observed_insert_states.append(
            (
                insert_state.insert_position,
                insert_state.should_replace_selection,
            )
        )

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        _context_event_for_source_text(editor, "beta")
    )

    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    cast(Any, editor)._set_context_menu_selection_state_for_tests(
        had_selection=True,
        selection_snapshot=(0, 5, "alpha"),
    )
    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        _context_event_for_source_text(editor, "alpha")
    )

    assert len(observed_insert_states) == 2
    assert observed_insert_states[0][0] is not None
    assert observed_insert_states[0][1] is False
    assert observed_insert_states[1] == (None, True)


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


def test_prompt_editor_context_menu_uses_cached_segment_menu_model(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Opening the context menu should not list saved segments from the source."""

    source = _PromptSegmentPresetSource(
        PromptSegmentPresetMenuModel(
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
            save_scopes=(),
        )
    )
    editor = create_prompt_editor_with_segments(prompt_widgets, source)
    source.list_calls = 0
    visual_rows: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture built menu rows without opening a popup."""

        visual_rows.extend(_menu_visual_rows(self))

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        _context_event_for_source_text(editor, "alpha")
    )

    assert source.list_calls == 0
    assert "Insert saved segment" in visual_rows


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


def test_prompt_editor_general_context_menu_nests_single_trigger_action(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """One trigger-word action should still live in the dedicated submenu."""

    editor = create_lora_prompt_editor(prompt_widgets)
    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("imp princess",),
        source="cube_field",
    )
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    menu_type = _PromptEditorTextEditMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        trigger_word_actions=(
            _adapt_trigger_words_action_for_lora(
                editor,
                scheduled_lora,
                prompt_text=editor.toPlainText(),
            ),
        ),
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    assert "Friendly Midna" not in action_texts
    assert "Insert trigger words" in _menu_visual_rows(menu)
    submenu = next(
        submenu
        for submenu in cast(Any, menu)._subMenus
        if submenu.title() == "Insert trigger words"
    )
    getattr(submenu, "populate_if_needed")()
    trigger_action = submenu.menuActions()[0]
    assert trigger_action.text() == "Friendly Midna"
    assert trigger_action.toolTip() == "Trigger words: Friendly Midna"
    assert action_texts[-2] == "Schedule LoRA"
    assert action_texts[-1] == "Rich prompt rendering"


def test_phase24_1_context_menu_groups_multiple_trigger_actions(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Multiple prepared trigger-word actions should appear in one submenu."""

    editor = create_lora_prompt_editor(prompt_widgets)
    first_action = _adapt_trigger_words_action_for_lora(
        editor,
        PromptScheduledLora(
            prompt_name="midna",
            backend_value="midna.safetensors",
            display_name="Friendly Midna",
            trained_words=("imp princess",),
            source="cube_field",
        ),
        prompt_text=editor.toPlainText(),
    )
    second_action = _adapt_trigger_words_action_for_lora(
        editor,
        PromptScheduledLora(
            prompt_name="zelda",
            backend_value="zelda.safetensors",
            display_name="Friendly Zelda",
            trained_words=("wise princess",),
            source="cube_field",
        ),
        prompt_text=editor.toPlainText(),
    )
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)

    menu = _PromptEditorTextEditMenu(
        editor,
        schedule_lora=lambda: None,
        trigger_word_actions=(first_action, second_action),
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    visual_rows = _menu_visual_rows(menu)
    assert "Insert trigger words" in visual_rows
    submenu = next(
        submenu
        for submenu in cast(Any, menu)._subMenus
        if submenu.title() == "Insert trigger words"
    )
    populate = getattr(submenu, "populate_if_needed")
    populate()
    assert [action.text() for action in submenu.menuActions()] == [
        "Friendly Midna",
        "Friendly Zelda",
    ]
    assert [
        action.property("promptFullTriggerWordsLabel")
        for action in submenu.menuActions()
    ] == [
        "Trigger words: Friendly Midna",
        "Trigger words: Friendly Zelda",
    ]


def test_prompt_editor_trigger_action_label_elides_to_total_menu_budget(
    prompt_widgets: list[QWidget],
) -> None:
    """Long LoRA names should not make trigger-word context menus wide."""

    editor = create_lora_prompt_editor(prompt_widgets)
    long_name = (
        "Extremely Long CivitAI Friendly LoRA Name With Version Details And "
        "Training Notes That Would Otherwise Blow Out The Context Menu"
    )

    label = PromptTriggerWordActionAdapter(
        action_parent=editor,
        text_insertion_executor=cast(Any, editor)._command_adapter,
        identity_validator=lambda _identity: True,
    ).trigger_words_action_label(long_name)

    metrics = QFontMetrics(QApplication.font())
    assert not label.startswith("Trigger words:")
    assert metrics.horizontalAdvance(label) <= 191
    assert label != long_name


def test_prompt_editor_trigger_action_inserts_provider_words_without_suppression(
    prompt_widgets: list[QWidget],
) -> None:
    """Trigger actions should insert provider words even when prompt has duplicates."""

    app = ensure_qapp()
    editor = create_lora_prompt_editor(prompt_widgets)
    editor.setPlainText("imp_princess, portrait")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(len(editor.toPlainText()))
    editor.setTextCursor(cursor)
    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("imp princess", "twili helmet"),
        source="cube_field",
    )

    action = _adapt_trigger_words_action_for_lora(
        editor,
        scheduled_lora,
        prompt_text=editor.toPlainText(),
    )
    assert action is not None
    action.trigger()
    process_events(app)

    assert editor.toPlainText() == (
        "imp_princess, portrait, imp princess, twili helmet"
    )


def test_prompt_editor_trigger_action_uses_context_position_without_deleting_blank_line(
    prompt_widgets: list[QWidget],
) -> None:
    """Trigger insertion should not replace a stale caret on a nearby blank line."""

    app = ensure_qapp()
    editor = create_lora_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha,\n\nbeta")
    process_events(app)
    stale_cursor = editor.textCursor()
    stale_cursor.setPosition(7)
    editor.setTextCursor(stale_cursor)
    cast(Any, editor)._set_context_menu_insert_state_for_tests(insert_position=6)

    action = _adapt_trigger_words_action_for_lora(
        editor,
        PromptScheduledLora(
            prompt_name="midna",
            backend_value="midna.safetensors",
            display_name="Friendly Midna",
            trained_words=("trigger",),
            source="cube_field",
        ),
        prompt_text=editor.toPlainText(),
    )
    assert action is not None
    action.trigger()
    process_events(app)

    assert editor.toPlainText() == "alpha, trigger\n\nbeta"


def test_prompt_editor_trigger_action_ignores_selection_created_by_context_click(
    prompt_widgets: list[QWidget],
) -> None:
    """Context-click blank-line selection should not replace text on insertion."""

    app = ensure_qapp()
    editor = create_lora_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha,\n\nbeta")
    process_events(app)
    incidental_cursor = editor.textCursor()
    incidental_cursor.setPosition(7)
    incidental_cursor.setPosition(8, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(incidental_cursor)
    cast(Any, editor)._set_context_menu_insert_state_for_tests(
        insert_position=6,
        should_replace_selection=False,
    )

    action = _adapt_trigger_words_action_for_lora(
        editor,
        PromptScheduledLora(
            prompt_name="midna",
            backend_value="midna.safetensors",
            display_name="Friendly Midna",
            trained_words=("trigger",),
            source="cube_field",
        ),
        prompt_text=editor.toPlainText(),
    )
    assert action is not None
    action.trigger()
    process_events(app)

    assert editor.toPlainText() == "alpha, trigger\n\nbeta"


def test_prompt_editor_trigger_action_replaces_selection_like_paste(
    prompt_widgets: list[QWidget],
) -> None:
    """Trigger insertion should replace active selections before using context position."""

    app = ensure_qapp()
    editor = create_lora_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha,\n\nbeta")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(7)
    cursor.setPosition(8, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    cast(Any, editor)._set_context_menu_insert_state_for_tests(insert_position=6)

    action = _adapt_trigger_words_action_for_lora(
        editor,
        PromptScheduledLora(
            prompt_name="midna",
            backend_value="midna.safetensors",
            display_name="Friendly Midna",
            trained_words=("trigger",),
            source="cube_field",
        ),
        prompt_text=editor.toPlainText(),
    )
    assert action is not None
    action.trigger()
    process_events(app)

    assert editor.toPlainText() == "alpha,\ntriggerbeta"


def test_prompt_editor_lora_picker_insertion_uses_shared_schedule_text(
    prompt_widgets: list[QWidget],
) -> None:
    """The context picker insertion path should use scheduler-safe default text."""

    app = ensure_qapp()
    editor = create_lora_prompt_editor(prompt_widgets)
    editor.setPlainText("")
    process_events(app)

    cast(Any, editor)._lora_picker_popup_presenter.insert_lora_schedule(
        _lora_item(
            display_name="Friendly Midna",
            basename="raw_midna",
            prompt_name=r"illustrious\characters\safe_midna",
        )
    )
    process_events(app)

    assert editor.toPlainText() == r"<lora:illustrious\characters\safe_midna:1.00>"


def _lora_item(
    *,
    display_name: str = "Midna",
    basename: str = "Midna",
    prompt_name: str = r"illustrious\characters\Midna",
) -> PromptLoraCatalogItem:
    """Return one LoRA catalog item for prompt-editor insertion tests."""

    return PromptLoraCatalogItem(
        display_name=display_name,
        display_subtitle=None,
        prompt_name=prompt_name,
        backend_value=f"{prompt_name}.safetensors",
        relative_path=f"{prompt_name}.safetensors",
        folder=r"illustrious\characters",
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=" ".join((display_name, basename, prompt_name)).casefold(),
    )
