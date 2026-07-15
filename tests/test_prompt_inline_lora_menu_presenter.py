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

"""Tests for inline LoRA context-menu presentation ownership."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import cast
from uuid import UUID

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction, QFontMetrics
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.commands import PromptCommandResult
from substitute.presentation.editor.prompt_editor.features import (
    PromptFeatureCommandRequest,
    PromptFeatureSnapshotIdentity,
    PromptLoraModelPageAction,
    PromptLoraModelPagePayload,
    PromptLoraTokenContext,
    PromptLoraTriggerWordsAction,
    PromptLoraTriggerWordsPayload,
    PromptScenePositionContext,
    PromptScenePositionContextSnapshot,
)
from substitute.presentation.editor.prompt_editor.interactions import (
    PromptExternalUrlActionRunner,
    PromptInlineLoraContextMenuPresenter,
    PromptTriggerWordActionAdapter,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.shell.output_canvas_thumbnail_choices import (
    OutputCanvasThumbnailChoice,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextMenuTarget,
    ModelMetadataMenuAction,
    ModelMetadataMenuItem,
)


@dataclass(frozen=True, slots=True)
class _PreparedScene:
    """Provide prepared scene-position state for inline menu tests."""

    effective_prompt_text: str
    ready: bool = True
    stale: bool = False

    def snapshot(self) -> PromptScenePositionContextSnapshot:
        """Return prepared scene-position context state."""

        return PromptScenePositionContextSnapshot(
            identity=PromptFeatureSnapshotIdentity(source_revision=7, stale=self.stale),
            source_position=4,
            context=(
                None
                if not self.ready
                else PromptScenePositionContext(
                    source_position=4,
                    scene_key=None,
                    queueable_scene_key=None,
                    effective_prompt_text=self.effective_prompt_text,
                )
            ),
            ready=self.ready and not self.stale,
            stale=self.stale,
            unavailable_reason=(
                "scene_position_context_unprepared"
                if not self.ready or self.stale
                else None
            ),
        )


class _LoraMetadata:
    """Return prepared LoRA feature actions for presenter tests."""

    def __init__(self) -> None:
        """Prepare fake feature state and observations."""

        self.trigger_prompt_texts: list[str] = []

    def model_page_action_for_token(
        self,
        token_context: PromptLoraTokenContext,
    ) -> PromptLoraModelPageAction | None:
        """Return a model-page action when the token exposes a URL."""

        url = (
            "" if token_context.model_page_url is None else token_context.model_page_url
        )
        url = url.strip()
        if not url:
            return None
        return PromptLoraModelPageAction(
            action_id="lora.open_model_page",
            label="Open CivitAI page",
            ready=True,
            command_request=PromptFeatureCommandRequest(
                command_name="lora_open_model_page",
                identity=PromptFeatureSnapshotIdentity(source_revision=7),
                payload=PromptLoraModelPagePayload(url=url),
            ),
        )

    def inline_action(
        self,
        token_context: PromptLoraTokenContext,
        *,
        prompt_text: str,
    ) -> PromptLoraTriggerWordsAction | None:
        """Project a trigger-word action when token metadata has insertable words."""

        self.trigger_prompt_texts.append(prompt_text)
        if not token_context.trained_words:
            return None
        insertion_text = ", ".join(token_context.trained_words)
        full_label = f"Trigger words: {token_context.display_name}"
        return PromptLoraTriggerWordsAction(
            action_id="lora.trigger_words:test",
            label=full_label,
            ready=True,
            command_request=PromptFeatureCommandRequest(
                command_name="lora_insert_trigger_words",
                identity=PromptFeatureSnapshotIdentity(source_revision=7),
                payload=PromptLoraTriggerWordsPayload(
                    insertion_text=insertion_text,
                    display_name=token_context.display_name,
                    full_label=full_label,
                ),
            ),
        )


class _InsertionExecutor:
    """Record trigger-word insertions routed through the command adapter seam."""

    def __init__(self) -> None:
        """Prepare insertion observations."""

        self.inserted: list[str] = []

    def insert_context_menu_text(
        self,
        insertion_text: str,
        *,
        command_name: str = "context_menu_insert_text",
    ) -> PromptCommandResult[object]:
        """Record one context-menu insertion request."""

        _ = command_name
        self.inserted.append(insertion_text)
        return PromptCommandResult.completed("context_menu_insert_text")

    def execute_trigger_word_insertion(
        self,
        *,
        trigger_words: str,
        source_identity: object,
    ) -> PromptCommandResult[object]:
        """Record one identity-safe trigger-word insertion request."""

        _ = source_identity
        self.inserted.append(trigger_words)
        return PromptCommandResult.completed("lora_insert_trigger_words")


class _ShellMenu:
    """Record inline LoRA shell menu presentation requests."""

    def __init__(self) -> None:
        """Prepare shell presentation observations."""

        self.calls: list[
            tuple[QPoint, QAction | None, tuple[ModelMetadataMenuItem, ...]]
        ] = []
        self.insert_states: list[tuple[int | None, bool | None]] = []

    def set_context_insert_state(
        self,
        *,
        insert_position: int | None,
        should_replace_selection: bool | None = None,
    ) -> None:
        """Record the inline insertion target."""

        self.insert_states.append((insert_position, should_replace_selection))

    def show_inline_lora_context_menu(
        self,
        *,
        global_pos: QPoint,
        trigger_action: QAction | None,
        metadata_menu_items: tuple[ModelMetadataMenuItem, ...],
    ) -> None:
        """Record one shell menu presentation request."""

        self.calls.append((QPoint(global_pos), trigger_action, metadata_menu_items))


class _MetadataActionHandler:
    """Record manual refresh requests from inline LoRA menu actions."""

    def __init__(self) -> None:
        """Prepare refresh observations."""

        self.refresh_targets: list[object] = []

    def refresh_civitai_metadata(self, target: object) -> None:
        """Record one refresh target."""

        self.refresh_targets.append(target)

    def output_canvas_thumbnail_choices(
        self,
    ) -> tuple[OutputCanvasThumbnailChoice, ...]:
        """Return no output choices for existing inline tests."""

        return ()

    def active_output_canvas_thumbnail_choice(
        self,
    ) -> OutputCanvasThumbnailChoice | None:
        """Return no active output choice for existing inline tests."""

        return None

    def set_thumbnail_from_output_image(
        self,
        target: ModelMetadataContextMenuTarget,
        image_id: UUID,
    ) -> None:
        """Ignore output thumbnail requests in existing inline tests."""

        _ = (target, image_id)


def test_inline_lora_presenter_builds_page_and_trigger_actions() -> None:
    """The presenter should adapt a projected token into shell menu actions."""

    _ensure_qapp()
    opened_urls: list[str] = []
    metadata = _LoraMetadata()
    shell_menu = _ShellMenu()
    insertion_executor = _InsertionExecutor()
    finish_reasons: list[str] = []
    presenter = _presenter(
        metadata=metadata,
        shell_menu=shell_menu,
        insertion_executor=insertion_executor,
        opened_urls=opened_urls,
        effective_prompt_text="imp princess, portrait",
        finish_reasons=finish_reasons,
    )

    presenter.show_lora_context_menu(
        _token(
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
    metadata_actions = _actions(metadata_menu_items)
    assert len(metadata_actions) == 1
    page_action = metadata_actions[0]
    assert page_action is not None
    assert page_action.label == "Go to CivitAI page"
    page_action.callback()
    assert opened_urls == ["https://civitai.example/models/1"]


def test_inline_lora_presenter_suppresses_missing_url_and_empty_triggers() -> None:
    """Missing prepared actions should be passed to the passive shell as absent."""

    _ensure_qapp()
    shell_menu = _ShellMenu()
    presenter = _presenter(
        metadata=_LoraMetadata(),
        shell_menu=shell_menu,
        insertion_executor=_InsertionExecutor(),
        opened_urls=[],
        effective_prompt_text="portrait",
        finish_reasons=[],
    )

    presenter.show_lora_context_menu(
        _token(model_page_url="  ", trained_words=()),
        QPoint(1, 2),
    )

    assert len(shell_menu.calls) == 1
    _global_pos, trigger_action, metadata_menu_items = shell_menu.calls[0]
    assert trigger_action is None
    assert metadata_menu_items == ()


def test_phase24_1_inline_lora_presenter_ignores_non_projection_tokens() -> None:
    """Non-token menu requests should finish edits without opening a menu."""

    _ensure_qapp()
    shell_menu = _ShellMenu()
    finish_reasons: list[str] = []
    presenter = _presenter(
        metadata=_LoraMetadata(),
        shell_menu=shell_menu,
        insertion_executor=_InsertionExecutor(),
        opened_urls=[],
        effective_prompt_text="portrait",
        finish_reasons=finish_reasons,
    )

    presenter.show_lora_context_menu(object(), QPoint(4, 8))

    assert finish_reasons == ["lora_context_menu"]
    assert shell_menu.calls == []


def test_phase24_1_inline_lora_presenter_passes_single_prepared_actions() -> None:
    """Inline LoRA menus should pass page-only or trigger-only state to shell."""

    _ensure_qapp()
    shell_menu = _ShellMenu()
    insertion_executor = _InsertionExecutor()
    presenter = _presenter(
        metadata=_LoraMetadata(),
        shell_menu=shell_menu,
        insertion_executor=insertion_executor,
        opened_urls=[],
        effective_prompt_text="scene-local prompt",
        finish_reasons=[],
    )

    presenter.show_lora_context_menu(
        _token(
            model_page_url="https://civitai.example/models/2",
            trained_words=(),
        ),
        QPoint(10, 20),
    )
    presenter.show_lora_context_menu(
        _token(model_page_url=None, trained_words=("scene trigger",)),
        QPoint(30, 40),
    )

    assert len(shell_menu.calls) == 2
    _page_pos, page_trigger_action, page_metadata_items = shell_menu.calls[0]
    assert page_trigger_action is None
    page_action = _actions(page_metadata_items)[0]
    assert page_action is not None
    _trigger_pos, trigger_action, trigger_metadata_items = shell_menu.calls[1]
    assert trigger_action is not None
    assert trigger_metadata_items == ()
    assert trigger_action.toolTip() == "Trigger words: Friendly Midna"
    trigger_action.trigger()
    assert insertion_executor.inserted == ["scene trigger"]


def test_phase24_5_inline_lora_presenter_omits_stale_scene_trigger_action() -> None:
    """Inline LoRA menus should not compute trigger words from stale scene context."""

    _ensure_qapp()
    metadata = _LoraMetadata()
    shell_menu = _ShellMenu()
    presenter = _presenter(
        metadata=metadata,
        shell_menu=shell_menu,
        insertion_executor=_InsertionExecutor(),
        opened_urls=[],
        effective_prompt_text="stale scene prompt",
        finish_reasons=[],
        scene_ready=False,
    )

    presenter.show_lora_context_menu(
        _token(
            model_page_url="https://civitai.example/models/2",
            trained_words=("scene trigger",),
        ),
        QPoint(30, 40),
    )

    assert metadata.trigger_prompt_texts == []
    assert len(shell_menu.calls) == 1
    _trigger_pos, trigger_action, metadata_menu_items = shell_menu.calls[0]
    assert trigger_action is None
    page_action = _actions(metadata_menu_items)[0]
    assert page_action is not None


def test_inline_lora_presenter_builds_refresh_action_for_backend_token() -> None:
    """Inline LoRA metadata actions should include refresh for local targets."""

    _ensure_qapp()
    shell_menu = _ShellMenu()
    metadata_handler = _MetadataActionHandler()
    presenter = _presenter(
        metadata=_LoraMetadata(),
        shell_menu=shell_menu,
        insertion_executor=_InsertionExecutor(),
        opened_urls=[],
        effective_prompt_text="portrait",
        finish_reasons=[],
        metadata_action_handler=metadata_handler,
    )

    presenter.show_lora_context_menu(
        _token(model_page_url=None, trained_words=()),
        QPoint(1, 2),
    )

    assert len(shell_menu.calls) == 1
    _global_pos, trigger_action, metadata_menu_items = shell_menu.calls[0]
    assert trigger_action is None
    metadata_actions = _actions(metadata_menu_items)
    assert [action.label for action in metadata_actions] == [
        "Refresh CivitAI metadata",
        "Set thumbnail from canvas",
    ]
    refresh_action = metadata_actions[0]

    refresh_action.callback()

    assert len(metadata_handler.refresh_targets) == 1
    target = metadata_handler.refresh_targets[0]
    assert getattr(target, "backend_value") == "midna.safetensors"
    assert getattr(target, "model_kind") == "loras"


def test_inline_lora_presenter_label_elides_to_menu_budget() -> None:
    """Long LoRA names should stay within the established trigger-word width."""

    _ensure_qapp()
    adapter = PromptTriggerWordActionAdapter(
        action_parent=QWidget(),
        text_insertion_executor=_InsertionExecutor(),
        identity_validator=lambda _identity: True,
    )
    long_name = (
        "Extremely Long CivitAI Friendly LoRA Name With Version Details And "
        "Training Notes That Would Otherwise Blow Out The Context Menu"
    )

    label = adapter.trigger_words_action_label(long_name)

    assert not label.startswith("Trigger words:")
    assert QFontMetrics(QApplication.font()).horizontalAdvance(label) <= 191
    assert label != long_name


def _presenter(
    *,
    metadata: _LoraMetadata,
    shell_menu: _ShellMenu,
    insertion_executor: _InsertionExecutor,
    opened_urls: list[str],
    effective_prompt_text: str,
    finish_reasons: list[str],
    scene_ready: bool = True,
    scene_stale: bool = False,
    metadata_action_handler: _MetadataActionHandler | None = None,
) -> PromptInlineLoraContextMenuPresenter:
    """Return an inline LoRA presenter with fake collaborators."""

    def open_url(url: str) -> bool:
        """Record one URL opening request."""

        opened_urls.append(url)
        return True

    return PromptInlineLoraContextMenuPresenter(
        lora_metadata=metadata,
        lora_trigger_words=metadata,
        prepared_scene_context_at_position=(
            lambda _position: _PreparedScene(
                effective_prompt_text=effective_prompt_text,
                ready=scene_ready,
                stale=scene_stale,
            ).snapshot()
        ),
        trigger_word_action_adapter=PromptTriggerWordActionAdapter(
            action_parent=QWidget(),
            text_insertion_executor=insertion_executor,
            identity_validator=lambda _identity: True,
        ),
        shell_menu=shell_menu,
        finish_pending_key_edit_block=finish_reasons.append,
        external_url_actions=PromptExternalUrlActionRunner(open_url),
        metadata_action_handler=metadata_action_handler,
    )


def _actions(
    items: tuple[ModelMetadataMenuItem, ...],
) -> tuple[ModelMetadataMenuAction, ...]:
    """Return action items from one menu item tuple."""

    return tuple(item for item in items if isinstance(item, ModelMetadataMenuAction))


def _token(
    *,
    model_page_url: str | None,
    trained_words: tuple[str, ...],
) -> PromptProjectionToken:
    """Return one projected LoRA token for presenter tests."""

    return PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=4,
        source_end=30,
        display_text="Friendly Midna",
        detail_text="midna",
        lora_backend_value="midna.safetensors",
        lora_trained_words=trained_words,
        model_page_url=model_page_url,
    )


def _ensure_qapp() -> QApplication:
    """Return a Qt application for QAction tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)
