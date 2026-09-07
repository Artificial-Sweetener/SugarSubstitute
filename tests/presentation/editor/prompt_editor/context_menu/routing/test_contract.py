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

"""Verify context-menu routing, diagnostics, and read-only policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QTextCursor
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QWidget
from qfluentwidgets import TextEdit as QFluentTextEdit  # type: ignore[import-untyped]
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    RoundMenu,
)
from substitute.application.prompt_editor.diagnostics.wildcard import (
    PromptWildcardDiagnosticProvider,
)
from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLora,
)
from substitute.domain.prompt.features.models import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
)
from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.features import (
    PromptContextMenuAction,
)
from substitute.presentation.editor.prompt_editor.shell.prompt_text_menu import (
    PromptTextMenu,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetMenuItem,
    PromptSegmentPresetMenuModel,
    PromptSegmentPresetMenuSection,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
)
from tests.support.execution import immediate_prompt_task_executor_factory
from tests.presentation.editor.prompt_editor.context_menu.mounting import (
    create_prompt_editor,
    ensure_qapp,
    process_events,
)
from tests.presentation.editor.prompt_editor.context_menu.menu_rows import (
    visible_menu_rows as _menu_visual_rows,
)
from tests.presentation.editor.prompt_editor.context_menu.event_positions import (
    send_context_menu_event,
    shell_viewport,
)
from tests.presentation.editor.prompt_editor.context_menu.trigger_actions import (
    trigger_words_action_for_lora,
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

    send_context_menu_event(editor.viewport())

    assert host_calls == []
    assert "Rich prompt rendering" in action_texts
    assert "Cancel" not in action_texts
    assert "Undo" not in action_texts


def test_prompt_editorshell_viewport_context_menu_uses_prompt_menu(
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

    send_context_menu_event(shell_viewport(editor))

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

    send_context_menu_event(editor.viewport())

    assert host_calls == []
    assert surface_calls == []


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
    service = cast(Any, controller)._providers.service

    assert any(
        isinstance(provider, PromptWildcardDiagnosticProvider)
        for provider in cast(Any, service)._providers
    )


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

    menu = PromptTextMenu(
        editor,
        schedule_lora=lambda: None,
        trigger_word_actions=(
            trigger_words_action_for_lora(
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
