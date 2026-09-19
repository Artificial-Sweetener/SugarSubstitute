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

"""Bind regional editor widgets to durable actions and linked hover routing."""

from __future__ import annotations

from typing import Any

from substitute.presentation.editor.panel.widgets.fields.regional_mask_batch import (
    RegionalMaskBatchEditor,
)


class _PromptSourceChangeRelay:
    """Publish prompt source transitions without creating a second value authority."""

    def __init__(
        self,
        *,
        widget: Any,
        panel: Any,
        cube_alias: str,
        node_name: str,
    ) -> None:
        """Capture only the prior event value required to describe the next edit."""

        self._widget = widget
        self._panel = panel
        self._cube_alias = cube_alias
        self._node_name = node_name
        self._source_text = str(widget.toPlainText())

    def publish(self) -> None:
        """Publish one previous/current transition and advance the event cursor."""

        current_source_text = str(self._widget.toPlainText())
        previous_source_text = self._source_text
        self._source_text = current_source_text
        _publish_region_names(
            self._panel,
            self._cube_alias,
            self._node_name,
            previous_source_text,
            current_source_text,
        )


def bind_regional_panel_signals(
    widget: Any,
    panel: Any,
    *,
    cube_alias: str | None,
    node_name: str,
) -> None:
    """Connect one prompt or mask widget to regional action coordination."""

    region_hovered = getattr(widget, "regionHovered", None)
    if cube_alias is not None and region_hovered is not None:
        region_hovered.connect(
            lambda index, alias=cube_alias, name=node_name: _publish_region_hover(
                panel,
                "prompt",
                alias,
                name,
                index,
            )
        )
        text_changed = getattr(widget, "textChanged", None)
        source_text = getattr(widget, "toPlainText", None)
        if text_changed is not None and callable(source_text):
            relay = _PromptSourceChangeRelay(
                widget=widget,
                panel=panel,
                cube_alias=cube_alias,
                node_name=node_name,
            )
            setattr(widget, "_regional_prompt_source_change_relay", relay)
            text_changed.connect(relay.publish)
            _normalize_region_names(panel, cube_alias, node_name, source_kind="prompt")
    if not isinstance(widget, RegionalMaskBatchEditor):
        return
    widget.regionActionRequested.connect(
        lambda alias, name, action: panel.inputMaskClicked.emit(
            alias,
            name,
            action,
        )
    )
    widget.regionHoverChanged.connect(
        lambda index, alias=cube_alias, name=node_name: _publish_region_hover(
            panel,
            "mask",
            alias,
            name,
            index,
        )
    )


def _publish_region_hover(
    panel: Any,
    source_kind: str,
    cube_alias: str | None,
    node_name: str,
    region_index: object,
) -> None:
    """Route widget hover intent through the shell-owned regional coordinator."""

    if cube_alias is None:
        return
    mainwindow = getattr(panel, "mainwindow", None)
    coordinator = getattr(mainwindow, "regional_interaction_coordinator", None)
    handler = getattr(
        coordinator,
        "handle_prompt_hover" if source_kind == "prompt" else "handle_mask_hover",
        None,
    )
    if callable(handler):
        handler(panel, cube_alias, node_name, region_index)


def _publish_region_names(
    panel: Any,
    cube_alias: str,
    node_name: str,
    previous_source_text: str,
    current_source_text: str,
) -> None:
    """Route one prompt source transition to the regional graph invariant owner."""

    mainwindow = getattr(panel, "mainwindow", None)
    coordinator = getattr(mainwindow, "regional_interaction_coordinator", None)
    handler = getattr(coordinator, "handle_prompt_text_changed", None)
    if callable(handler):
        handler(
            panel,
            cube_alias,
            node_name,
            previous_source_text,
            current_source_text,
        )


def _normalize_region_names(
    panel: Any,
    cube_alias: str,
    node_name: str,
    *,
    source_kind: str,
) -> None:
    """Request canonical name normalization when a regional widget is mounted."""

    mainwindow = getattr(panel, "mainwindow", None)
    coordinator = getattr(mainwindow, "regional_interaction_coordinator", None)
    handler = getattr(
        coordinator,
        (
            "normalize_prompt_names_for_prompt"
            if source_kind == "prompt"
            else "normalize_prompt_names_for_mask"
        ),
        None,
    )
    if callable(handler):
        handler(panel, cube_alias, node_name)


__all__ = ["bind_regional_panel_signals"]
