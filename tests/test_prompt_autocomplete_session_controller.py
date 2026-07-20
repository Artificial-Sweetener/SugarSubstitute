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

"""Cover autocomplete session transition ownership."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtCore import Qt

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor import (
    PromptAutocompleteQuery,
    PromptLoraAutocompleteCandidate,
    PromptLoraAutocompleteQuery,
    PromptLoraCatalogItem,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteQueryState,
    PromptAutocompleteResultSnapshot,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_session import (
    PromptAutocompleteSessionController,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession
from substitute.presentation.editor.prompt_editor.projection.autocomplete_ghost_text import (
    PromptAutocompleteGhostTextPublisher,
    PromptAutocompleteGhostTextSourceSnapshot,
)
from tests.prompt_autocomplete_test_helpers import build_test_autocomplete_coordinator
from tests.prompt_editor_controller_test_helpers import (
    EmptyAutocompleteGateway,
    TextAutocompleteEditorDouble,
    autocomplete_session_controller_with_session,
    import_autocomplete_module,
    key_event,
)


class _VisibilityRecordingPresenter:
    """Record autocomplete presentation while exposing explicit visibility changes."""

    def __init__(self, *, visible: bool) -> None:
        """Initialize the presenter with a deterministic visible result."""

        self.visible = visible
        self.visibility_handler: Callable[[bool], None] | None = None

    @property
    def panel(self) -> None:
        """Return no concrete panel for coordinator tests."""

        return None

    def present_session(self, session: AutocompleteSession) -> bool:
        """Record one present request and return the configured visibility."""

        _ = session
        return self.visible

    def set_activation_handler(self, handler: Callable[[Any], None] | None) -> None:
        """Accept activation wiring without using it."""

        _ = handler

    def set_selection_changed_handler(
        self,
        handler: Callable[[int], None] | None,
    ) -> None:
        """Accept selection wiring without using it."""

        _ = handler

    def set_visibility_changed_handler(
        self,
        handler: Callable[[bool], None] | None,
    ) -> None:
        """Store the visibility callback supplied by the coordinator."""

        self.visibility_handler = handler

    def panel_under_mouse(self) -> bool:
        """Return whether the panel is visible for focus-retention checks."""

        return self.visible

    def activate(self, intent: Any) -> None:
        """Accept activation forwarding without using it."""

        _ = intent

    def current_index(self) -> int:
        """Return no selected panel index for coordinator tests."""

        return -1

    def panel_visible(self) -> bool:
        """Return the configured panel visibility state."""

        return self.visible

    def hide(self) -> None:
        """Hide the panel and publish the visibility transition."""

        self.set_visible(False)

    def move_lora_selection(self, direction: str) -> int | None:
        """Return no panel-owned LoRA movement for these tests."""

        _ = direction
        return None

    def set_visible(self, visible: bool) -> None:
        """Apply a visible-state transition through the stored callback."""

        self.visible = visible
        handler = self.visibility_handler
        if callable(handler):
            handler(visible)


def test_session_controller_preserves_selected_tag_across_result_replacement() -> None:
    """Tag result replacement should preserve the selected suggestion identity."""

    controller = PromptAutocompleteSessionController()
    source_identity = PromptCommandSourceIdentity(source_revision=4, source_length=3)
    ghost_snapshot = PromptAutocompleteGhostTextSourceSnapshot(
        source_revision=4,
        source_length=3,
        cursor_position=3,
        source_text="1gi",
    )
    controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(PromptAutocompleteSuggestion("1girls", 3_424),),
            word_start=0,
            word_end=3,
            active_tag_end=3,
            prefix="1gi",
        ),
        source_identity=source_identity,
        ghost_text_source_snapshot=ghost_snapshot,
    )

    controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(
                PromptAutocompleteSuggestion("1girl", 5_889_398),
                PromptAutocompleteSuggestion("1girls", 3_424),
            ),
            word_start=0,
            word_end=3,
            active_tag_end=3,
            prefix="1gi",
        ),
        source_identity=source_identity,
        ghost_text_source_snapshot=ghost_snapshot,
    )

    assert controller.session.selected_index == 1
    assert controller.source_identity is source_identity
    assert controller.ghost_text_source_snapshot is ghost_snapshot


def test_session_controller_moves_selection_and_clears_state() -> None:
    """Selection movement should wrap before clear resets transient state."""

    controller = PromptAutocompleteSessionController()
    controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(
                PromptAutocompleteSuggestion("alpha"),
                PromptAutocompleteSuggestion("beta"),
            ),
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )

    assert controller.move_suggestion_selection(1) is True
    assert controller.session.selected_index == 1
    assert controller.move_suggestion_selection(1) is True
    assert controller.session.selected_index == 0
    assert controller.move_suggestion_selection(-1) is True
    assert controller.session.selected_index == 1

    controller.dismiss("escape")

    assert controller.session.mode == "none"
    assert controller.source_identity is None
    assert controller.ghost_text_source_snapshot is None


def test_session_controller_preserves_selected_lora_candidate() -> None:
    """LoRA result replacement should preserve the selected prompt name."""

    controller = PromptAutocompleteSessionController()
    midna = _lora_candidate("midna")
    other = _lora_candidate("other")
    query = PromptLoraAutocompleteQuery(
        query_text="mid",
        token_start=0,
        token_end=9,
        name_start=6,
        name_end=9,
        replacement_start=0,
        replacement_end=9,
        typed_weight_text=None,
        has_closing_bracket=False,
    )
    controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="lora",
            status="ready",
            lora_candidates=(midna,),
            lora_query=query,
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )

    controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="lora",
            status="ready",
            lora_candidates=(other, midna),
            lora_query=query,
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )

    assert controller.session.selected_index == 1
    assert controller.session.lora_candidates[1].item.prompt_name == "midna"


def test_session_controller_activation_index_can_force_missing_selection() -> None:
    """Presenter activation should mirror the index before acceptance validates it."""

    controller = PromptAutocompleteSessionController()
    controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(PromptAutocompleteSuggestion("alpha"),),
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )

    controller.select_index(-1)

    assert controller.session.selected_index == -1
    assert not controller.has_active_session()


def test_session_controller_retargets_compatible_tag_without_replacing_rows() -> None:
    """Compatible typing should keep rows selected while updating query geometry."""

    controller = PromptAutocompleteSessionController()
    suggestions = (
        PromptAutocompleteSuggestion("1girl", 5_889_398),
        PromptAutocompleteSuggestion("1girls", 3_424),
    )
    controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=suggestions,
            word_start=0,
            word_end=2,
            active_tag_end=2,
            prefix="1g",
        ),
        source_identity=PromptCommandSourceIdentity(source_revision=1, source_length=2),
        ghost_text_source_snapshot=None,
    )
    controller.select_index(1)

    retargeted = controller.retarget(
        PromptAutocompleteQueryState(
            source_revision=2,
            source_length=3,
            source_text="1gi",
            cursor_position=3,
            has_selection=False,
            source_identity=PromptCommandSourceIdentity(
                source_revision=2,
                source_length=3,
            ),
            tag_query=PromptAutocompleteQuery(
                prefix="1gi",
                word_start=0,
                word_end=3,
                active_tag_end=3,
            ),
        )
    )

    assert retargeted is True
    assert controller.state.lifecycle == "refreshing"
    assert controller.session.suggestions is suggestions
    assert controller.session.selected_index == 1
    assert controller.session.prefix == "1gi"
    assert controller.session.word_end == 3
    assert controller.ghost_text_source_snapshot is not None
    assert controller.ghost_text_source_snapshot.cursor_position == 3


def test_refresh_geometry_preserves_active_session_and_updates_surfaces() -> None:
    """Geometry refresh repositions live surfaces without clearing the session."""

    mod = import_autocomplete_module()
    session = AutocompleteSession(
        suggestions=(PromptAutocompleteSuggestion("1girl", 5_889_398),),
        selected_index=0,
        word_start=0,
        word_end=2,
        prefix="1g",
    )
    session_controller = autocomplete_session_controller_with_session(mod, session)
    refresh_calls: list[str] = []
    coordinator = build_test_autocomplete_coordinator(
        SimpleNamespace(
            set_autocomplete_preview_state=lambda _preview_state: None,
            viewport=lambda: SimpleNamespace(rect=lambda: "viewport-rect"),
        ),
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_session_controller=session_controller,
    )

    def record_visible_panel() -> bool:
        """Record panel presentation and report successful visibility."""

        refresh_calls.append("panel")
        return True

    setattr(coordinator, "_present_panel", record_visible_panel)
    setattr(
        coordinator,
        "_publish_inline_completion_preview",
        lambda: refresh_calls.append("preview"),
    )

    coordinator.refresh_geometry()

    assert refresh_calls == ["panel", "preview"]
    assert session_controller.session is session


def test_hidden_panel_prevents_autocomplete_ghost_publication() -> None:
    """Ghost text should not publish when panel presentation is unavailable."""

    mod = import_autocomplete_module()
    editor = TextAutocompleteEditorDouble("1g")
    presenter = _VisibilityRecordingPresenter(visible=False)
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            mode="tag",
            suggestions=(PromptAutocompleteSuggestion("1girl"),),
            selected_index=0,
            word_start=0,
            word_end=2,
            active_tag_end=2,
            prefix="1g",
        ),
    )
    session_controller._state.ghost_text_source_snapshot = (
        PromptAutocompleteGhostTextSourceSnapshot(
            source_revision=0,
            source_length=2,
            cursor_position=2,
            source_text="1g",
        )
    )
    coordinator = build_test_autocomplete_coordinator(
        editor,
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_presenter=presenter,
        autocomplete_ghost_text_publisher=PromptAutocompleteGhostTextPublisher(
            preview_sink=editor,
        ),
        autocomplete_session_controller=session_controller,
    )

    coordinator.refresh_geometry()

    assert editor.autocomplete_preview_state is None


def test_panel_hide_clears_existing_autocomplete_ghost_text() -> None:
    """A hidden autocomplete panel should immediately clear its ghost preview."""

    mod = import_autocomplete_module()
    editor = TextAutocompleteEditorDouble("1g")
    presenter = _VisibilityRecordingPresenter(visible=True)
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            mode="tag",
            suggestions=(PromptAutocompleteSuggestion("1girl"),),
            selected_index=0,
            word_start=0,
            word_end=2,
            active_tag_end=2,
            prefix="1g",
        ),
    )
    session_controller._state.ghost_text_source_snapshot = (
        PromptAutocompleteGhostTextSourceSnapshot(
            source_revision=0,
            source_length=2,
            cursor_position=2,
            source_text="1g",
        )
    )
    coordinator = build_test_autocomplete_coordinator(
        editor,
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_presenter=presenter,
        autocomplete_ghost_text_publisher=PromptAutocompleteGhostTextPublisher(
            preview_sink=editor,
        ),
        autocomplete_session_controller=session_controller,
    )
    coordinator.refresh_geometry()
    assert editor.autocomplete_preview_state is not None

    presenter.set_visible(False)

    assert editor.autocomplete_preview_state is None


def test_autocomplete_handle_key_press_leaves_enter_to_editor_text_input() -> None:
    """Leave Enter key handling to the editor text input for tag autocomplete."""

    mod = import_autocomplete_module()
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            mode="tag",
            suggestions=(PromptAutocompleteSuggestion("1girl", 100),),
            selected_index=0,
            word_start=0,
            word_end=2,
            active_tag_end=2,
            prefix="1g",
        ),
    )
    coordinator = build_test_autocomplete_coordinator(
        SimpleNamespace(isAncestorOf=lambda _widget: False),
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_session_controller=session_controller,
    )

    assert coordinator.handle_key_press(key_event(Qt.Key.Key_Return)) is False
    assert coordinator.handle_key_press(key_event(Qt.Key.Key_Enter)) is False


def test_lora_autocomplete_handle_key_press_leaves_enter_to_editor_text_input() -> None:
    """Leave Enter key handling to the editor text input for LoRA autocomplete."""

    mod = import_autocomplete_module()
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            mode="lora",
            selected_index=0,
            lora_candidates=(_lora_candidate("midna"),),
        ),
    )
    coordinator = build_test_autocomplete_coordinator(
        SimpleNamespace(),
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_session_controller=session_controller,
    )

    assert coordinator.handle_key_press(key_event(Qt.Key.Key_Return)) is False
    assert coordinator.handle_key_press(key_event(Qt.Key.Key_Enter)) is False


def test_focus_lost_dismissal_keeps_session_when_panel_is_under_pointer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep autocomplete alive while the pointer stays over the panel."""

    mod = import_autocomplete_module()
    monkeypatch.setattr(
        mod,
        "QApplication",
        SimpleNamespace(focusWidget=lambda: object()),
    )
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            suggestions=(PromptAutocompleteSuggestion("1girl"),),
            selected_index=0,
        ),
    )
    coordinator = build_test_autocomplete_coordinator(
        SimpleNamespace(isAncestorOf=lambda _widget: False),
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_session_controller=session_controller,
    )
    coordinator._presenter = SimpleNamespace(
        panel_under_mouse=lambda: True,
    )

    coordinator.dismiss_autocomplete("focus_lost")

    assert session_controller.state.lifecycle == "active"


def test_focus_lost_dismissal_keeps_session_for_editor_descendant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep autocomplete when the projection surface owns editor focus."""

    mod = import_autocomplete_module()
    projection_surface = object()
    editor = SimpleNamespace(
        isAncestorOf=lambda widget: widget is projection_surface,
    )
    monkeypatch.setattr(
        mod,
        "QApplication",
        SimpleNamespace(focusWidget=lambda: projection_surface),
    )
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            suggestions=(PromptAutocompleteSuggestion("1girl"),),
            selected_index=0,
        ),
    )
    coordinator = build_test_autocomplete_coordinator(
        editor,
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_session_controller=session_controller,
    )

    coordinator.dismiss_autocomplete("focus_lost")

    assert session_controller.state.lifecycle == "active"


def test_focus_lost_dismissal_clears_when_focus_leaves_editor_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dismiss autocomplete when focus and pointer both leave the editor."""

    mod = import_autocomplete_module()
    monkeypatch.setattr(
        mod,
        "QApplication",
        SimpleNamespace(focusWidget=lambda: object()),
    )
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            suggestions=(PromptAutocompleteSuggestion("1girl"),),
            selected_index=0,
        ),
    )
    coordinator = build_test_autocomplete_coordinator(
        SimpleNamespace(isAncestorOf=lambda _widget: False),
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        autocomplete_session_controller=session_controller,
    )
    coordinator._presenter = SimpleNamespace(
        hide=lambda: None,
        panel_under_mouse=lambda: False,
    )

    coordinator.dismiss_autocomplete("focus_lost")

    assert session_controller.state.lifecycle == "idle"


def _lora_candidate(prompt_name: str) -> PromptLoraAutocompleteCandidate:
    """Return one deterministic LoRA autocomplete candidate."""

    item = PromptLoraCatalogItem(
        display_name=prompt_name.title(),
        display_subtitle=None,
        prompt_name=prompt_name,
        backend_value=f"{prompt_name}.safetensors",
        relative_path=f"{prompt_name}.safetensors",
        folder="",
        basename=prompt_name,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=prompt_name.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=prompt_name.casefold(),
    )
    return PromptLoraAutocompleteCandidate(
        item=item,
        score=10,
        display_text=prompt_name.title(),
        display_completion_suffix="",
        replacement_text=f"<lora:{prompt_name}:1>",
        match_kind="display",
    )
