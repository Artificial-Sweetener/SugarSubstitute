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

"""Verify registration state after a field-construction failure."""

from __future__ import annotations

from typing import cast

import pytest
from PySide6.QtWidgets import QWidget
from qfluentwidgets import LineEdit  # type: ignore[import-untyped]

from tests.presentation.editor.node_card.rebuild.support import (
    create_rebuild_scenario,
)


def test_field_failure_preserves_other_fields_without_stale_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep a useful field without publishing state for the failed field."""

    build_count = 0
    panel_owner: list[QWidget] = []

    def fail_second_widget_build(**_kwargs: object) -> QWidget:
        """Build one registered field before the second field raises."""

        nonlocal build_count
        build_count += 1
        if build_count == 2:
            raise RuntimeError("forced field build failure")
        return cast(QWidget, LineEdit(panel_owner[0]))

    scenario = create_rebuild_scenario(
        monkeypatch,
        node_name="loader",
        node_type="ModelLoader",
        widget_factory=fail_second_widget_build,
    )
    panel_owner.append(scenario.panel)
    wrapper = scenario.build(
        inputs={"first": "kept until rollback", "second": "fails"},
        definitions={
            "ModelLoader": {
                "input": {
                    "required": {
                        "first": ["STRING", {"default": ""}],
                        "second": ["STRING", {"default": ""}],
                    }
                }
            }
        },
    )
    try:
        assert set(scenario.panel.input_widgets_by_field_key) == {
            ("A", "loader", "first")
        }
        assert (
            "A",
            "loader",
            "second",
        ) not in scenario.panel.input_widgets_by_field_key
    finally:
        scenario.destroy(wrapper)
