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

"""Verify synthetic canvas resolution dialog interaction and defaults."""

from __future__ import annotations


from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)

from substitute.domain.workflow import (
    CanvasDimensions,
    SyntheticCanvasAnchor,
    SyntheticCanvasResamplingMode,
    SyntheticCanvasResizeRequest,
    SyntheticCanvasResizeScope,
)
from substitute.presentation.dialogs.synthetic_canvas_resolution_dialog import (
    SyntheticCanvasResolutionDialog,
)
from tests.presentation.dialogs.synthetic_resolution.support import (
    _app,
    _role,
)


def test_dialog_emits_resampling_request_and_stays_open_busy() -> None:
    """Applying should publish typed intent without dropping the modal wash."""

    _app()
    dialog = SyntheticCanvasResolutionDialog(
        role=_role(),
        preset_source=None,
        parent=QWidget(),
    )
    requests: list[SyntheticCanvasResizeRequest] = []
    dialog.resizeRequested.connect(requests.append)
    dialog.form.width_spin.setValue(1024)
    dialog.form.height_spin.setValue(1024)
    dialog.form.mode_selector.setCurrentItem(
        SyntheticCanvasResizeScope.CANVAS_AND_LAYERS.value
    )
    dialog.form.fast_radio.setChecked(True)

    dialog.yesButton.click()

    assert requests == [
        SyntheticCanvasResizeRequest(
            dimensions=CanvasDimensions(1024, 1024),
            scope=SyntheticCanvasResizeScope.CANVAS_AND_LAYERS,
            anchor=SyntheticCanvasAnchor.CENTER,
            resampling_mode=SyntheticCanvasResamplingMode.FAST,
        )
    ]
    assert dialog.progress_bar.isVisibleTo(dialog)
    assert not dialog.form.width_spin.isEnabled()


def test_dialog_reveals_only_controls_for_the_selected_operation() -> None:
    """The primary operation switch should replace, not accumulate, settings."""

    _app()
    dialog = SyntheticCanvasResolutionDialog(
        role=_role(),
        preset_source=None,
        parent=QWidget(),
    )

    assert dialog.form.scope_options.currentWidget() is dialog.form.anchor_options

    dialog.form.mode_selector.setCurrentItem(
        SyntheticCanvasResizeScope.CANVAS_AND_LAYERS.value
    )

    assert dialog.form.scope_options.currentWidget() is dialog.form.resampling_options
    assert dialog.resize_request().scope is SyntheticCanvasResizeScope.CANVAS_AND_LAYERS


def test_scaling_quality_choices_are_horizontal_and_descriptive() -> None:
    """Scaling choices should identify their algorithms and explain their effects."""

    _app()
    dialog = SyntheticCanvasResolutionDialog(
        role=_role(),
        preset_source=None,
        parent=QWidget(),
    )

    assert isinstance(dialog.form.scaling_quality_options_layout, QVBoxLayout)
    copy_item = dialog.form.scaling_quality_options_layout.itemAt(0)
    choices_item = dialog.form.scaling_quality_options_layout.itemAt(1)
    assert copy_item is not None
    assert choices_item is not None
    assert copy_item.layout() is dialog.form.scaling_quality_copy_layout
    assert choices_item.layout() is dialog.form.scaling_quality_layout
    assert isinstance(dialog.form.scaling_quality_layout, QHBoxLayout)
    assert dialog.form.fast_radio.text() == render_application_text(
        app_text("Nearest Neighbor")
    )
    assert dialog.form.smooth_radio.text() == render_application_text(
        app_text("Qt Smooth")
    )
    assert "nearest pixel" in dialog.form.fast_radio.toolTip()
    assert "blend neighboring pixels" in dialog.form.smooth_radio.toolTip()


def test_busy_cancel_requests_cancellation_without_closing_early() -> None:
    """Cancel should preserve the blocking modal until the canvas owner terminates."""

    _app()
    dialog = SyntheticCanvasResolutionDialog(
        role=_role(),
        preset_source=None,
        parent=QWidget(),
    )
    cancellations: list[bool] = []
    dialog.cancellationRequested.connect(lambda: cancellations.append(True))
    dialog.form.width_spin.setValue(1024)
    dialog.yesButton.click()

    dialog.cancelButton.click()

    assert cancellations == [True]
    assert dialog.isModal()
    assert not dialog.cancelButton.isEnabled()
