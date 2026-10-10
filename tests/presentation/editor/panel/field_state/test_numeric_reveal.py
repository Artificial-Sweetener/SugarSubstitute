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

"""Verify reused numeric fields reveal current authority without edit side effects."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.presentation.editor.panel.current_field_state_resolver import (
    CurrentEditorFieldStateResolver,
)
from substitute.presentation.editor.panel.field_value_store import EditorFieldValueStore
from substitute.presentation.editor.panel.field_widget_state_controller import (
    FieldWidgetStateController,
)
from substitute.presentation.widgets import DoubleSpinBox, SeedBox
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


@pytest.mark.parametrize("seed", [True, False], ids=["seed", "cfg"])
@pytest.mark.parametrize(
    "replace_owner", [False, True], ids=["same-owner", "new-owner"]
)
def test_numeric_reveal_projects_current_value_without_writing_state(
    seed: bool, replace_owner: bool
) -> None:
    """Reveal cached values from the current owner, never as a user edit."""

    ensure_qt_application()
    parent = QWidget()
    widget = SeedBox(parent) if seed else DoubleSpinBox(parent)
    field = "noise_seed" if seed else "cfg"
    widget.setProperty(
        "input_metadata", {"cube_alias": "A", "node_name": "n", "key": field}
    )
    layout = QVBoxLayout(parent)
    layout.addWidget(widget)
    original = SimpleNamespace(
        buffer={"nodes": {"n": {"inputs": {field: 8}}}}, dirty=False
    )
    host = SimpleNamespace(_cube_states={"A": original})
    edits: list[object] = []
    signals: list[object] = []
    controller = FieldWidgetStateController(
        EditorFieldValueStore(lambda _binding, value: edits.append(value)),
        CurrentEditorFieldStateResolver(host),
    )
    try:
        controller.wire_numeric_state(widget, original)
        widget.valueChanged.connect(signals.append)
        parent.show()
        assert widget.value() == 8
        parent.hide()
        current = deepcopy(original) if replace_owner else original
        host._cube_states["A"] = current
        value = 42 if seed else 6.25
        current.buffer["nodes"]["n"]["inputs"][field] = value
        before = deepcopy(current.__dict__)
        parent.show()
        assert widget.value() == value
        assert current.__dict__ == before
        assert not edits
        assert not signals
        parent.hide()
        parent.show()
        assert widget.value() == value
        assert not edits
        assert not signals
    finally:
        destroy_qt_object(parent)


@pytest.mark.parametrize("decimal", [False, True], ids=["integer", "decimal"])
def test_composite_reveal_preserves_slider_sync_and_later_user_edits(
    decimal: bool,
) -> None:
    """Project the composite owner so its internal slider stays synchronized."""

    from substitute.presentation.editor.panel.field_state_controller import (
        EditorPanelFieldStateController,
    )
    from substitute.presentation.widgets.spinner_slider import (
        DecimalSpinnerSlider,
        IntegerSpinnerSlider,
    )

    ensure_qt_application()
    control = (
        DecimalSpinnerSlider(minimum=0, maximum=1, step=0.01, value=0.2)
        if decimal
        else IntegerSpinnerSlider(minimum=0, maximum=100, step=1, value=20)
    )
    field = "denoise" if decimal else "steps"
    original = 0.2 if decimal else 20
    desired = 0.8 if decimal else 80
    state = SimpleNamespace(
        buffer={"nodes": {"n": {"inputs": {field: original}}}}, dirty=False
    )
    changes: list[object] = []
    try:
        controller = EditorPanelFieldStateController(
            field_value_changed=lambda _binding, value: changes.append(value)
        )
        controller.bind_node_widget_state(
            control, state, {"node_name": "n", "key": field}
        )
        control.show()
        control.hide()
        state.buffer["nodes"]["n"]["inputs"][field] = desired
        control.show()
        assert control.value() == desired
        assert control.slider.value() == 80
        assert not changes
        assert state.dirty is False
        control.slider.setValue(60)
        assert state.buffer["nodes"]["n"]["inputs"][field] == (0.6 if decimal else 60)
        assert len(changes) == 1
        assert state.dirty is True
    finally:
        destroy_qt_object(control)


def test_seed_reveal_preserves_fallback_until_numeric_value_is_authored() -> None:
    """Keep live defaults for blank inputs but prefer subsequent authored values."""

    ensure_qt_application()
    control = SeedBox()
    control.setProperty(
        "input_metadata",
        {
            "node_name": "n",
            "key": "seed",
            "value_source": "live_default",
            "resolved_value": 77,
        },
    )
    state = SimpleNamespace(
        buffer={"nodes": {"n": {"inputs": {"seed": ""}}}}, dirty=False
    )
    controller = FieldWidgetStateController(
        EditorFieldValueStore(), CurrentEditorFieldStateResolver(None)
    )
    try:
        controller.wire_numeric_state(control, state)
        assert control.value() == 77
        control.show()
        assert control.value() == 77
        control.hide()
        state.buffer["nodes"]["n"]["inputs"]["seed"] = 42
        control.show()
        assert control.value() == 42
        assert state.dirty is False
    finally:
        destroy_qt_object(control)
