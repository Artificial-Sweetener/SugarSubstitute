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

"""Render editor-panel content with bottom-only virtual overscroll."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from PySide6.QtCore import QEvent, QObject, QTimer, Qt, Signal
from PySide6.QtGui import QResizeEvent, QShowEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QAbstractScrollArea, QWidget
from qfluentwidgets import ScrollBar  # type: ignore[import-untyped]
from shiboken6 import isValid

from substitute.shared.logging.logger import get_logger, log_timing

_LOGGER = get_logger("presentation.editor.panel.widgets.scroll_surface")


class EditorPanelScrollModel:
    """Store editor-panel scroll metrics and expose bottom-only overscroll policy."""

    def __init__(
        self,
        *,
        overscroll_policy_factor: float = 0.5,
        single_step: int = 72,
    ) -> None:
        """Initialize the scroll model with a viewport-based overscroll policy."""

        self._viewport_height = 0
        self._content_height = 0
        self._content_present = True
        self._scroll_value = 0
        self._visible_top_intent = 0
        self._single_step = max(1, single_step)
        self._overscroll_policy_factor = max(0.0, overscroll_policy_factor)
        self._overscroll_override: tuple[int, int] | None = None

    def set_viewport_height(self, height: int) -> None:
        """Store the current viewport height in pixels."""

        self._viewport_height = max(0, height)
        self._set_scroll_value_internal(self._scroll_value, update_intent=False)

    def set_content_height(self, height: int) -> None:
        """Store the current content height in pixels."""

        self._content_height = max(0, height)
        self._set_scroll_value_internal(self._scroll_value, update_intent=False)

    def set_content_present(self, present: bool) -> None:
        """Record whether the editor currently has real cube content."""

        self._content_present = present
        self._set_scroll_value_internal(self._scroll_value, update_intent=False)

    def set_overscroll_policy_factor(self, factor: float) -> None:
        """Update the viewport-based overscroll factor."""

        self._overscroll_policy_factor = max(0.0, factor)
        self._set_scroll_value_internal(self._scroll_value, update_intent=False)

    def set_overscroll_override(self, top: int, bottom: int) -> None:
        """Replace the viewport policy with one explicit overscroll override."""

        self._overscroll_override = (max(0, top), max(0, bottom))
        self._set_scroll_value_internal(self._scroll_value, update_intent=False)

    def clear_overscroll_override(self) -> None:
        """Return the model to viewport-policy-derived overscroll values."""

        self._overscroll_override = None
        self._set_scroll_value_internal(self._scroll_value, update_intent=False)

    def set_scroll_value(self, value: int, *, update_intent: bool = True) -> None:
        """Store one scroll-space value and optionally replace visible-top intent."""

        self._set_scroll_value_internal(value, update_intent=update_intent)

    def scroll_value(self) -> int:
        """Return the current scroll-space value."""

        return self._scroll_value

    def visible_top_intent(self) -> int:
        """Return the preserved non-rest visible-top target."""

        return self._visible_top_intent

    def minimum_value(self) -> int:
        """Return the minimum legal scroll value."""

        return 0

    def max_scroll_value(self) -> int:
        """Return the maximum legal scroll value."""

        if not self.has_scrollable_content():
            return 0
        return (
            self.overscroll_top() + self.base_scroll_range() + self.overscroll_bottom()
        )

    def page_step(self) -> int:
        """Return the viewport-sized page step for a linked scrollbar shell."""

        return max(1, self._viewport_height)

    def single_step(self) -> int:
        """Return the baseline single-step distance used for wheel scrolling."""

        return self._single_step

    def base_scroll_range(self) -> int:
        """Return the real-content scroll range before virtual overscroll is added."""

        return max(0, self._content_height - self._viewport_height)

    def has_scrollable_content(self) -> bool:
        """Return whether the editor has real overflow content to scroll."""

        return self._content_present and self.base_scroll_range() > 0

    def should_show_scrollbar(self) -> bool:
        """Return whether the editor should expose a visible scrollbar affordance."""

        return self.has_scrollable_content()

    def overscroll_top(self) -> int:
        """Return the effective virtual overscroll above content start."""

        return self._effective_overscroll()[0]

    def overscroll_bottom(self) -> int:
        """Return the effective virtual overscroll below content end."""

        return self._effective_overscroll()[1]

    def rest_scroll_value(self) -> int:
        """Return the normal top-aligned resting scroll position."""

        return self.overscroll_top()

    def visible_content_top(self) -> int:
        """Return the content-space y coordinate at the top of the viewport."""

        return self._scroll_value - self.overscroll_top()

    def content_widget_y(self) -> int:
        """Return the viewport-local y position for the real content widget."""

        return self.overscroll_top() - self._scroll_value

    def content_y_to_scroll_value(self, y: int) -> int:
        """Convert one content-space y coordinate into a scroll-space value."""

        return self._clamp_scroll_value(y + self.overscroll_top())

    def _effective_overscroll(self) -> tuple[int, int]:
        """Return the active top and bottom overscroll values."""

        if not self.has_scrollable_content():
            return (0, 0)
        if self._overscroll_override is not None:
            return self._overscroll_override
        overscroll = max(
            0,
            round(self._viewport_height * self._overscroll_policy_factor),
        )
        return (0, overscroll)

    def _clamp_scroll_value(self, value: int) -> int:
        """Clamp one proposed scroll value to the current legal range."""

        return max(self.minimum_value(), min(int(value), self.max_scroll_value()))

    def _set_scroll_value_internal(self, value: int, *, update_intent: bool) -> None:
        """Clamp and store one scroll value, optionally replacing visible intent."""

        self._scroll_value = self._clamp_scroll_value(value)
        if update_intent:
            self._visible_top_intent = self.visible_content_top()


@dataclass(frozen=True, slots=True)
class EditorScrollMetricsSignature:
    """Describe the applied editor scroll metrics for redundant refresh skips."""

    viewport_width: int
    viewport_height: int
    content_height: int
    max_scroll_value: int
    scroll_value: int
    content_present: bool


class EditorPanelScrollSurface(QAbstractScrollArea):
    """Host editor-panel content while the app owns the scroll range."""

    _DEFAULT_WHEEL_STEP = 72
    metrics_refreshed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize a scroll surface with QFluent scrollbar chrome."""

        super().__init__(parent)
        self._content_widget: QWidget | None = None
        self._widget_resizable = False
        self._refresh_pending = False
        self._refresh_needed_while_hidden = False
        self._refresh_in_progress = False
        self._refresh_requested_during_refresh = False
        self._suppress_content_refresh_events = False
        self._last_metrics_signature: EditorScrollMetricsSignature | None = None
        self._coalesced_refresh_count = 0
        self._signature_skip_count = 0
        self._scrollbar_sync_in_progress = False
        self._model = EditorPanelScrollModel(single_step=self._default_wheel_step())
        self.setFrameShape(QAbstractScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.verticalScrollBar().valueChanged.connect(self._on_scrollbar_value_changed)
        self._fluent_vertical_scroll_bar = ScrollBar(Qt.Orientation.Vertical, self)
        self._sync_scrollbar_from_model()

    def setWidgetResizable(self, resizable: bool) -> None:  # noqa: N802
        """Set whether the content widget should track viewport width."""

        self._widget_resizable = resizable
        self._schedule_refresh()

    def widgetResizable(self) -> bool:  # noqa: N802
        """Return whether the content widget tracks viewport width."""

        return self._widget_resizable

    def setWidget(self, widget: QWidget) -> None:  # noqa: N802
        """Attach the root content widget to the scroll viewport."""

        previous_widget = self._content_widget
        if previous_widget is widget:
            self._schedule_refresh()
            return
        if previous_widget is not None and isValid(previous_widget):
            previous_widget.removeEventFilter(self)
            previous_widget.setParent(None)

        self._content_widget = widget
        widget.setParent(self.viewport())
        widget.installEventFilter(self)
        widget.show()
        self._schedule_refresh()

    def widget(self) -> QWidget | None:
        """Return the attached content widget."""

        return self._content_widget

    def visible_content_top(self) -> int:
        """Return the content-space y coordinate at the viewport top."""

        return self._model.visible_content_top()

    def visible_content_bottom(self) -> int:
        """Return the content-space y coordinate at the viewport bottom."""

        return self._model.visible_content_top() + max(0, self.viewport().height())

    def content_y_to_scroll_value(self, y: int) -> int:
        """Convert one content-space y coordinate into scroll-space."""

        return self._model.content_y_to_scroll_value(y)

    def schedule_metrics_refresh(self) -> None:
        """Request a coalesced metrics refresh on the next event-loop turn."""

        self._schedule_refresh()

    def refresh_metrics_now(self) -> None:
        """Synchronously recompute content geometry and scroll metrics."""

        if not isValid(self):
            return
        self._refresh_pending = False
        if not self.isVisible():
            self._refresh_needed_while_hidden = True
            return
        if self._refresh_in_progress:
            self._refresh_requested_during_refresh = True
            self._coalesced_refresh_count += 1
            return
        self._refresh_metrics()

    def overscroll_top(self) -> int:
        """Return the effective top overscroll."""

        return self._model.overscroll_top()

    def overscroll_bottom(self) -> int:
        """Return the effective bottom overscroll."""

        return self._model.overscroll_bottom()

    def rest_scroll_value(self) -> int:
        """Return the normal top-aligned resting scroll value."""

        return self._model.rest_scroll_value()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Refresh content metrics after viewport geometry changes."""

        super().resizeEvent(event)
        self._schedule_refresh()

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh deferred metrics after the scroll surface becomes visible."""

        super().showEvent(event)
        if self._refresh_needed_while_hidden:
            self._refresh_needed_while_hidden = False
            self._schedule_refresh()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Refresh scroll metrics when the content geometry changes."""

        try:
            content_widget = self._content_widget
            if (
                content_widget is not None
                and isValid(content_widget)
                and watched is content_widget
                and event.type()
                in {
                    QEvent.Type.LayoutRequest,
                    QEvent.Type.Resize,
                    QEvent.Type.Show,
                    QEvent.Type.Hide,
                }
            ):
                self._schedule_refresh()
            return super().eventFilter(watched, event)
        except RuntimeError:
            return False

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Scroll the content by updating the app-owned scrollbar value."""

        scroll_bar = self.verticalScrollBar()
        pixel_delta = event.pixelDelta().y()
        if pixel_delta:
            scroll_bar.setValue(scroll_bar.value() - pixel_delta)
            event.accept()
            return

        angle_delta = event.angleDelta().y()
        if angle_delta == 0:
            super().wheelEvent(event)
            return

        notches = angle_delta / 120.0
        scroll_bar.setValue(
            scroll_bar.value() - round(notches * self._model.single_step())
        )
        event.accept()

    def _on_scrollbar_value_changed(self, value: int) -> None:
        """Render one scrollbar change through the scroll model."""

        if self._scrollbar_sync_in_progress:
            return
        self._model.set_scroll_value(value)
        self._sync_content_widget_position()

    def _schedule_refresh(self) -> None:
        """Coalesce one geometry refresh onto the next event-loop turn."""

        if not self.isVisible():
            if self._refresh_needed_while_hidden:
                return
            self._refresh_needed_while_hidden = True
            return
        if self._suppress_content_refresh_events:
            self._coalesced_refresh_count += 1
            return
        if self._refresh_in_progress:
            self._refresh_requested_during_refresh = True
            self._coalesced_refresh_count += 1
            return
        if self._refresh_pending:
            self._coalesced_refresh_count += 1
            return
        self._refresh_pending = True
        QTimer.singleShot(0, self._refresh_metrics)

    def _refresh_metrics(self) -> None:
        """Recompute content geometry and update scroll range."""

        if not isValid(self):
            return
        refresh_started_at = perf_counter()
        self._refresh_pending = False
        self._refresh_in_progress = True
        self._refresh_requested_during_refresh = False
        try:
            content_widget = self._content_widget
            try:
                viewport = self.viewport()
                viewport_width = max(1, viewport.width())
                viewport_height = max(1, viewport.height())
            except RuntimeError:
                return
            content_height = 0

            if content_widget is not None and isValid(content_widget):
                self._suppress_content_refresh_events = True
                try:
                    if (
                        self._widget_resizable
                        and content_widget.width() != viewport_width
                    ):
                        content_widget.resize(
                            viewport_width,
                            max(1, content_widget.height()),
                        )
                        content_widget.updateGeometry()
                    content_layout = content_widget.layout()
                    if content_layout is not None:
                        content_layout.activate()
                    content_height = max(
                        0,
                        content_widget.sizeHint().height(),
                        content_widget.minimumSizeHint().height(),
                    )
                    content_widget.resize(viewport_width, max(1, content_height))
                finally:
                    self._suppress_content_refresh_events = False

            self._model.set_viewport_height(viewport_height)
            self._model.set_content_height(content_height)
            self._model.set_content_present(content_height > 0)
            signature = EditorScrollMetricsSignature(
                viewport_width=viewport_width,
                viewport_height=viewport_height,
                content_height=content_height,
                max_scroll_value=self._model.max_scroll_value(),
                scroll_value=self._model.scroll_value(),
                content_present=content_height > 0,
            )
            if signature == self._last_metrics_signature:
                self._signature_skip_count += 1
                return
            self._last_metrics_signature = signature
            self._sync_scrollbar_from_model()
            self._sync_content_widget_position()
            log_timing(
                _LOGGER,
                "Refreshed editor panel scroll surface metrics",
                started_at=refresh_started_at,
                level="debug",
                viewport_height=viewport_height,
                content_height=content_height,
                overscroll_top=self._model.overscroll_top(),
                overscroll_bottom=self._model.overscroll_bottom(),
                max_scroll_value=self._model.max_scroll_value(),
                scroll_value=self._model.scroll_value(),
                coalesced_refresh_count=self._coalesced_refresh_count,
                signature_skip_count=self._signature_skip_count,
            )
            self.metrics_refreshed.emit()
        finally:
            self._refresh_in_progress = False
            if self._refresh_requested_during_refresh and self.isVisible():
                self._refresh_requested_during_refresh = False
                self._schedule_refresh()

    def _sync_scrollbar_from_model(self) -> None:
        """Mirror model metrics onto Qt and QFluent scrollbars."""

        scroll_bar = self.verticalScrollBar()
        self._scrollbar_sync_in_progress = True
        scroll_bar.setPageStep(self._model.page_step())
        scroll_bar.setSingleStep(self._model.single_step())
        scroll_bar.setRange(self._model.minimum_value(), self._model.max_scroll_value())
        scroll_bar.setValue(self._model.scroll_value())
        self._scrollbar_sync_in_progress = False
        self._fluent_vertical_scroll_bar.setPageStep(scroll_bar.pageStep())
        self._fluent_vertical_scroll_bar.setSingleStep(scroll_bar.singleStep())
        set_force_hidden = getattr(
            self._fluent_vertical_scroll_bar,
            "setForceHidden",
            None,
        )
        if callable(set_force_hidden):
            set_force_hidden(not self._model.should_show_scrollbar())

    def _sync_content_widget_position(self) -> None:
        """Move the attached content widget according to the model scroll value."""

        content_widget = self._content_widget
        if content_widget is None or not isValid(content_widget):
            return
        content_widget.move(0, self._model.content_widget_y())

    @classmethod
    def _default_wheel_step(cls) -> int:
        """Return the baseline vertical wheel distance in pixels."""

        return max(24, QApplication.wheelScrollLines() * 24, cls._DEFAULT_WHEEL_STEP)


__all__ = [
    "EditorPanelScrollModel",
    "EditorPanelScrollSurface",
    "EditorScrollMetricsSignature",
]
