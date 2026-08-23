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

"""Tests for panel numeric field factory ownership."""

from __future__ import annotations

from typing import Any

import pytest

import substitute.presentation.editor.panel.factories.numeric_factory as numeric_factory
from substitute.domain.node_behavior import FieldPresentation
from substitute.presentation.editor.panel.factories.numeric_factory import (
    NumericFieldBuildRequest,
    NumericFieldFactory,
)


class _FakeLineEdit:
    """Record line-edit text assigned by overflow integer fields."""

    def __init__(self, _parent: object = None) -> None:
        """Create an empty text recorder."""

        self.text = ""

    def setText(self, text: str) -> None:
        """Record assigned text."""

        self.text = text


class _FakeSpinBox:
    """Record integer spinbox configuration."""

    def __init__(self, _parent: object = None) -> None:
        """Create an empty spinbox recorder."""

        self.symbol_visible: bool | None = None
        self.minimum: object = None
        self.maximum: object = None
        self.step: object = None
        self.value: object = None

    def setSymbolVisible(self, visible: bool) -> None:
        """Record symbol visibility."""

        self.symbol_visible = visible

    def setMinimum(self, value: object) -> None:
        """Record minimum."""

        self.minimum = value

    def setMaximum(self, value: object) -> None:
        """Record maximum."""

        self.maximum = value

    def setSingleStep(self, step: object) -> None:
        """Record single-step value."""

        self.step = step

    def setValue(self, value: object) -> None:
        """Record current value."""

        self.value = value


class _FakeDoubleSpinBox(_FakeSpinBox):
    """Record floating-point spinbox configuration."""

    def __init__(self, _parent: object = None) -> None:
        """Create an empty double-spinbox recorder."""

        super().__init__(_parent)
        self.decimals: int | None = None

    def setDecimals(self, decimals: int) -> None:
        """Record decimal precision."""

        self.decimals = decimals


class _FakeSeedBox(_FakeSpinBox):
    """Record seed-box numeric configuration."""


def test_numeric_factory_builds_int_spinbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """In-range INT fields should build configured spin boxes in the new owner."""

    monkeypatch.setattr(numeric_factory, "SpinBox", _FakeSpinBox)

    widget = NumericFieldFactory().build_field_widget(
        NumericFieldBuildRequest(
            parent=None,
            node_name="node",
            key="steps",
            value=42,
            field_meta={},
            field_type="INT",
            constraints={"min": 1, "max": 100, "step": 3},
        )
    )

    assert isinstance(widget, _FakeSpinBox)
    assert widget.symbol_visible is False
    assert widget.minimum == 1
    assert widget.maximum == 100
    assert widget.step == 3
    assert widget.value == 42


def test_numeric_factory_uses_line_edit_for_int_overflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INT values outside the 32-bit spinbox range should keep the line-edit fallback."""

    monkeypatch.setattr(numeric_factory, "LineEdit", _FakeLineEdit)

    widget = NumericFieldFactory().build_field_widget(
        NumericFieldBuildRequest(
            parent=None,
            node_name="node",
            key="large_number",
            value=3_000_000_000,
            field_meta={},
            field_type="INT",
            constraints={},
        )
    )

    assert isinstance(widget, _FakeLineEdit)
    assert widget.text == "3000000000"


def test_numeric_factory_builds_float_spinbox_with_decimal_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FLOAT fields should preserve the existing decimal policy from step values."""

    monkeypatch.setattr(numeric_factory, "DoubleSpinBox", _FakeDoubleSpinBox)

    integer_step_widget = NumericFieldFactory().build_field_widget(
        NumericFieldBuildRequest(
            parent=None,
            node_name="node",
            key="cfg",
            value=8,
            field_meta={},
            field_type="FLOAT",
            constraints={"step": 1.0},
        )
    )
    fractional_step_widget = NumericFieldFactory().build_field_widget(
        NumericFieldBuildRequest(
            parent=None,
            node_name="node",
            key="cfg",
            value=8.5,
            field_meta={},
            field_type="FLOAT",
            constraints={"step": 0.25},
        )
    )

    assert isinstance(integer_step_widget, _FakeDoubleSpinBox)
    assert isinstance(fractional_step_widget, _FakeDoubleSpinBox)
    assert integer_step_widget.decimals == 0
    assert fractional_step_widget.decimals == 2


def test_numeric_factory_builds_seedbox_before_generic_int(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canonical seed field should keep SeedBox behavior before INT fallback."""

    monkeypatch.setattr(numeric_factory, "SeedBox", _FakeSeedBox)

    widget = NumericFieldFactory().build_field_widget(
        NumericFieldBuildRequest(
            parent=None,
            node_name="ksampler",
            key="seed",
            value=123,
            field_meta={},
            field_type="INT",
            field_presentation=FieldPresentation.SEED_BOX,
            constraints={"min": 0, "max": 999, "step": 1},
        )
    )

    assert isinstance(widget, _FakeSeedBox)
    assert widget.minimum == 0
    assert widget.maximum == 999
    assert widget.step == 1
    assert widget.value == 123


def test_numeric_factory_builds_seedbox_for_comfy_noise_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Comfy's noise_seed field should use the same SeedBox as seed."""

    monkeypatch.setattr(numeric_factory, "SeedBox", _FakeSeedBox)

    widget = NumericFieldFactory().build_field_widget(
        NumericFieldBuildRequest(
            parent=None,
            node_name="SamplerCustom",
            key="noise_seed",
            value=0,
            field_meta={},
            field_type="INT",
            field_presentation=FieldPresentation.SEED_BOX,
            constraints={"min": 0, "max": 18_446_744_073_709_551_615, "step": 1},
        )
    )

    assert isinstance(widget, _FakeSeedBox)
    assert widget.minimum == 0
    assert widget.maximum == 18_446_744_073_709_551_615
    assert widget.step == 1
    assert widget.value == 0


def test_numeric_factory_does_not_infer_seedbox_from_raw_field_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raw aliases should not bypass resolved field-presentation ownership."""

    monkeypatch.setattr(numeric_factory, "SeedBox", _FakeSeedBox)
    monkeypatch.setattr(numeric_factory, "SpinBox", _FakeSpinBox)

    widget = NumericFieldFactory().build_field_widget(
        NumericFieldBuildRequest(
            parent=None,
            node_name="node",
            key="seed",
            value=7,
            field_meta={},
            field_type="INT",
            constraints={"min": 0, "max": 999, "step": 1},
        )
    )

    assert isinstance(widget, _FakeSpinBox)
    assert not isinstance(widget, _FakeSeedBox)


def test_numeric_factory_uses_integer_fallback_for_nonseed_unsigned_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-seed INT ranges outside Qt's limits should keep the generic fallback."""

    monkeypatch.setattr(numeric_factory, "LineEdit", _FakeLineEdit)

    widget = NumericFieldFactory().build_field_widget(
        NumericFieldBuildRequest(
            parent=None,
            node_name="PrimitiveInt",
            key="value",
            value=0,
            field_meta={},
            field_type="INT",
            constraints={"min": 0, "max": 18_446_744_073_709_551_615, "step": 1},
        )
    )

    assert isinstance(widget, _FakeLineEdit)
    assert widget.text == "0"


def test_numeric_factory_spinner_slider_uses_default_constraints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spinner/slider fields should treat explicit None constraints as missing."""

    captured: dict[str, object] = {}

    def _fake_spinner_slider(
        parent: object,
        value: object,
        min_val: object,
        max_val: object,
        step_val: object,
    ) -> object:
        """Record spinner-slider arguments."""

        captured.update(
            {
                "parent": parent,
                "value": value,
                "min": min_val,
                "max": max_val,
                "step": step_val,
            }
        )
        return object()

    monkeypatch.setattr(
        numeric_factory, "_build_spinner_slider_widget", _fake_spinner_slider
    )

    widget = NumericFieldFactory().build_field_widget(
        NumericFieldBuildRequest(
            parent="parent",
            node_name="detailer",
            key="denoise",
            value=0.5,
            field_meta={},
            field_type="FLOAT",
            constraints={"min": None, "max": None, "step": None},
        )
    )

    assert widget is not None
    assert captured == {
        "parent": "parent",
        "value": 0.5,
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
    }


def test_numeric_factory_spinner_slider_matches_normalized_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spinner/slider selection should still match normalized visible labels."""

    monkeypatch.setattr(
        numeric_factory,
        "_build_spinner_slider_widget",
        lambda *_args: object(),
    )

    widget = NumericFieldFactory().build_field_widget(
        NumericFieldBuildRequest(
            parent=None,
            node_name="upscale_by_factor",
            key="value",
            value=1.5,
            field_meta={"label": "Scale Factor"},
            field_type="FLOAT",
            constraints={"min": 0.25, "max": 3.0, "step": 0.05},
        )
    )

    assert widget is not None


def test_numeric_factory_spinner_slider_declines_qt_unsafe_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spinner/slider rendering should not build ranges Qt cannot represent."""

    def _fail_spinner_slider(*_args: Any) -> object:
        """Fail when the unsafe range was not rejected first."""

        pytest.fail("Unsafe spinner/slider range should be declined before build.")

    monkeypatch.setattr(
        numeric_factory, "_build_spinner_slider_widget", _fail_spinner_slider
    )

    widget = numeric_factory.widget_factory_spinner_slider(
        parent=None,
        node_name="upscale_by_factor",
        key="value",
        value=1.5,
        field_meta={"label": "Scale Factor"},
        field_type="FLOAT",
        constraints={
            "min": -9_223_372_036_854_775_807,
            "max": 9_223_372_036_854_775_807,
            "step": 0.1,
        },
    )

    assert widget is None


def test_numeric_factory_declines_non_numeric_field() -> None:
    """Non-numeric fields should be left for later factories."""

    widget = NumericFieldFactory().build_field_widget(
        NumericFieldBuildRequest(
            parent=None,
            node_name="node",
            key="text",
            value="hello",
            field_meta={},
            field_type="STRING",
            constraints={},
        )
    )

    assert widget is None
