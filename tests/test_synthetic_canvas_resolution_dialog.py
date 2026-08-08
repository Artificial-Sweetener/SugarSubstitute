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

from typing import Protocol, cast

from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import themeColor  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)

from substitute.application.workflows.synthetic_canvas_resolution_role_service import (
    SyntheticCanvasResolutionRole,
)
from substitute.domain.workflow import (
    CanvasDimensionAuthority,
    CanvasDimensions,
    SyntheticCanvasAnchor,
    SyntheticCanvasResamplingMode,
    SyntheticCanvasResizeRequest,
    SyntheticCanvasResizeScope,
)
from substitute.presentation.dialogs.synthetic_canvas_resolution_dialog import (
    SyntheticCanvasResolutionDialog,
)
from substitute.presentation.dialogs.synthetic_canvas_anchor_button import (
    SyntheticCanvasAnchorButton,
)
from substitute.presentation.editor.panel.dimension_presets import (
    DimensionPresetCatalog,
    DimensionPresetItem,
    DimensionPresetSection,
)


class _PresetSource:
    """Provide deterministic shared presets to dialog tests."""

    def __init__(self) -> None:
        """Initialize prepared state and save calls."""

        self.prepare_reasons: list[str] = []
        self.saved_global: list[tuple[int, int]] = []
        self.saved_model: list[tuple[int, int]] = []
        self.catalog = DimensionPresetCatalog(
            sections=(
                DimensionPresetSection(
                    title="Global",
                    presets=(DimensionPresetItem("Portrait", 832, 1216),),
                ),
            ),
            model_save_label="Illustrious",
        )

    def prepare_dimension_preset_catalog(self, *, reason: str) -> None:
        """Record preparation."""

        self.prepare_reasons.append(reason)

    def current_dimension_preset_catalog(self) -> DimensionPresetCatalog:
        """Return the deterministic catalog."""

        return self.catalog

    def save_current_dimensions_globally(self, width: int, height: int) -> None:
        """Record a global save."""

        self.saved_global.append((width, height))

    def save_current_dimensions_for_model(self, width: int, height: int) -> None:
        """Record a model save."""

        self.saved_model.append((width, height))


class _MenuLike(Protocol):
    """Describe the QFluent menu surface inspected by hierarchy tests."""

    _subMenus: list[_MenuLike]
    _actions: list[_ActionLike]

    def title(self) -> str:
        """Return the visible submenu title."""


class _ActionLike(Protocol):
    """Describe one enabled action exposed by the shared preset menu."""

    def isEnabled(self) -> bool:  # noqa: N802
        """Return whether the action can be triggered."""

    def text(self) -> str:
        """Return the visible action label."""

    def trigger(self) -> None:
        """Invoke the action callback."""


def _app() -> QApplication:
    """Return the process QApplication."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _activate_hidden_dialog_layout(
    dialog: SyntheticCanvasResolutionDialog,
) -> None:
    """Resolve nested widget geometry without showing a native window."""

    dialog.widget.ensurePolished()
    dialog.widget.resize(dialog.widget.sizeHint())
    for widget in (
        dialog.widget,
        dialog.form,
        dialog.form.scope_options,
    ):
        layout = widget.layout()
        if layout is not None:
            layout.activate()
    dialog.form.anchor_options.resize(dialog.form.scope_options.size())
    anchor_layout = dialog.form.anchor_options.layout()
    if anchor_layout is not None:
        anchor_layout.activate()
    _app().processEvents()


def _submenu(menu: object, title: str) -> _MenuLike:
    """Return one rendered QFluent submenu by its visible title."""

    submenus = getattr(menu, "_subMenus", ())
    return cast(
        _MenuLike,
        next(submenu for submenu in submenus if submenu.title() == title),
    )


def _enabled_action(menu: object, text: str) -> _ActionLike:
    """Return one enabled rendered action by its visible text."""

    actions = getattr(menu, "_actions", ())
    return cast(
        _ActionLike,
        next(
            action for action in actions if action.isEnabled() and action.text() == text
        ),
    )


def test_dialog_defaults_to_centered_canvas_only_and_existing_dimension_menu() -> None:
    """The modal should reuse the complete dimension-row menu hierarchy."""

    _app()
    parent = QWidget()
    source = _PresetSource()
    dialog = SyntheticCanvasResolutionDialog(
        role=_role(),
        preset_source=source,
        parent=parent,
    )

    assert (
        dialog.form.mode_selector.currentRouteKey()
        == SyntheticCanvasResizeScope.CANVAS_ONLY.value
    )
    assert dialog.selected_anchor() is SyntheticCanvasAnchor.CENTER
    assert dialog.form.smooth_radio.isChecked()
    assert dialog.form.preset_menu_button.text() == render_application_text(
        app_text("Save or Load preset")
    )
    assert dialog.form.preset_menu_button.isEnabled()
    dimension_menu = dialog.form.preset_menu_button.menu()
    assert all(
        action.text() != render_application_text(app_text("Swap width & height"))
        for action in dimension_menu._actions
    )
    assert [submenu.title() for submenu in dimension_menu._subMenus] == [
        render_application_text(app_text("Set dimensions")),
        render_application_text(app_text("Set ratio by Width")),
        render_application_text(app_text("Set ratio by Height")),
        render_application_text(app_text("Save current dimensions")),
    ]
    preset_menu = _submenu(
        dimension_menu,
        render_application_text(app_text("Set dimensions")),
    )
    assert [submenu.title() for submenu in preset_menu._subMenus] == [
        render_application_text(app_text("Portrait")),
        render_application_text(app_text("Landscape")),
    ]
    assert not dialog.yesButton.isEnabled()
    assert source.prepare_reasons == ["resolution_dialog_opened"]
    assert not hasattr(dialog, "resize_preview")


def test_dimension_menu_shares_the_size_editor_row_without_current_readout() -> None:
    """Width, height, and their existing menu should form one concise control row."""

    _app()
    dialog = SyntheticCanvasResolutionDialog(
        role=_role(),
        preset_source=_PresetSource(),
        parent=QWidget(),
    )

    grid = dialog.form.dimension_grid
    button_index = grid.indexOf(dialog.form.preset_menu_button)
    height_index = grid.indexOf(dialog.form.height_spin)
    assert grid.getItemPosition(height_index) == (1, 2, 1, 1)
    assert grid.getItemPosition(button_index) == (1, 3, 1, 1)
    assert all(
        not label.text().startswith("Current:")
        for label in dialog.form.findChildren(QLabel)
    )
    assert any(
        label.text() == render_application_text(app_text("Preset"))
        for label in dialog.form.findChildren(QLabel)
    )


def test_dialog_retains_non_preset_dimension_actions_for_an_empty_catalog() -> None:
    """The existing menu should omit only unavailable preset selection."""

    _app()
    source = _PresetSource()
    source.catalog = DimensionPresetCatalog(sections=(), model_save_label="Illustrious")
    dialog = SyntheticCanvasResolutionDialog(
        role=_role(),
        preset_source=source,
        parent=QWidget(),
    )

    dimension_menu = dialog.form.preset_menu_button.menu()
    assert dialog.form.preset_menu_button.isEnabled()
    assert [submenu.title() for submenu in dimension_menu._subMenus] == [
        render_application_text(app_text("Set ratio by Width")),
        render_application_text(app_text("Set ratio by Height")),
        render_application_text(app_text("Save current dimensions")),
    ]


def test_dialog_does_not_infer_preset_selection_from_matching_dimensions() -> None:
    """Matching dimensions should not impersonate an explicit preset choice."""

    _app()
    source = _PresetSource()
    source.catalog = DimensionPresetCatalog(
        sections=(
            DimensionPresetSection(
                title="Global",
                presets=(DimensionPresetItem("960 x 1344", 960, 1344),),
            ),
        ),
    )
    dialog = SyntheticCanvasResolutionDialog(
        role=_role(),
        preset_source=source,
        parent=QWidget(),
    )

    assert dialog.form.preset_menu_button.text() == render_application_text(
        app_text("Save or Load preset")
    )


def test_existing_dimension_menu_applies_its_nested_preset_action() -> None:
    """The reused menu should retain its nested preset callback behavior."""

    _app()
    dialog = SyntheticCanvasResolutionDialog(
        role=_role(),
        preset_source=_PresetSource(),
        parent=QWidget(),
    )

    dimension_menu = dialog.form.preset_menu_button.menu()
    preset_menu = _submenu(
        dimension_menu,
        render_application_text(app_text("Set dimensions")),
    )
    portrait_menu = _submenu(
        preset_menu,
        render_application_text(app_text("Portrait")),
    )
    action = _enabled_action(portrait_menu, "Portrait 832 x 1216")
    action.trigger()

    assert dialog.form.dimensions() == CanvasDimensions(832, 1216)

    dialog.form.width_spin.setValue(840)

    assert dialog.form.dimensions() == CanvasDimensions(840, 1216)


def test_center_anchor_renders_a_large_live_accent_dot() -> None:
    """The center anchor should remain legible as an accent-colored spatial mark."""

    app = _app()
    parent = QWidget()
    parent.resize(1200, 900)
    dialog = SyntheticCanvasResolutionDialog(
        role=_role(),
        preset_source=None,
        parent=parent,
    )
    _activate_hidden_dialog_layout(dialog)

    buttons = dialog.findChildren(SyntheticCanvasAnchorButton)
    assert len(buttons) == 9
    center_button = next(button for button in buttons if button.isChecked())
    image = center_button.grab().toImage()
    center = center_button.rect().center()
    accent = QColor(themeColor())
    assert image.pixelColor(center).rgb() == accent.rgb()
    assert image.pixelColor(center + QPoint(4, 0)).rgb() == accent.rgb()

    bottom_left = next(
        button
        for button in buttons
        if button.anchor is SyntheticCanvasAnchor.BOTTOM_LEFT
    )
    bottom_left.click()
    app.processEvents()
    assert bottom_left.isChecked()
    assert not center_button.isChecked()
    selected_image = bottom_left.grab().toImage()
    assert selected_image.pixelColor(bottom_left.rect().center()).rgb() == accent.rgb()
    former_center_image = center_button.grab().toImage()
    white = QColor(255, 255, 255)
    assert former_center_image.pixelColor(center_button.rect().center()).rgb() == (
        white.rgb()
    )
    assert (
        former_center_image.pixelColor(
            center_button.rect().center() + QPoint(4, 0)
        ).alpha()
        < 255
    )


def test_dialog_preserves_the_fluent_modal_backing_surface() -> None:
    """The dialog body should retain the primitive-owned opaque surface styling."""

    app = _app()
    parent = QWidget()
    parent.resize(1200, 900)
    dialog = SyntheticCanvasResolutionDialog(
        role=_role(),
        preset_source=None,
        parent=parent,
    )
    _activate_hidden_dialog_layout(dialog)
    dialog.widget.repaint()
    app.processEvents()

    assert dialog.widget.objectName() == "centerWidget"
    surface_image = dialog.widget.grab().toImage()
    assert surface_image.pixelColor(QPoint(12, 12)).alpha() == 255


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


def _role() -> SyntheticCanvasResolutionRole:
    """Build one representative Prompt by Region authority role."""

    return SyntheticCanvasResolutionRole(
        section_key="Prompt by Region",
        surface_key="@synthetic/role",
        authority=CanvasDimensionAuthority(
            dimensions=CanvasDimensions(960, 1344),
            node_names=("spatial root",),
            field_pairs=(("width", "height"),),
            convergence_node_names=("sampler",),
            structural_fingerprint="structure",
            dimension_fingerprint="dimensions",
        ),
    )
