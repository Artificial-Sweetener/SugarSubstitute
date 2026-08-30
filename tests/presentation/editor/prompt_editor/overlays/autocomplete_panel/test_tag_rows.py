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

"""Verify direct tag-row presentation through the autocomplete panel."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMenu, QWidget
from qfluentwidgets.components.widgets.line_edit import (  # type: ignore[import-untyped]
    CompleterMenu,
    LineEdit,
)

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompletePanelRenderState,
    PromptAutocompleteRowRenderState,
)
from substitute.presentation.widgets.fluent_popup_frame import (
    AttachedFluentPopupFrame,
)
from tests.presentation.editor.prompt_editor.autocomplete.real_widget_support import (
    ensure_qapp,
    process_events,
    widgets as _widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_assertions import (
    panel_rows,
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_fixtures import (
    sample_suggestions,
)
from tests.presentation.editor.prompt_editor.overlays.autocomplete_panel.support import (
    autocomplete_panel,
    render_panel_rows,
    row_texts,
)


def test_prompt_autocomplete_panel_builds_tag_and_popularity_rows(
    widgets: list[QWidget],
) -> None:
    """Panel rows should render only tag text and formatted popularity text."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    host.show()
    widgets.append(host)

    panel = autocomplete_panel(host)
    render_panel_rows(panel, sample_suggestions())
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    rows = panel_rows(panel)
    assert len(rows) == 2

    first_tag, first_popularity = row_texts(rows[0])
    second_tag, second_popularity = row_texts(rows[1])

    assert first_tag == "1girl"
    assert first_popularity == "5,889,398"
    assert second_tag == "1girls"
    assert second_popularity == "3,424"
    assert (
        "General" not in first_tag + first_popularity + second_tag + second_popularity
    )
    assert (
        "danbooru" not in first_tag + first_popularity + second_tag + second_popularity
    )
    assert isinstance(panel, QMenu) is False


def test_prompt_autocomplete_panel_renders_prepared_state_and_activation_intent(
    widgets: list[QWidget],
) -> None:
    """Prepared panel state should render rows and relay activation intent."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    host.show()
    widgets.append(host)
    panel = autocomplete_panel(host)
    widgets.append(panel)
    activated: list[int] = []
    panel.set_activation_handler(lambda intent: activated.append(intent.index))

    panel.set_render_state(
        PromptAutocompletePanelRenderState(
            rows=(
                PromptAutocompleteRowRenderState(
                    index=0,
                    title="1girl",
                    source_label="5,889,398",
                    is_selected=True,
                ),
                PromptAutocompleteRowRenderState(
                    index=1,
                    title="1girls",
                    source_label="3,424",
                ),
            ),
            visible=True,
            anchor_rect=QRect(20, 20, 1, 18),
        )
    )
    panel.show_overlay(QRect(20, 20, 1, 18))
    process_events(app)

    rows = panel_rows(panel)
    assert panel.is_panel_visible() is True
    assert panel.current_index() == 0
    assert [row_texts(row) for row in rows] == [
        ("1girl", "5,889,398"),
        ("1girls", "3,424"),
    ]

    QTest.mouseClick(rows[1], Qt.MouseButton.LeftButton, pos=QPoint(4, 4))
    process_events(app)

    assert activated == [1]


def test_prompt_autocomplete_panel_renders_lora_source_label(
    widgets: list[QWidget],
) -> None:
    """LoRA trigger rows should render their source label instead of popularity."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    host.show()
    widgets.append(host)

    panel = autocomplete_panel(host)
    render_panel_rows(
        panel,
        (
            PromptAutocompleteSuggestion(
                "midna helmet",
                popularity=None,
                source_label="Friendly Midna",
                source_kind="lora_trigger",
            ),
        ),
    )
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    rows = panel_rows(panel)
    assert len(rows) == 1
    tag_text, source_text = row_texts(rows[0])
    assert tag_text.startswith("midna hel")
    assert source_text.startswith("Friendly Mid")


def test_prompt_autocomplete_panel_uses_editor_attached_fluent_frame(
    widgets: list[QWidget],
) -> None:
    """Autocomplete should share QFluent frame chrome without becoming a popup."""

    ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    panel = autocomplete_panel(host)
    widgets.extend([host, panel])

    assert isinstance(panel, AttachedFluentPopupFrame)
    assert panel.parentWidget() is host
    assert not bool(panel.windowFlags() & Qt.WindowType.Popup)


def test_prompt_autocomplete_panel_updates_selected_row(
    widgets: list[QWidget],
) -> None:
    """Panel selection should track the requested row index."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    host.show()
    widgets.append(host)

    panel = autocomplete_panel(host)
    render_panel_rows(panel, sample_suggestions())
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    panel.set_current_index(0)
    assert panel.current_index() == 0

    panel.set_current_index(1)
    process_events(app)

    rows = panel_rows(panel)
    assert panel.current_index() == 1
    assert bool(rows[0].property("selected")) is False
    assert bool(rows[1].property("selected")) is True


def test_prompt_autocomplete_panel_detaches_stale_rows_during_rapid_refresh(
    widgets: list[QWidget],
) -> None:
    """Rapid tag refreshes should not leave old visible rows stacked in the panel."""

    ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    host.show()
    widgets.append(host)

    panel = autocomplete_panel(host)
    render_panel_rows(panel, sample_suggestions())
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    render_panel_rows(
        panel,
        (
            PromptAutocompleteSuggestion("solo", 10),
            PromptAutocompleteSuggestion("solo focus", 8),
        ),
    )
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)

    rows = panel_rows(panel)

    assert [row.rendered_tag_text() for row in rows] == ["solo", "solo focus"]
    assert all(row.isVisible() for row in rows)
    assert len({row.geometry().top() for row in rows}) == len(rows)


def test_prompt_autocomplete_panel_rows_own_text_painting(
    widgets: list[QWidget],
) -> None:
    """Autocomplete rows should not compose child labels over row fills."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    host.show()
    widgets.append(host)

    panel = autocomplete_panel(host)
    render_panel_rows(panel, sample_suggestions())
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    rows = panel_rows(panel)
    lora_wall = panel.lora_wall()

    assert rows
    assert all(row.findChildren(QWidget) == [] for row in rows)
    assert lora_wall is not None
    assert lora_wall.isHidden()


def test_prompt_autocomplete_panel_matches_qfluent_completer_metrics(
    widgets: list[QWidget],
) -> None:
    """Autocomplete panel metrics should match the live QFluent completer shell."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    host.show()
    widgets.append(host)

    panel = autocomplete_panel(host)
    render_panel_rows(panel, sample_suggestions())
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)

    reference_line_edit = LineEdit(host)
    reference_menu = CompleterMenu(reference_line_edit)
    reference_menu.setItems(["1girl", "1girls"])
    widgets.extend([reference_line_edit, reference_menu])
    process_events(app)

    rows = panel_rows(panel)
    layout = panel.content_layout()
    assert layout is not None
    margins = layout.contentsMargins()
    reference_margins = reference_menu.view.viewportMargins()

    assert rows[0].height() == reference_menu.itemHeight
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        reference_margins.left(),
        reference_margins.top(),
        reference_margins.right(),
        reference_margins.bottom(),
    )


def test_prompt_autocomplete_panel_click_emits_row_index(
    widgets: list[QWidget],
) -> None:
    """Clicking a rendered row should emit its suggestion index."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    host.show()
    widgets.append(host)

    panel = autocomplete_panel(host)
    activated: list[int] = []
    panel.suggestionActivated.connect(activated.append)
    render_panel_rows(panel, sample_suggestions())
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    row = panel_rows(panel)[1]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert activated == [1]
