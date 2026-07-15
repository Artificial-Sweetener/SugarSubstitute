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

"""Render Cube Library update choices in a qfluent modal."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
)
from shiboken6 import isValid

from substitute.application.cube_library import (
    LoadedCubeUpdateAction,
    LoadedCubeUpdateCandidate,
    LoadedCubeUpdateSelection,
)
from substitute.presentation.shell.chrome_style import (
    connect_theme_refresh,
    winui_card_border_color,
    winui_card_fill_color,
)

_DIALOG_WIDTH = 720
_MIN_DIALOG_HEIGHT = 280
_DIALOG_HEIGHT_MARGIN = 48
_CONTENT_TOP_MARGIN = 24
_CONTENT_SIDE_MARGIN = 24
_CONTENT_BOTTOM_MARGIN = 16
_CONTENT_SPACING = 12
_ACTION_BUTTON_HEIGHT = 32
_ACTION_BUTTON_MINIMUM_WIDTH = 108
_FALLBACK_PARENT: QWidget | None = None


@dataclass(frozen=True, slots=True)
class _CandidateRowControls:
    """Store widgets that define one candidate row's selected action."""

    checkbox: CheckBox
    action_combo: ComboBox
    version_combo: ComboBox


class CubeUpdateModal(MessageBoxBase):  # type: ignore[misc]
    """Ask which loaded cubes should be refreshed to the latest version."""

    def __init__(
        self,
        *,
        candidates: Sequence[LoadedCubeUpdateCandidate],
        available_versions_by_cube_id: Mapping[str, Sequence[str]] | None = None,
        parent: object | None = None,
    ) -> None:
        """Build the update selection modal."""

        parent_widget = _resolve_parent(parent)
        super().__init__(parent_widget)
        self._candidates = tuple(candidates)
        self._available_versions_by_cube_id = {
            cube_id: tuple(versions)
            for cube_id, versions in (available_versions_by_cube_id or {}).items()
        }
        self._checkboxes: dict[LoadedCubeUpdateCandidate, CheckBox] = {}
        self._row_controls: dict[LoadedCubeUpdateCandidate, _CandidateRowControls] = {}
        self._dialog_max_height = _dialog_max_height(parent_widget)

        self.setClosableOnMaskClicked(False)
        self.setModal(True)
        self.widget.setMinimumWidth(_DIALOG_WIDTH)
        self.widget.setMaximumWidth(_DIALOG_WIDTH)
        self.widget.setMaximumHeight(self._dialog_max_height)
        self.viewLayout.setContentsMargins(
            _CONTENT_SIDE_MARGIN,
            _CONTENT_TOP_MARGIN,
            _CONTENT_SIDE_MARGIN,
            _CONTENT_BOTTOM_MARGIN,
        )
        self.viewLayout.setSpacing(0)

        self._build_body_container()
        self._build_header()
        self._build_candidate_rows()
        self._build_actions()
        self._sync_body_height()
        self._apply_theme()
        connect_theme_refresh(self, self._apply_theme)

    def selected_candidates(self) -> tuple[LoadedCubeUpdateCandidate, ...]:
        """Return candidates whose checkbox is currently checked."""

        return tuple(
            candidate
            for candidate, checkbox in self._checkboxes.items()
            if checkbox.isChecked()
        )

    def selected_update_selections(self) -> tuple[LoadedCubeUpdateSelection, ...]:
        """Return one explicit update action for every candidate row."""

        selections: list[LoadedCubeUpdateSelection] = []
        for candidate, row in self._row_controls.items():
            checked = row.checkbox.isChecked()
            action = (
                _action_from_combo(row.action_combo)
                if checked
                else LoadedCubeUpdateAction.KEEP_PINNED
            )
            target_version = (
                _selected_version(row.version_combo)
                if checked
                else candidate.current_version
            )
            selections.append(
                LoadedCubeUpdateSelection(
                    candidate=candidate,
                    action=action,
                    target_version=target_version,
                )
            )
        return tuple(selections)

    def choose_updates(self) -> tuple[LoadedCubeUpdateCandidate, ...]:
        """Execute the modal and return checked candidates when accepted."""

        result = self.exec()
        if result:
            return self.selected_candidates()
        return ()

    def choose_update_selections(self) -> tuple[LoadedCubeUpdateSelection, ...]:
        """Execute the modal and return explicit actions for every row."""

        result = self.exec()
        if result:
            return self.selected_update_selections()
        return tuple(
            LoadedCubeUpdateSelection(
                candidate=candidate,
                action=LoadedCubeUpdateAction.KEEP_PINNED,
                target_version=candidate.current_version,
            )
            for candidate in self._candidates
        )

    def _build_body_container(self) -> None:
        """Create the scrollable body area above the fixed footer."""

        self._body_scroll_area = QScrollArea(self.widget)
        self._body_scroll_area.setWidgetResizable(True)
        self._body_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._body_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._body_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._body_scroll_area.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
            "QScrollArea > QWidget { background: transparent; }"
        )
        self._body_scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._body_widget = QWidget(self._body_scroll_area)
        self._body_layout = QVBoxLayout(self._body_widget)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(_CONTENT_SPACING)
        self._body_scroll_area.setWidget(self._body_widget)
        self.viewLayout.addWidget(self._body_scroll_area)

    def _build_header(self) -> None:
        """Create the title and explanatory text."""

        self._title_label = SubtitleLabel("Cube updates available", self.widget)
        self._message_label = BodyLabel(
            "Updated versions are available for loaded cubes.",
            self.widget,
        )
        self._message_label.setWordWrap(True)
        self._body_layout.addWidget(self._title_label)
        self._body_layout.addWidget(self._message_label)

    def _build_candidate_rows(self) -> None:
        """Create one checked row for each update candidate."""

        self._rows_frame = QFrame(self.widget)
        self._rows_frame.setObjectName("CubeUpdateRowsFrame")
        layout = QGridLayout(self._rows_frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)

        for row_index, candidate in enumerate(self._candidates):
            checkbox = CheckBox(self._rows_frame)
            checkbox.setChecked(True)
            checkbox.setToolTip("Update this workflow cube to the latest version")
            self._checkboxes[candidate] = checkbox

            primary = StrongBodyLabel(_primary_text(candidate), self._rows_frame)
            primary.setWordWrap(True)
            secondary = CaptionLabel(_secondary_text(candidate), self._rows_frame)
            secondary.setWordWrap(True)
            action_combo = ComboBox(self._rows_frame)
            action_combo.setToolTip(
                "Choose how this workflow cube should handle the update"
            )
            _populate_action_combo(action_combo, candidate=candidate)
            version_combo = ComboBox(self._rows_frame)
            version_combo.setToolTip("Choose a specific cube version")
            _populate_version_combo(
                version_combo,
                candidate=candidate,
                versions=self._available_versions_by_cube_id.get(candidate.cube_id, ()),
            )
            self._row_controls[candidate] = _CandidateRowControls(
                checkbox=checkbox,
                action_combo=action_combo,
                version_combo=version_combo,
            )

            layout.addWidget(
                checkbox, row_index * 2, 0, 2, 1, Qt.AlignmentFlag.AlignTop
            )
            layout.addWidget(primary, row_index * 2, 1)
            layout.addWidget(secondary, row_index * 2 + 1, 1)
            layout.addWidget(action_combo, row_index * 2, 2)
            layout.addWidget(version_combo, row_index * 2 + 1, 2)
        layout.setColumnStretch(1, 1)
        self._body_layout.addWidget(self._rows_frame)

    def _build_actions(self) -> None:
        """Create footer actions."""

        self.buttonGroup.show()
        self.buttonGroup.setFixedHeight(68)
        _clear_layout(self.buttonLayout)
        self.yesButton.hide()
        self.cancelButton.hide()
        self.buttonLayout.setContentsMargins(24, 16, 24, 16)
        self.buttonLayout.setSpacing(12)
        self.buttonLayout.addStretch(1)

        self._keep_button = PushButton("Keep current", self.buttonGroup)
        self._keep_button.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        self._keep_button.setMinimumWidth(_ACTION_BUTTON_MINIMUM_WIDTH)
        self._keep_button.clicked.connect(self.reject)
        self.buttonLayout.addWidget(self._keep_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self._update_button = PrimaryPushButton("Update selected", self.buttonGroup)
        self._update_button.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        self._update_button.setMinimumWidth(_ACTION_BUTTON_MINIMUM_WIDTH)
        self._update_button.clicked.connect(self.accept)
        self.buttonLayout.addWidget(
            self._update_button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

    def _sync_body_height(self) -> None:
        """Size the scroll body naturally unless parent height forces scrolling."""

        self._body_layout.activate()
        self._body_widget.adjustSize()
        content_height = self._body_widget.sizeHint().height()
        margins = self.viewLayout.contentsMargins()
        maximum_body_height = max(
            1,
            self._dialog_max_height
            - self.buttonGroup.height()
            - margins.top()
            - margins.bottom(),
        )
        needs_scroll = content_height > maximum_body_height
        self._body_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if needs_scroll
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._body_scroll_area.setFixedHeight(
            maximum_body_height
            if needs_scroll
            else min(content_height + 2, maximum_body_height)
        )

    def _apply_theme(self) -> None:
        """Refresh WinUI-style row colors for the current theme."""

        fill = _rgba_string(winui_card_fill_color())
        border = _rgba_string(winui_card_border_color())
        self._rows_frame.setStyleSheet(
            "QFrame#CubeUpdateRowsFrame {"
            f"background: {fill};"
            f"border: 1px solid {border};"
            "border-radius: 8px;"
            "}"
        )


def _primary_text(candidate: LoadedCubeUpdateCandidate) -> str:
    """Return primary row text for one candidate."""

    display_name = candidate.display_name or candidate.cube_id
    return f"{candidate.cube_alias} - {display_name}"


def _secondary_text(candidate: LoadedCubeUpdateCandidate) -> str:
    """Return secondary row text for one candidate."""

    workflow_name = candidate.workflow_name or candidate.workflow_id
    return (
        f"{workflow_name} | Current: v{candidate.current_version} | "
        f"Available: v{candidate.latest_version}"
    )


def _populate_action_combo(
    combo: ComboBox,
    *,
    candidate: LoadedCubeUpdateCandidate,
) -> None:
    """Populate the per-instance update action choices."""

    for action, label in (
        (
            LoadedCubeUpdateAction.UPDATE_INSTANCE,
            f"Update to v{candidate.latest_version}",
        ),
        (LoadedCubeUpdateAction.KEEP_PINNED, f"Keep v{candidate.current_version}"),
        (
            LoadedCubeUpdateAction.UPDATE_MATCHING_VERSION,
            f"Update all v{candidate.current_version} instances",
        ),
        (LoadedCubeUpdateAction.SWITCH_TO_VERSION, "Choose version..."),
        (LoadedCubeUpdateAction.FOLLOW_LATEST, "Always use newest version"),
    ):
        combo.addItem(label, userData=action)


def _populate_version_combo(
    combo: ComboBox,
    *,
    candidate: LoadedCubeUpdateCandidate,
    versions: Sequence[str],
) -> None:
    """Populate versions available for one cube id."""

    for version in _unique_versions(candidate, versions):
        combo.addItem(_version_label(version, candidate=candidate), userData=version)


def _unique_versions(
    candidate: LoadedCubeUpdateCandidate,
    versions: Sequence[str],
) -> tuple[str, ...]:
    """Return display versions with latest/current included once."""

    ordered: list[str] = []
    for raw_version in (candidate.latest_version, *versions, candidate.current_version):
        version = raw_version.strip()
        if not version or version in ordered:
            continue
        ordered.append(version)
    return tuple(ordered)


def _action_from_combo(combo: ComboBox) -> LoadedCubeUpdateAction:
    """Return the selected update action from a row combo box."""

    data = combo.currentData()
    if isinstance(data, LoadedCubeUpdateAction):
        return data
    try:
        return LoadedCubeUpdateAction(str(data))
    except ValueError:
        return LoadedCubeUpdateAction.UPDATE_INSTANCE


def _selected_version(combo: ComboBox) -> str | None:
    """Return the selected version from a row combo box."""

    data = combo.currentData()
    return data if isinstance(data, str) and data else None


def _version_label(
    version: str,
    *,
    candidate: LoadedCubeUpdateCandidate,
) -> str:
    """Return a compact human-readable version label."""

    suffix = ""
    if version == candidate.latest_version:
        suffix = "  Newest"
    elif version == candidate.current_version:
        suffix = "  Current"
    return f"v{version}{suffix}"


def _resolve_parent(parent: object | None) -> QWidget:
    """Return a QWidget parent because qfluent mask dialogs require one."""

    if isinstance(parent, QWidget) and isValid(parent):
        return parent
    active_window = QApplication.activeWindow()
    if isinstance(active_window, QWidget) and isValid(active_window):
        return active_window
    global _FALLBACK_PARENT
    if _FALLBACK_PARENT is None or not isValid(_FALLBACK_PARENT):
        _FALLBACK_PARENT = QWidget()
        _FALLBACK_PARENT.resize(1024, 768)
    return _FALLBACK_PARENT


def _dialog_max_height(parent: QWidget) -> int:
    """Return a dialog height cap that fits inside the parent."""

    return max(_MIN_DIALOG_HEIGHT, parent.height() - _DIALOG_HEIGHT_MARGIN)


def _clear_layout(layout: QLayout) -> None:
    """Hide widgets owned by a nested layout removed from the footer."""

    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.hide()
        nested_layout = item.layout()
        if nested_layout is not None:
            _clear_layout(nested_layout)


def _rgba_string(color: tuple[int, int, int, int]) -> str:
    """Return a Qt stylesheet rgba value from an RGBA tuple."""

    red, green, blue, alpha = color
    return f"rgba({red}, {green}, {blue}, {alpha})"


__all__ = ["CubeUpdateModal"]
