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

"""Own node-card body geometry, collapse state, and layout participation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtWidgets import QVBoxLayout, QWidget

_MAX_WIDGET_HEIGHT: Final[int] = 16777215


@dataclass
class CardBodyLayoutState:
    """Track authoritative card-body collapse and presentation state."""

    collapsed: bool = False
    animating: bool = False
    expanded_height: int = 0
    forced_collapsed: bool = False


def resolve_card_body_expanded_height(
    *,
    content_layout: QVBoxLayout,
    allow_unbounded_height: bool,
) -> int:
    """Return the current natural expanded height for one card body."""

    if allow_unbounded_height:
        return _MAX_WIDGET_HEIGHT
    return content_layout.sizeHint().height()


def ensure_card_body_layout_state(
    *,
    content_body: QWidget,
    expanded_height: int,
) -> CardBodyLayoutState:
    """Return the attached card-body state, creating it when missing."""

    state = getattr(content_body, "_card_body_layout_state", None)
    if not isinstance(state, CardBodyLayoutState):
        state = CardBodyLayoutState(expanded_height=expanded_height)
        setattr(content_body, "_card_body_layout_state", state)
        return state
    state.expanded_height = expanded_height
    return state


def apply_card_body_layout_state(
    *,
    content_body: QWidget,
    state: CardBodyLayoutState,
    allow_unbounded_height: bool,
    preserve_animation_height: bool = False,
) -> None:
    """Apply the authoritative collapse policy to body height and layout presence."""

    _sync_reveal_content_height(content_body, state.expanded_height)
    if preserve_animation_height and state.animating:
        content_body.setVisible(True)
        return
    if _body_should_rest_collapsed(state):
        _apply_collapsed_rest(content_body)
        return
    content_body.setVisible(True)
    if allow_unbounded_height:
        content_body.setMaximumHeight(_MAX_WIDGET_HEIGHT)
        return
    content_body.setMaximumHeight(state.expanded_height)
    content_body.updateGeometry()


def prepare_card_body_expand(
    *,
    content_body: QWidget,
    state: CardBodyLayoutState,
) -> None:
    """Make a collapsed body participate in layout before expansion begins."""

    state.forced_collapsed = False
    content_body.setVisible(True)
    content_body.setMaximumHeight(max(0, content_body.maximumHeight()))
    content_body.updateGeometry()


def prepare_card_body_collapse(
    *,
    content_body: QWidget,
) -> None:
    """Keep the body in the parent layout while collapse animation is running."""

    content_body.setVisible(True)
    content_body.updateGeometry()


def set_card_body_forced_collapsed(
    *,
    content_body: QWidget,
    state: CardBodyLayoutState,
    forced_collapsed: bool,
    allow_unbounded_height: bool,
) -> None:
    """Apply or clear presentation-forced body collapse without changing user state."""

    state.forced_collapsed = forced_collapsed
    apply_card_body_layout_state(
        content_body=content_body,
        state=state,
        allow_unbounded_height=allow_unbounded_height,
    )


def _body_should_rest_collapsed(state: CardBodyLayoutState) -> bool:
    """Return whether the body should be absent from parent-layout sizing."""

    return bool(state.collapsed or state.forced_collapsed)


def _apply_collapsed_rest(content_body: QWidget) -> None:
    """Apply the zero-height hidden rest state that removes layout spacing."""

    content_body.setMaximumHeight(0)
    content_body.setVisible(False)
    content_body.updateGeometry()


def _sync_reveal_content_height(content_body: QWidget, expanded_height: int) -> None:
    """Update optional clipped reveal viewports without owning their animation."""

    set_content_height = getattr(content_body, "set_content_height", None)
    if callable(set_content_height):
        set_content_height(expanded_height)


__all__ = [
    "CardBodyLayoutState",
    "apply_card_body_layout_state",
    "ensure_card_body_layout_state",
    "prepare_card_body_collapse",
    "prepare_card_body_expand",
    "resolve_card_body_expanded_height",
    "set_card_body_forced_collapsed",
]
