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

"""Observe direct-workflow card visibility changes at production boundaries."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import cast

from substitute.application.workflows.editor_projection_service import (
    DIRECT_WORKFLOW_SECTION_KEY,
)
from substitute.presentation.editor.panel.behavior.behavior_applier import (
    EditorBehaviorApplier,
)
from substitute.presentation.editor.panel.field_sync_controller import (
    EditorPanelFieldSyncController,
)
from substitute.presentation.editor.panel.rendering.render_transaction import (
    EditorRenderTransaction,
)
from tests.qualification.comfy.bundled_workflows.rendering_audit.models import (
    CardVisibilityEvent,
)


class ProductionCardVisibilityObserver:
    """Record production visibility mutations without recomputing their policy."""

    def __init__(self) -> None:
        """Initialize an uninstalled observer with no mutation events."""
        self._events: list[CardVisibilityEvent] = []
        self._original_behavior_visibility: Callable[..., object] | None = None
        self._original_empty_card_visibility: Callable[..., object] | None = None
        self._original_render_attach: Callable[..., object] | None = None

    def __enter__(self) -> ProductionCardVisibilityObserver:
        """Wrap the three production owners that directly reveal or hide cards."""
        if self._original_behavior_visibility is not None:
            raise RuntimeError("Production visibility observer is already installed.")
        behavior_visibility = cast(
            Callable[..., object],
            getattr(EditorBehaviorApplier, "_set_wrapper_visible"),
        )
        empty_card_visibility = cast(
            Callable[..., object],
            getattr(EditorPanelFieldSyncController, "_set_card_visible"),
        )
        render_attach = cast(
            Callable[..., object], getattr(EditorRenderTransaction, "attach_node_card")
        )
        self._original_behavior_visibility = behavior_visibility
        self._original_empty_card_visibility = empty_card_visibility
        self._original_render_attach = render_attach

        def observe_behavior_visibility(
            owner: object, alias: str, node_name: str, visible: bool
        ) -> object:
            """Record production behavior snapshot visibility application."""
            result = behavior_visibility(owner, alias, node_name, visible)
            if alias == DIRECT_WORKFLOW_SECTION_KEY:
                self._events.append(
                    _visibility_event(
                        node_name,
                        "behavior_snapshot",
                        visible,
                        _behavior_wrapper(owner, alias, node_name),
                    )
                )
            return result

        def observe_empty_card_visibility(
            owner: object, wrapper: object, visible: bool
        ) -> object:
            """Record production empty-card reconciliation visibility."""
            result = empty_card_visibility(owner, wrapper, visible)
            cube_alias = _widget_property(wrapper, "cube_alias")
            node_name = _widget_property(wrapper, "node_name")
            if cube_alias == DIRECT_WORKFLOW_SECTION_KEY and isinstance(node_name, str):
                self._events.append(
                    _visibility_event(
                        node_name, "empty_card_reconciliation", visible, wrapper
                    )
                )
            return result

        def observe_render_attach(owner: object, card: object) -> object:
            """Record production render-transaction attachment reveals."""
            result = render_attach(owner, card)
            cube_alias = _widget_property(card, "cube_alias")
            node_name = _widget_property(card, "node_name")
            if cube_alias == DIRECT_WORKFLOW_SECTION_KEY and isinstance(node_name, str):
                self._events.append(
                    _visibility_event(
                        node_name, "render_transaction_attach", True, card
                    )
                )
            return result

        setattr(
            EditorBehaviorApplier, "_set_wrapper_visible", observe_behavior_visibility
        )
        setattr(
            EditorPanelFieldSyncController,
            "_set_card_visible",
            observe_empty_card_visibility,
        )
        setattr(EditorRenderTransaction, "attach_node_card", observe_render_attach)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Restore the exact production visibility methods after observation."""
        del exc_type, exc, tb
        restorations = (
            (
                EditorBehaviorApplier,
                "_set_wrapper_visible",
                self._original_behavior_visibility,
            ),
            (
                EditorPanelFieldSyncController,
                "_set_card_visible",
                self._original_empty_card_visibility,
            ),
            (EditorRenderTransaction, "attach_node_card", self._original_render_attach),
        )
        self._original_behavior_visibility = None
        self._original_empty_card_visibility = None
        self._original_render_attach = None
        for owner, method_name, original in restorations:
            if original is not None:
                setattr(owner, method_name, original)

    def reset(self) -> None:
        """Discard visibility events from the previously completed workflow."""
        self._events.clear()

    def events(self) -> tuple[CardVisibilityEvent, ...]:
        """Return visibility operations recorded for the current workflow."""
        return tuple(self._events)


def _behavior_wrapper(owner: object, alias: str, node_name: str) -> object | None:
    """Return the wrapper addressed by production behavior-application ports."""
    ports = getattr(owner, "_ports", None)
    card_wrapper = getattr(ports, "card_wrapper", None)
    if not callable(card_wrapper):
        return None
    try:
        return cast(object | None, card_wrapper(alias, node_name))
    except (RuntimeError, TypeError):
        return None


def _widget_property(widget: object | None, property_name: str) -> object:
    """Read one Qt dynamic property from an observed production widget."""
    getter = getattr(widget, "property", None)
    if not callable(getter):
        return None
    try:
        return getter(property_name)
    except (RuntimeError, TypeError):
        return None


def _visibility_event(
    node_name: str, event: str, requested_visible: bool, wrapper: object | None
) -> CardVisibilityEvent:
    """Build one visibility event from the production operation's final state."""
    is_visible = getattr(wrapper, "isVisible", None)
    try:
        actual_visible = bool(is_visible()) if callable(is_visible) else None
    except RuntimeError:
        actual_visible = None
    base_visible = _widget_property(wrapper, "base_card_visible")
    return CardVisibilityEvent(
        node_id=node_name,
        event=event,
        requested_visible=bool(requested_visible),
        actual_visible=actual_visible,
        base_card_visible=base_visible if isinstance(base_visible, bool) else None,
    )
