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

"""Verify autocomplete ghost-preview projection and feature policy."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.domain.prompt.features.models import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptFeatureDecision,
)
from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompletePanel,
)
from tests.presentation.editor.prompt_editor.autocomplete.real_widget_support import (
    ensure_qapp,
    process_events,
    widgets as _widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_fixtures import (
    sample_suggestions,
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_support import (
    StaticPromptAutocompleteGateway,
    active_projection_line_texts,
    create_prompt_editor,
    editor_autocomplete_preview_text,
)
from tests.support.prompt_editor.projection_engine_support import surface_for


def _profile_without_ghost_text() -> PromptEditorFeatureProfile:
    """Return a prompt feature profile that disables only autocomplete ghost text."""

    return PromptEditorFeatureProfile(
        decisions=tuple(
            PromptFeatureDecision(
                feature=feature,
                enabled=feature is not PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT,
            )
            for feature in PromptEditorFeature
        )
    )


def test_prompt_editor_autocomplete_preview_reflows_downstream_text(
    widgets: list[QWidget],
) -> None:
    """Layout-backed ghost text should wrap following text as real text would."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(230, 220)
    box = create_prompt_editor(
        parent=host,
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({}),
    )
    box.setGeometry(10, 10, 200, 140)
    host.show()
    host.activateWindow()
    box.show()
    box.setFocus()
    box.setPlainText("alpha omega")
    widgets.extend([host, box])
    process_events(app)

    cursor = box.textCursor()
    cursor.setPosition(len("alpha "))
    box.setTextCursor(cursor)
    process_events(app)

    assert active_projection_line_texts(box) == ("alpha omega",)

    preview_suffix = "bright detailed elaborate cinematic "
    surface = surface_for(box)
    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=len("alpha "),
            suffix_text=preview_suffix,
        )
    )
    process_events(app)

    assert box.toPlainText() == "alpha omega"
    line_texts = active_projection_line_texts(box)
    assert len(line_texts) > 1
    assert "".join(line_texts) == f"alpha {preview_suffix}omega"
    assert line_texts[-1].endswith("omega")


def test_prompt_editor_autocomplete_preview_does_not_mutate_source_or_undo(
    widgets: list[QWidget],
) -> None:
    """Preview layout changes should not emit textChanged or alter undo state."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    box = create_prompt_editor(
        parent=host,
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({}),
    )
    box.setGeometry(10, 10, 260, 140)
    host.show()
    box.show()
    box.setFocus()
    box.setPlainText("alpha omega")
    widgets.extend([host, box])
    process_events(app)

    cursor = box.textCursor()
    cursor.setPosition(len("alpha "))
    box.setTextCursor(cursor)
    process_events(app)

    changed_count = 0

    def record_text_changed() -> None:
        """Record an unexpected source text change."""

        nonlocal changed_count
        changed_count += 1

    box.textChanged.connect(record_text_changed)
    surface = surface_for(box)
    can_undo_before = surface.can_undo()

    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=len("alpha "),
            suffix_text="bright ",
        )
    )
    process_events(app)

    assert box.toPlainText() == "alpha omega"
    assert changed_count == 0
    assert surface.can_undo() is can_undo_before


def test_prompt_editor_autocomplete_preview_clears_on_selection(
    widgets: list[QWidget],
) -> None:
    """Selecting real text should remove active non-source-backed preview layout."""

    app = ensure_qapp()
    box = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({}),
    )
    box.show()
    box.setFocus()
    box.setPlainText("alpha omega")
    widgets.append(box)
    process_events(app)

    cursor = box.textCursor()
    cursor.setPosition(len("alpha "))
    box.setTextCursor(cursor)
    surface = surface_for(box)
    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=len("alpha "),
            suffix_text="bright ",
        )
    )
    process_events(app)

    cursor = box.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    assert editor_autocomplete_preview_text(box) == ""
    assert surface.active_projection_document().projection_text == "alpha omega"


def test_prompt_editor_autocomplete_preview_clears_on_source_edit(
    widgets: list[QWidget],
) -> None:
    """Typing real source text should remove stale active autocomplete preview."""

    app = ensure_qapp()
    box = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({}),
    )
    box.show()
    box.setFocus()
    box.setPlainText("alpha omega")
    widgets.append(box)
    process_events(app)

    cursor = box.textCursor()
    cursor.setPosition(len("alpha "))
    box.setTextCursor(cursor)
    process_events(app)

    surface = surface_for(box)
    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=len("alpha "),
            suffix_text="bright ",
        )
    )
    process_events(app)

    assert editor_autocomplete_preview_text(box) == "bright "
    assert surface.active_projection_document().projection_text == "alpha bright omega"

    QTest.keyClicks(box, "x")
    process_events(app)

    assert box.toPlainText() == "alpha xomega"
    assert surface.active_projection_document().projection_text == "alpha xomega"


def test_prompt_editor_projection_owned_preview_tracks_suffix_and_clear_state(
    widgets: list[QWidget],
) -> None:
    """Autocomplete preview should live in the projection session and clear cleanly."""

    app = ensure_qapp()
    gateway = StaticPromptAutocompleteGateway({"1g": sample_suggestions()})

    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "1g")
    process_events(app)

    assert editor_autocomplete_preview_text(box) == "irl"

    QTest.keyClick(box, Qt.Key.Key_Escape)
    process_events(app)

    assert editor_autocomplete_preview_text(box) == ""


def test_prompt_editor_disabled_ghost_text_keeps_autocomplete_panel(
    widgets: list[QWidget],
) -> None:
    """Ghost-text settings should not disable autocomplete suggestions."""

    app = ensure_qapp()
    gateway = StaticPromptAutocompleteGateway({"1g": sample_suggestions()})

    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=gateway,
        prompt_feature_profile=_profile_without_ghost_text(),
    )
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "1g")
    process_events(app)

    panel = getattr(box, "_autocomplete_panel")
    assert isinstance(panel, PromptAutocompletePanel)
    assert panel.is_panel_visible() is True
    assert box.toPlainText() == "1g"
    assert editor_autocomplete_preview_text(box) == ""
