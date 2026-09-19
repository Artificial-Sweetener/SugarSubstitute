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

"""Verify the node-card action menu through its shared button lifecycle."""

from __future__ import annotations

from typing import Any, cast

import pytest
from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget

import substitute.presentation.editor.panel.node_card.action_menu as action_menu
from substitute.presentation.editor.field_actions import FieldActionContribution
from substitute.presentation.editor.panel.menus.node_title_preset_actions import (
    NodeInputPresetContext,
)
from substitute.presentation.editor.panel.node_card.action_menu import (
    NodeCardActionMenuBinding,
)
from substitute.presentation.widgets.menu_model import MenuItem


def test_node_action_menu_second_click_closes_without_rebuilding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The node cog should close its open menu before allowing a fresh open."""

    _ensure_app()
    rendered_menus: list[Any] = []
    renderer_type = cast(Any, action_menu).QFluentMenuRenderer
    original_render = renderer_type.render

    def capture_render(renderer: Any, model: Any) -> Any:
        """Retain and return each production-rendered menu."""

        menu = original_render(renderer, model)
        rendered_menus.append(menu)
        return menu

    monkeypatch.setattr(renderer_type, "render", capture_render)
    monkeypatch.setattr(
        "qfluentwidgets.components.widgets.menu.RoundMenu.exec",
        lambda menu, *_args, **_kwargs: menu.show(),
    )
    title = QWidget()
    binding = NodeCardActionMenuBinding.create(
        title_row=title,
        title_layout=QHBoxLayout(title),
        preset_context=NodeInputPresetContext(
            cube_alias="A",
            node_name="sampler",
            node_type="KSampler",
            inputs={},
            field_specs={},
            cube_state=object(),
            input_widgets_by_field_key={},
        ),
        preset_source=None,
        dialog_parent=lambda: title,
        is_connection=None,
        advanced_inputs=None,
        field_action_contributions=(
            FieldActionContribution(
                contribution_id="test.action",
                availability_factory=lambda: True,
                entries_factory=lambda _context: (MenuItem("test", "Test"),),
            ),
        ),
    )
    assert binding is not None
    try:
        binding.button.click()
        assert len(rendered_menus) == 1
        assert rendered_menus[0].isVisible() is True

        binding.button.click()
        assert len(rendered_menus) == 1
        assert rendered_menus[0].isVisible() is False

        binding.button.click()
        assert len(rendered_menus) == 2
        assert rendered_menus[1].isVisible() is True
    finally:
        title.close()


def _ensure_app() -> QApplication:
    """Return the process QApplication used by headless widget tests."""

    app = QApplication.instance()
    return app if isinstance(app, QApplication) else QApplication([])
