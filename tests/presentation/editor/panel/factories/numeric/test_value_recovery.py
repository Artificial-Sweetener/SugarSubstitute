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

"""Tests for numeric field recovery from invalid Comfy values."""

from __future__ import annotations

import pytest

import substitute.presentation.editor.panel.factories.numeric_factory as numeric_factory
from substitute.domain.node_behavior import FieldPresentation
from substitute.presentation.editor.panel.factories.numeric_factory import (
    NumericFieldBuildRequest,
    NumericFieldFactory,
)


class _FakeNumericWidget:
    """Record the numeric value applied by one factory-built control."""

    def __init__(self, _parent: object = None) -> None:
        """Create an empty value recorder."""

        self.minimum: object = None
        self.maximum: object = None
        self.step: object = None
        self.value: object = None

    def setMinimum(self, value: object) -> None:
        """Record the configured lower bound."""

        self.minimum = value

    def setMaximum(self, value: object) -> None:
        """Record the configured upper bound."""

        self.maximum = value

    def setSingleStep(self, value: object) -> None:
        """Record the configured step."""

        self.step = value

    def setSymbolVisible(self, _visible: bool) -> None:
        """Accept the standard spinbox decoration configuration."""

    def setDecimals(self, _decimals: int) -> None:
        """Accept the standard floating-point precision configuration."""

    def setValue(self, value: object) -> None:
        """Record the initialized numeric value."""

        self.value = value


@pytest.mark.parametrize(
    ("field_meta", "constraints", "expected_value"),
    [
        ({"default": 729}, {"min": 11, "max": 999, "step": 1}, 729),
        (
            {"default": "Qwen3-VL-4B-Instruct"},
            {"min": 11, "max": 999, "step": 1},
            11,
        ),
        ({"default": "Qwen3-VL-4B-Instruct"}, {}, 0),
    ],
)
def test_numeric_factory_recovers_invalid_comfy_seed_values(
    monkeypatch: pytest.MonkeyPatch,
    field_meta: dict[str, object],
    constraints: dict[str, object],
    expected_value: int,
) -> None:
    """Invalid persisted seeds should prefer Comfy's default, bounds, then zero."""

    monkeypatch.setattr(numeric_factory, "SeedBox", _FakeNumericWidget)

    widget = NumericFieldFactory().build_field_widget(
        NumericFieldBuildRequest(
            parent=None,
            node_name="AILab_QwenVL",
            key="seed",
            value="Qwen3-VL-4B-Instruct",
            field_meta=field_meta,
            field_type="INT",
            field_presentation=FieldPresentation.SEED_BOX,
            constraints=constraints,
        )
    )

    assert isinstance(widget, _FakeNumericWidget)
    assert widget.value == expected_value


def test_numeric_factory_recovers_invalid_float_to_comfy_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid floating values should use the declared minimum after a bad default."""

    monkeypatch.setattr(numeric_factory, "DoubleSpinBox", _FakeNumericWidget)

    widget = NumericFieldFactory().build_field_widget(
        NumericFieldBuildRequest(
            parent=None,
            node_name="ExampleNode",
            key="scale",
            value="not-a-float",
            field_meta={"default": "not-a-float"},
            field_type="FLOAT",
            constraints={"min": 0.25, "max": 3.0, "step": 0.05},
        )
    )

    assert isinstance(widget, _FakeNumericWidget)
    assert widget.value == 0.25
