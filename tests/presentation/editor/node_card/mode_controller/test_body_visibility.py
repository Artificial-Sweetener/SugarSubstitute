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

"""Verify card-body state across linked and independent modes."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout

from substitute.presentation.editor.panel.node_card.body_layout import (
    ensure_card_body_layout_state,
)
from tests.presentation.editor.node_card.mode_controller.support import (
    create_body_harness,
    expected_visible_item_height,
    independent_decision,
    linked_decision,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_linked_mode_hides_and_independent_mode_restores_controls() -> None:
    """Hide linked controls and restore them on the existing independent card."""

    harness = create_body_harness()
    assert harness.content_body is not None
    assert harness.content_layout is not None
    assert harness.chevron is not None
    assert harness.switch_wrapper is not None
    assert harness.enabled_switch is not None
    content_body = harness.content_body
    wrapper_layout = harness.wrapper.layout()
    assert isinstance(wrapper_layout, QVBoxLayout)
    harness.wrapper.show()
    wait_for_qt_condition(harness.wrapper.isVisible)
    try:
        harness.apply(linked_decision())

        assert content_body.maximumHeight() == 0
        assert content_body.isHidden()
        body_item = wrapper_layout.itemAt(1)
        assert body_item is not None
        assert body_item.isEmpty() is True
        wait_for_qt_condition(
            lambda: (
                harness.wrapper.sizeHint().height()
                == expected_visible_item_height(
                    wrapper_layout,
                    harness.title_row,
                    content_body,
                )
            )
        )
        assert harness.chevron.isHidden()
        assert harness.switch_wrapper.isHidden()
        assert harness.enabled_switch.isChecked() is False

        harness.apply(independent_decision(enabled=True))

        assert content_body.isHidden() is False
        assert content_body.maximumHeight() > 0
        assert body_item.isEmpty() is False
        assert harness.chevron.isHidden() is False
        assert harness.switch_wrapper.isHidden() is False
        assert harness.enabled_switch.isChecked() is True
    finally:
        harness.destroy()


def test_linked_mode_preserves_manual_collapse() -> None:
    """Keep the user's accordion state distinct from forced linked collapse."""

    harness = create_body_harness()
    assert harness.content_body is not None
    assert harness.content_layout is not None
    state = ensure_card_body_layout_state(
        content_body=harness.content_body,
        expanded_height=harness.content_layout.sizeHint().height(),
    )
    state.collapsed = True
    try:
        harness.apply(linked_decision())
        harness.apply(independent_decision(enabled=True))

        assert state.collapsed is True
        assert state.forced_collapsed is False
        assert harness.content_body.maximumHeight() == 0
        assert harness.content_body.isHidden()
    finally:
        harness.destroy()
