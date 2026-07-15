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

"""Animate persistent generation queue side-panel visibility in shell layout."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, Property, QPropertyAnimation

from substitute.presentation.motion import (
    SIDE_PANEL_DURATION_MS,
    TRANSFORM_EASING_CURVE,
    resolve_motion_duration,
    stop_animation,
)
from substitute.presentation.shell.shell_layout_state import MIN_CANVAS_PANEL_WIDTH
from substitute.shared.logging.logger import get_logger, log_info

_EDITOR_MINIMUM_WIDTH = 1
_SIDE_MINIMUM_RENDERED_WIDTH = 0
_LOGGER = get_logger("presentation.shell.generation_queue_panel_transition")


@dataclass(frozen=True)
class _SplitterSnapshot:
    """Store splitter geometry captured at the beginning of one transition."""

    splitter: Any
    sizes: list[int]
    editor_index: int
    canvas_index: int
    side_index: int


def _clamp_progress(progress: float) -> float:
    """Return side-panel progress clamped to the valid animation range."""

    return max(0.0, min(1.0, float(progress)))


def _lerp_int(start: int, end: int, progress: float) -> int:
    """Return an integer linear interpolation for one animation frame."""

    return round(start + ((end - start) * progress))


class GenerationQueuePanelTransition(QObject):
    """Animate the persistent generation queue side panel in shell layout."""

    def __init__(self, view: Any) -> None:
        """Create a transition driver for one MainWindow-like view object."""

        super().__init__(view if isinstance(view, QObject) else None)
        self._view = view
        self._progress = self._infer_progress_from_host()
        self._start_progress = self._progress
        self._target_visible = self._progress >= 0.5
        self._animating = False
        self._start_width = self._current_rendered_width()
        self._target_width = self._open_width() if self._target_visible else 0
        self._splitter_snapshot: _SplitterSnapshot | None = None
        self._animation = QPropertyAnimation(self, b"progress", self)
        self._animation.finished.connect(self._finish_transition)

    def transition_to(self, visible: bool) -> None:
        """Animate or immediately apply requested side-panel visibility."""

        self._trace("generation queue panel transition requested", visible=visible)
        target_progress = 1.0 if visible else 0.0
        self._animation.stop()
        self._animating = False
        self._target_visible = visible
        self._progress = self._infer_progress_from_host()
        self._start_progress = self._progress
        self._start_width = self._current_rendered_width()
        self._target_width = self._open_width() if visible else 0
        self._splitter_snapshot = self._capture_splitter_snapshot()
        self._trace(
            "generation queue panel transition captured start state",
            target_visible=visible,
            start_progress=self._start_progress,
            start_width=self._start_width,
            target_width=self._target_width,
            splitter_snapshot_sizes=tuple(self._splitter_snapshot.sizes)
            if self._splitter_snapshot is not None
            else (),
        )
        self._begin_host_transition(visible)

        duration_ms = resolve_motion_duration(SIDE_PANEL_DURATION_MS)
        if duration_ms <= 0 or abs(self._progress - target_progress) < 0.0001:
            self.setProgress(target_progress)
            self._finish_transition()
            return

        self._animating = True
        self._animation.setStartValue(self._progress)
        self._animation.setEndValue(target_progress)
        self._animation.setDuration(duration_ms)
        self._animation.setEasingCurve(TRANSFORM_EASING_CURVE)
        self._animation.start()

    def stop(self) -> None:
        """Stop any in-flight side-panel animation."""

        stop_animation(self._animation)
        self._animating = False

    def is_animating(self) -> bool:
        """Return whether a side-panel transition is active."""

        return self._animating

    def _get_progress(self) -> float:
        """Return current side-panel open progress."""

        return self._progress

    def setProgress(self, progress: float) -> None:
        """Apply one rendered side-panel transition frame."""

        self._progress = _clamp_progress(progress)
        rendered_width = self._width_for_progress(self._progress)
        self._trace(
            "generation queue panel transition progress",
            requested_progress=progress,
            clamped_progress=self._progress,
            rendered_width=rendered_width,
        )
        self._apply_host_width(rendered_width)
        self._apply_splitter_progress(rendered_width)

    def _finish_transition(self) -> None:
        """Commit final target state after animation or reduced-motion jump."""

        self._animating = False
        self._progress = 1.0 if self._target_visible else 0.0
        rendered_width = self._target_width
        self._apply_host_width(rendered_width)
        self._apply_splitter_progress(rendered_width)
        self._finish_host_transition(self._target_visible)
        self._trace(
            "generation queue panel transition finished",
            target_visible=self._target_visible,
            final_width=rendered_width,
            target_progress=self._progress,
        )

    def _width_for_progress(self, progress: float) -> int:
        """Return rendered side-panel width for absolute progress value."""

        start_progress = self._start_progress
        target_progress = 1.0 if self._target_visible else 0.0
        denominator = target_progress - start_progress
        if abs(denominator) < 0.0001:
            return self._target_width
        interval_progress = _clamp_progress((progress - start_progress) / denominator)
        return _lerp_int(self._start_width, self._target_width, interval_progress)

    def _begin_host_transition(self, target_visible: bool) -> None:
        """Prepare the side-panel host for animated rendered-width changes."""

        host = self._host()
        begin = getattr(host, "begin_width_transition", None)
        if callable(begin):
            begin(target_visible=target_visible)
            return
        set_visible = getattr(host, "setVisible", None)
        if callable(set_visible):
            set_visible(True)

    def _apply_host_width(self, width: int) -> None:
        """Apply rendered width to the side-panel host."""

        host = self._host()
        apply_width = getattr(host, "apply_width_transition", None)
        if callable(apply_width):
            apply_width(max(_SIDE_MINIMUM_RENDERED_WIDTH, width))
            return
        set_fixed_width = getattr(host, "setFixedWidth", None)
        if callable(set_fixed_width):
            set_fixed_width(max(_SIDE_MINIMUM_RENDERED_WIDTH, width))

    def _finish_host_transition(self, visible: bool) -> None:
        """Commit final host visibility after a transition."""

        host = self._host()
        finish = getattr(host, "finish_width_transition", None)
        if callable(finish):
            finish(visible=visible)
            return
        set_visible = getattr(host, "setVisible", None)
        if callable(set_visible):
            set_visible(visible)

    def _apply_splitter_progress(self, rendered_width: int) -> None:
        """Apply side-panel width transfer to main splitter panes."""

        snapshot = self._splitter_snapshot
        if snapshot is None:
            self._trace(
                "generation queue panel transition splitter progress skipped no snapshot",
            )
            return

        sizes = list(snapshot.sizes)
        side_delta = rendered_width - self._start_width
        sizes[snapshot.editor_index] = max(
            _EDITOR_MINIMUM_WIDTH,
            snapshot.sizes[snapshot.editor_index],
        )
        unclamped_canvas = snapshot.sizes[snapshot.canvas_index] - side_delta
        sizes[snapshot.canvas_index] = max(
            MIN_CANVAS_PANEL_WIDTH,
            unclamped_canvas,
        )
        sizes[snapshot.side_index] = max(_SIDE_MINIMUM_RENDERED_WIDTH, rendered_width)
        snapshot.splitter.setSizes(sizes)
        layout_controller = getattr(self._view, "shell_layout_controller", None)
        remember_sizes = getattr(
            layout_controller,
            "remember_workflow_splitter_sizes",
            None,
        )
        if callable(remember_sizes):
            remember_sizes(sizes)
        self._trace(
            "generation queue panel transition applied splitter progress",
            rendered_width=rendered_width,
            start_width=self._start_width,
            side_delta=side_delta,
            canvas_clamped=unclamped_canvas < MIN_CANVAS_PANEL_WIDTH,
            new_splitter_sizes=tuple(sizes),
            snapshot_splitter_sizes=tuple(snapshot.sizes),
            editor_index=snapshot.editor_index,
            canvas_index=snapshot.canvas_index,
            side_index=snapshot.side_index,
            remembered=callable(remember_sizes),
        )

    def _capture_splitter_snapshot(self) -> _SplitterSnapshot | None:
        """Return splitter geometry needed to preserve editor width."""

        splitter = getattr(self._view, "splitter", None)
        editor_widget = getattr(self._view, "editor_output_container", None)
        canvas_widget = getattr(self._view, "canvas_tabs_container", None)
        side_widget = self._host()
        if (
            splitter is None
            or editor_widget is None
            or canvas_widget is None
            or side_widget is None
        ):
            self._trace(
                "generation queue panel transition splitter snapshot unavailable missing widget",
                splitter_present=splitter is not None,
                editor_widget_present=editor_widget is not None,
                canvas_widget_present=canvas_widget is not None,
                side_widget_present=side_widget is not None,
            )
            return None

        index_of = getattr(splitter, "indexOf", None)
        sizes_method = getattr(splitter, "sizes", None)
        set_sizes = getattr(splitter, "setSizes", None)
        if (
            not callable(index_of)
            or not callable(sizes_method)
            or not callable(set_sizes)
        ):
            self._trace(
                "generation queue panel transition splitter snapshot unavailable missing api",
                index_of_callable=callable(index_of),
                sizes_callable=callable(sizes_method),
                set_sizes_callable=callable(set_sizes),
            )
            return None

        editor_index = int(index_of(editor_widget))
        canvas_index = int(index_of(canvas_widget))
        side_index = int(index_of(side_widget))
        if editor_index < 0 or canvas_index < 0 or side_index < 0:
            self._trace(
                "generation queue panel transition splitter snapshot widgets absent",
                editor_index=editor_index,
                canvas_index=canvas_index,
                side_index=side_index,
            )
            return None

        sizes = list(sizes_method())
        max_index = max(editor_index, canvas_index, side_index)
        if len(sizes) <= max_index:
            self._trace(
                "generation queue panel transition splitter snapshot sizes too short",
                sizes=tuple(sizes),
                max_index=max_index,
            )
            return None

        self._trace(
            "generation queue panel transition captured splitter snapshot",
            splitter_sizes=tuple(sizes),
            editor_index=editor_index,
            canvas_index=canvas_index,
            side_index=side_index,
        )
        return _SplitterSnapshot(
            splitter=splitter,
            sizes=sizes,
            editor_index=editor_index,
            canvas_index=canvas_index,
            side_index=side_index,
        )

    def _infer_progress_from_host(self) -> float:
        """Infer open progress from the current rendered host width."""

        open_width = self._open_width()
        if open_width <= 0:
            return 0.0
        return _clamp_progress(self._current_rendered_width() / open_width)

    def _current_rendered_width(self) -> int:
        """Return current host width, treating hidden hosts as closed."""

        host = self._host()
        is_visible = getattr(host, "is_queue_panel_visible", None)
        if callable(is_visible) and not bool(is_visible()):
            return 0
        rendered_width = getattr(host, "rendered_width", None)
        if callable(rendered_width):
            return max(0, int(rendered_width()))
        width = getattr(host, "width", None)
        return max(0, int(width())) if callable(width) else 0

    def _open_width(self) -> int:
        """Return durable side-panel open width."""

        host = self._host()
        panel_width = getattr(host, "panel_width", None)
        if callable(panel_width):
            return max(0, int(panel_width()))
        width = getattr(host, "width", None)
        return max(0, int(width())) if callable(width) else 0

    def _host(self) -> Any:
        """Return the side-panel host from the view."""

        return getattr(self._view, "sidePanelHost", None)

    def _trace(self, event: str, **context: object) -> None:
        """Log side-panel transition shell layout context."""

        layout_controller = getattr(self._view, "shell_layout_controller", None)
        view_trace = getattr(layout_controller, "log_editor_width_trace", None)
        if callable(view_trace):
            view_trace(
                event,
                transition_progress=self._progress,
                transition_target_visible=self._target_visible,
                **context,
            )
            return
        log_info(
            _LOGGER,
            "generation queue panel transition shell layout",
            transition_event=event,
            transition_progress=self._progress,
            transition_target_visible=self._target_visible,
            **context,
        )

    progress = Property(float, _get_progress, setProgress)


__all__ = ["GenerationQueuePanelTransition"]
