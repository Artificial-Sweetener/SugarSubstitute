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


from PySide6.QtWidgets import QLabel, QWidget

from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)

from substitute.domain.workflow import (
    CanvasDimensions,
    SyntheticCanvasAnchor,
    SyntheticCanvasResizeScope,
)
from substitute.presentation.dialogs.synthetic_canvas_resolution_dialog import (
    SyntheticCanvasResolutionDialog,
)
from substitute.presentation.editor.panel.dimension_presets import (
    DimensionPresetCatalog,
    DimensionPresetItem,
    DimensionPresetSection,
)
from tests.presentation.dialogs.synthetic_resolution.support import (
    _PresetSource,
    _app,
    _enabled_action,
    _role,
    _submenu,
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
