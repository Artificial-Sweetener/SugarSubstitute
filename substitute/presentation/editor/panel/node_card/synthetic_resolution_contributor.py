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

"""Present graph-derived synthetic canvas dimensions inside authority cards."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QHBoxLayout

from sugarsubstitute_shared.presentation.localization import app_text
from substitute.application.workflows.synthetic_canvas_resolution_role_service import (
    SyntheticCanvasResolutionRole,
)
from substitute.presentation.editor.panel.node_card.body_contribution import (
    NodeCardBodyContribution,
    NodeCardBodyContributionContext,
)
from substitute.presentation.editor.panel.widgets.field_row import (
    BuiltFieldRow,
    apply_editor_control_height,
    make_grouped_field_divider,
)
from substitute.presentation.localization import LocalizedPushButton


class SyntheticCanvasResolutionRoleResolver(Protocol):
    """Resolve a card role from one section graph and node identity."""

    def resolve_for_node(
        self,
        *,
        section_key: str,
        graph: Mapping[str, object],
        node_name: str,
        node_definitions: Mapping[str, Mapping[str, object]] | None = None,
    ) -> SyntheticCanvasResolutionRole | None:
        """Return a role only when semantic graph evidence is unambiguous."""


class SyntheticCanvasResolutionContributor:
    """Decorate authority dimension fields with one focused resize action."""

    def __init__(
        self,
        *,
        roles: SyntheticCanvasResolutionRoleResolver,
        change_requested: Callable[[SyntheticCanvasResolutionRole], None],
    ) -> None:
        """Store semantic role resolution and the shell-owned change intent."""

        self._roles = roles
        self._change_requested = change_requested

    def build(
        self,
        context: NodeCardBodyContributionContext,
    ) -> NodeCardBodyContribution | None:
        """Decorate dimensions only for a graph-authoritative node."""

        if not context.section_key:
            return None
        role = self._roles.resolve_for_node(
            section_key=context.section_key,
            graph=context.graph,
            node_name=context.node_name,
        )
        if role is None:
            return None
        field_pair = role.field_pair_for_node(context.node_name)
        if field_pair is None:
            return None
        return NodeCardBodyContribution(
            field_keys=field_pair,
            row_decorator=SyntheticCanvasResolutionRowDecorator(
                role=role,
                field_keys=field_pair,
                change_requested=self._change_requested,
            ),
        )


class SyntheticCanvasResolutionRowDecorator(QObject):
    """Lock genuine dimension fields and append one explicit resize action."""

    def __init__(
        self,
        *,
        role: SyntheticCanvasResolutionRole,
        field_keys: tuple[str, str],
        change_requested: Callable[[SyntheticCanvasResolutionRole], None],
    ) -> None:
        """Store authority identity and the shell-owned change intent."""

        super().__init__()
        self._role = role
        self._field_keys = field_keys
        self._change_requested = change_requested
        self.change_button: LocalizedPushButton | None = None

    def decorate(self, built_row: BuiltFieldRow) -> None:
        """Lock the row's original fields and append the resize action."""

        self.setParent(built_row.row)
        if built_row.dimension_actions is not None:
            built_row.dimension_actions.show_save_only()
        targets_by_key = {
            target.field_key: target.field_widget for target in built_row.text_targets
        }
        if not all(field_key in targets_by_key for field_key in self._field_keys):
            raise ValueError("Synthetic resolution row is missing an authority field")
        for field_key in self._field_keys:
            targets_by_key[field_key].setEnabled(False)

        row_layout = built_row.row.layout()
        if not isinstance(row_layout, QHBoxLayout):
            raise TypeError(
                "Synthetic resolution action requires a horizontal field row"
            )
        change_button = LocalizedPushButton(
            app_text("Resize canvas"),
            built_row.row,
        )
        apply_editor_control_height(change_button)
        change_button.setAccessibleDescription(
            app_text("Choose a new size for the Input canvas and its masks")
        )
        change_button.clicked.connect(self._request_change)
        action_index = max(0, row_layout.count() - 1)
        divider = make_grouped_field_divider(built_row.row)
        row_layout.insertWidget(
            action_index,
            divider,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        row_layout.insertWidget(
            action_index + 1,
            change_button,
            1,
            Qt.AlignmentFlag.AlignVCenter,
        )
        self.change_button = change_button

    def _request_change(self) -> None:
        """Forward the immutable authority snapshot to shell orchestration."""

        self._change_requested(self._role)


__all__ = [
    "SyntheticCanvasResolutionContributor",
    "SyntheticCanvasResolutionRowDecorator",
    "SyntheticCanvasResolutionRoleResolver",
]
