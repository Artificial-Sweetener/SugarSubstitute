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

"""Reconcile node-card layout after a field changes its owned geometry."""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.presentation.editor.panel.node_card.body_layout import (
    CardBodyLayoutState,
    apply_card_body_layout_state,
    ensure_card_body_layout_state,
    resolve_card_body_expanded_height,
)

_MAX_WIDGET_HEIGHT: Final[int] = 16_777_215
_RELAYOUT_EVENT_TYPES: Final[tuple[QEvent.Type, ...]] = (
    QEvent.Type.LayoutRequest,
    QEvent.Type.Resize,
    QEvent.Type.Show,
)
_OPTIONAL_LAYOUT_SIGNAL_NAMES: Final[tuple[str, ...]] = (
    "resized",
    "layoutInvalidated",
    "contentSizeChanged",
)

try:
    from shiboken6 import isValid as _runtime_is_valid
except ImportError:  # pragma: no cover - test-stub fallback only

    def _is_valid_widget(widget: object) -> bool:
        """Treat test doubles as valid when shiboken is unavailable."""

        del widget
        return True

else:

    def _is_valid_widget(widget: object) -> bool:
        """Return whether one QWidget/QObject reference is still alive."""

        return bool(_runtime_is_valid(widget))


class _FieldWidgetRelayoutFilter(QObject):
    """Defer row and card relayout after a field changes its layout needs."""

    def __init__(
        self,
        *,
        field_widget: QWidget,
        content_body: QWidget,
        content_layout: QVBoxLayout,
        allow_unbounded_height: bool,
    ) -> None:
        """Store field and card-body references for deferred reconciliation."""

        super().__init__(field_widget)
        self._field_widget = field_widget
        self._content_body = content_body
        self._content_layout = content_layout
        self._allow_unbounded_height = allow_unbounded_height
        self._update_pending = False
        self._applying_relayout = False
        self._force_geometry_refresh_pending = False
        self._last_field_geometry_signature: tuple[int, int, int, int] | None = None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Schedule one deferred relayout when the watched field changes."""

        event_type = event.type()
        if (
            not self._applying_relayout
            and watched is self._field_widget
            and event_type in _RELAYOUT_EVENT_TYPES
        ):
            if (
                event_type == QEvent.Type.LayoutRequest
                and self._layout_request_is_settled()
            ):
                return super().eventFilter(watched, event)
            self.schedule_relayout(
                force_geometry_refresh=event_type != QEvent.Type.LayoutRequest,
                reason=f"event:{event_type.name}",
            )
        return super().eventFilter(watched, event)

    def schedule_relayout(
        self,
        *,
        force_geometry_refresh: bool = False,
        reason: str = "explicit",
    ) -> None:
        """Coalesce repeated geometry changes into one deferred relayout pass."""

        if force_geometry_refresh:
            self._force_geometry_refresh_pending = True
        if self._update_pending:
            return
        self._update_pending = True
        del reason
        QTimer.singleShot(0, self._apply_relayout)

    def _apply_relayout(self) -> None:
        """Invalidate the row and card body after one field size change."""

        self._update_pending = False
        force_geometry_refresh = self._force_geometry_refresh_pending
        self._force_geometry_refresh_pending = False
        if not _is_valid_widget(self._field_widget) or not _is_valid_widget(
            self._content_body
        ):
            return

        self._applying_relayout = True
        try:
            field_geometry_signature = self._field_geometry_signature()
            field_geometry_changed = (
                field_geometry_signature != self._last_field_geometry_signature
            )
            if force_geometry_refresh or field_geometry_changed:
                self._invalidate_parent_chain(self._field_widget.parentWidget())
            else:
                self._invalidate_parent_layouts(self._field_widget.parentWidget())
            self._content_layout.invalidate()
            expanded_height = resolve_card_body_expanded_height(
                content_layout=self._content_layout,
                allow_unbounded_height=self._allow_unbounded_height,
            )
            existing_state = _card_body_layout_state(self._content_body)
            if (
                existing_state is not None
                and not field_geometry_changed
                and existing_state.expanded_height == expanded_height
                and self._card_body_layout_is_applied(existing_state)
            ):
                self._last_field_geometry_signature = field_geometry_signature
                return
            self._invalidate_parent_chain(self._field_widget.parentWidget())
            state = ensure_card_body_layout_state(
                content_body=self._content_body,
                expanded_height=expanded_height,
            )
            apply_card_body_layout_state(
                content_body=self._content_body,
                state=state,
                allow_unbounded_height=self._allow_unbounded_height,
                preserve_animation_height=True,
            )
            self._content_body.updateGeometry()
            self._invalidate_parent_chain(self._content_body.parentWidget())
            self._notify_owner_section()
            self._last_field_geometry_signature = field_geometry_signature
        finally:
            self._applying_relayout = False

    def _field_geometry_signature(self) -> tuple[int, int, int, int]:
        """Return field geometry values that affect parent layout sizing."""

        return (
            self._field_widget.minimumHeight(),
            self._field_widget.maximumHeight(),
            self._field_widget.sizeHint().height(),
            self._field_widget.height(),
        )

    def _layout_request_is_settled(self) -> bool:
        """Return whether a layout request cannot change card-body geometry."""

        existing_state = _card_body_layout_state(self._content_body)
        return (
            existing_state is not None
            and self._last_field_geometry_signature == self._field_geometry_signature()
            and self._card_body_layout_is_applied(existing_state)
        )

    def _card_body_layout_is_applied(self, state: CardBodyLayoutState) -> bool:
        """Return whether the current body geometry reflects the layout state."""

        if state.collapsed or state.forced_collapsed:
            return self._content_body.maximumHeight() == 0
        if self._allow_unbounded_height:
            return self._content_body.maximumHeight() == _MAX_WIDGET_HEIGHT
        return self._content_body.maximumHeight() == state.expanded_height

    def _invalidate_parent_chain(self, widget: QWidget | None) -> None:
        """Invalidate layouts and geometry through the parent chain."""

        current = widget
        while current is not None and _is_valid_widget(current):
            layout = current.layout()
            if layout is not None:
                layout.invalidate()
            current.updateGeometry()
            current = current.parentWidget()

    def _invalidate_parent_layouts(self, widget: QWidget | None) -> None:
        """Invalidate parent layouts without requesting widget geometry."""

        current = widget
        while current is not None and _is_valid_widget(current):
            layout = current.layout()
            if layout is not None:
                layout.invalidate()
            current = current.parentWidget()

    def _notify_owner_section(self) -> None:
        """Ask the nearest cube section to settle after relayout."""

        current = self._content_body.parentWidget()
        while current is not None and _is_valid_widget(current):
            finalize = getattr(current, "finalize_layout_after_child_relayout", None)
            if callable(finalize):
                finalize(reason="field_relayout")
                return
            update_height = getattr(current, "update_cube_height", None)
            if callable(update_height):
                update_height()
                return
            current = current.parentWidget()


def _card_body_layout_state(content_body: QWidget) -> CardBodyLayoutState | None:
    """Return existing card-body layout state without mutating it."""

    state = getattr(content_body, "_card_body_layout_state", None)
    return state if isinstance(state, CardBodyLayoutState) else None


def bind_field_widget_card_relayout(
    *,
    field_widget: QWidget,
    content_body: QWidget,
    content_layout: QVBoxLayout,
    allow_unbounded_height: bool,
) -> None:
    """Attach generic row and card relayout behavior to one field widget."""

    relayout_filter = _FieldWidgetRelayoutFilter(
        field_widget=field_widget,
        content_body=content_body,
        content_layout=content_layout,
        allow_unbounded_height=allow_unbounded_height,
    )
    field_widget.installEventFilter(relayout_filter)
    for signal_name in _OPTIONAL_LAYOUT_SIGNAL_NAMES:
        signal = getattr(field_widget, signal_name, None)
        if signal is None:
            continue
        try:
            signal.connect(
                lambda *_args, signal_name=signal_name: (
                    relayout_filter.schedule_relayout(
                        force_geometry_refresh=True,
                        reason=f"signal:{signal_name}",
                    )
                )
            )
        except TypeError:
            continue
    setattr(field_widget, "_card_field_relayout_filter", relayout_filter)
    relayout_filter.schedule_relayout(
        force_geometry_refresh=True,
        reason="initial_bind",
    )


__all__ = ["bind_field_widget_card_relayout"]
