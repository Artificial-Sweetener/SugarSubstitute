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

"""Contract tests for the autocomplete panel presenter boundary."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect, Signal
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor import (
    PromptLoraAutocompleteCandidate,
    PromptLoraCatalogItem,
    PromptLoraScheduleService,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompleteActivationIntent,
    PromptAutocompleteLoraWall,
    PromptAutocompletePanel,
    PromptAutocompletePanelPresenter,
    PromptAutocompletePanelRenderState,
    PromptAutocompleteRowRenderState,
)


def ensure_qapp() -> QApplication:
    """Return the active Qt application for presenter widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


class _PresenterEditor(QWidget):
    """Expose the QWidget geometry interface consumed by the presenter."""

    def __init__(self) -> None:
        """Create an editor host with a distinct viewport child."""

        super().__init__()
        self._viewport = QWidget(self)
        self._viewport.setGeometry(12, 18, 300, 160)
        self._cursor_rect = QRect(5, 7, 1, 18)

    def viewport(self) -> QWidget:
        """Return the viewport used as the caret coordinate source."""

        return self._viewport

    def cursorRect(self) -> QRect:
        """Return the prepared caret rectangle in viewport coordinates."""

        return self._cursor_rect


class _RecordingPanel(PromptAutocompletePanel):
    """Record presenter calls without relying on panel rendering internals."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize recording state."""

        super().__init__(parent)
        self.render_states: list[PromptAutocompletePanelRenderState] = []
        self.shown_anchors: list[QRect] = []
        self.hide_calls = 0
        self.selection_index = -1
        self.lora_moves: list[str] = []
        self.visible = False

    def set_render_state(self, state: PromptAutocompletePanelRenderState) -> None:
        """Record prepared state supplied by the presenter."""

        self.render_states.append(state)
        selected_row = next((row.index for row in state.rows if row.is_selected), -1)
        if state.lora_wall is not None:
            self.selection_index = state.lora_wall.selected_index
        else:
            self.selection_index = selected_row

    def show_overlay(self, anchor_rect: QRect) -> None:
        """Record one presenter show request."""

        self.shown_anchors.append(anchor_rect)
        self.visible = True

    def hide_overlay(self) -> None:
        """Record one presenter hide request."""

        self.hide_calls += 1
        self.visible = False

    def is_panel_visible(self) -> bool:
        """Return the recorded presenter-visible state."""

        return self.visible

    def set_current_index(self, index: int) -> None:
        """Record selection changes requested after rendering."""

        self.selection_index = index

    def current_index(self) -> int:
        """Return the recorded selection index."""

        return self.selection_index

    def move_current_lora_left(self) -> None:
        """Record left LoRA navigation."""

        self.lora_moves.append("left")
        self.selection_index -= 1

    def move_current_lora_right(self) -> None:
        """Record right LoRA navigation."""

        self.lora_moves.append("right")
        self.selection_index += 1

    def move_current_lora_up(self) -> None:
        """Record up LoRA navigation."""

        self.lora_moves.append("up")
        self.selection_index -= 4

    def move_current_lora_down(self) -> None:
        """Record down LoRA navigation."""

        self.lora_moves.append("down")
        self.selection_index += 4


class _FakeLoraWall(QWidget):
    """Provide the wall protocol needed by presenter injection."""

    loraActivated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize wall state."""

        super().__init__(parent)
        self.items: tuple[PromptLoraCatalogItem, ...] = ()
        self.index = -1

    def set_loras(self, items: tuple[PromptLoraCatalogItem, ...]) -> None:
        """Store prepared LoRA items."""

        self.items = items

    def set_current_index(self, index: int) -> None:
        """Store current wall index."""

        self.index = index

    def current_index(self) -> int:
        """Return current wall index."""

        return self.index

    def move_current_left(self) -> None:
        """Move current wall index left."""

        self.index -= 1

    def move_current_right(self) -> None:
        """Move current wall index right."""

        self.index += 1

    def move_current_up(self) -> None:
        """Move current wall index up."""

        self.index -= 4

    def move_current_down(self) -> None:
        """Move current wall index down."""

        self.index += 4

    def activate_current(self) -> bool:
        """Activate current wall item when one exists."""

        if 0 <= self.index < len(self.items):
            self.loraActivated.emit(self.items[self.index])
            return True
        return False


def _sample_lora() -> PromptLoraCatalogItem:
    """Return one stable LoRA catalog item for presenter tests."""

    return PromptLoraCatalogItem(
        display_name="CivitAI Midna",
        display_subtitle=None,
        prompt_name=r"illustrious\characters\raw_midna",
        backend_value=r"illustrious\characters\raw_midna.safetensors",
        relative_path=r"illustrious\characters\raw_midna.safetensors",
        folder=r"illustrious\characters",
        basename="raw_midna",
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=(),
        tags=("character",),
        model_page_url=None,
        collision_key="raw_midna",
        collision_count=1,
        has_collision=False,
        search_text="civitai midna raw_midna",
    )


def _lora_candidate(item: PromptLoraCatalogItem) -> PromptLoraAutocompleteCandidate:
    """Return one prepared LoRA autocomplete candidate."""

    return PromptLoraAutocompleteCandidate(
        item=item,
        score=100,
        display_text=item.display_name or item.basename,
        display_completion_suffix="itAI Midna",
        replacement_text=PromptLoraScheduleService().schedule_text(item),
        match_kind="display_prefix",
    )


def _presenter_with_panel(
    editor: _PresenterEditor,
    *,
    lora_wall_factory: Callable[[QWidget], PromptAutocompleteLoraWall] | None = None,
) -> tuple[PromptAutocompletePanelPresenter, list[_RecordingPanel]]:
    """Create a presenter and return the recording panels it creates."""

    panel_holder: list[_RecordingPanel] = []

    def create_panel(parent: QWidget) -> PromptAutocompletePanel:
        """Create and retain one recording panel."""

        panel = _RecordingPanel(parent)
        panel_holder.append(panel)
        return panel

    presenter = PromptAutocompletePanelPresenter(
        editor=editor,
        panel_factory=create_panel,
        lora_wall_factory=(
            None
            if lora_wall_factory is None
            else lambda parent, *, thumbnail_cache: lora_wall_factory(parent)
        ),
        lora_thumbnail_cache=object() if lora_wall_factory is not None else None,
    )
    return presenter, panel_holder


def test_presenter_maps_tag_session_to_prepared_rows() -> None:
    """Presenter should convert tag sessions into passive row render state."""

    ensure_qapp()
    editor = _PresenterEditor()
    presenter, panels = _presenter_with_panel(editor)
    suggestion = PromptAutocompleteSuggestion("1girl", 5_889_398)

    assert presenter.present_session(
        AutocompleteSession(
            mode="tag",
            suggestions=(suggestion,),
            selected_index=0,
        )
    )

    panel = panels[-1]
    state = panel.render_states[-1]
    assert state.visible is True
    assert state.rows[0].title == "1girl"
    assert state.rows[0].source_label == "5,889,398"
    assert state.rows[0].payload is suggestion
    assert panel.shown_anchors[-1] == QRect(17, 25, 1, 18)


def test_presenter_maps_lora_session_to_wall_items_and_payloads() -> None:
    """Presenter should prepare LoRA wall items without panel-side adaptation."""

    ensure_qapp()
    editor = _PresenterEditor()
    presenter, panels = _presenter_with_panel(
        editor,
        lora_wall_factory=lambda parent: cast(
            PromptAutocompleteLoraWall,
            _FakeLoraWall(parent),
        ),
    )
    item = _sample_lora()
    candidate = _lora_candidate(item)

    assert presenter.present_session(
        AutocompleteSession(
            mode="lora",
            lora_candidates=(candidate,),
            selected_index=0,
        )
    )

    panel = panels[-1]
    state = panel.render_states[-1]
    assert state.lora_wall is not None
    assert state.lora_wall.items == (item,)
    assert state.lora_wall.activation_payloads == (candidate,)
    assert state.lora_wall.selected_index == 0
    assert panel.selection_index == 0


def test_presenter_hides_empty_sessions_and_relays_intents() -> None:
    """Presenter should hide empty sessions and relay panel activation."""

    ensure_qapp()
    editor = _PresenterEditor()
    presenter, panels = _presenter_with_panel(editor)
    activated: list[PromptAutocompleteActivationIntent] = []
    presenter.set_activation_handler(activated.append)

    assert presenter.present_session(
        AutocompleteSession(
            mode="tag",
            suggestions=(PromptAutocompleteSuggestion("1girl", 1),),
            selected_index=0,
        )
    )
    panel = panels[-1]
    assert presenter.present_session(AutocompleteSession()) is False
    presenter.activate(PromptAutocompleteActivationIntent(index=2, payload="row"))

    assert panel.hide_calls == 1
    assert activated == [PromptAutocompleteActivationIntent(index=2, payload="row")]


def test_panel_reports_visibility_changes() -> None:
    """Panel hide events should be observable by the autocomplete coordinator."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(320, 180)
    host.show()
    panel = PromptAutocompletePanel(host)
    changes: list[bool] = []
    panel.set_visibility_changed_handler(changes.append)
    panel.set_render_state(
        PromptAutocompletePanelRenderState(
            rows=(
                PromptAutocompleteRowRenderState(
                    index=0,
                    title="1girl",
                    is_selected=True,
                ),
            ),
            visible=True,
        )
    )

    panel.show_overlay(QRect(20, 20, 1, 18))
    app.processEvents()
    panel.hide_panel()
    app.processEvents()

    assert changes == [True, False]


def test_presenter_delegates_lora_navigation_to_panel() -> None:
    """Presenter should keep LoRA keyboard navigation a presentation concern."""

    ensure_qapp()
    editor = _PresenterEditor()
    presenter, panels = _presenter_with_panel(editor)
    assert presenter.present_session(
        AutocompleteSession(
            mode="tag",
            suggestions=(PromptAutocompleteSuggestion("1girl", 1),),
            selected_index=0,
        )
    )
    panel = panels[-1]
    panel.selection_index = 4

    moved_index = presenter.move_lora_selection("down")

    assert panel.lora_moves == ["down"]
    assert moved_index == 8
