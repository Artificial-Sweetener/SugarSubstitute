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

"""Present compact synthetic-canvas dimensions and conditional resize options."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon,
    HorizontalSeparator,
    SegmentedWidget,
    TransparentToolButton,
    RoundMenu,
)

from sugarsubstitute_shared.localization import ApplicationMessage
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
    set_localized_accessible_name,
    set_localized_text,
    set_localized_tooltip,
)
from substitute.domain.workflow import (
    CanvasDimensions,
    SyntheticCanvasAnchor,
    SyntheticCanvasResamplingMode,
    SyntheticCanvasResizeScope,
)
from substitute.presentation.dialogs.synthetic_canvas_anchor_button import (
    SyntheticCanvasAnchorButton,
)
from substitute.presentation.localization import (
    LocalizedCaptionLabel,
    LocalizedRadioButton,
    LocalizedStrongBodyLabel,
)
from substitute.presentation.widgets.spin_box import SpinBox
from substitute.presentation.widgets.menu_buttons import ToggleDropDownPushButton

_DIMENSION_MINIMUM = 64
_DIMENSION_MAXIMUM = 32768
_DIMENSION_STEP = 8
_OPTION_PANEL_HEIGHT = 116

_ANCHOR_PRESENTATION: Mapping[SyntheticCanvasAnchor, tuple[str, str]] = {
    SyntheticCanvasAnchor.TOP_LEFT: ("↖", "Top left"),
    SyntheticCanvasAnchor.TOP: ("↑", "Top"),
    SyntheticCanvasAnchor.TOP_RIGHT: ("↗", "Top right"),
    SyntheticCanvasAnchor.LEFT: ("←", "Left"),
    SyntheticCanvasAnchor.CENTER: ("", "Center"),
    SyntheticCanvasAnchor.RIGHT: ("→", "Right"),
    SyntheticCanvasAnchor.BOTTOM_LEFT: ("↙", "Bottom left"),
    SyntheticCanvasAnchor.BOTTOM: ("↓", "Bottom"),
    SyntheticCanvasAnchor.BOTTOM_RIGHT: ("↘", "Bottom right"),
}


class SyntheticCanvasResolutionForm(QWidget):
    """Own compact resize controls and their internally consistent state."""

    stateChanged = Signal()
    scopeChanged = Signal(object)

    def __init__(
        self,
        *,
        current_dimensions: CanvasDimensions,
        parent: QWidget | None = None,
    ) -> None:
        """Build one resize form around immutable current dimensions."""

        super().__init__(parent)
        self._current_dimensions = current_dimensions
        self._updating_dimensions = False
        self._anchor_buttons: dict[SyntheticCanvasAnchor, QToolButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        self._build_mode_selector(layout)
        layout.addWidget(HorizontalSeparator(self))
        self._build_size_controls(layout)
        layout.addWidget(HorizontalSeparator(self))
        self._build_scope_options(layout)

        self.mode_selector.currentItemChanged.connect(self._on_scope_changed)
        self.mode_selector.setCurrentItem(SyntheticCanvasResizeScope.CANVAS_ONLY.value)

    def dimensions(self) -> CanvasDimensions:
        """Return the currently authored target size."""

        return CanvasDimensions(self.width_spin.value(), self.height_spin.value())

    def selected_scope(self) -> SyntheticCanvasResizeScope:
        """Return whether the canvas alone or every mask should be resized."""

        if (
            self.mode_selector.currentRouteKey()
            == SyntheticCanvasResizeScope.CANVAS_ONLY.value
        ):
            return SyntheticCanvasResizeScope.CANVAS_ONLY
        return SyntheticCanvasResizeScope.CANVAS_AND_LAYERS

    def selected_anchor(self) -> SyntheticCanvasAnchor:
        """Return the checked fixed point for a canvas-only resize."""

        return next(
            (
                anchor
                for anchor, button in self._anchor_buttons.items()
                if button.isChecked()
            ),
            SyntheticCanvasAnchor.CENTER,
        )

    def resampling_mode(self) -> SyntheticCanvasResamplingMode:
        """Return the selected whole-mask resampling quality."""

        if self.fast_radio.isChecked():
            return SyntheticCanvasResamplingMode.FAST
        return SyntheticCanvasResamplingMode.SMOOTH

    def set_preset_menu(self, menu: RoundMenu) -> None:
        """Install the existing preset menu without adapting its contents."""

        self.preset_menu_button.set_popup_menu(menu)

    def set_preset_menu_enabled(self, enabled: bool) -> None:
        """Enable or disable the shared preset-menu trigger."""

        self.preset_menu_button.setEnabled(enabled)

    def set_editing_enabled(self, enabled: bool) -> None:
        """Enable or disable every resize decision control as one unit."""

        for widget in (
            self.width_spin,
            self.height_spin,
            self.swap_button,
            self.mode_selector,
            self.fast_radio,
            self.smooth_radio,
            *self._anchor_buttons.values(),
        ):
            widget.setEnabled(enabled)

    def _build_mode_selector(self, layout: QVBoxLayout) -> None:
        """Build the primary operation choice without surrounding card chrome."""

        self.mode_selector = SegmentedWidget(self)
        canvas_item = self.mode_selector.addItem(
            SyntheticCanvasResizeScope.CANVAS_ONLY.value,
            render_application_text(app_text("Resize canvas only")),
        )
        masks_item = self.mode_selector.addItem(
            SyntheticCanvasResizeScope.CANVAS_AND_LAYERS.value,
            render_application_text(app_text("Scale canvas and masks")),
        )
        set_localized_text(canvas_item, "Resize canvas only")
        set_localized_text(masks_item, "Scale canvas and masks")
        self.mode_selector.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        layout.addWidget(self.mode_selector)

    def _build_size_controls(self, layout: QVBoxLayout) -> None:
        """Build dimension actions and values as one compact group."""

        layout.addWidget(LocalizedStrongBodyLabel(app_text("New size"), self))

        self.preset_menu_button = ToggleDropDownPushButton(self)
        self.preset_menu_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        set_localized_text(self.preset_menu_button, "Save or Load preset")

        self.dimension_grid = QGridLayout()
        self.dimension_grid.setContentsMargins(0, 0, 0, 0)
        self.dimension_grid.setHorizontalSpacing(8)
        self.dimension_grid.setVerticalSpacing(4)
        self.width_spin = self._dimension_spin(
            self._current_dimensions.width,
            app_text("Width"),
        )
        self.height_spin = self._dimension_spin(
            self._current_dimensions.height,
            app_text("Height"),
        )
        self.dimension_grid.addWidget(
            LocalizedCaptionLabel(app_text("Width"), self), 0, 0
        )
        self.dimension_grid.addWidget(
            LocalizedCaptionLabel(app_text("Height"), self), 0, 2
        )
        self.dimension_grid.addWidget(
            LocalizedCaptionLabel(app_text("Preset"), self), 0, 3
        )
        self.dimension_grid.addWidget(self.width_spin, 1, 0)
        self.swap_button = TransparentToolButton(FluentIcon.SYNC, self)
        self.swap_button.setFixedSize(36, 32)
        set_localized_tooltip(self.swap_button, "Swap width and height")
        set_localized_accessible_name(self.swap_button, "Swap width and height")
        self.swap_button.clicked.connect(self._swap_dimensions)
        self.dimension_grid.addWidget(self.swap_button, 1, 1)
        self.dimension_grid.addWidget(self.height_spin, 1, 2)
        self.dimension_grid.addWidget(self.preset_menu_button, 1, 3)
        self.dimension_grid.setColumnStretch(0, 1)
        self.dimension_grid.setColumnStretch(2, 1)
        layout.addLayout(self.dimension_grid)

    def _build_scope_options(self, layout: QVBoxLayout) -> None:
        """Build equally sized conditional anchor and resampling panels."""

        self.scope_options = QStackedWidget(self)
        self.scope_options.setStyleSheet("background: transparent;")
        self.scope_options.setFixedHeight(_OPTION_PANEL_HEIGHT)
        self.anchor_options = self._build_anchor_options(self.scope_options)
        self.resampling_options = self._build_resampling_options(self.scope_options)
        self.scope_options.addWidget(self.anchor_options)
        self.scope_options.addWidget(self.resampling_options)
        layout.addWidget(self.scope_options)

    def _build_anchor_options(self, parent: QWidget) -> QWidget:
        """Build a compact explanation beside the nine-point anchor picker."""

        container = QWidget(parent)
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(20)
        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(4)
        copy.addWidget(LocalizedStrongBodyLabel(app_text("Anchor point"), container))
        caption = LocalizedCaptionLabel(
            app_text("Choose the point that stays fixed while the canvas changes."),
            container,
        )
        caption.setWordWrap(True)
        copy.addWidget(caption)
        copy.addStretch(1)
        row.addLayout(copy, 1)

        anchor_grid = QWidget(container)
        anchor_grid.setFixedSize(132, 114)
        grid = QGridLayout(anchor_grid)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        group = QButtonGroup(self)
        group.setExclusive(True)
        self._anchor_group = group
        for index, (anchor, presentation) in enumerate(_ANCHOR_PRESENTATION.items()):
            symbol, label = presentation
            button = SyntheticCanvasAnchorButton(anchor, symbol, anchor_grid)
            button.setFixedSize(40, 34)
            set_localized_tooltip(button, label)
            set_localized_accessible_name(button, label)
            group.addButton(button)
            grid.addWidget(button, index // 3, index % 3)
            self._anchor_buttons[anchor] = button
        self._anchor_buttons[SyntheticCanvasAnchor.CENTER].setChecked(True)
        row.addWidget(anchor_grid)
        return container

    def _build_resampling_options(self, parent: QWidget) -> QWidget:
        """Stack resampling copy above one horizontal quality-choice row."""

        container = QWidget(parent)
        self.scaling_quality_options_layout = QVBoxLayout(container)
        self.scaling_quality_options_layout.setContentsMargins(0, 0, 0, 0)
        self.scaling_quality_options_layout.setSpacing(8)
        self.scaling_quality_copy_layout = QVBoxLayout()
        self.scaling_quality_copy_layout.setContentsMargins(0, 0, 0, 0)
        self.scaling_quality_copy_layout.setSpacing(4)
        self.scaling_quality_copy_layout.addWidget(
            LocalizedStrongBodyLabel(app_text("Scaling quality"), container)
        )
        caption = LocalizedCaptionLabel(
            app_text("Choose how regional mask pixels are resampled."),
            container,
        )
        caption.setWordWrap(True)
        self.scaling_quality_copy_layout.addWidget(caption)
        self.scaling_quality_options_layout.addLayout(self.scaling_quality_copy_layout)

        self.scaling_quality_layout = QHBoxLayout()
        self.scaling_quality_layout.setContentsMargins(0, 0, 0, 0)
        self.scaling_quality_layout.setSpacing(16)
        self.fast_radio = LocalizedRadioButton(app_text("Nearest Neighbor"), container)
        set_localized_tooltip(
            self.fast_radio,
            "Preserves hard mask edges by copying the nearest pixel without blending.",
        )
        self.smooth_radio = LocalizedRadioButton(app_text("Qt Smooth"), container)
        set_localized_tooltip(
            self.smooth_radio,
            "Uses Qt smooth scaling to blend neighboring pixels for softer resized masks.",
        )
        group = QButtonGroup(self)
        group.addButton(self.fast_radio)
        group.addButton(self.smooth_radio)
        self._resampling_group = group
        self.smooth_radio.setChecked(True)
        self.scaling_quality_layout.addWidget(self.fast_radio)
        self.scaling_quality_layout.addWidget(self.smooth_radio)
        self.scaling_quality_layout.addStretch(1)
        self.scaling_quality_options_layout.addLayout(self.scaling_quality_layout)
        return container

    def _dimension_spin(
        self,
        value: int,
        label: ApplicationMessage,
    ) -> SpinBox:
        """Create one constrained dimension editor that updates form state."""

        spin = SpinBox(self)
        spin.setRange(_DIMENSION_MINIMUM, _DIMENSION_MAXIMUM)
        spin.setSingleStep(_DIMENSION_STEP)
        spin.setValue(value)
        spin.setAccessibleName(render_application_text(label))
        spin.valueChanged.connect(self._on_dimensions_changed)
        return spin

    def _on_scope_changed(self, route_key: str) -> None:
        """Replace conditional options and publish the selected operation."""

        scope = (
            SyntheticCanvasResizeScope.CANVAS_ONLY
            if route_key == SyntheticCanvasResizeScope.CANVAS_ONLY.value
            else SyntheticCanvasResizeScope.CANVAS_AND_LAYERS
        )
        self.scope_options.setCurrentWidget(
            self.anchor_options
            if scope is SyntheticCanvasResizeScope.CANVAS_ONLY
            else self.resampling_options
        )
        self.scopeChanged.emit(scope)
        self.stateChanged.emit()

    def _swap_dimensions(self) -> None:
        """Swap width and height as one state transition."""

        dimensions = self.dimensions()
        self._updating_dimensions = True
        try:
            self.width_spin.setValue(dimensions.height)
            self.height_spin.setValue(dimensions.width)
        finally:
            self._updating_dimensions = False
        self.stateChanged.emit()

    def _on_dimensions_changed(self, _value: int) -> None:
        """Publish direct dimension edits outside an atomic preset update."""

        if self._updating_dimensions:
            return
        self.stateChanged.emit()


__all__ = ["SyntheticCanvasResolutionForm"]
