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

"""Build numeric editor field widgets from prepared field inputs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import LineEdit  # type: ignore[import-untyped]

try:
    from qfluentwidgets.common.font import setFont  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - test-stub fallback only

    def setFont(_widget: object, _font_size: int = 14, _weight: int = 50) -> None:
        """Provide a no-op font helper when qfluentwidgets font utilities are unavailable."""


from substitute.application.overrides.control_registry_service import (
    register_editor_control_builders,
)
from substitute.domain.node_behavior import FieldPresentation
from substitute.presentation.editor.panel.widgets.field_row import (
    apply_editor_control_height,
)
from substitute.presentation.widgets import (
    DoubleSpinBox,
    DragOnlySlider,
    SeedBox,
    SpinBox,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.editor.panel.factories.numeric")
_SPINNER_SLIDER_VISUAL_HEIGHT = 22
_QT_SLIDER_MAXIMUM = 2_147_483_647
SPINNER_SLIDER_INPUTS = {
    "denoise",
}
SPINNER_SLIDER_LABELS = {
    "scale factor",
}


def _to_float(value: object) -> float:
    """Convert a dynamic numeric field value into a float."""

    return float(cast(Any, value))


def _to_int(value: object) -> int:
    """Convert a dynamic numeric field value into an integer."""

    return int(cast(Any, value))


@dataclass(frozen=True, slots=True)
class NumericFieldBuildRequest:
    """Carry prepared numeric field data to numeric field factories."""

    parent: Any
    node_name: str
    key: str
    value: object
    field_meta: dict[str, object]
    field_type: object = None
    field_presentation: FieldPresentation = FieldPresentation.STANDARD
    constraints: dict[str, object] = field(default_factory=dict)


class NumericFieldFactory:
    """Build numeric editor widgets while leaving value sync to wiring owners."""

    def build_field_widget(self, request: NumericFieldBuildRequest) -> object | None:
        """Return a numeric field widget, or None when this field is not numeric."""

        for factory in (
            widget_factory_spinner_slider,
            widget_factory_seedbox,
            widget_factory_int,
            widget_factory_float,
        ):
            result = factory(
                request.parent,
                request.node_name,
                request.key,
                request.value,
                request.field_meta,
                field_type=request.field_type,
                field_presentation=request.field_presentation,
                constraints=request.constraints,
            )
            if result is not None:
                return result
        return None


def _apply_spinner_slider_visual_height(slider: DragOnlySlider) -> None:
    """Keep qfluent slider visuals centered inside the fixed editor row height."""

    slider.setFixedHeight(_SPINNER_SLIDER_VISUAL_HEIGHT)


def _build_spinner_slider_widget(
    parent: Any,
    value: object,
    min_val: object,
    max_val: object,
    step_val: object,
) -> QWidget:
    """Build a float spinner/slider pair that stays synchronized both ways."""

    container = QWidget(parent)
    apply_editor_control_height(container)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    step_count = _spinner_slider_step_count(min_val, max_val, step_val)
    if step_count is None:
        raise ValueError("Spinner/slider range cannot fit Qt slider bounds.")

    slider = DragOnlySlider(Qt.Orientation.Horizontal, container)
    slider.setRange(0, step_count)
    slider.setFixedWidth(120)
    _apply_spinner_slider_visual_height(slider)

    minimum = _to_float(min_val)
    step = _to_float(step_val)
    current_value = _to_float(value)
    spinbox = DoubleSpinBox(container)
    spinbox.setRange(minimum, _to_float(max_val))
    spinbox.setSingleStep(step)
    spinbox.setDecimals(2)
    spinbox.setValue(current_value)
    spinbox.setFixedWidth(80)
    spinbox.setSymbolVisible(False)
    apply_editor_control_height(spinbox)

    def slider_to_value(slider_val: int) -> float:
        """Return the floating-point value represented by one slider position."""

        return round(minimum + slider_val * step, 10)

    def value_to_slider(val: float) -> int:
        """Return the slider position represented by one floating-point value."""

        return int(round((val - minimum) / step))

    slider.blockSignals(True)
    slider.setValue(value_to_slider(current_value))
    slider.blockSignals(False)

    slider.valueChanged.connect(lambda v: spinbox.setValue(slider_to_value(v)))
    spinbox.valueChanged.connect(lambda v: slider.setValue(value_to_slider(v)))

    layout.addWidget(spinbox, 0, Qt.AlignmentFlag.AlignVCenter)
    layout.addWidget(slider, 0, Qt.AlignmentFlag.AlignVCenter)

    setattr(container, "spinbox", spinbox)
    return container


def _spinner_slider_step_count(
    min_val: object,
    max_val: object,
    step_val: object,
) -> int | None:
    """Return a Qt-safe slider step count for one float spinner/slider range."""

    try:
        minimum = _to_float(min_val)
        maximum = _to_float(max_val)
        step = _to_float(step_val)
    except (TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(item) for item in (minimum, maximum, step)):
        return None
    if step <= 0 or maximum < minimum:
        return None
    step_count = (maximum - minimum) / step
    if step_count > _QT_SLIDER_MAXIMUM:
        return None
    return max(1, int(round(step_count)))


def _build_int_spinner_slider_widget(
    parent: Any,
    value: object,
    min_val: object,
    max_val: object,
    step_val: object,
) -> QWidget:
    """Build an integer spinner/slider pair that stays synchronized both ways."""

    container = QWidget(parent)
    apply_editor_control_height(container)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    try:
        current_value = _to_int(value)
    except (TypeError, ValueError, OverflowError):
        current_value = 0

    minimum = _to_int(min_val)
    maximum = _to_int(max_val)
    step = max(1, _to_int(step_val or 1))
    step_count = max(1, int(round((maximum - minimum) / step)))

    slider = DragOnlySlider(Qt.Orientation.Horizontal, container)
    slider.setRange(0, step_count)
    slider.setFixedWidth(120)
    _apply_spinner_slider_visual_height(slider)

    spinbox = SpinBox(container)
    spinbox.setRange(minimum, maximum)
    spinbox.setSingleStep(step)
    spinbox.setValue(current_value)
    spinbox.setFixedWidth(80)
    spinbox.setSymbolVisible(False)
    apply_editor_control_height(spinbox)

    def slider_to_value(slider_val: int) -> int:
        """Return the integer value represented by one slider position."""

        return int(minimum + slider_val * step)

    def value_to_slider(val: int) -> int:
        """Return the slider position represented by one integer value."""

        return int(round((val - minimum) / step))

    slider.blockSignals(True)
    slider.setValue(value_to_slider(current_value))
    slider.blockSignals(False)

    slider.valueChanged.connect(lambda v: spinbox.setValue(slider_to_value(v)))
    spinbox.valueChanged.connect(lambda v: slider.setValue(value_to_slider(v)))

    layout.addWidget(spinbox, 0, Qt.AlignmentFlag.AlignVCenter)
    layout.addWidget(slider, 0, Qt.AlignmentFlag.AlignVCenter)

    setattr(container, "spinbox", spinbox)
    return container


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    """Convert one hex color string into an RGB tuple."""

    c = color.strip()
    if c.startswith("#"):
        c = c[1:]
    if len(c) == 3:
        c = "".join([ch * 2 for ch in c])
    r = int(c[0:2], 16)
    g = int(c[2:4], 16)
    b = int(c[4:6], 16)
    return r, g, b


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convert one RGB tuple into a hex color string."""

    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def _lerp_color(
    a: tuple[int, int, int], b: tuple[int, int, int], t: float
) -> tuple[int, int, int]:
    """Interpolate linearly between two RGB colors for one normalized progress value."""

    t = 0.0 if t is None else max(0.0, min(1.0, float(t)))
    return (
        int(round(a[0] + (b[0] - a[0]) * t)),
        int(round(a[1] + (b[1] - a[1]) * t)),
        int(round(a[2] + (b[2] - a[2]) * t)),
    )


def _build_color_slider_widget(
    parent: Any,
    value: object,
    min_val: object,
    max_val: object,
    step_val: object,
    start_color: str = "#007bff",
    end_color: str = "#ffd000",
    integer: bool = False,
) -> QWidget:
    """Build a spinner/slider pair for color-slider registered controls."""

    container = QWidget(parent)
    apply_editor_control_height(container)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    try:
        v0 = _to_int(value) if integer else _to_float(value)
    except (TypeError, ValueError, OverflowError):
        v0 = 0 if integer else _to_float(min_val)

    step = _to_int(step_val or 1) if integer else _to_float(step_val or 0.01)
    rng = (
        (_to_int(max_val) - _to_int(min_val))
        if integer
        else (_to_float(max_val) - _to_float(min_val))
    )
    step_count = max(1, int(round(rng / (step if step else 1))))

    slider = DragOnlySlider(Qt.Orientation.Horizontal, container)
    slider.setRange(0, step_count)
    slider.setFixedWidth(120)
    _apply_spinner_slider_visual_height(slider)

    if integer:
        integer_spinbox = SpinBox(container)
        integer_spinbox.setRange(_to_int(min_val), _to_int(max_val))
        integer_spinbox.setSingleStep(_to_int(step or 1))
        integer_spinbox.setValue(_to_int(v0))
        integer_spinbox.setFixedWidth(80)
        integer_spinbox.setSymbolVisible(False)
        apply_editor_control_height(integer_spinbox)
        spinbox: Any = integer_spinbox
    else:
        float_spinbox = DoubleSpinBox(container)
        float_spinbox.setRange(_to_float(min_val), _to_float(max_val))
        float_spinbox.setSingleStep(_to_float(step))
        try:
            decimals = max(0, min(4, len(str(step).split(".")[1].rstrip("0"))))
        except (IndexError, ValueError):
            decimals = 2
        float_spinbox.setDecimals(decimals)
        float_spinbox.setValue(_to_float(v0))
        float_spinbox.setFixedWidth(80)
        float_spinbox.setSymbolVisible(False)
        apply_editor_control_height(float_spinbox)
        spinbox = float_spinbox

    def slider_to_value(slider_val: int) -> int | float:
        """Return the numeric value represented by one slider position."""

        return (
            (_to_int(min_val) + slider_val * _to_int(step or 1))
            if integer
            else round(_to_float(min_val) + slider_val * _to_float(step), 10)
        )

    def value_to_slider(val: int | float) -> int:
        """Return the slider position represented by one numeric value."""

        return int(
            round(
                (
                    (int(val) if integer else float(val))
                    - (_to_int(min_val) if integer else _to_float(min_val))
                )
                / (_to_int(step or 1) if integer else _to_float(step))
            )
        )

    slider.blockSignals(True)
    slider.setValue(value_to_slider(v0))
    slider.blockSignals(False)

    slider.valueChanged.connect(lambda v: spinbox.setValue(slider_to_value(v)))
    spinbox.valueChanged.connect(lambda v: slider.setValue(value_to_slider(v)))

    layout.addWidget(spinbox, 0, Qt.AlignmentFlag.AlignVCenter)
    layout.addWidget(slider, 0, Qt.AlignmentFlag.AlignVCenter)

    setattr(container, "spinbox", spinbox)
    return container


def constraint_or(
    constraints: Mapping[str, object], key: str, fallback: object
) -> object:
    """Return the configured constraint value or the supplied fallback."""

    val = constraints.get(key)
    return val if val is not None else fallback


def _apply_widget_font(widget: object, pixel_size: int) -> None:
    """Apply a pixel-sized font when the widget supports Qt font assignment."""

    if not hasattr(widget, "setFont"):
        return
    setFont(widget, pixel_size)


def _normalized_spinner_slider_label(value: object) -> str | None:
    """Return the normalized label used by spinner/slider presentation matching."""

    if not isinstance(value, str):
        return None
    normalized = " ".join(
        value.strip().casefold().replace("_", " ").replace("-", " ").split()
    )
    return normalized or None


def should_use_spinner_slider(
    key: str, field_meta: Mapping[str, object] | None = None
) -> bool:
    """Return whether the field key should use the shared spinner/slider presentation."""

    if key in SPINNER_SLIDER_INPUTS:
        return True
    if field_meta is None:
        return False
    return _normalized_spinner_slider_label(field_meta.get("label")) in (
        SPINNER_SLIDER_LABELS
    )


def widget_factory_spinner_slider(
    parent: Any,
    node_name: str,
    key: str,
    value: object,
    field_meta: dict[str, object],
    **kwargs: object,
) -> object | None:
    """Build the shared spinner/slider composite for supported float fields."""

    if not should_use_spinner_slider(key, field_meta):
        return None
    if kwargs.get("field_type") != "FLOAT":
        return None

    raw_constraints = kwargs.get("constraints", {})
    constraints = raw_constraints if isinstance(raw_constraints, dict) else {}
    min_val = constraint_or(constraints, "min", 0.0)
    max_val = constraint_or(constraints, "max", 1.0)
    step_val = constraint_or(constraints, "step", 0.01)
    if _spinner_slider_step_count(min_val, max_val, step_val) is None:
        log_warning(
            _LOGGER,
            "Skipped spinner/slider because numeric range cannot fit Qt slider bounds",
            node_name=node_name,
            field_key=key,
            min_value=min_val,
            max_value=max_val,
            step_value=step_val,
        )
        return None

    return _build_spinner_slider_widget(parent, value, min_val, max_val, step_val)


def widget_factory_seedbox(
    parent: Any,
    node_name: str,
    key: str,
    value: object,
    field_meta: dict[str, object],
    **kwargs: object,
) -> object | None:
    """Build a seed box when resolved behavior selects seed presentation."""

    _ = (node_name, field_meta)
    if kwargs.get("field_presentation") is not FieldPresentation.SEED_BOX:
        return None

    raw_constraints = kwargs.get("constraints", {})
    constraints = raw_constraints if isinstance(raw_constraints, dict) else {}
    min_val = constraints.get("min")
    max_val = constraints.get("max")
    step_val = constraints.get("step", 1)

    field_widget = SeedBox(parent)
    if min_val is not None:
        field_widget.setMinimum(_to_int(min_val))
    if max_val is not None:
        field_widget.setMaximum(_to_int(max_val))
    if step_val is not None:
        field_widget.setSingleStep(_to_int(step_val))
    field_widget.setValue(_to_int(value))
    return field_widget


def widget_factory_int(
    parent: Any,
    node_name: str,
    key: str,
    value: object,
    field_meta: dict[str, object],
    **kwargs: object,
) -> object | None:
    """Build the integer editor widget for INT field specs."""

    _ = (node_name, key, field_meta)
    field_type = kwargs.get("field_type")
    raw_constraints = kwargs.get("constraints", {})
    constraints = raw_constraints if isinstance(raw_constraints, dict) else {}

    if field_type != "INT":
        return None

    int_value = _to_int(value)
    minimum = _to_int(constraint_or(constraints, "min", -2_147_483_648))
    maximum = _to_int(constraint_or(constraints, "max", 2_147_483_647))
    if (
        int_value < -2_147_483_648
        or int_value > 2_147_483_647
        or minimum < -2_147_483_648
        or maximum > 2_147_483_647
    ):
        line_edit: Any = LineEdit(parent)
        line_edit.setText(str(value))
        return cast(object, line_edit)

    field_widget = SpinBox(parent)
    field_widget.setSymbolVisible(False)
    _apply_widget_font(field_widget, 14)

    field_widget.setMinimum(minimum)
    field_widget.setMaximum(maximum)
    field_widget.setSingleStep(_to_int(constraint_or(constraints, "step", 1)))
    field_widget.setValue(int_value)

    return field_widget


def widget_factory_float(
    parent: Any,
    node_name: str,
    key: str,
    value: object,
    field_meta: dict[str, object],
    **kwargs: object,
) -> object | None:
    """Build the floating-point editor widget for FLOAT field specs."""

    _ = (node_name, key, field_meta)
    field_type = kwargs.get("field_type")
    raw_constraints = kwargs.get("constraints", {})
    constraints = raw_constraints if isinstance(raw_constraints, dict) else {}

    if field_type != "FLOAT":
        return None

    try:
        float_value = _to_float(value)
    except (TypeError, ValueError):
        return None

    field_widget = DoubleSpinBox(parent)
    field_widget.setSymbolVisible(False)
    _apply_widget_font(field_widget, 14)

    min_val = constraint_or(constraints, "min", -1e10)
    max_val = constraint_or(constraints, "max", 1e10)
    step_val = constraint_or(constraints, "step", 0.1)

    field_widget.setMinimum(_to_float(min_val))
    field_widget.setMaximum(_to_float(max_val))
    field_widget.setSingleStep(_to_float(step_val))

    if isinstance(step_val, float) and step_val.is_integer():
        field_widget.setDecimals(0)
    else:
        field_widget.setDecimals(2)

    field_widget.setValue(float_value)

    return field_widget


def register_numeric_control_builders() -> None:
    """Register numeric control builders with the configured application registry."""

    try:
        register_editor_control_builders(
            float_builder=_build_spinner_slider_widget,
            int_builder=_build_int_spinner_slider_widget,
            color_builder=_build_color_slider_widget,
        )
    except RuntimeError:
        log_warning(
            _LOGGER,
            "Skipped editor control registration because registry service is unconfigured",
        )
