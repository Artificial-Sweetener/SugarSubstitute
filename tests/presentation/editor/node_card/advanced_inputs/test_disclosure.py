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

"""Verify production node-card advanced-input disclosure behavior."""

from __future__ import annotations

from typing import Any, cast

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from substitute.presentation.widgets.action_menu import ActionMenu

from substitute.presentation.editor.panel.node_card.body_layout import (
    CardBodyLayoutState,
)
from substitute.presentation.editor.panel.node_card.action_menu import (
    NodeCardActionMenuButton,
)
from substitute.presentation.editor.panel.node_card.accordion_motion import (
    AccordionChevronWidget,
)
from tests.presentation.editor.node_card.body_layout.support import mount_body_card
from tests.presentation.editor.node_card.support import (
    WidgetPanel,
    accordion_content_attached,
    content_body_for,
    title_row_for,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


def _field_surface(
    panel: WidgetPanel,
    identity: tuple[str, str, str],
) -> QWidget:
    """Return a registered scalar row or grouped column for one field."""

    columns = panel.col_widgets
    if identity in columns:
        surface = columns[identity][1]
    else:
        surface = panel.row_widgets[identity][1]
    assert isinstance(surface, QWidget)
    return surface


def _open_node_action_menu(
    monkeypatch: pytest.MonkeyPatch,
    wrapper: QWidget,
) -> object:
    """Open a card's production gear menu without displaying a popup."""

    monkeypatch.setattr(
        "qfluentwidgets.components.widgets.menu.RoundMenu.exec",
        lambda *_args, **_kwargs: None,
    )
    title_row = title_row_for(wrapper)
    button = title_row.findChild(NodeCardActionMenuButton)
    assert button is not None
    button.click()
    binding = getattr(title_row, "_node_card_action_menu_binding", None)
    menu = cast(Any, binding)._menu_controller.menu()
    assert menu is not None
    return menu


def _menu_actions(menu: object) -> list[QAction]:
    """Return executable actions from one rendered Fluent menu."""

    actions = getattr(menu, "menuActions")()
    return [action for action in actions if isinstance(action, QAction)]


def test_mixed_card_hides_advanced_row_until_gear_menu_action_is_activated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mixed card should mount every value while disclosing advanced rows on demand."""

    mounted = mount_body_card(
        monkeypatch,
        node_name="sampler",
        node_type="AdvancedSampler",
        inputs={"steps": 20, "cfg": 7.0},
        definitions={
            "AdvancedSampler": {
                "input": {
                    "required": {
                        "steps": ["INT", {"default": 20}],
                        "cfg": ["FLOAT", {"default": 7.0, "advanced": True}],
                    }
                }
            }
        },
    )
    advanced_identity = ("A", "sampler", "cfg")
    try:
        title_row = title_row_for(mounted.wrapper)
        button = title_row.findChild(NodeCardActionMenuButton)
        assert button is not None
        assert button.icon().isNull() is False
        assert button.toolTip() == "Node actions"
        assert button.accessibleName() == "Node actions"
        assert title_row.contextMenuPolicy() == Qt.ContextMenuPolicy.DefaultContextMenu
        assert (
            mounted.wrapper.findChild(QWidget, "AdvancedInputDisclosureFooter") is None
        )
        advanced_surface = _field_surface(mounted.panel, advanced_identity)
        assert advanced_surface.isHidden() is True
        assert mounted.cube_state.buffer["nodes"]["sampler"]["inputs"] == {
            "steps": 20,
            "cfg": 7.0,
        }

        menu = _open_node_action_menu(monkeypatch, mounted.wrapper)
        assert isinstance(menu, ActionMenu)
        actions = _menu_actions(menu)
        assert [action.text() for action in actions] == ["Show advanced inputs"]
        assert actions[-1].isCheckable() is True
        assert actions[-1].isChecked() is False
        actions[-1].trigger()

        assert advanced_surface.isHidden() is False
        assert mounted.cube_state.ui["advanced_input_visibility"] == {"sampler": True}
        assert mounted.cube_state.dirty is True
        assert mounted.cube_state.buffer["nodes"]["sampler"]["inputs"] == {
            "steps": 20,
            "cfg": 7.0,
        }
        shown_menu = _open_node_action_menu(monkeypatch, mounted.wrapper)
        assert [action.text() for action in _menu_actions(shown_menu)] == [
            "Show advanced inputs"
        ]
        shown_action = _menu_actions(shown_menu)[-1]
        assert shown_action.isChecked() is True
        shown_action.trigger()
        assert advanced_surface.isHidden() is True
        assert mounted.cube_state.ui["advanced_input_visibility"] == {"sampler": False}
    finally:
        mounted.destroy()


def test_imported_comfy_disclosure_state_opens_card_without_mutating_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A direct workflow's serialized showAdvanced state should open its card."""

    mounted = mount_body_card(
        monkeypatch,
        node_name="7",
        node_type="AdvancedSampler",
        inputs={"cfg": 7.0},
        node_metadata={"_workflow": {"show_advanced_inputs": True}},
        definitions={
            "AdvancedSampler": {
                "input": {
                    "required": {"cfg": ["FLOAT", {"default": 7.0, "advanced": True}]}
                }
            }
        },
    )
    try:
        menu = _open_node_action_menu(monkeypatch, mounted.wrapper)
        assert [action.text() for action in _menu_actions(menu)] == [
            "Show advanced inputs"
        ]
        assert _menu_actions(menu)[-1].isChecked() is True
        assert _field_surface(mounted.panel, ("A", "7", "cfg")).isHidden() is False
        assert "advanced_input_visibility" not in mounted.cube_state.ui
        assert mounted.cube_state.dirty is False
    finally:
        mounted.destroy()


def test_advanced_disclosure_survives_card_rebuild_and_definition_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Durable card state should survive replacing its live node definition."""

    persisted_ui: dict[str, object] = {"advanced_input_visibility": {"sampler": True}}
    mounted = mount_body_card(
        monkeypatch,
        node_name="sampler",
        node_type="AdvancedSampler",
        inputs={"cfg": 7.0},
        ui=persisted_ui,
        definitions={
            "AdvancedSampler": {
                "input": {
                    "required": {
                        "cfg": [
                            "FLOAT",
                            {"default": 7.0, "advanced": True, "max": 20.0},
                        ]
                    }
                }
            }
        },
    )
    try:
        menu = _open_node_action_menu(monkeypatch, mounted.wrapper)
        assert [action.text() for action in _menu_actions(menu)] == [
            "Show advanced inputs"
        ]
        assert _menu_actions(menu)[-1].isChecked() is True
        assert (
            _field_surface(mounted.panel, ("A", "sampler", "cfg")).isHidden() is False
        )
        assert mounted.cube_state.ui is persisted_ui
    finally:
        mounted.destroy()


def test_card_collapse_hides_advanced_footer_with_the_complete_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Card accordion collapse should clip rows and disclosure as one body."""

    mounted = mount_body_card(
        monkeypatch,
        node_name="sampler",
        node_type="AdvancedSampler",
        inputs={"steps": 20, "cfg": 7.0},
        definitions={
            "AdvancedSampler": {
                "input": {
                    "required": {
                        "steps": ["INT", {"default": 20}],
                        "cfg": ["FLOAT", {"default": 7.0, "advanced": True}],
                    }
                }
            }
        },
    )
    try:
        content_body = content_body_for(mounted.wrapper)
        button = title_row_for(mounted.wrapper).findChild(NodeCardActionMenuButton)
        assert button is not None
        assert content_body.isAncestorOf(button) is False
        state = getattr(content_body, "_card_body_layout_state", None)
        assert isinstance(state, CardBodyLayoutState)

        QTest.mouseClick(
            title_row_for(mounted.wrapper),
            Qt.MouseButton.LeftButton,
            pos=QPoint(4, 4),
        )
        wait_for_qt_condition(lambda: not state.animating)

        assert state.collapsed is True
        assert content_body.maximumHeight() == 0
        menu = _open_node_action_menu(monkeypatch, mounted.wrapper)
        actions = _menu_actions(menu)
        assert actions[-1].text() == "Show advanced inputs"
        actions[-1].trigger()
        assert state.collapsed is True
        assert content_body.maximumHeight() == 0
    finally:
        mounted.destroy()


def test_all_advanced_card_remains_available_when_its_field_is_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An all-advanced node should retain its title and action gear."""

    mounted = mount_body_card(
        monkeypatch,
        node_name="advanced_only",
        node_type="AdvancedOnly",
        inputs={"expert_mode": True},
        definitions={
            "AdvancedOnly": {
                "input": {
                    "required": {
                        "expert_mode": [
                            "BOOLEAN",
                            {"default": True, "advanced": True},
                        ]
                    }
                }
            }
        },
    )
    try:
        title_row = title_row_for(mounted.wrapper)
        button = title_row.findChild(NodeCardActionMenuButton)
        assert button is not None
        assert mounted.wrapper.property("has_advanced_input_action") is True
        assert _field_surface(
            mounted.panel,
            ("A", "advanced_only", "expert_mode"),
        ).isHidden()
        assert button.isHidden() is False
        assert content_body_for(mounted.wrapper).maximumHeight() == 0
        assert accordion_content_attached(title_row) is False
    finally:
        mounted.destroy()


def test_gear_is_immediately_left_of_chevron_and_does_not_roll_up_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep node actions separate from the adjacent accordion interaction."""

    mounted = mount_body_card(
        monkeypatch,
        node_name="sampler",
        node_type="AdvancedSampler",
        inputs={"steps": 20, "cfg": 7.0},
        definitions={
            "AdvancedSampler": {
                "input": {
                    "required": {
                        "steps": ["INT", {"default": 20}],
                        "cfg": ["FLOAT", {"default": 7.0, "advanced": True}],
                    }
                }
            }
        },
    )
    try:
        title_row = title_row_for(mounted.wrapper)
        layout = title_row.layout()
        button = title_row.findChild(NodeCardActionMenuButton)
        chevron = title_row.findChild(AccordionChevronWidget)
        assert layout is not None
        assert button is not None
        assert chevron is not None
        assert layout.indexOf(button) + 1 == layout.indexOf(chevron)
        content_body = content_body_for(mounted.wrapper)
        state = getattr(content_body, "_card_body_layout_state", None)
        assert isinstance(state, CardBodyLayoutState)

        _open_node_action_menu(monkeypatch, mounted.wrapper)

        assert state.collapsed is False
    finally:
        mounted.destroy()
