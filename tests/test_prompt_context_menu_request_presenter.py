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

"""Tests for prompt context-menu request presentation ownership."""

from __future__ import annotations

from sugarsubstitute_shared.localization import app_text

import os
from dataclasses import dataclass
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandResult,
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptContextMenuAction,
    PromptContextMenuActionController,
    PromptContextMenuActionSnapshot,
    PromptDanbooruActionSnapshot,
    PromptDanbooruUrlImportState,
    PromptDanbooruWikiLookupPayload,
    PromptFeatureActionState,
    PromptFeatureCommandRequest,
    PromptFeatureSnapshotIdentity,
    PromptLoraTriggerWordsPayload,
    PromptSegmentPresetController,
    PromptSegmentPresetDialogResult,
    PromptSegmentPresetMenuModel,
    PromptSegmentPresetSaveDialogRequest,
    PromptSegmentPresetSaveState,
    PromptSegmentPresetSnapshot,
    PromptSegmentSelectionSnapshot,
    PromptScenePositionContext,
)
from substitute.presentation.editor.prompt_editor.interactions import (
    PromptContextMenuRequestPresenter,
    PromptMenuEditorHost,
    PromptSegmentPresetHostAdapter,
    PromptTriggerWordActionAdapter,
)
from substitute.presentation.editor.prompt_editor.shell import (
    PromptShellContextMenuOpening,
)
from substitute.presentation.widgets.save_preset_dialog import PresetSaveScope
from substitute.domain.user_presets import GLOBAL_PRESET_ASSOCIATION


@dataclass(slots=True)
class _Cursor:
    """Provide a QTextCursor-like selection object for host-adapter tests."""

    selection_start: int
    selection_end: int
    cursor_position: int
    positions: list[tuple[int, QTextCursor.MoveMode | None]]

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether this fake cursor has a selected range."""

        return self.selection_start != self.selection_end

    def selectionStart(self) -> int:  # noqa: N802
        """Return the fake selection start endpoint."""

        return self.selection_start

    def selectionEnd(self) -> int:  # noqa: N802
        """Return the fake selection end endpoint."""

        return self.selection_end

    def position(self) -> int:
        """Return the fake cursor position."""

        return self.cursor_position

    def setPosition(  # noqa: N802
        self,
        position: int,
        mode: QTextCursor.MoveMode | None = None,
    ) -> None:
        """Record cursor position writes."""

        self.positions.append((position, mode))


class _Host(QWidget):
    """Provide the editor host behavior needed by the segment host adapter."""

    def __init__(self, *, text: str = "alpha beta") -> None:
        """Initialize fake editor state."""

        super().__init__()
        self.text = text
        self.fake_cursor = _Cursor(0, 5, 5, [])
        self.applied_cursors: list[_Cursor] = []

    def textCursor(self) -> QTextCursor:  # noqa: N802
        """Return the fake cursor."""

        return cast(QTextCursor, self.fake_cursor)

    def setTextCursor(self, cursor: object) -> None:  # noqa: N802
        """Record cursor restoration."""

        self.applied_cursors.append(cast(_Cursor, cursor))

    def toPlainText(self) -> str:  # noqa: N802
        """Return the fake source text."""

        return self.text


class _SnapshotProvider:
    """Return one prepared prompt context-menu action snapshot."""

    def __init__(self, snapshot: PromptContextMenuActionSnapshot) -> None:
        """Store a snapshot and prepare call observations."""

        self.snapshot = snapshot
        self.calls: list[tuple[int, str, tuple[int, int] | None, bool, bool]] = []
        self.prepared: list[tuple[str, tuple[int, int] | None, bool, str]] = []

    def prepare_menu_selection(
        self,
        *,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
        reason: str,
    ) -> None:
        """Record one prepared selected-text menu request."""

        self.prepared.append((selected_text, selection_range, read_only, reason))

    def prepared_action_snapshot_for_menu(
        self,
        *,
        source_position: int,
        selected_text: str,
        selection_range: tuple[int, int] | None = None,
        read_only: bool,
        rich_prompt_rendering_enabled: bool,
    ) -> PromptContextMenuActionSnapshot:
        """Record and return the configured snapshot."""

        self.calls.append(
            (
                source_position,
                selected_text,
                selection_range,
                read_only,
                rich_prompt_rendering_enabled,
            )
        )
        return self.snapshot


class _Segments:
    """Capture segment-preset requests made by the menu presenter."""

    def __init__(self) -> None:
        """Prepare fake segment state and observations."""

        self.restored: list[PromptSegmentSelectionSnapshot] = []
        self.saved: list[tuple[str | None, PromptSegmentPresetDialogResult]] = []
        self.inserted: list[str] = []
        self.selected_snapshot = PromptSegmentSelectionSnapshot(
            start=1,
            end=5,
            text="lpha",
        )

    def selected_prompt_text(self) -> str:
        """Return fake selected text."""

        return self.selected_snapshot.text

    def selected_prompt_range_and_text(
        self,
    ) -> PromptSegmentSelectionSnapshot | None:
        """Return the fake selected range."""

        return self.selected_snapshot

    def restore_selection_snapshot(
        self,
        selection_snapshot: PromptSegmentSelectionSnapshot,
    ) -> None:
        """Record restored selections."""

        self.restored.append(selection_snapshot)

    def save_selected_segment_as_preset(
        self,
        selected_text: str | None = None,
        *,
        dialog_runner: Any,
    ) -> bool:
        """Run the supplied dialog runner and record the save call."""

        result = dialog_runner(
            PromptSegmentPresetSaveDialogRequest(
                parent=QWidget(),
                title="Save segment",
                scopes=(_scope(),),
                selected_text=selected_text or "",
            )
        )
        self.saved.append((selected_text, result))
        return result is not None

    def insert_saved_prompt_segment(
        self,
        insertion_text: str,
    ) -> PromptCommandResult[object]:
        """Record one saved segment insertion."""

        self.inserted.append(insertion_text)
        return PromptCommandResult.completed("context_menu_insert_text")


class _InsertionExecutor:
    """Capture trigger-word insertions routed through the command adapter seam."""

    def __init__(self) -> None:
        """Prepare insertion observations."""

        self.inserted: list[str] = []

    def insert_context_menu_text(
        self,
        insertion_text: str,
        *,
        command_name: str = "context_menu_insert_text",
    ) -> PromptCommandResult[object]:
        """Record one context-menu text insertion."""

        _ = command_name
        self.inserted.append(insertion_text)
        return PromptCommandResult.completed("context_menu_insert_text")

    def execute_trigger_word_insertion(
        self,
        *,
        trigger_words: str,
        source_identity: object,
    ) -> PromptCommandResult[object]:
        """Record one identity-bearing trigger-word insertion."""

        _ = source_identity
        self.inserted.append(trigger_words)
        return PromptCommandResult.completed("insert_lora_trigger_words")


def test_prompt_menu_presenter_builds_shell_request_from_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The presenter should adapt prepared feature state into shell inputs."""

    _ensure_qapp()
    segments = _Segments()
    provider = _SnapshotProvider(_snapshot(source_available=True))
    insertion_executor = _InsertionExecutor()
    schedule_calls = 0
    wiki_calls: list[str] = []
    queued_keys: list[str] = []
    toggled: list[bool] = []

    def schedule_lora() -> None:
        """Record a LoRA picker schedule request."""

        nonlocal schedule_calls
        schedule_calls += 1

    monkeypatch.setattr(
        "substitute.presentation.editor.prompt_editor.interactions."
        "prompt_menu_presenter.preset_dialog_result",
        lambda _dialog: ("Segment name", _scope()),
    )

    presenter = PromptContextMenuRequestPresenter(
        action_snapshot_provider=cast(PromptContextMenuActionController, provider),
        segment_presets=cast(PromptSegmentPresetController, segments),
        trigger_word_action_adapter=PromptTriggerWordActionAdapter(
            action_parent=QWidget(),
            text_insertion_executor=insertion_executor,
            identity_validator=lambda _identity: True,
        ),
        schedule_lora=schedule_lora,
        open_danbooru_wiki_for_selection=wiki_calls.append,
        queue_scene=queued_keys.append,
        is_read_only=lambda: False,
        rich_prompt_rendering_enabled=lambda: True,
        toggle_rich_prompt_rendering=toggled.append,
    )
    presenter.prepare_prompt_menu_selection(
        selected_text="beta",
        selection_snapshot=(1, 5, "beta"),
        reason="test",
    )

    request = presenter.prepared_prompt_menu_request(
        PromptShellContextMenuOpening(
            source_position=4,
            selected_text="beta",
            selection_snapshot=(1, 5, "beta"),
        )
    )

    assert provider.prepared == [("beta", (1, 5), False, "test")]
    assert provider.calls == [(4, "beta", (1, 5), False, True)]
    assert request.schedule_lora_enabled is True
    request.schedule_lora()
    assert schedule_calls == 1
    assert request.trigger_word_actions[0].toolTip() == "Trigger words: Friendly"
    request.trigger_word_actions[0].trigger()
    assert insertion_executor.inserted == ["friendly words"]
    assert request.save_prompt_segment is not None
    request.save_prompt_segment()
    assert segments.restored == [
        PromptSegmentSelectionSnapshot(start=1, end=5, text="beta")
    ]
    assert segments.saved == [("beta", ("Segment name", _scope()))]
    assert request.lookup_danbooru_wiki is not None
    request.lookup_danbooru_wiki()
    assert wiki_calls == ["beta"]
    insert_prompt_segment = request.insert_prompt_segment
    assert insert_prompt_segment is not None
    insert_prompt_segment("saved")
    assert segments.inserted == ["saved"]
    assert request.queue_scene_key == "portrait"
    assert request.queue_scene is not None
    request.queue_scene(request.queue_scene_key)
    assert queued_keys == ["portrait"]
    assert request.rich_prompt_rendering_enabled is True
    toggle_rich_prompt_rendering = request.toggle_rich_prompt_rendering
    assert toggle_rich_prompt_rendering is not None
    toggle_rich_prompt_rendering(False)
    assert toggled == [False]


def test_prompt_menu_presenter_suppresses_unready_optional_callbacks() -> None:
    """Unavailable feature actions should become absent shell callbacks."""

    _ensure_qapp()
    segments = _Segments()
    presenter = PromptContextMenuRequestPresenter(
        action_snapshot_provider=cast(
            PromptContextMenuActionController,
            _SnapshotProvider(
                _snapshot(
                    source_available=False,
                    danbooru_ready=False,
                    rich_prompt_rendering_enabled=False,
                )
            ),
        ),
        segment_presets=cast(PromptSegmentPresetController, segments),
        trigger_word_action_adapter=PromptTriggerWordActionAdapter(
            action_parent=QWidget(),
            text_insertion_executor=_InsertionExecutor(),
            identity_validator=lambda _identity: True,
        ),
        schedule_lora=lambda: None,
        open_danbooru_wiki_for_selection=lambda _text: None,
        queue_scene=lambda _key: None,
        is_read_only=lambda: True,
        rich_prompt_rendering_enabled=lambda: False,
        toggle_rich_prompt_rendering=lambda _enabled: None,
    )

    request = presenter.prepared_prompt_menu_request(
        PromptShellContextMenuOpening(
            source_position=4,
            selected_text="",
            selection_snapshot=None,
        )
    )

    assert request.save_prompt_segment is None
    assert request.lookup_danbooru_wiki is None
    assert request.danbooru_wiki_lookup_enabled is False
    assert request.rich_prompt_rendering_enabled is False


def test_prompt_menu_presenter_save_callback_requires_prepared_save_ready() -> None:
    """Save callbacks should follow prepared save readiness, not source presence."""

    _ensure_qapp()
    segments = _Segments()
    presenter = PromptContextMenuRequestPresenter(
        action_snapshot_provider=cast(
            PromptContextMenuActionController,
            _SnapshotProvider(_snapshot(source_available=True, save_ready=False)),
        ),
        segment_presets=cast(PromptSegmentPresetController, segments),
        trigger_word_action_adapter=PromptTriggerWordActionAdapter(
            action_parent=QWidget(),
            text_insertion_executor=_InsertionExecutor(),
            identity_validator=lambda _identity: True,
        ),
        schedule_lora=lambda: None,
        open_danbooru_wiki_for_selection=lambda _text: None,
        queue_scene=lambda _key: None,
        is_read_only=lambda: False,
        rich_prompt_rendering_enabled=lambda: True,
        toggle_rich_prompt_rendering=lambda _enabled: None,
    )

    request = presenter.prepared_prompt_menu_request(
        PromptShellContextMenuOpening(
            source_position=4,
            selected_text="beta",
            selection_snapshot=(1, 5, "beta"),
        )
    )

    assert request.save_prompt_segment is None


def test_phase24_1_prompt_menu_presenter_adapts_unavailable_snapshot() -> None:
    """The presenter should map unavailable prepared state to cheap menu inputs."""

    _ensure_qapp()
    provider = _SnapshotProvider(
        _snapshot(
            source_available=False,
            danbooru_ready=False,
            rich_prompt_rendering_enabled=False,
            lora_picker_ready=False,
            queue_scene_key=None,
            diagnostic_actions=(),
            trigger_word_actions=(),
            insert_ready=False,
        )
    )
    presenter = PromptContextMenuRequestPresenter(
        action_snapshot_provider=cast(PromptContextMenuActionController, provider),
        segment_presets=cast(PromptSegmentPresetController, _Segments()),
        trigger_word_action_adapter=PromptTriggerWordActionAdapter(
            action_parent=QWidget(),
            text_insertion_executor=_InsertionExecutor(),
            identity_validator=lambda _identity: True,
        ),
        schedule_lora=lambda: None,
        open_danbooru_wiki_for_selection=lambda _text: None,
        queue_scene=lambda _key: None,
        is_read_only=lambda: True,
        rich_prompt_rendering_enabled=lambda: False,
        toggle_rich_prompt_rendering=lambda _enabled: None,
    )

    request = presenter.prepared_prompt_menu_request(
        PromptShellContextMenuOpening(
            source_position=8,
            selected_text="",
            selection_snapshot=None,
        )
    )

    assert provider.calls == [(8, "", None, True, False)]
    assert request.schedule_lora_enabled is False
    assert request.trigger_word_actions == ()
    assert request.prompt_segment_model is not None
    assert request.save_prompt_segment is None
    assert request.insert_prompt_segment is None
    assert request.lookup_danbooru_wiki is None
    assert request.danbooru_wiki_lookup_enabled is False
    assert request.queue_scene_key is None
    assert request.diagnostic_actions == ()
    assert request.rich_prompt_rendering_enabled is False


def test_segment_host_adapter_restores_selection_and_parent() -> None:
    """Segment host adapter should own save-dialog parent and selection behavior."""

    _ensure_qapp()

    class EditorPanel(QWidget):
        """Minimal class name match for editor panel parent resolution."""

    panel = EditorPanel()
    host = _Host()
    host.setParent(panel)
    identity = PromptCommandSourceIdentity(source_revision=3, source_length=10)
    adapter = PromptSegmentPresetHostAdapter(
        host=cast(PromptMenuEditorHost, host),
        source_identity_provider=lambda: identity,
    )

    adapter.restore_prompt_segment_selection(start=2, end=7)

    assert adapter.toPlainText() == "alpha beta"
    assert cast(object, adapter.textCursor()) is host.fake_cursor
    assert adapter.prompt_command_source_identity() is identity
    assert adapter.prompt_segment_dialog_parent() is panel
    assert host.fake_cursor.positions == [
        (2, None),
        (7, QTextCursor.MoveMode.KeepAnchor),
    ]
    assert host.applied_cursors == [host.fake_cursor]


def _snapshot(
    *,
    source_available: bool = True,
    save_ready: bool | None = None,
    danbooru_ready: bool = True,
    rich_prompt_rendering_enabled: bool = True,
    lora_picker_ready: bool = True,
    queue_scene_key: str | None = "portrait",
    diagnostic_actions: tuple[PromptContextMenuAction, ...] | None = None,
    trigger_word_actions: (
        tuple[PromptFeatureActionState[PromptLoraTriggerWordsPayload], ...] | None
    ) = None,
    insert_ready: bool = True,
) -> PromptContextMenuActionSnapshot:
    """Build one prepared context-menu action snapshot."""

    prepared_diagnostic_actions = (
        (PromptContextMenuAction(label="Fix"),)
        if diagnostic_actions is None
        else diagnostic_actions
    )
    prepared_trigger_word_actions = (
        (
            PromptFeatureActionState(
                action_id="lora.trigger_words:test",
                label="Trigger words: Friendly",
                ready=True,
                command_request=PromptFeatureCommandRequest(
                    command_name="lora_insert_trigger_words",
                    identity=PromptFeatureSnapshotIdentity(source_revision=9),
                    payload=PromptLoraTriggerWordsPayload(
                        insertion_text="friendly words",
                        display_name="Friendly",
                        full_label=app_text("Trigger words: %1", "Friendly"),
                    ),
                ),
            ),
        )
        if trigger_word_actions is None
        else trigger_word_actions
    )
    wiki_action = (
        PromptFeatureActionState(
            action_id="danbooru.wiki_lookup",
            label="Danbooru wiki lookup",
            ready=True,
            command_request=PromptFeatureCommandRequest(
                command_name="danbooru_wiki_lookup",
                identity=PromptFeatureSnapshotIdentity(source_revision=9),
                payload=PromptDanbooruWikiLookupPayload(selection_text="beta"),
            ),
        )
        if danbooru_ready
        else None
    )
    return PromptContextMenuActionSnapshot(
        source_position=4,
        selected_text="beta",
        scene_context=PromptScenePositionContext(
            source_position=4,
            scene_key="portrait",
            queueable_scene_key=queue_scene_key,
            effective_prompt_text="scene prompt",
        ),
        diagnostic_actions=prepared_diagnostic_actions,
        lora_picker_ready=lora_picker_ready,
        lora_trigger_word_actions=prepared_trigger_word_actions,
        segment_snapshot=PromptSegmentPresetSnapshot(
            identity=PromptFeatureSnapshotIdentity(source_revision=9),
            menu_model=PromptSegmentPresetMenuModel(),
            save_state=PromptSegmentPresetSaveState(
                source_available=source_available,
                selected_text="beta",
                ready=source_available if save_ready is None else save_ready,
            ),
            insert_ready=insert_ready,
        ),
        danbooru_snapshot=PromptDanbooruActionSnapshot(
            identity=PromptFeatureSnapshotIdentity(source_revision=9),
            wiki_lookup_action=wiki_action,
            url_import_state=PromptDanbooruUrlImportState(
                service_available=False,
                enabled=False,
                ready=False,
                disabled_reason="service_unavailable",
            ),
        ),
        read_only=False,
        rich_prompt_rendering_enabled=rich_prompt_rendering_enabled,
    )


def _scope() -> PresetSaveScope:
    """Return the fake global preset scope used by presenter tests."""

    return PresetSaveScope(
        title="Global",
        full_label="Global",
        association=GLOBAL_PRESET_ASSOCIATION,
    )


def _ensure_qapp() -> QApplication:
    """Return a Qt application for QAction tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)
