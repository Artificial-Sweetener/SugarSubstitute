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

"""Build typed inline LoRA menu presenter scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QWidget
from sugarsubstitute_shared.localization import app_text

from substitute.presentation.editor.prompt_editor.commands.contracts import (
    PromptCommandResult,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
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
from substitute.presentation.shell.output_canvas_thumbnail_choices import (
    OutputCanvasThumbnailChoice,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextMenuTarget,
    ModelMetadataMenuAction,
    ModelMetadataMenuItem,
)


@dataclass(frozen=True, slots=True)
class PreparedScene:
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


class LoraMetadata:
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
                    full_label=app_text(
                        "Trigger words: %1", token_context.display_name
                    ),
                ),
            ),
        )


class InsertionExecutor:
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


class ShellMenu:
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


class MetadataActionHandler:
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


def build_presenter(
    *,
    metadata: LoraMetadata,
    shell_menu: ShellMenu,
    insertion_executor: InsertionExecutor,
    opened_urls: list[str],
    effective_prompt_text: str,
    finish_reasons: list[str],
    scene_ready: bool = True,
    scene_stale: bool = False,
    metadata_action_handler: MetadataActionHandler | None = None,
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
            lambda _position: PreparedScene(
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


def actions(
    items: tuple[ModelMetadataMenuItem, ...],
) -> tuple[ModelMetadataMenuAction, ...]:
    """Return action items from one menu item tuple."""

    return tuple(item for item in items if isinstance(item, ModelMetadataMenuAction))


def token(
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


def ensure_qapp() -> QApplication:
    """Return a Qt application for QAction tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)
