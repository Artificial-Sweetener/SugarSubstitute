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

"""Compose passive cube-section widget shells for the editor panel."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import cast

from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    CheckableMenu,
    FluentIcon as FIF,
    MenuIndicatorType,
    SubtitleLabel,
)

from sugarsubstitute_shared.presentation.localization import set_localized_tooltip
from substitute.presentation.editor.panel.cube_identity_header import (
    build_cube_identity_header,
)
from substitute.presentation.editor.panel.widgets.cube_section import CubeSectionView
from substitute.presentation.editor.panel.widgets.masonry_grid_layout import (
    EDITOR_SECTION_GAP,
    MasonryGridLayout,
)
from substitute.presentation.editor.panel.widgets.runtime_issue_card import (
    build_runtime_issue_card,
)
from substitute.presentation.editor.utils.create_vbox import create_vbox
from substitute.presentation.widgets.menu_buttons import (
    ToggleTransparentDropDownToolButton,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_info,
    log_timing,
    log_warning,
)

_LOGGER = get_logger("presentation.editor.panel.widgets.cube_section")


@dataclass(frozen=True, slots=True)
class CubeSectionWidgetParts:
    """Carry the passive widgets that make up one cube section."""

    widget: CubeSectionView
    grid_layout: MasonryGridLayout
    header_label: SubtitleLabel
    reveal_button: ToggleTransparentDropDownToolButton
    reveal_menu: CheckableMenu


class CubeSectionBuilder:
    """Compose passive cube-section widgets for an editor panel host."""

    def __init__(
        self,
        *,
        parent: QWidget,
        cube_headers: dict[str, SubtitleLabel],
        cube_states: Callable[[], Mapping[str, object]],
        cube_visibility_buttons: dict[str, ToggleTransparentDropDownToolButton],
        cube_visibility_menus: dict[str, CheckableMenu],
        schedule_metrics_refresh: Callable[[], None] | None,
    ) -> None:
        """Store the owning panel bindings used during shell construction."""

        self._parent = parent
        self._cube_headers = cube_headers
        self._cube_states = cube_states
        self._cube_visibility_buttons = cube_visibility_buttons
        self._cube_visibility_menus = cube_visibility_menus
        self._schedule_metrics_refresh = schedule_metrics_refresh

    def build_cube_section(self, route_key: str) -> CubeSectionWidgetParts:
        """Build the passive wrapper and layouts for one normal cube section."""

        build_started_at = perf_counter()
        header_label = self._build_header_label(route_key)
        header_bar = QWidget()
        header_layout = QHBoxLayout(header_bar)
        shows_title = self._section_shows_title(route_key)
        header_layout.setContentsMargins(
            4,
            0,
            0,
            EDITOR_SECTION_GAP if shows_title else 0,
        )
        header_layout.setSpacing(6)
        header_layout.addWidget(header_label)
        header_label.setVisible(shows_title)
        header_layout.addItem(
            QSpacerItem(
                10,
                1,
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum,
            )
        )

        reveal_button = ToggleTransparentDropDownToolButton(FIF.VIEW, header_bar)
        set_localized_tooltip(reveal_button, "Reveal Hidden Cards")
        reveal_menu = CheckableMenu(
            parent=header_bar,
            indicatorType=MenuIndicatorType.CHECK,
        )
        reveal_button.set_popup_menu(reveal_menu)
        header_layout.addWidget(reveal_button)
        self._cube_visibility_buttons[route_key] = reveal_button
        self._cube_visibility_menus[route_key] = reveal_menu

        prompt_area = create_vbox(spacing=0)
        grid_layout = MasonryGridLayout()
        widget = self._build_section_widget(
            route_key=route_key,
            header_bar=header_bar,
            prompt_area=prompt_area,
            grid_layout=grid_layout,
        )
        log_timing(
            _LOGGER,
            "Built passive cube-section widget shell",
            started_at=build_started_at,
            cube_alias=route_key,
            level="debug",
        )
        return CubeSectionWidgetParts(
            widget=widget,
            grid_layout=grid_layout,
            header_label=header_label,
            reveal_button=reveal_button,
            reveal_menu=reveal_menu,
        )

    def build_error_cube_widget(
        self,
        route_key: str,
        *,
        issue_lines: tuple[str, ...],
    ) -> CubeSectionView:
        """Build a passive cube section that shows recoverable issue details."""

        build_started_at = perf_counter()
        header_label = self._build_header_label(route_key)
        header_bar = QWidget()
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(4, 0, 0, EDITOR_SECTION_GAP)
        header_layout.setSpacing(6)
        header_layout.addWidget(header_label)
        header_layout.addItem(
            QSpacerItem(
                10,
                1,
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum,
            )
        )
        prompt_area = create_vbox(spacing=0)
        prompt_area.setContentsMargins(12, 4, 12, 14)
        prompt_area.addWidget(build_runtime_issue_card(issue_lines))
        widget = self._build_section_widget(
            route_key=route_key,
            header_bar=header_bar,
            prompt_area=prompt_area,
            grid_layout=MasonryGridLayout(),
        )
        widget.setIssueSeverity("error")
        widget.setIssueMessages(issue_lines)
        log_info(
            _LOGGER,
            "Built cube-section runtime issue widget",
            cube_alias=route_key,
            issue_count=len(issue_lines),
        )
        log_timing(
            _LOGGER,
            "Built passive cube-section issue widget",
            started_at=build_started_at,
            cube_alias=route_key,
            level="debug",
        )
        return widget

    def _section_shows_title(self, route_key: str) -> bool:
        """Return whether projected graph state uses cube title chrome."""

        cube_state = self._cube_states().get(route_key)
        return bool(getattr(cube_state, "shows_cube_section_title", True))

    def _build_header_label(self, route_key: str) -> SubtitleLabel:
        """Build and register the qfluent title label for one cube section."""

        cube_state = self._cube_states().get(route_key)
        header_label = build_cube_identity_header(route_key, cube_state)
        self._cube_headers[route_key] = header_label
        return header_label

    def _build_section_widget(
        self,
        *,
        route_key: str,
        header_bar: QWidget,
        prompt_area: QVBoxLayout,
        grid_layout: MasonryGridLayout,
    ) -> CubeSectionView:
        """Build a section wrapper and attach panel height-refresh wiring."""

        widget = CubeSectionView(
            header_bar=header_bar,
            prompt_area=prompt_area,
            grid_layout=grid_layout,
            parent=self._parent,
        )
        widget.setProperty("cube_alias", route_key)
        if self._schedule_metrics_refresh is not None:
            widget.cube_height_changed.connect(self._schedule_metrics_refresh)
        try:
            widget.setObjectName(f"CubePanel-{route_key}")
        except (AttributeError, RuntimeError, TypeError) as error:
            log_warning(
                _LOGGER,
                "Failed to name cube-section widget",
                cube_alias=route_key,
                error_type=type(error).__name__,
            )
        return widget


def cube_section_builder_for_panel(panel: QWidget) -> CubeSectionBuilder:
    """Adapt one panel-shaped QWidget to cube-section construction bindings."""

    scroll = getattr(panel, "scroll", None)
    schedule_metrics_refresh = getattr(scroll, "schedule_metrics_refresh", None)
    return CubeSectionBuilder(
        parent=panel,
        cube_headers=cast(dict[str, SubtitleLabel], getattr(panel, "cube_headers", {})),
        cube_states=lambda: cast(
            Mapping[str, object], getattr(panel, "_cube_states", {})
        ),
        cube_visibility_buttons=cast(
            dict[str, ToggleTransparentDropDownToolButton],
            getattr(panel, "_cube_visibility_btns", {}),
        ),
        cube_visibility_menus=cast(
            dict[str, CheckableMenu],
            getattr(panel, "_cube_visibility_menus", {}),
        ),
        schedule_metrics_refresh=(
            cast(Callable[[], None], schedule_metrics_refresh)
            if callable(schedule_metrics_refresh)
            else None
        ),
    )


__all__ = [
    "CubeSectionBuilder",
    "CubeSectionWidgetParts",
    "cube_section_builder_for_panel",
]
