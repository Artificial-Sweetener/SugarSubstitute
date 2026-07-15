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

"""Widget contract tests for the Cube Library update modal."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication
from qfluentwidgets import (  # type: ignore[import-untyped]
    CheckBox,
    ComboBox,
    PrimaryPushButton,
)

from substitute.application.cube_library import (
    CubeLibraryUpdateReason,
    LoadedCubeUpdateAction,
    LoadedCubeUpdateCandidate,
)
from substitute.presentation.cube_updates import CubeUpdateModal


def _app() -> QApplication:
    """Return a QApplication for widget construction."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def test_cube_update_modal_defaults_all_candidates_checked() -> None:
    """The modal should opt into updating every stale cube by default."""

    app = _app()
    candidates = (_candidate("Demo"), _candidate("Second"))
    dialog = CubeUpdateModal(candidates=candidates)

    try:
        assert dialog._title_label.text() == "Cube updates available"
        assert dialog._update_button.text() == "Update selected"
        assert isinstance(dialog._update_button, PrimaryPushButton)
        assert dialog._keep_button.text() == "Keep current"
        assert all(checkbox.isChecked() for checkbox in dialog._checkboxes.values())
        assert len(dialog._rows_frame.findChildren(CheckBox)) == 2
        assert len(dialog._rows_frame.findChildren(ComboBox)) == 4
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_cube_update_modal_returns_only_checked_candidates() -> None:
    """Unchecked rows should not be returned for update application."""

    app = _app()
    first = _candidate("Demo")
    second = _candidate("Second")
    dialog = CubeUpdateModal(candidates=(first, second))

    try:
        dialog._checkboxes[second].setChecked(False)

        assert dialog.selected_candidates() == (first,)
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_cube_update_modal_returns_explicit_row_actions() -> None:
    """Every row should produce a policy-aware update selection."""

    app = _app()
    first = _candidate("Demo")
    second = _candidate("Second")
    dialog = CubeUpdateModal(
        candidates=(first, second),
        available_versions_by_cube_id={first.cube_id: ("1.5",)},
    )

    try:
        dialog._checkboxes[second].setChecked(False)
        first_controls = dialog._row_controls[first]
        first_controls.action_combo.setCurrentText("Choose version...")
        first_controls.version_combo.setCurrentText("v1.5")

        selections = dialog.selected_update_selections()

        assert selections[0].candidate == first
        assert selections[0].action == LoadedCubeUpdateAction.SWITCH_TO_VERSION
        assert selections[0].target_version == "1.5"
        assert selections[1].candidate == second
        assert selections[1].action == LoadedCubeUpdateAction.KEEP_PINNED
        assert selections[1].target_version == second.current_version
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_cube_update_modal_uses_version_language() -> None:
    """The modal should not expose ref, revision, hash, or SHA terminology."""

    app = _app()
    candidate = _candidate("Demo")
    dialog = CubeUpdateModal(candidates=(candidate,))

    try:
        labels = [
            dialog._row_controls[candidate].action_combo.itemText(index)
            for index in range(dialog._row_controls[candidate].action_combo.count())
        ]
        joined = " ".join(labels)
        assert "Update to v2.0" in labels
        assert "Keep v1.0" in labels
        assert "Update all v1.0 instances" in labels
        assert "Choose version..." in labels
        assert "Always use newest version" in labels
        assert "ref" not in joined.lower()
        assert "revision" not in joined.lower()
        assert "hash" not in joined.lower()
        assert "sha" not in joined.lower()
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def _candidate(alias: str) -> LoadedCubeUpdateCandidate:
    """Build one modal candidate."""

    return LoadedCubeUpdateCandidate(
        workflow_id="workflow-1",
        workflow_name="Workflow One",
        cube_alias=alias,
        cube_id="owner/repo/demo.cube",
        current_version="1.0",
        latest_version="2.0",
        catalog_revision="rev",
        display_name="Demo Cube",
        reason=CubeLibraryUpdateReason.VERSION_DRIFT,
    )
