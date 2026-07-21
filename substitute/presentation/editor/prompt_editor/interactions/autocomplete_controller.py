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

"""Define autocomplete interaction controller protocol boundaries."""

from __future__ import annotations

from collections.abc import Hashable
from typing import Protocol, cast

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor import (
    PromptAutocompleteQuery,
    PromptLoraAutocompleteQuery,
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.autocomplete_refresh_intent import (
    PASSIVE_AUTOCOMPLETE_REFRESH_INTENTS,
    PromptAutocompleteRefreshIntent,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteQueryController,
    PromptAutocompleteQueryState,
    PromptAutocompleteResultController,
    PromptAutocompleteSceneContextController,
    PromptAutocompleteScheduledLoraContextController,
    PromptFeatureSnapshotIdentity,
)
from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.debug_probe import (
    autocomplete_probe_state,
    log_prompt_editor_probe,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompletePanel,
    PromptAutocompletePresenter,
)
from substitute.presentation.editor.prompt_editor.projection.autocomplete_ghost_text import (
    PromptAutocompleteGhostTextPublisher,
    PromptAutocompleteGhostTextSourceSnapshot,
)
from substitute.presentation.widgets.picker_keyboard_navigation import (
    PickerKeyboardAction,
    picker_keyboard_action_for_key,
)
from .autocomplete_acceptance import (
    PromptAutocompleteAcceptanceCommandFactory,
    PromptAutocompleteAcceptanceController,
)
from .autocomplete_session import (
    PromptAutocompleteDismissReason,
    PromptAutocompleteSessionController,
    PromptAutocompleteSessionState,
)
from .autocomplete_timing import PromptAutocompleteSourceSnapshot

_TagQueryIdentity = tuple[str, str, int, int, int, int]


class PromptAutocompleteCursor(Protocol):
    """Describe read-only cursor behavior needed by autocomplete state."""

    def position(self) -> int:
        """Return the current cursor position."""

    def hasSelection(self) -> bool:
        """Return whether the cursor currently selects source text."""


class PromptAutocompleteQueryEditor(Protocol):
    """Describe editor state needed for autocomplete query refresh."""

    def toPlainText(self) -> str:
        """Return the current source text snapshot."""

    def textCursor(self) -> PromptAutocompleteCursor:
        """Return the editor's live text cursor."""

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return the current source identity used to reject stale commands."""


class PromptAutocompleteEditor(
    PromptAutocompleteAcceptanceCommandFactory,
    PromptAutocompleteQueryEditor,
    Protocol,
):
    """Describe editor behavior consumed by autocomplete interaction owners."""

    def cursorRect(self) -> QRect:
        """Return the caret rectangle in viewport coordinates."""

    def viewport(self) -> QWidget:
        """Return the editor viewport used for autocomplete geometry placement."""

    def setFocus(self) -> None:
        """Restore focus to the editor after suggestion activation."""

    def set_autocomplete_preview_state(
        self,
        preview_state: PromptAutocompletePreviewState | None,
    ) -> None:
        """Replace the projection-owned autocomplete preview state."""

    def commit_lora_autocomplete_replacement(self) -> None:
        """Publish syntax state after accepting one complete LoRA replacement."""


class PromptAutocompleteCoordinator:
    """Coordinate prompt autocomplete session state and presentation surfaces."""

    def __init__(
        self,
        editor: PromptAutocompleteEditor,
        *,
        autocomplete_result_controller: PromptAutocompleteResultController,
        autocomplete_scene_context_controller: PromptAutocompleteSceneContextController,
        autocomplete_scheduled_lora_context_controller: (
            PromptAutocompleteScheduledLoraContextController
        ),
        autocomplete_acceptance_controller: PromptAutocompleteAcceptanceController,
        autocomplete_session_controller: PromptAutocompleteSessionController,
        autocomplete_presenter: PromptAutocompletePresenter | None = None,
        autocomplete_ghost_text_publisher: (
            PromptAutocompleteGhostTextPublisher | None
        ) = None,
        autocomplete_ghost_text_enabled: bool = True,
        lora_autocomplete_enabled: bool = True,
        lora_thumbnail_cache_available: bool = False,
    ) -> None:
        """Store the editor dependencies and initialize empty autocomplete state."""

        self._editor = editor
        self._scene_context_controller = autocomplete_scene_context_controller
        self._scheduled_lora_context = autocomplete_scheduled_lora_context_controller
        self._result_controller = autocomplete_result_controller
        self._lora_autocomplete_enabled = lora_autocomplete_enabled
        self._lora_thumbnail_cache_available = lora_thumbnail_cache_available
        self._autocomplete_ghost_text_enabled = autocomplete_ghost_text_enabled
        self._presenter = autocomplete_presenter
        self._ghost_text_publisher = autocomplete_ghost_text_publisher
        self._acceptance_controller = autocomplete_acceptance_controller
        if self._presenter is not None:
            self._presenter.set_activation_handler(self._handle_presenter_activation)
            self._presenter.set_selection_changed_handler(
                self._handle_presenter_selection_changed
            )
            self._presenter.set_visibility_changed_handler(
                self._handle_presenter_visibility_changed
            )
        self._sessions = autocomplete_session_controller
        self._latest_tag_query: PromptAutocompleteQuery | None = None
        self._latest_tag_source_text: str | None = None
        self._latest_tag_query_identity: _TagQueryIdentity | None = None
        self._latest_wildcard_query: PromptWildcardAutocompleteQuery | None = None
        self._latest_wildcard_query_identity: Hashable | None = None

    @property
    def panel(self) -> PromptAutocompletePanel | None:
        """Return the live autocomplete panel widget when it exists."""

        if self._presenter is None:
            return None
        return self._presenter.panel

    def refresh_active_scene_session(self) -> None:
        """Refresh visible scene suggestions after scene feature state changes."""

        session = self._sessions.session
        if session.mode == "scene":
            self.refresh_for_scene_query(
                session.scene_query,
                source_identity=self._sessions.source_identity,
                ghost_text_source_snapshot=(self._sessions.ghost_text_source_snapshot),
            )

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle non-text autocomplete controls without interrupting normal typing."""

        log_prompt_editor_probe(
            "autocomplete.handle_key_press.begin",
            key=int(event.key()),
            text=event.text(),
            autocomplete=autocomplete_probe_state(self),
        )
        if not self._has_active_session():
            log_prompt_editor_probe(
                "autocomplete.handle_key_press.end",
                handled=False,
                reason="inactive",
                autocomplete=autocomplete_probe_state(self),
            )
            return False

        modifiers = event.modifiers()
        if modifiers not in (
            Qt.KeyboardModifier.NoModifier,
            Qt.KeyboardModifier.KeypadModifier,
        ):
            log_prompt_editor_probe(
                "autocomplete.handle_key_press.end",
                handled=False,
                reason="modifiers",
                autocomplete=autocomplete_probe_state(self),
            )
            return False

        key = event.key()
        if self._sessions.session.mode == "lora":
            return self._handle_lora_key_press(key)

        if key == Qt.Key.Key_Down:
            self._sessions.move_suggestion_selection(1)
            self._present_active_surfaces()
            log_prompt_editor_probe(
                "autocomplete.handle_key_press.end",
                handled=True,
                reason="down_selection",
                autocomplete=autocomplete_probe_state(self),
            )
            return True
        if key == Qt.Key.Key_Up:
            self._sessions.move_suggestion_selection(-1)
            self._present_active_surfaces()
            log_prompt_editor_probe(
                "autocomplete.handle_key_press.end",
                handled=True,
                reason="up_selection",
                autocomplete=autocomplete_probe_state(self),
            )
            return True
        if key in {
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
        }:
            self.dismiss_autocomplete("caret_left_query")
            log_prompt_editor_probe(
                "autocomplete.handle_key_press.end",
                handled=False,
                reason="horizontal_or_line_key",
                autocomplete=autocomplete_probe_state(self),
            )
            return False
        if key == Qt.Key.Key_Tab:
            self.accept_selection(add_comma=True)
            log_prompt_editor_probe(
                "autocomplete.handle_key_press.end",
                handled=True,
                reason="tab_accept",
                autocomplete=autocomplete_probe_state(self),
            )
            return True
        if key == Qt.Key.Key_Escape:
            self.dismiss_autocomplete("escape")
            log_prompt_editor_probe(
                "autocomplete.handle_key_press.end",
                handled=True,
                reason="escape",
                autocomplete=autocomplete_probe_state(self),
            )
            return True
        log_prompt_editor_probe(
            "autocomplete.handle_key_press.end",
            handled=False,
            reason="unhandled",
            autocomplete=autocomplete_probe_state(self),
        )
        return False

    def refresh_for_query(
        self,
        query: PromptAutocompleteQuery | None,
        *,
        source_text: str,
        source_identity: PromptCommandSourceIdentity | None = None,
        feature_profile_identity: PromptFeatureSnapshotIdentity | None = None,
        query_identity: Hashable | None = None,
        ghost_text_source_snapshot: (
            PromptAutocompleteGhostTextSourceSnapshot | None
        ) = None,
        refresh_intent: PromptAutocompleteRefreshIntent = "programmatic",
    ) -> None:
        """Refresh suggestions from one application-owned autocomplete query."""

        self._refresh_for_query_measured(
            query,
            source_text=source_text,
            source_identity=source_identity,
            feature_profile_identity=feature_profile_identity,
            query_identity=query_identity,
            ghost_text_source_snapshot=ghost_text_source_snapshot,
            refresh_intent=refresh_intent,
        )

    def _refresh_for_query_measured(
        self,
        query: PromptAutocompleteQuery | None,
        *,
        source_text: str,
        source_identity: PromptCommandSourceIdentity | None,
        feature_profile_identity: PromptFeatureSnapshotIdentity | None,
        query_identity: Hashable | None,
        ghost_text_source_snapshot: PromptAutocompleteGhostTextSourceSnapshot | None,
        refresh_intent: PromptAutocompleteRefreshIntent,
    ) -> None:
        """Refresh tag autocomplete after refresh_for_query starts probe timing."""

        if refresh_intent in PASSIVE_AUTOCOMPLETE_REFRESH_INTENTS:
            self._latest_tag_query = None
            self._latest_tag_source_text = None
            self._latest_tag_query_identity = None
            self._latest_wildcard_query = None
            self._latest_wildcard_query_identity = None
            self.dismiss_autocomplete("no_query")
            return

        if query is None:
            self._latest_tag_query = None
            self._latest_tag_source_text = None
            self._latest_tag_query_identity = None
            self._latest_wildcard_query = None
            self._latest_wildcard_query_identity = None
            self.dismiss_autocomplete("no_query")
            return

        scene_context = self._scene_context_controller.context_for_tag_query(
            query,
            source_text=source_text,
            source_identity=source_identity,
            feature_profile_identity=feature_profile_identity,
            query_identity=query_identity,
        )
        result = self._result_controller.result_for_tag_query(
            query=query,
            context=scene_context.tag_context,
            source_identity=source_identity,
        )
        self._latest_tag_source_text = source_text
        self._latest_tag_query = result.tag_query
        self._latest_tag_query_identity = (
            None
            if result.tag_query is None
            else self._tag_query_identity(
                query=result.tag_query,
                prompt_text=source_text,
            )
        )
        self._latest_wildcard_query = None
        self._latest_wildcard_query_identity = None
        if result.status != "ready" or not result.suggestions:
            self.dismiss_autocomplete("no_query")
            return

        self._sessions.replace_result(
            result,
            source_identity=source_identity,
            ghost_text_source_snapshot=ghost_text_source_snapshot,
        )
        self._present_active_surfaces()

    def refresh_for_scene_query(
        self,
        query: PromptSceneAutocompleteQuery | None,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
        ghost_text_source_snapshot: (
            PromptAutocompleteGhostTextSourceSnapshot | None
        ) = None,
        refresh_intent: PromptAutocompleteRefreshIntent = "programmatic",
    ) -> None:
        """Refresh suggestions from the workflow scene title list."""

        self._refresh_for_scene_query_measured(
            query,
            source_identity=source_identity,
            ghost_text_source_snapshot=ghost_text_source_snapshot,
            refresh_intent=refresh_intent,
        )

    def _refresh_for_scene_query_measured(
        self,
        query: PromptSceneAutocompleteQuery | None,
        *,
        source_identity: PromptCommandSourceIdentity | None,
        ghost_text_source_snapshot: PromptAutocompleteGhostTextSourceSnapshot | None,
        refresh_intent: PromptAutocompleteRefreshIntent,
    ) -> None:
        """Refresh scene autocomplete after refresh_for_scene_query starts timing."""

        self._latest_tag_query = None
        self._latest_tag_source_text = None
        self._latest_tag_query_identity = None
        self._latest_wildcard_query = None
        self._latest_wildcard_query_identity = None
        if refresh_intent in PASSIVE_AUTOCOMPLETE_REFRESH_INTENTS:
            self.dismiss_autocomplete("no_query")
            return
        if query is None:
            self.dismiss_autocomplete("no_query")
            return

        result = self._result_controller.result_for_scene_query(
            query,
            source_identity=source_identity,
        )
        if result.status != "ready" or not result.suggestions:
            self.dismiss_autocomplete("no_query")
            return

        self._sessions.replace_result(
            result,
            source_identity=source_identity,
            ghost_text_source_snapshot=ghost_text_source_snapshot,
        )
        self._present_active_surfaces()

    def refresh_for_wildcard_query(
        self,
        query: PromptWildcardAutocompleteQuery | None,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
        ghost_text_source_snapshot: (
            PromptAutocompleteGhostTextSourceSnapshot | None
        ) = None,
        refresh_intent: PromptAutocompleteRefreshIntent = "programmatic",
    ) -> None:
        """Refresh wildcard file autocomplete from one active curly placeholder."""

        self._refresh_for_wildcard_query_measured(
            query,
            source_identity=source_identity,
            ghost_text_source_snapshot=ghost_text_source_snapshot,
            refresh_intent=refresh_intent,
        )

    def _refresh_for_wildcard_query_measured(
        self,
        query: PromptWildcardAutocompleteQuery | None,
        *,
        source_identity: PromptCommandSourceIdentity | None,
        ghost_text_source_snapshot: PromptAutocompleteGhostTextSourceSnapshot | None,
        refresh_intent: PromptAutocompleteRefreshIntent,
    ) -> None:
        """Refresh wildcard autocomplete after refresh_for_wildcard_query starts timing."""

        self._latest_tag_query = None
        self._latest_tag_source_text = None
        self._latest_tag_query_identity = None
        if refresh_intent in PASSIVE_AUTOCOMPLETE_REFRESH_INTENTS:
            self._latest_wildcard_query = None
            self._latest_wildcard_query_identity = None
            self.dismiss_autocomplete("no_query")
            return
        if query is None:
            self._latest_wildcard_query = None
            self._latest_wildcard_query_identity = None
            self.dismiss_autocomplete("no_query")
            return
        self._latest_wildcard_query = query
        self._latest_wildcard_query_identity = self._wildcard_query_identity(query)

        result = self._result_controller.result_for_wildcard_query(
            query,
            source_identity=source_identity,
            current_query_identity=self._current_safe_wildcard_query_identity,
            refresh_current_query=self._refresh_latest_wildcard_query,
        )
        if result.status != "ready" or not result.suggestions:
            self.dismiss_autocomplete("no_query")
            return

        self._sessions.replace_result(
            result,
            source_identity=source_identity,
            ghost_text_source_snapshot=ghost_text_source_snapshot,
        )
        self._present_active_surfaces()

    def _current_safe_wildcard_query_identity(self) -> Hashable | None:
        """Return the active wildcard query identity without prompt text."""

        return self._latest_wildcard_query_identity

    def _refresh_latest_wildcard_query(self) -> None:
        """Refresh the active wildcard query after async catalog rows publish."""

        query = self._latest_wildcard_query
        if query is None:
            return
        self.refresh_for_wildcard_query(
            query,
            source_identity=self._sessions.source_identity,
            ghost_text_source_snapshot=self._sessions.ghost_text_source_snapshot,
        )

    def _wildcard_query_identity(
        self,
        query: PromptWildcardAutocompleteQuery,
    ) -> Hashable:
        """Return the identity used to discard stale wildcard async results."""

        return (
            "wildcard",
            query.prefix,
            self._result_controller.limit,
            self._result_controller.wildcard_feature_identity(),
        )

    def _current_safe_tag_query_identity(self) -> Hashable | None:
        """Return the active tag query identity without prompt text."""

        query = self._latest_tag_query
        if query is None:
            return None
        return self._result_controller.safe_tag_query_identity(query)

    def current_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return the current editor source identity for async freshness checks."""

        return self._editor.prompt_command_source_identity()

    def current_query_identity(self) -> Hashable | None:
        """Return the active prompt-safe tag query identity."""

        return self._current_safe_tag_query_identity()

    def refresh_current_query(self) -> None:
        """Refresh the active tag query after prepared context publication."""

        self._refresh_latest_tag_query()

    def _refresh_latest_tag_query(self) -> None:
        """Refresh the active tag query after async trigger context resolves."""

        query = self._latest_tag_query
        source_text = self._latest_tag_source_text
        if query is None or source_text is None:
            return
        self.refresh_for_query(
            query,
            source_text=source_text,
            source_identity=self._sessions.source_identity,
            ghost_text_source_snapshot=self._sessions.ghost_text_source_snapshot,
        )

    def _tag_query_identity(
        self,
        *,
        query: PromptAutocompleteQuery,
        prompt_text: str,
    ) -> _TagQueryIdentity:
        """Return the identity used to discard stale async tag results."""

        return self._result_controller.tag_query_identity(
            query=query,
            prompt_text=prompt_text,
        )

    def retarget_from_query_state(
        self,
        query_state: PromptAutocompleteQueryState,
    ) -> bool:
        """Retarget active autocomplete surfaces to one compatible source edit."""

        if self._sessions.retarget(query_state):
            self._record_latest_query_state(query_state)
            self._present_active_surfaces()
            return True
        if self._has_active_session() and not query_state.has_selection:
            self.dismiss_autocomplete("incompatible_query")
        if query_state.has_selection:
            self.dismiss_autocomplete("selection_started")
        return False

    def _record_latest_query_state(
        self,
        query_state: PromptAutocompleteQueryState,
    ) -> None:
        """Record current-query identities for async autocomplete refresh owners."""

        self._latest_tag_query = None
        self._latest_tag_source_text = None
        self._latest_tag_query_identity = None
        self._latest_wildcard_query = None
        self._latest_wildcard_query_identity = None
        if query_state.tag_query is not None:
            self._latest_tag_query = query_state.tag_query
            self._latest_tag_source_text = query_state.source_text
            self._latest_tag_query_identity = self._tag_query_identity(
                query=query_state.tag_query,
                prompt_text=query_state.source_text,
            )
            return
        if query_state.wildcard_query is not None:
            self._latest_wildcard_query = query_state.wildcard_query
            self._latest_wildcard_query_identity = self._wildcard_query_identity(
                query_state.wildcard_query
            )

    def refresh_for_lora_query(
        self,
        query: PromptLoraAutocompleteQuery | None,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
        ghost_text_source_snapshot: (
            PromptAutocompleteGhostTextSourceSnapshot | None
        ) = None,
        refresh_intent: PromptAutocompleteRefreshIntent = "programmatic",
    ) -> None:
        """Refresh LoRA autocomplete from one application-owned query."""

        self._refresh_for_lora_query_measured(
            query,
            source_identity=source_identity,
            ghost_text_source_snapshot=ghost_text_source_snapshot,
            refresh_intent=refresh_intent,
        )

    def _refresh_for_lora_query_measured(
        self,
        query: PromptLoraAutocompleteQuery | None,
        *,
        source_identity: PromptCommandSourceIdentity | None,
        ghost_text_source_snapshot: PromptAutocompleteGhostTextSourceSnapshot | None,
        refresh_intent: PromptAutocompleteRefreshIntent,
    ) -> None:
        """Refresh LoRA autocomplete after refresh_for_lora_query starts timing."""

        self._latest_tag_query = None
        self._latest_tag_source_text = None
        self._latest_tag_query_identity = None
        self._latest_wildcard_query = None
        self._latest_wildcard_query_identity = None
        if refresh_intent in PASSIVE_AUTOCOMPLETE_REFRESH_INTENTS:
            self.dismiss_autocomplete("no_query")
            return
        if query is None:
            self.dismiss_autocomplete("no_query")
            return

        result = self._result_controller.result_for_lora_query(
            query,
            source_identity=source_identity,
            enabled=self._lora_autocomplete_enabled,
            thumbnail_cache_available=self._lora_thumbnail_cache_available,
        )
        if result.status != "ready" or not result.lora_candidates:
            self.dismiss_autocomplete("no_query")
            return

        self._sessions.replace_result(
            result,
            source_identity=source_identity,
            ghost_text_source_snapshot=ghost_text_source_snapshot,
        )
        self._present_active_surfaces()

    def accept_selection(self, *, add_comma: bool) -> None:
        """Accept the selected autocomplete suggestion through command wiring."""

        self._acceptance_controller.accept_session(
            self._sessions.session,
            source_identity=self._sessions.source_identity,
            add_comma=add_comma,
        )
        self.dismiss_autocomplete("accepted")

    def accept_scene_selection(self) -> None:
        """Accept the selected workflow scene title through command wiring."""

        self._acceptance_controller.accept_scene_session(
            self._sessions.session,
            source_identity=self._sessions.source_identity,
        )
        self.dismiss_autocomplete("accepted")

    def accept_wildcard_selection(self) -> None:
        """Accept the selected wildcard placeholder through command wiring."""

        self._acceptance_controller.accept_wildcard_session(
            self._sessions.session,
            source_identity=self._sessions.source_identity,
        )
        self.dismiss_autocomplete("accepted")

    def accept_lora_selection(self) -> None:
        """Accept the selected scheduler-safe LoRA token through command wiring."""

        self._acceptance_controller.accept_lora_session(
            self._sessions.session,
            source_identity=self._sessions.source_identity,
        )
        self.dismiss_autocomplete("accepted")

    def activate_suggestion(self, index: int) -> None:
        """Accept the clicked suggestion row and keep focus in the editor."""

        self._sessions.select_index(index)
        self.accept_selection(add_comma=False)
        self._editor.setFocus()

    def activate_lora_candidate(self, index: int) -> None:
        """Accept the clicked LoRA wall candidate and keep focus in the editor."""

        self._sessions.select_index(index)
        self.accept_lora_selection()
        self._editor.setFocus()

    def _handle_presenter_activation(
        self,
        intent: object,
    ) -> None:
        """Accept one activation emitted by the presenter-owned overlay."""

        index = getattr(intent, "index", -1)
        if not isinstance(index, int):
            return
        if self._sessions.session.mode == "lora":
            self.activate_lora_candidate(index)
            return
        self.activate_suggestion(index)

    def _handle_presenter_selection_changed(self, index: int) -> None:
        """Mirror presenter-owned overlay selection into the autocomplete session."""

        if index < 0:
            return
        self._sessions.select_index(index)
        self._publish_inline_completion_preview_if_panel_visible()

    def _handle_presenter_visibility_changed(self, visible: bool) -> None:
        """Clear ghost text as soon as autocomplete presentation is hidden."""

        log_prompt_editor_probe(
            "autocomplete.presenter_visibility_changed",
            visible=visible,
            autocomplete=autocomplete_probe_state(self),
        )
        if not visible:
            self._clear_inline_completion_preview()

    def dismiss_autocomplete(
        self,
        reason: PromptAutocompleteDismissReason,
    ) -> None:
        """Hide autocomplete visuals and reset state for one lifecycle reason."""

        log_prompt_editor_probe(
            "autocomplete.dismiss.begin",
            reason=reason,
            autocomplete=autocomplete_probe_state(self),
        )
        if reason == "focus_lost" and self._should_keep_autocomplete_on_focus_loss():
            log_prompt_editor_probe(
                "autocomplete.dismiss.end",
                reason=reason,
                dismissed=False,
                kept_for_focus=True,
                autocomplete=autocomplete_probe_state(self),
            )
            return

        if self._presenter is not None:
            self._presenter.hide()
        self._clear_inline_completion_preview()
        self._sessions.dismiss(reason)
        log_prompt_editor_probe(
            "autocomplete.dismiss.end",
            reason=reason,
            dismissed=True,
            autocomplete=autocomplete_probe_state(self),
        )

    def _should_keep_autocomplete_on_focus_loss(self) -> bool:
        """Return whether focus loss still belongs to autocomplete interaction."""

        focus_widget = QApplication.focusWidget()
        if focus_widget is cast(QWidget, self._editor):
            return True

        if self._presenter is not None and self._presenter.panel_under_mouse():
            return True

        return False

    def refresh_geometry(self) -> None:
        """Reposition the panel and inline preview after editor geometry changes."""

        if not self._has_active_session():
            return

        self._present_active_surfaces()

    def _present_active_surfaces(self) -> None:
        """Present autocomplete surfaces with ghost text gated by panel visibility."""

        log_prompt_editor_probe(
            "autocomplete.present_active_surfaces.begin",
            autocomplete=autocomplete_probe_state(self),
        )
        if self._present_panel():
            self._publish_inline_completion_preview()
            log_prompt_editor_probe(
                "autocomplete.present_active_surfaces.end",
                presented=True,
                autocomplete=autocomplete_probe_state(self),
            )
            return
        self._clear_inline_completion_preview()
        log_prompt_editor_probe(
            "autocomplete.present_active_surfaces.end",
            presented=False,
            autocomplete=autocomplete_probe_state(self),
        )

    def _present_panel(self) -> bool:
        """Present the active autocomplete session through the panel presenter."""

        if self._presenter is None:
            return False
        return self._presenter.present_session(self._sessions.session)

    def _publish_inline_completion_preview(self) -> None:
        """Delegate ghost text publication to the projection-facing publisher."""

        log_prompt_editor_probe(
            "autocomplete.publish_inline_completion_preview.begin",
            autocomplete=autocomplete_probe_state(self),
        )
        if self._ghost_text_publisher is None:
            log_prompt_editor_probe(
                "autocomplete.publish_inline_completion_preview.end",
                published=False,
                reason="no_publisher",
                autocomplete=autocomplete_probe_state(self),
            )
            return
        if not self._autocomplete_ghost_text_enabled:
            self._ghost_text_publisher.clear()
            log_prompt_editor_probe(
                "autocomplete.publish_inline_completion_preview.end",
                published=False,
                reason="disabled",
                autocomplete=autocomplete_probe_state(self),
            )
            return
        source_snapshot = self._sessions.ghost_text_source_snapshot
        if source_snapshot is None:
            self._ghost_text_publisher.clear()
            log_prompt_editor_probe(
                "autocomplete.publish_inline_completion_preview.end",
                published=False,
                reason="no_source_snapshot",
                autocomplete=autocomplete_probe_state(self),
            )
            return
        self._ghost_text_publisher.publish_for_session(
            self._sessions.session,
            source_snapshot=source_snapshot,
        )
        log_prompt_editor_probe(
            "autocomplete.publish_inline_completion_preview.end",
            published=True,
            autocomplete=autocomplete_probe_state(self),
        )

    def _publish_inline_completion_preview_if_panel_visible(self) -> None:
        """Publish ghost text only while autocomplete panel presentation is visible."""

        log_prompt_editor_probe(
            "autocomplete.publish_inline_completion_preview_if_panel_visible.begin",
            autocomplete=autocomplete_probe_state(self),
        )
        if self._presenter is None or not self._presenter.panel_visible():
            self._clear_inline_completion_preview()
            log_prompt_editor_probe(
                "autocomplete.publish_inline_completion_preview_if_panel_visible.end",
                published=False,
                autocomplete=autocomplete_probe_state(self),
            )
            return
        self._publish_inline_completion_preview()
        log_prompt_editor_probe(
            "autocomplete.publish_inline_completion_preview_if_panel_visible.end",
            published=True,
            autocomplete=autocomplete_probe_state(self),
        )

    def _clear_inline_completion_preview(self) -> None:
        """Delegate ghost text clearing to the projection-facing publisher."""

        log_prompt_editor_probe(
            "autocomplete.clear_inline_completion_preview.begin",
            autocomplete=autocomplete_probe_state(self),
        )
        if self._ghost_text_publisher is not None:
            self._ghost_text_publisher.clear()
        log_prompt_editor_probe(
            "autocomplete.clear_inline_completion_preview.end",
            autocomplete=autocomplete_probe_state(self),
        )

    def _handle_lora_key_press(self, key: int) -> bool:
        """Handle keyboard controls for the LoRA media wall mode."""

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return False

        action = picker_keyboard_action_for_key(
            key,
            tab_activates=True,
            escape_dismisses=True,
        )
        if action is PickerKeyboardAction.RIGHT:
            presenter_index = self._move_presenter_lora_selection("right")
            if presenter_index is not None:
                self._sessions.select_index(presenter_index)
            else:
                self._sessions.move_lora_selection_linear(1)
            self._publish_inline_completion_preview_if_panel_visible()
            return True
        if action is PickerKeyboardAction.LEFT:
            presenter_index = self._move_presenter_lora_selection("left")
            if presenter_index is not None:
                self._sessions.select_index(presenter_index)
            else:
                self._sessions.move_lora_selection_linear(-1)
            self._publish_inline_completion_preview_if_panel_visible()
            return True
        if action is PickerKeyboardAction.DOWN:
            presenter_index = self._move_presenter_lora_selection("down")
            if presenter_index is not None:
                self._sessions.select_index(presenter_index)
            else:
                self._sessions.move_lora_selection_linear(1)
            self._publish_inline_completion_preview_if_panel_visible()
            return True
        if action is PickerKeyboardAction.UP:
            presenter_index = self._move_presenter_lora_selection("up")
            if presenter_index is not None:
                self._sessions.select_index(presenter_index)
            else:
                self._sessions.move_lora_selection_linear(-1)
            self._publish_inline_completion_preview_if_panel_visible()
            return True
        if action is PickerKeyboardAction.ACTIVATE:
            self.accept_lora_selection()
            return True
        if action is PickerKeyboardAction.DISMISS:
            self.dismiss_autocomplete("escape")
            return True
        if key in {Qt.Key.Key_Home, Qt.Key.Key_End}:
            self.dismiss_autocomplete("caret_left_query")
            return False
        return False

    def _move_presenter_lora_selection(self, direction: str) -> int | None:
        """Move LoRA wall selection through the presenter when available."""

        if self._presenter is None:
            return None
        return self._presenter.move_lora_selection(direction)

    def _has_active_session(self) -> bool:
        """Return whether the current autocomplete session has selectable content."""

        return self._sessions.has_active_session()

    def has_active_session(self) -> bool:
        """Return whether source edits have an autocomplete session to retarget."""

        return self._has_active_session()


class PromptAutocompleteController(Protocol):
    """Describe the autocomplete controller used by interaction orchestration."""

    @property
    def panel(self) -> PromptAutocompletePanel | None:
        """Return the live autocomplete panel while legacy tests inspect it."""

    def refresh_active_scene_session(self) -> None:
        """Refresh visible scene suggestions after scene feature state changes."""

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle autocomplete-owned non-text key presses."""

    def refresh_for_query(
        self,
        query: PromptAutocompleteQuery | None,
        *,
        source_text: str,
        source_identity: PromptCommandSourceIdentity | None = None,
        feature_profile_identity: PromptFeatureSnapshotIdentity | None = None,
        query_identity: Hashable | None = None,
        ghost_text_source_snapshot: (
            PromptAutocompleteGhostTextSourceSnapshot | None
        ) = None,
        refresh_intent: PromptAutocompleteRefreshIntent = "programmatic",
    ) -> None:
        """Refresh tag autocomplete from one application-owned query."""

    def refresh_for_scene_query(
        self,
        query: PromptSceneAutocompleteQuery | None,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
        ghost_text_source_snapshot: (
            PromptAutocompleteGhostTextSourceSnapshot | None
        ) = None,
        refresh_intent: PromptAutocompleteRefreshIntent = "programmatic",
    ) -> None:
        """Refresh scene autocomplete from one application-owned query."""

    def refresh_for_wildcard_query(
        self,
        query: PromptWildcardAutocompleteQuery | None,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
        ghost_text_source_snapshot: (
            PromptAutocompleteGhostTextSourceSnapshot | None
        ) = None,
        refresh_intent: PromptAutocompleteRefreshIntent = "programmatic",
    ) -> None:
        """Refresh wildcard autocomplete from one application-owned query."""

    def refresh_for_lora_query(
        self,
        query: PromptLoraAutocompleteQuery | None,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
        ghost_text_source_snapshot: (
            PromptAutocompleteGhostTextSourceSnapshot | None
        ) = None,
        refresh_intent: PromptAutocompleteRefreshIntent = "programmatic",
    ) -> None:
        """Refresh LoRA autocomplete from one application-owned query."""

    def retarget_from_query_state(
        self,
        query_state: PromptAutocompleteQueryState,
    ) -> bool:
        """Retarget active autocomplete surfaces to one compatible source edit."""

    def has_active_session(self) -> bool:
        """Return whether source edits have an autocomplete session to retarget."""

    def accept_selection(self, *, add_comma: bool) -> None:
        """Accept the selected autocomplete suggestion."""

    def accept_scene_selection(self) -> None:
        """Accept the selected scene autocomplete suggestion."""

    def accept_wildcard_selection(self) -> None:
        """Accept the selected wildcard autocomplete suggestion."""

    def accept_lora_selection(self) -> None:
        """Accept the selected LoRA autocomplete suggestion."""

    def activate_suggestion(self, index: int) -> None:
        """Accept the activated suggestion row and restore focus."""

    def activate_lora_candidate(self, index: int) -> None:
        """Accept the activated LoRA candidate and restore focus."""

    def dismiss_autocomplete(
        self,
        reason: PromptAutocompleteDismissReason,
    ) -> None:
        """Dismiss autocomplete state for one explicit lifecycle reason."""

    def refresh_geometry(self) -> None:
        """Reposition autocomplete surfaces after geometry changes."""


class PromptAutocompleteQueryRefreshController:
    """Route feature-owned autocomplete query states into interaction refresh."""

    def __init__(
        self,
        *,
        autocomplete: PromptAutocompleteController,
        query_controller: PromptAutocompleteQueryController,
    ) -> None:
        """Store the interaction target and pure query owner."""

        self._autocomplete = autocomplete
        self._query_controller = query_controller
        self._latest_query_state: PromptAutocompleteQueryState | None = None

    @property
    def latest_query_state(self) -> PromptAutocompleteQueryState | None:
        """Return the latest application-owned query snapshot."""

        return self._latest_query_state

    def retarget_from_source_snapshot(
        self,
        snapshot: PromptAutocompleteSourceSnapshot,
    ) -> bool:
        """Retarget active autocomplete state from one prepared source snapshot."""

        if not self._autocomplete.has_active_session():
            return False
        query_state = self._query_controller.query_state_from_source_snapshot(snapshot)
        self._latest_query_state = query_state
        return self._autocomplete.retarget_from_query_state(query_state)

    def refresh_results_from_source_snapshot(
        self,
        snapshot: PromptAutocompleteSourceSnapshot,
    ) -> None:
        """Refresh autocomplete from one prepared source snapshot."""

        query_state = self._query_controller.query_state_from_source_snapshot(snapshot)
        self._latest_query_state = query_state
        source_identity = cast(
            PromptCommandSourceIdentity | None,
            query_state.source_identity,
        )
        ghost_text_source_snapshot = self._ghost_text_source_snapshot(query_state)
        if query_state.lora_query is not None:
            self._autocomplete.refresh_for_lora_query(
                query_state.lora_query,
                source_identity=source_identity,
                ghost_text_source_snapshot=ghost_text_source_snapshot,
                refresh_intent=query_state.refresh_intent,
            )
            return
        if query_state.wildcard_query is not None:
            self._autocomplete.refresh_for_wildcard_query(
                query_state.wildcard_query,
                source_identity=source_identity,
                ghost_text_source_snapshot=ghost_text_source_snapshot,
                refresh_intent=query_state.refresh_intent,
            )
            return
        if query_state.scene_query is not None:
            self._autocomplete.refresh_for_scene_query(
                query_state.scene_query,
                source_identity=source_identity,
                ghost_text_source_snapshot=ghost_text_source_snapshot,
                refresh_intent=query_state.refresh_intent,
            )
            return
        self._autocomplete.refresh_for_query(
            query_state.tag_query,
            source_text=query_state.source_text,
            source_identity=source_identity,
            feature_profile_identity=query_state.feature_profile_identity,
            query_identity=query_state.query_identity,
            ghost_text_source_snapshot=ghost_text_source_snapshot,
            refresh_intent=query_state.refresh_intent,
        )

    def dismiss_autocomplete(
        self,
        reason: PromptAutocompleteDismissReason,
    ) -> None:
        """Dismiss active autocomplete state for one lifecycle reason."""

        self._autocomplete.dismiss_autocomplete(reason)

    @staticmethod
    def _ghost_text_source_snapshot(
        query_state: PromptAutocompleteQueryState,
    ) -> PromptAutocompleteGhostTextSourceSnapshot:
        """Return the prepared source snapshot consumed by ghost text projection."""

        return PromptAutocompleteGhostTextSourceSnapshot(
            source_revision=query_state.source_revision,
            source_length=query_state.source_length,
            cursor_position=query_state.cursor_position,
            source_text=query_state.source_text,
        )


__all__ = [
    "PromptAutocompleteAcceptanceCommandFactory",
    "PromptAutocompleteCoordinator",
    "PromptAutocompleteController",
    "PromptAutocompleteCursor",
    "PromptAutocompleteEditor",
    "PromptAutocompleteQueryEditor",
    "PromptAutocompleteQueryRefreshController",
    "PromptAutocompleteSessionController",
    "PromptAutocompleteSessionState",
]
