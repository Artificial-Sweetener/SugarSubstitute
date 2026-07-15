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

"""Animate shell cube-stack mode changes between expanded and compact states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, Property, QPropertyAnimation, Signal

from substitute.presentation.motion import (
    CUBE_STACK_MODE_DURATION_MS,
    TRANSFORM_EASING_CURVE,
    resolve_motion_duration,
    stop_animation,
)
from substitute.presentation.shell.search_overlay_controller import (
    search_overlay_controller_for,
)
from substitute.presentation.workflows.cube_stack_view import (
    CUBE_ITEM_COMPACT_WIDTH,
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_STACK_COMPACT_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
)
from substitute.shared.logging.logger import get_logger, log_info

_DETAILS_MINIMUM_WIDTH = 1
_CANVAS_MINIMUM_WIDTH = 100
_LOGGER = get_logger("presentation.shell.cube_stack_mode_transition")


@dataclass(frozen=True)
class _SplitterSnapshot:
    """Store splitter geometry captured at the beginning of one transition."""

    splitter: Any
    sizes: list[int]
    details_index: int
    canvas_index: int


def _clamp_progress(progress: float) -> float:
    """Return compactness progress clamped to the valid animation range."""

    return max(0.0, min(1.0, float(progress)))


def _lerp_int(start: int, end: int, progress: float) -> int:
    """Return an integer linear interpolation for one animation frame."""

    return round(start + ((end - start) * progress))


class CubeStackModeTransition(QObject):
    """Animate workflow cube-stack presentation between expanded and compact modes."""

    transitionFinished = Signal(bool)

    def __init__(self, view: Any) -> None:
        """Create a transition driver for one MainWindow-like view object."""

        super().__init__(view if isinstance(view, QObject) else None)
        self._view = view
        self._progress = self._infer_progress_from_container()
        self._target_compact = self._progress >= 0.5
        self._animating = False
        self._start_stack_width = self._stack_width_for_progress(self._progress)
        self._target_stack_width = self._start_stack_width
        self._splitter_snapshot: _SplitterSnapshot | None = None
        self._animation = QPropertyAnimation(self, b"progress", self)
        self._animation.finished.connect(self._finish_transition)

    def transition_to(self, compact: bool) -> None:
        """Animate or immediately apply the requested cube-stack mode."""

        self._trace("cube stack transition requested", compact=compact)
        target_progress = 1.0 if compact else 0.0
        self._animation.stop()
        self._animating = False
        self._target_compact = compact
        self._progress = self._infer_progress_from_container()
        self._start_stack_width = self._container_width()
        self._target_stack_width = (
            CUBE_STACK_COMPACT_WIDTH if compact else CUBE_STACK_EXPANDED_WIDTH
        )
        self._splitter_snapshot = self._capture_splitter_snapshot()
        self._trace(
            "cube stack transition captured start state",
            compact=compact,
            start_progress=self._progress,
            start_stack_width=self._start_stack_width,
            target_stack_width=self._target_stack_width,
            splitter_snapshot_sizes=tuple(self._splitter_snapshot.sizes)
            if self._splitter_snapshot is not None
            else (),
        )
        self._begin_stack_transitions(compact)

        duration_ms = resolve_motion_duration(CUBE_STACK_MODE_DURATION_MS)
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
        """Stop any in-flight transition."""

        stop_animation(self._animation)
        self._animating = False

    def is_animating(self) -> bool:
        """Return whether a cube-stack mode transition is active."""

        return self._animating

    def _get_progress(self) -> float:
        """Return the current compactness progress."""

        return self._progress

    def setProgress(self, progress: float) -> None:
        """Apply one rendered compactness progress frame."""

        self._progress = _clamp_progress(progress)
        stack_width = self._stack_width_for_progress(self._progress)
        item_width = self._item_width_for_progress(self._progress)
        self._trace(
            "cube stack transition progress",
            requested_progress=progress,
            clamped_progress=self._progress,
            stack_width=stack_width,
            item_width=item_width,
        )
        self._set_container_width(stack_width)
        self._apply_stack_progress(stack_width, item_width, self._progress)
        self._apply_splitter_progress(stack_width)
        self._apply_material_progress()
        self._position_search_box()

    def _finish_transition(self) -> None:
        """Commit final target state after an animation or reduced-motion jump."""

        self._animating = False
        target_progress = 1.0 if self._target_compact else 0.0
        self._progress = target_progress
        stack_width = (
            CUBE_STACK_COMPACT_WIDTH
            if self._target_compact
            else CUBE_STACK_EXPANDED_WIDTH
        )
        item_width = (
            CUBE_ITEM_COMPACT_WIDTH
            if self._target_compact
            else CUBE_ITEM_EXPANDED_WIDTH
        )
        self._set_container_width(stack_width)
        self._apply_stack_progress(stack_width, item_width, target_progress)
        self._apply_splitter_progress(stack_width)
        self._apply_material_progress()
        self._finish_stack_transitions(self._target_compact)
        self._position_search_box()
        self._trace(
            "cube stack transition finished",
            target_compact=self._target_compact,
            final_stack_width=stack_width,
            target_progress=target_progress,
        )
        self.transitionFinished.emit(self._target_compact)

    def _begin_stack_transitions(self, target_compact: bool) -> None:
        """Prepare all workflow stacks for the requested animated target."""

        for cube_stack in self._cube_stacks():
            begin = getattr(cube_stack, "beginCompactTransition", None)
            if callable(begin):
                begin(target_compact)

    def _apply_stack_progress(
        self,
        stack_width: int,
        item_width: int,
        compact_progress: float,
    ) -> None:
        """Apply interpolated geometry to all workflow cube stacks."""

        for cube_stack in self._cube_stacks():
            apply_transition = getattr(cube_stack, "applyCompactTransition", None)
            if callable(apply_transition):
                apply_transition(
                    stack_width=stack_width,
                    item_width=item_width,
                    compact_progress=compact_progress,
                )

    def _finish_stack_transitions(self, target_compact: bool) -> None:
        """Commit all workflow stacks to the target compact state."""

        for cube_stack in self._cube_stacks():
            finish = getattr(cube_stack, "finishCompactTransition", None)
            if callable(finish):
                finish(target_compact)
                continue
            set_compact = getattr(cube_stack, "setCompact", None)
            if callable(set_compact):
                set_compact(target_compact)

    def _apply_splitter_progress(self, stack_width: int) -> None:
        """Apply width transfer to the captured splitter panes for one frame."""

        snapshot = self._splitter_snapshot
        if snapshot is None:
            self._trace("cube stack transition splitter progress skipped no snapshot")
            return

        sizes = list(snapshot.sizes)
        freed_width = self._start_stack_width - stack_width
        sizes[snapshot.details_index] = max(
            _DETAILS_MINIMUM_WIDTH,
            snapshot.sizes[snapshot.details_index] - freed_width,
        )
        sizes[snapshot.canvas_index] = max(
            _CANVAS_MINIMUM_WIDTH,
            snapshot.sizes[snapshot.canvas_index] + freed_width,
        )
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
            "cube stack transition applied splitter progress",
            stack_width=stack_width,
            start_stack_width=self._start_stack_width,
            new_splitter_sizes=tuple(sizes),
            snapshot_splitter_sizes=tuple(snapshot.sizes),
            remembered=callable(remember_sizes),
        )

    def _capture_splitter_snapshot(self) -> _SplitterSnapshot | None:
        """Return splitter geometry needed to preserve editor width."""

        splitter = getattr(self._view, "splitter", None)
        details_widget = getattr(self._view, "editor_output_container", None)
        canvas_widget = getattr(self._view, "canvas_tabs_container", None)
        if splitter is None or details_widget is None or canvas_widget is None:
            self._trace(
                "cube stack transition splitter snapshot unavailable missing widget",
                splitter_present=splitter is not None,
                details_widget_present=details_widget is not None,
                canvas_widget_present=canvas_widget is not None,
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
                "cube stack transition splitter snapshot unavailable missing api",
                index_of_callable=callable(index_of),
                sizes_callable=callable(sizes_method),
                set_sizes_callable=callable(set_sizes),
            )
            return None

        details_index = int(index_of(details_widget))
        canvas_index = int(index_of(canvas_widget))
        if details_index < 0 or canvas_index < 0:
            self._trace(
                "cube stack transition splitter snapshot widgets absent",
                details_index=details_index,
                canvas_index=canvas_index,
            )
            return None

        sizes = list(sizes_method())
        max_index = max(details_index, canvas_index)
        if len(sizes) <= max_index:
            self._trace(
                "cube stack transition splitter snapshot sizes too short",
                sizes=tuple(sizes),
                max_index=max_index,
            )
            return None

        self._trace(
            "cube stack transition captured splitter snapshot",
            splitter_sizes=tuple(sizes),
            details_index=details_index,
            canvas_index=canvas_index,
        )
        return _SplitterSnapshot(
            splitter=splitter,
            sizes=sizes,
            details_index=details_index,
            canvas_index=canvas_index,
        )

    def _cube_stacks(self) -> list[Any]:
        """Return the managed workflow cube stack widgets."""

        cube_stacks = getattr(self._view, "cube_stacks", {})
        values = getattr(cube_stacks, "values", None)
        return list(values()) if callable(values) else []

    def _container_width(self) -> int:
        """Return the current shared cube-stack container width."""

        container = getattr(self._view, "cube_stack_container", None)
        width = getattr(container, "width", None)
        if callable(width):
            return int(width())
        return self._stack_width_for_progress(self._progress)

    def _set_container_width(self, width: int) -> None:
        """Set the shared cube-stack container width when available."""

        container = getattr(self._view, "cube_stack_container", None)
        set_fixed_width = getattr(container, "setFixedWidth", None)
        if callable(set_fixed_width):
            set_fixed_width(width)

    def _infer_progress_from_container(self) -> float:
        """Infer compactness progress from the current container width."""

        width = self._container_width_from_view()
        denominator = CUBE_STACK_EXPANDED_WIDTH - CUBE_STACK_COMPACT_WIDTH
        if denominator <= 0:
            return 0.0
        return _clamp_progress((CUBE_STACK_EXPANDED_WIDTH - width) / denominator)

    def _container_width_from_view(self) -> int:
        """Return current container width without depending on transition state."""

        container = getattr(self._view, "cube_stack_container", None)
        width = getattr(container, "width", None)
        if callable(width):
            return int(width())
        return CUBE_STACK_EXPANDED_WIDTH

    @staticmethod
    def _stack_width_for_progress(progress: float) -> int:
        """Return stack width for one compactness progress value."""

        return _lerp_int(
            CUBE_STACK_EXPANDED_WIDTH,
            CUBE_STACK_COMPACT_WIDTH,
            _clamp_progress(progress),
        )

    @staticmethod
    def _item_width_for_progress(progress: float) -> int:
        """Return cube item width for one compactness progress value."""

        return _lerp_int(
            CUBE_ITEM_EXPANDED_WIDTH,
            CUBE_ITEM_COMPACT_WIDTH,
            _clamp_progress(progress),
        )

    def _position_search_box(self) -> None:
        """Keep the floating search box aligned with animated shell geometry."""

        search_overlay_controller = getattr(
            self._view,
            "search_overlay_controller",
            None,
        )
        position_search_box = getattr(
            search_overlay_controller,
            "position_search_box",
            None,
        )
        if callable(position_search_box):
            position_search_box()
            return
        search_overlay_controller_for(self._view).position_search_box()

    def _apply_material_progress(self) -> None:
        """Synchronize workspace material opacity with compact transition progress."""

        layout_controller = getattr(self._view, "shell_layout_controller", None)
        sync_material = getattr(
            layout_controller,
            "set_cube_stack_material_progress",
            None,
        )
        if callable(sync_material):
            sync_material(self._progress)

    def _trace(self, event: str, **context: object) -> None:
        """Log cube-stack transition shell layout context."""

        layout_controller = getattr(self._view, "shell_layout_controller", None)
        view_trace = getattr(layout_controller, "log_editor_width_trace", None)
        if callable(view_trace):
            view_trace(
                event,
                transition_progress=self._progress,
                transition_target_compact=self._target_compact,
                **context,
            )
            return
        log_info(
            _LOGGER,
            "cube stack mode transition shell layout",
            transition_event=event,
            transition_progress=self._progress,
            transition_target_compact=self._target_compact,
            **context,
        )

    progress = Property(float, _get_progress, setProgress)


__all__ = ["CubeStackModeTransition"]
