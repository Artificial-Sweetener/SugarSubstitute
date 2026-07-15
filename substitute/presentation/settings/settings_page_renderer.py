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

"""Render catalog-backed Settings pages."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.presentation.settings.settings_card_group import SettingsCardGroup
from substitute.presentation.settings.settings_catalog import (
    SettingsControlEntry,
    SettingsPageEntry,
    SettingsSectionEntry,
)
from substitute.presentation.settings.settings_style import (
    SETTINGS_CARD_GROUP_TOP_MARGIN,
)


class CatalogSettingsPage(QWidget):
    """Render static Settings sections from catalog entries."""

    def __init__(
        self,
        page: SettingsPageEntry,
        parent: QWidget | None = None,
    ) -> None:
        """Create a catalog-backed Settings page."""

        super().__init__(parent)
        self._page = page
        self._section_groups: dict[str, SettingsCardGroup] = {}
        self._section_control_ids: dict[str, tuple[str, ...]] = {}
        self._control_widgets: dict[str, QWidget] = {}
        self._build_layout()

    def refresh(self) -> None:
        """Reconcile visible catalog controls without rebuilding unchanged rows."""

        self._sync_sections()

    def _build_layout(self) -> None:
        """Create the page layout and initial static sections."""

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SETTINGS_CARD_GROUP_TOP_MARGIN)
        self._layout.addStretch(1)
        self._sync_sections()

    def _sync_sections(self) -> None:
        """Reconcile visible sections and controls by stable catalog ids."""

        visible_sections = self._page.visible_sections()
        visible_section_ids = {section.section_id for section in visible_sections}
        for section_id in tuple(self._section_groups):
            if section_id not in visible_section_ids:
                self._remove_section(section_id)
        for index, section in enumerate(visible_sections):
            group = self._section_group(section)
            group.set_cards(self._control_widgets_for(section))
            self._move_section_group(group, index)

    def _section_group(self, section: SettingsSectionEntry) -> SettingsCardGroup:
        """Return the stable group widget for one visible catalog section."""

        group = self._section_groups.get(section.section_id)
        if group is None:
            group = SettingsCardGroup(
                section.title,
                subtitle=section.subtitle,
                parent=self,
            )
            self._section_groups[section.section_id] = group
        else:
            group.set_heading(section.title, section.subtitle)
        return group

    def _control_widgets_for(
        self,
        section: SettingsSectionEntry,
    ) -> tuple[QWidget, ...]:
        """Return stable widgets for the visible controls in one section."""

        visible_controls = section.visible_controls()
        visible_control_ids = tuple(control.setting_id for control in visible_controls)
        stale_control_ids = set(
            self._section_control_ids.get(section.section_id, ())
        ) - set(visible_control_ids)
        for setting_id in stale_control_ids:
            self._remove_control(setting_id)
        self._section_control_ids[section.section_id] = visible_control_ids
        return tuple(self._control_widget(control) for control in visible_controls)

    def _control_widget(self, control: SettingsControlEntry) -> QWidget:
        """Return the stable widget for one catalog control."""

        widget = self._control_widgets.get(control.setting_id)
        if widget is None:
            widget = control.factory(self)
            self._control_widgets[control.setting_id] = widget
        return widget

    def _move_section_group(self, group: SettingsCardGroup, index: int) -> None:
        """Ensure a section group appears before the stretch in catalog order."""

        current_index = self._layout.indexOf(group)
        if current_index == index:
            return
        if current_index >= 0:
            item = self._layout.takeAt(current_index)
            _ = item
        self._layout.insertWidget(index, group)

    def _remove_section(self, section_id: str) -> None:
        """Remove one hidden catalog section and its owned controls."""

        for setting_id in self._section_control_ids.pop(section_id, ()):
            self._remove_control(setting_id)
        group = self._section_groups.pop(section_id)
        self._layout.removeWidget(group)
        group.setParent(None)
        group.deleteLater()

    def _remove_control(self, setting_id: str) -> None:
        """Remove one hidden catalog control widget."""

        widget = self._control_widgets.pop(setting_id, None)
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


__all__ = ["CatalogSettingsPage"]
