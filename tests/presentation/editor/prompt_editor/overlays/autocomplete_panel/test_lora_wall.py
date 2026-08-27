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

"""Verify direct LoRA-wall presentation through the autocomplete panel."""

from __future__ import annotations

from typing import cast

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QLineEdit, QMenu, QWidget

from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.overlays import PromptLoraWallView
from tests.presentation.editor.prompt_editor.autocomplete.real_widget_support import (
    ensure_qapp,
    process_events,
    widgets as _widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_assertions import (
    panel_rows,
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_fixtures import (
    sample_lora,
)
from tests.presentation.editor.prompt_editor.overlays.autocomplete_panel.support import (
    autocomplete_panel,
    lora_candidate,
    render_panel_lora_candidates,
)


def test_prompt_autocomplete_panel_hosts_lora_wall_without_tag_rows(
    widgets: list[QWidget],
) -> None:
    """LoRA mode should reuse the panel shell with wall content instead of rows."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(720, 520)
    host.show()
    widgets.append(host)
    panel = autocomplete_panel(host)
    item = sample_lora()

    render_panel_lora_candidates(panel, (lora_candidate(item),))
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    wall = panel.lora_wall()
    assert wall is not None
    assert isinstance(wall, PromptLoraWallView)
    assert panel.is_panel_visible() is True
    assert panel_rows(panel) == []
    assert wall.items()[0].title == "CivitAI Midna"
    assert panel.findChildren(QLineEdit) == []
    assert isinstance(panel, QMenu) is False


def test_prompt_autocomplete_panel_uses_taller_lora_wall_geometry(
    widgets: list[QWidget],
) -> None:
    """LoRA autocomplete should share the taller picker popup height."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(720, 760)
    host.show()
    widgets.append(host)
    panel = autocomplete_panel(host)

    render_panel_lora_candidates(panel, (lora_candidate(sample_lora()),))
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    assert panel.width() == 560
    assert panel.height() == 630


def test_prompt_autocomplete_panel_lora_wall_click_emits_candidate_index(
    widgets: list[QWidget],
) -> None:
    """Wall activation should flow through the autocomplete panel as an index."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(720, 520)
    host.show()
    widgets.append(host)
    panel = autocomplete_panel(host)
    item = sample_lora()
    activated: list[int] = []
    panel.loraActivated.connect(activated.append)

    render_panel_lora_candidates(panel, (lora_candidate(item),))
    widgets.append(panel)
    process_events(app)
    wall = panel.lora_wall()
    assert wall is not None
    wall = cast(PromptLoraWallView, wall)
    assert wall.activate_current() is True

    assert activated == [0]


def test_prompt_autocomplete_panel_lora_wall_uses_directional_navigation(
    widgets: list[QWidget],
) -> None:
    """LoRA wall navigation should move up and down by visual rows."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(720, 520)
    host.show()
    widgets.append(host)
    panel = autocomplete_panel(host)
    candidates = tuple(
        lora_candidate(
            sample_lora(
                display_name=f"LoRA {index}",
                basename=f"lora_{index}",
                prompt_name=rf"folder\lora_{index}",
            )
        )
        for index in range(20)
    )
    render_panel_lora_candidates(panel, candidates)
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    panel.set_current_index(1)
    panel.move_current_lora_down()
    process_events(app)
    assert panel.current_index() == 5

    down_index = panel.current_index()
    panel.move_current_lora_up()
    process_events(app)
    assert panel.current_index() == 1

    panel.set_current_index(down_index)
    panel.move_current_lora_right()
    process_events(app)
    assert panel.current_index() == down_index + 1


def test_prompt_autocomplete_panel_defers_lora_selection_until_shown(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LoRA selection should use final popup geometry instead of hidden layout."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(720, 760)
    host.show()
    widgets.append(host)
    panel = autocomplete_panel(host)
    candidates = tuple(
        lora_candidate(
            sample_lora(
                display_name=f"LoRA {index}",
                basename=f"lora_{index}",
                prompt_name=rf"folder\lora_{index}",
            )
        )
        for index in range(20)
    )
    selection_viewport_heights: list[int] = []
    original_set_current_index = PromptLoraWallView.set_current_index

    def record_set_current_index(self: PromptLoraWallView, index: int) -> None:
        """Record the viewport height used when selecting a LoRA tile."""

        selection_viewport_heights.append(self.viewport().height())
        original_set_current_index(self, index)

    monkeypatch.setattr(
        PromptLoraWallView,
        "set_current_index",
        record_set_current_index,
    )

    render_panel_lora_candidates(panel, candidates)

    assert selection_viewport_heights == []

    panel.show_for_editor(host, QRect(24, 700, 1, 18))
    widgets.append(panel)
    process_events(app)
    panel.set_current_index(0)

    assert selection_viewport_heights[-1] >= 100


def test_prompt_lora_wall_skips_unchanged_lora_items(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated LoRA candidates should not rebuild the media wall contents."""

    item = sample_lora()
    wall = PromptLoraWallView(
        thumbnail_cache=PromptLoraThumbnailCache(),
    )
    widgets.append(wall)
    wall.set_loras((item,))
    rebuilds: list[object] = []

    def record_rebuild(items: object) -> None:
        """Record unexpected media wall rebuild requests."""

        rebuilds.append(items)

    monkeypatch.setattr(wall, "set_picker_items", record_rebuild)

    wall.set_loras((item,))

    assert rebuilds == []


def test_prompt_autocomplete_panel_reuses_lora_wall_for_same_items(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Panel refreshes should not rebuild LoRA wall layout when items are unchanged."""

    host = QWidget()
    widgets.append(host)
    panel = autocomplete_panel(host)
    widgets.append(panel)
    item = sample_lora()
    first_candidate = lora_candidate(item, suffix="itAI Midna")
    next_candidate = lora_candidate(item, suffix="AI Midna")
    render_panel_lora_candidates(panel, (first_candidate,))
    wall = panel.lora_wall()
    assert wall is not None
    wall = cast(PromptLoraWallView, wall)
    set_lora_calls: list[object] = []

    def record_set_loras(items: object) -> None:
        """Record unexpected media wall item replacement requests."""

        set_lora_calls.append(items)

    monkeypatch.setattr(wall, "set_loras", record_set_loras)

    render_panel_lora_candidates(panel, (next_candidate,))
    assert wall.activate_current() is True

    assert set_lora_calls == []
