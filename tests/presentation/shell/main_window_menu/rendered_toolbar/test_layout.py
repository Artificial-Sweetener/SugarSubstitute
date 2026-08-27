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

"""Rendered integration harness for the shared workflow/settings toolbar."""

from __future__ import annotations

from typing import Any, cast

import pytest
from PySide6.QtWidgets import QSizePolicy, QWidget

from substitute.application.node_behavior import FieldPresentation
from substitute.presentation.editor.panel.overrides_controller import (
    GlobalOverridesManager,
)
from substitute.presentation.widgets import SeedBox
from tests.presentation.shell.main_window_menu.rendered_toolbar.support import (
    assert_natural_override_gaps as _assert_natural_override_gaps,
    field_spec as _field_spec,
    override_snapshot as _override_snapshot,
    rebuild_real_overrides as _rebuild_real_overrides,
    render_manager_toolbar as _render_manager_toolbar,
    seed_override_geometry as _seed_override_geometry,
    show_settings_search as _show_settings_search,
    show_workflow_restart as _show_workflow_restart,
    show_workflow_without_restart as _show_workflow_without_restart,
    widget_gap as _widget_gap,
)
from tests.support.qt.lifecycle import destroy_qt_object


def test_seed_aliases_preserve_seedbox_owned_toolbar_geometry() -> None:
    """Seed aliases should consume one behavior-owned toolbar render contract."""

    seed = SeedBox()
    noise_seed = SeedBox()
    seed_spec = _field_spec(
        override_key="seed",
        field_key="seed",
        value=1,
        order=30,
        field_type="INT",
        presentation=FieldPresentation.SEED_BOX,
    )
    noise_seed_spec = _field_spec(
        override_key="seed",
        field_key="noise_seed",
        value=1,
        order=30,
        field_type="INT",
        presentation=FieldPresentation.SEED_BOX,
    )

    try:
        GlobalOverridesManager._apply_toolbar_widget_size(seed_spec, seed)
        GlobalOverridesManager._apply_toolbar_widget_size(noise_seed_spec, noise_seed)

        assert seed.height() == 33
        assert noise_seed.height() == seed.height()
        assert noise_seed.sizeHint() == seed.sizeHint()
        assert noise_seed.minimumSizeHint() == seed.minimumSizeHint()
        assert noise_seed.sizePolicy() == seed.sizePolicy()
        assert noise_seed.line_edit.geometry() == seed.line_edit.geometry()
        assert noise_seed.split_button.geometry() == seed.split_button.geometry()
    finally:
        destroy_qt_object(noise_seed)
        destroy_qt_object(seed)


@pytest.mark.parametrize("width", [1600, 600])
def test_cube_and_comfy_seed_aliases_render_identical_toolbar_pairs(width: int) -> None:
    """Equivalent resolved aliases should produce identical production toolbar UI."""

    cube = _render_manager_toolbar(width, seed_field_key="seed")
    direct = _render_manager_toolbar(width, seed_field_key="noise_seed")
    try:
        _show_workflow_without_restart(cube)
        _show_workflow_without_restart(direct)

        cube_geometry = _seed_override_geometry(cube)
        direct_geometry = _seed_override_geometry(direct)

        assert cube_geometry == direct_geometry
        assert cube_geometry[0] == "Seed"
        assert cube_geometry[1] is True
    finally:
        cube.close()
        direct.close()


def test_cached_toolbar_seed_control_rebuilds_equally_across_alias_switches() -> None:
    """Document switching should not retain alias-specific label or widget geometry."""

    harness = _render_manager_toolbar(800, seed_field_key="seed")
    try:
        _show_workflow_without_restart(harness)
        cube_geometry = _seed_override_geometry(harness)
        _old_label, old_control = harness.manager._global_override_controls["seed"]

        harness.snapshot_source.set_snapshot(_override_snapshot("noise_seed"))
        direct_geometry = _seed_override_geometry(harness)
        _new_label, direct_control = harness.manager._global_override_controls["seed"]

        assert direct_control is not old_control
        assert direct_geometry == cube_geometry

        harness.snapshot_source.set_snapshot(_override_snapshot("seed"))
        restored_geometry = _seed_override_geometry(harness)
        assert restored_geometry == cube_geometry
    finally:
        harness.close()


def test_settings_toolbar_search_is_centered_when_visible() -> None:
    """Settings mode should center the production search widget."""

    harness = _render_manager_toolbar(1200)
    try:
        _show_settings_search(harness)

        search = harness.parts.settings_toolbar_search_box.geometry()
        toolbar_center = harness.parts.menu_bar.rect().center().x()

        assert abs(search.center().x() - toolbar_center) <= 1
    finally:
        harness.close()


def test_settings_toolbar_search_stays_centered_with_restart_visible() -> None:
    """Settings search should remain centered while restart advisory is visible."""

    harness = _render_manager_toolbar(1200)
    try:
        _show_settings_search(harness)
        harness.parts.pending_restart_button.set_count(1)
        harness.parts.pending_restart_button.set_collapsed(False)
        harness.settle_layout()

        search = harness.parts.settings_toolbar_search_box.geometry()
        toolbar_center = harness.parts.menu_bar.rect().center().x()

        assert abs(search.center().x() - toolbar_center) <= 1
        assert (
            harness.parts.pending_restart_button.geometry().right()
            == harness.parts.menu_bar.width()
            - harness.parts.menu_bar_layout.contentsMargins().right()
            - 1
        )
    finally:
        harness.close()


def test_settings_route_blocks_real_override_toolbar_rendering() -> None:
    """The real override manager must not mount toolbar widgets in Settings."""

    harness = _render_manager_toolbar(1200)
    try:
        _show_workflow_without_restart(harness)
        workflow_widgets = _rebuild_real_overrides(harness)
        assert all(
            harness.parts.menu_bar_layout.indexOf(widget) >= 0
            for widget in workflow_widgets
        )

        _show_settings_search(harness)
        harness.manager.rebuild_active_override_controls()
        harness.settle_layout()

        assert all(
            harness.parts.menu_bar_layout.indexOf(widget) == -1
            for widget in workflow_widgets
        )
        assert not any(widget.isVisible() for widget in workflow_widgets)
    finally:
        harness.close()


def test_real_override_manager_packs_controls_left_and_restart_right() -> None:
    """The real override manager path should pack controls and right-align restart."""

    harness = _render_manager_toolbar(1600)
    try:
        _show_workflow_restart(harness)
        widgets = _rebuild_real_overrides(harness)

        restart_right_gap = (
            harness.parts.menu_bar.width()
            - harness.parts.menu_bar_layout.contentsMargins().right()
            - harness.parts.pending_restart_button.geometry().right()
            - 1
        )

        _assert_natural_override_gaps(
            widgets,
            spacing=harness.parts.menu_bar_layout.spacing(),
        )
        assert restart_right_gap == 0
        assert _widget_gap(widgets[-1], harness.parts.pending_restart_button) > 200
    finally:
        harness.close()


def test_real_override_harness_catches_missing_absorber_reconciliation() -> None:
    """The harness must fail when no production path restores the right absorber."""

    harness = _render_manager_toolbar(1600)
    try:
        _show_workflow_restart(harness)
        leading_spacer = harness.root.findChild(QWidget, "RestartToolbarLeadingSpacer")
        assert leading_spacer is not None
        harness.parts.menu_bar.removeEventFilter(harness.parts.pending_restart_button)
        harness.parts.menu_bar_layout.removeWidget(leading_spacer)
        leading_spacer.hide()
        delattr(cast(Any, harness.manager.mainwindow), "pendingRestartButton")
        widgets = _rebuild_real_overrides(harness)

        with pytest.raises(AssertionError):
            _assert_natural_override_gaps(
                widgets,
                spacing=harness.parts.menu_bar_layout.spacing(),
            )
    finally:
        harness.close()


def test_real_override_manager_starved_toolbar_does_not_spread_controls() -> None:
    """Width pressure should not distribute slack between real override widgets."""

    harness = _render_manager_toolbar(600)
    try:
        _show_workflow_restart(harness)
        widgets = _rebuild_real_overrides(harness)
        leading_spacer = harness.root.findChild(QWidget, "RestartToolbarLeadingSpacer")

        assert leading_spacer is not None
        assert harness.parts.menu_bar_layout.indexOf(leading_spacer) == -1
        _assert_natural_override_gaps(
            widgets,
            spacing=harness.parts.menu_bar_layout.spacing(),
        )
    finally:
        harness.close()


def test_override_controls_yield_without_absorbing_toolbar_slack() -> None:
    """Field controls should shrink when needed without absorbing toolbar slack."""

    harness = _render_manager_toolbar(1600)
    try:
        _show_workflow_restart(harness)
        widgets = _rebuild_real_overrides(harness)

        assert all(
            widget.sizePolicy().horizontalPolicy() is QSizePolicy.Policy.Maximum
            for widget in widgets[1::2]
        )
        assert harness.parts.menu_bar_layout.minimumSize().width() <= 600
        _assert_natural_override_gaps(
            widgets,
            spacing=harness.parts.menu_bar_layout.spacing(),
        )
    finally:
        harness.close()


def test_yielding_controls_preserve_labels_under_width_pressure() -> None:
    """Yielding field controls should prevent avoidable override-label clipping."""

    harness = _render_manager_toolbar(600)
    try:
        _show_workflow_restart(harness)
        widgets = _rebuild_real_overrides(harness)
        labels = widgets[::2]
        controls = widgets[1::2]

        label_minimum_widths = tuple(
            label.minimumSizeHint().width() for label in labels
        )

        assert tuple(label.width() for label in labels) == label_minimum_widths
        assert all(
            control.width() >= control.minimumSizeHint().width() for control in controls
        )
        assert harness.parts.menu_bar_layout.minimumSize().width() <= 600
    finally:
        harness.close()


def test_real_override_manager_stays_packed_after_settings_search_hides() -> None:
    """Leaving Settings after rebuild should not leave override widgets spread."""

    harness = _render_manager_toolbar(1600)
    try:
        _show_settings_search(harness)
        harness.parts.pending_restart_button.set_count(1)
        harness.parts.pending_restart_button.set_collapsed(False)
        _show_workflow_restart(harness)
        widgets = _rebuild_real_overrides(harness)
        harness.parts.settings_toolbar_search_box.setVisible(False)
        harness.settle_layout()

        _assert_natural_override_gaps(
            widgets,
            spacing=harness.parts.menu_bar_layout.spacing(),
        )
        assert _widget_gap(widgets[-1], harness.parts.pending_restart_button) > 200
    finally:
        harness.close()


def test_real_override_manager_recompacts_cached_controls_on_rebuild() -> None:
    """Cached override controls should be repaired before reuse shortcuts return."""

    harness = _render_manager_toolbar(1600)
    try:
        _show_workflow_without_restart(harness)
        widgets = _rebuild_real_overrides(harness)
        leading_spacer = harness.root.findChild(QWidget, "RestartToolbarLeadingSpacer")
        assert leading_spacer is not None
        assert harness.parts.menu_bar_layout.indexOf(leading_spacer) >= 0
        assert (
            _widget_gap(widgets[-1], leading_spacer)
            == harness.parts.menu_bar_layout.spacing()
        )
        for widget in widgets:
            widget.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )
            if widget.maximumWidth() < 16_777_215:
                widget.setMaximumWidth(16_777_215)
            widget.updateGeometry()
        harness.settle_layout()

        harness.manager.rebuild_active_override_controls()
        harness.settle_layout()

        _assert_natural_override_gaps(
            widgets,
            spacing=harness.parts.menu_bar_layout.spacing(),
        )
        for widget in widgets:
            expected_policy = (
                QSizePolicy.Policy.Fixed
                if widget in widgets[::2]
                else QSizePolicy.Policy.Maximum
            )
            assert widget.sizePolicy().horizontalPolicy() is expected_policy
        assert (
            _widget_gap(widgets[-1], leading_spacer)
            == harness.parts.menu_bar_layout.spacing()
        )
    finally:
        harness.close()
