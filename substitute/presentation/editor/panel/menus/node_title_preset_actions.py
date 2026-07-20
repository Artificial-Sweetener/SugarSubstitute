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

"""Bind node input preset actions to node-card title rows."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypeAlias

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QWidget

from substitute.application.display_labels import beautify_label
from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.presentation.editor.panel.menus.node_input_preset_apply import (
    apply_node_input_preset,
)
from substitute.presentation.editor.panel.menus.node_input_preset_capture import (
    capture_savable_node_inputs,
)
from substitute.presentation.editor.panel.menus.node_input_preset_menu_source import (
    NodeInputPresetMenuItem,
    NodeInputPresetMenuSection,
    NodeInputPresetSource,
)
from substitute.presentation.widgets.save_preset_dialog import (
    PresetSaveScope,
    SavePresetDialog,
    preset_dialog_result,
)
from substitute.presentation.widgets.menu_model import (
    LazyMenuSubmenu,
    MenuEntry,
    MenuItem,
    MenuModel,
    MenuSection,
    MenuSeparator,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from substitute.shared.logging.logger import get_logger, log_warning
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    translate_application_message,
)

APPLY_NODE_PRESET_MENU_TEXT = app_text("Apply preset")
_LOGGER = get_logger("presentation.editor.panel.menus.node_title_preset_actions")
JsonObject: TypeAlias = dict[str, object]


@dataclass(frozen=True)
class NodeInputPresetContext:
    """Carry node input preset data needed by a node-card title menu."""

    cube_alias: str | None
    node_name: str
    node_type: str
    inputs: Mapping[str, object]
    field_specs: Mapping[str, ResolvedFieldSpec]
    cube_state: object
    input_widgets_by_field_key: Mapping[tuple[str, str, str], object]


def bind_node_title_preset_actions(
    *,
    title_row: QWidget,
    context: NodeInputPresetContext,
    preset_source: NodeInputPresetSource | None,
    dialog_parent: Callable[[], QWidget],
    is_connection: Callable[[object], bool],
    position_mapper: Callable[[QPoint], QPoint] | None = None,
) -> None:
    """Attach node preset context-menu actions to one title row."""

    if preset_source is None:
        return

    def show_menu(position: QPoint) -> None:
        """Show the node preset menu for this title row."""

        _show_node_title_preset_menu(
            title_row=title_row,
            position=position,
            context=context,
            preset_source=preset_source,
            dialog_parent=dialog_parent,
            is_connection=is_connection,
            position_mapper=position_mapper,
        )

    title_row.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    title_row.customContextMenuRequested.connect(show_menu)


def _show_node_title_preset_menu(
    *,
    title_row: QWidget,
    position: QPoint,
    context: NodeInputPresetContext,
    preset_source: NodeInputPresetSource,
    dialog_parent: Callable[[], QWidget],
    is_connection: Callable[[object], bool],
    position_mapper: Callable[[QPoint], QPoint] | None,
) -> None:
    """Build and show the node title preset context menu."""

    menu_model = preset_source.current_node_input_preset_menu_model(
        node_type=context.node_type
    )
    save_scopes = menu_model.save_scopes if menu_model is not None else ()
    savable_inputs = capture_savable_node_inputs(
        node_inputs=context.inputs,
        field_specs=context.field_specs,
        is_connection=is_connection,
    )
    has_apply_actions = menu_model is not None and bool(menu_model.sections)
    has_save_action = bool(save_scopes and savable_inputs)
    if not has_apply_actions and not has_save_action:
        return

    entries: list[MenuEntry] = []
    if has_apply_actions and menu_model is not None:
        entries.append(
            LazyMenuSubmenu(
                APPLY_NODE_PRESET_MENU_TEXT,
                entries_factory=lambda: _apply_preset_entries(
                    context,
                    menu_model.sections,
                    is_connection,
                ),
            )
        )
    if has_save_action:
        if entries:
            entries.append(MenuSeparator())

        def save_current_inputs() -> None:
            """Open the save dialog for current node inputs."""

            _save_current_node_inputs(
                title_row=title_row,
                context=context,
                preset_source=preset_source,
                scopes=save_scopes,
                inputs=savable_inputs,
                dialog_parent=dialog_parent,
            )

        entries.append(
            MenuItem(
                "node_preset.save_current",
                _save_node_preset_action_text(context.node_name),
                callback=save_current_inputs,
            )
        )
    if not entries:
        return
    global_position = (
        position_mapper(position)
        if position_mapper is not None
        else title_row.mapToGlobal(position)
    )
    menu = QFluentMenuRenderer(parent=title_row).render(
        MenuModel(entries=tuple(entries))
    )
    menu.exec(global_position)


def _apply_preset_entries(
    context: NodeInputPresetContext,
    sections: tuple[NodeInputPresetMenuSection, ...],
    is_connection: Callable[[object], bool],
) -> tuple[MenuEntry, ...]:
    """Return apply-preset submenu entries for matching node input presets."""

    entries: list[MenuEntry] = []
    show_headers = len(sections) > 1
    for section_index, section in enumerate(sections):
        if section_index > 0:
            entries.append(MenuSeparator())
        section_entries = tuple(
            _apply_preset_item(context, preset, is_connection)
            for preset in section.presets
        )
        if show_headers:
            entries.append(MenuSection(title=section.title, entries=section_entries))
        else:
            entries.extend(section_entries)
    return tuple(entries)


def _apply_preset_item(
    context: NodeInputPresetContext,
    preset: NodeInputPresetMenuItem,
    is_connection: Callable[[object], bool],
) -> MenuItem:
    """Return one menu item that applies a saved node input preset."""

    def apply_preset() -> None:
        """Apply one selected node input preset."""

        try:
            apply_node_input_preset(
                cube_state=context.cube_state,
                cube_alias=context.cube_alias,
                node_name=context.node_name,
                node_type=context.node_type,
                preset_id=preset.id,
                preset_label=preset.label,
                preset_inputs=preset.inputs,
                node_inputs=context.inputs,
                field_specs=context.field_specs,
                is_connection=is_connection,
                input_widgets_by_field_key=context.input_widgets_by_field_key,
            )
        except Exception as error:
            log_warning(
                _LOGGER,
                "Failed to apply node input preset",
                cube_alias=context.cube_alias or "",
                node_name=context.node_name,
                node_type=context.node_type,
                preset_id=preset.id,
                preset_label_length=len(preset.label),
                error_type=type(error).__name__,
            )

    return MenuItem(
        f"node_preset.apply.{preset.id}",
        preset.label,
        callback=apply_preset,
        tooltip=preset.tooltip,
    )


def _save_node_preset_action_text(node_name: str) -> str:
    """Return title-row copy for saving the current node as a preset."""

    return translate_application_message(
        "Save current %1 as preset...",
        beautify_label(node_name),
    )


def _save_node_preset_dialog_title(node_name: str) -> str:
    """Return modal title copy for naming a node preset."""

    return translate_application_message(
        "Save %1 preset",
        beautify_label(node_name),
    )


def _save_current_node_inputs(
    *,
    title_row: QWidget,
    context: NodeInputPresetContext,
    preset_source: NodeInputPresetSource,
    scopes: tuple[PresetSaveScope, ...],
    inputs: JsonObject,
    dialog_parent: Callable[[], QWidget],
) -> None:
    """Open the save dialog and persist current node inputs when accepted."""

    result = preset_dialog_result(
        SavePresetDialog(
            parent=dialog_parent(),
            title=_save_node_preset_dialog_title(context.node_name),
            scopes=scopes,
        )
    )
    if result is None:
        return
    label, scope = result
    try:
        preset_source.save_node_input_preset(
            label=label,
            node_type=context.node_type,
            inputs=inputs,
            scope=scope,
        )
    except Exception as error:
        log_warning(
            _LOGGER,
            "Failed to save node input preset",
            cube_alias=context.cube_alias or "",
            node_name=context.node_name,
            node_type=context.node_type,
            preset_label_length=len(label),
            error_type=type(error).__name__,
        )
        return
    set_fluent_tooltip_text(title_row, title_row.toolTip())


__all__ = [
    "APPLY_NODE_PRESET_MENU_TEXT",
    "NodeInputPresetContext",
    "bind_node_title_preset_actions",
]
