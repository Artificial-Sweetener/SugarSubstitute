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

"""Schedule hidden editor cube-section builds across Qt event-loop turns."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from PySide6.QtCore import QTimer

from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_debug,
    log_warning,
)

from .projection_models import ProjectedCubeBuild
from .projection_observability import (
    log_panel_projection_event,
    log_panel_projection_timing,
    panel_projection_observability_started_at,
)

_LOGGER = get_logger("presentation.editor.panel.hidden_build_scheduler")
_PROJECTED_CUBE_BUILD_STEP_DELAY_MS = 8


@dataclass(frozen=True, slots=True)
class HiddenBuildSchedulerPorts:
    """Group collaborators required to publish and track hidden build results."""

    reveal_projected_cube_builds: Callable[[Sequence[ProjectedCubeBuild], str], None]
    mark_build_complete: Callable[[str, object], object]
    mark_build_failed: Callable[[str, object, object], object]


class HiddenBuildScheduler:
    """Own timer-driven hidden projection and cube-section build scheduling."""

    def __init__(self, ports: HiddenBuildSchedulerPorts) -> None:
        """Store collaborators used when hidden builds finish or fail."""

        self._ports = ports

    def schedule_projected_cube_builds(
        self,
        projected_builds: Sequence[ProjectedCubeBuild],
        on_complete: Callable[[], None],
        on_cancel: Callable[[], None],
        *,
        workflow_id: str,
        is_current: Callable[[], bool] | None = None,
        visible_commit: Callable[[Sequence[ProjectedCubeBuild]], bool] | None = None,
    ) -> None:
        """Build hidden projected cube sections and reveal them in one layout commit."""

        pending_builds = list(projected_builds)
        completed_builds: list[ProjectedCubeBuild] = []

        def run_next() -> None:
            current_build: ProjectedCubeBuild | None = None
            if is_current is not None and not is_current():
                on_cancel()
                return
            should_complete = False
            try:
                if not pending_builds:
                    if completed_builds:
                        completed_visible_commit = self.commit_scheduled_builds(
                            completed_builds,
                            workflow_id=workflow_id,
                            visible_commit=visible_commit,
                        )
                        if not completed_visible_commit:
                            return
                        if visible_commit is not None:
                            completed_builds.clear()
                            return
                    should_complete = True
                else:
                    current_build = pending_builds[0]
                    step = getattr(current_build.build_session, "step")
                    step_started_at = panel_projection_observability_started_at()
                    is_done = bool(step())
                    log_panel_projection_timing(
                        "hidden_build.cube_step",
                        started_at=step_started_at,
                        workflow_id=workflow_id,
                        cube_alias=current_build.cube_alias,
                        remaining_cube_count=len(pending_builds),
                        projection_mode="live",
                    )
                    if is_done:
                        pending_builds.pop(0)
                        completed_builds.append(
                            replace(
                                current_build,
                                build_elapsed_ms=elapsed_ms_since(
                                    current_build.started_at
                                ),
                                completed_at=panel_projection_observability_started_at(),
                            )
                        )
            except (RuntimeError, TypeError, ValueError) as error:
                if current_build is not None:
                    self._ports.mark_build_failed(
                        current_build.cube_alias,
                        current_build.token,
                        error,
                    )
                else:
                    for completed_build in completed_builds:
                        self._ports.mark_build_failed(
                            completed_build.cube_alias,
                            completed_build.token,
                            error,
                        )
                log_warning(
                    _LOGGER,
                    "Stopped projected editor cube build after expected failure",
                    workflow_id=workflow_id,
                    pending_build_count=len(pending_builds),
                    error_type=type(error).__name__,
                )
                on_cancel()
                return

            if should_complete:
                log_panel_projection_event(
                    "full_projection.projected_complete",
                    level="info",
                    workflow_id=workflow_id,
                    pending_build_count=0,
                    projection_mode="live",
                )
                completed_builds.clear()
                on_complete()
                return
            self._schedule_next_projected_build_step(
                workflow_id=workflow_id,
                pending_build_count=len(pending_builds),
                callback=run_next,
            )

        self._schedule_next_projected_build_step(
            workflow_id=workflow_id,
            pending_build_count=len(pending_builds),
            callback=run_next,
        )

    def commit_scheduled_builds(
        self,
        completed_builds: Sequence[ProjectedCubeBuild],
        *,
        workflow_id: str,
        visible_commit: Callable[[Sequence[ProjectedCubeBuild]], bool] | None,
    ) -> bool:
        """Reveal completed scheduler builds immediately or delegate commit ownership."""

        if visible_commit is not None:
            return visible_commit(tuple(completed_builds))
        self._ports.reveal_projected_cube_builds(
            completed_builds,
            workflow_id,
        )
        for completed_build in completed_builds:
            self._ports.mark_build_complete(
                completed_build.cube_alias,
                completed_build.token,
            )
        return True

    @staticmethod
    def schedule_cube_build_session(
        build_session: object,
        *,
        on_first_usable: Callable[[], None] | None = None,
        on_complete: Callable[[], None],
        is_current: Callable[[], bool] | None = None,
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        """Build one node per event-loop turn and report first usable/final states."""

        first_usable_sent = False

        def maybe_complete_first_usable() -> None:
            """Call the first-usable callback once when the session reaches it."""

            nonlocal first_usable_sent
            first_usable_reached = getattr(build_session, "first_usable_reached", True)
            if first_usable_sent:
                return
            if not bool(first_usable_reached):
                return
            first_usable_sent = True
            if on_first_usable is not None:
                on_first_usable()

        def run_next() -> None:
            is_current_result = is_current() if is_current is not None else None
            if is_current is not None and not is_current_result:
                log_debug(
                    _LOGGER,
                    "Cube load detail",
                    event="editor_build_session_cancelled_before_step",
                    build_session_type=type(build_session).__name__,
                )
                if on_cancel is not None:
                    on_cancel()
                return
            step = getattr(build_session, "step")
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="editor_build_session_step_start",
                build_session_type=type(build_session).__name__,
                first_usable_reached=getattr(
                    build_session,
                    "first_usable_reached",
                    None,
                ),
                is_current=is_current_result,
            )
            is_done = bool(step())
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="editor_build_session_step_end",
                build_session_type=type(build_session).__name__,
                is_done=is_done,
                first_usable_reached=getattr(
                    build_session,
                    "first_usable_reached",
                    None,
                ),
            )
            maybe_complete_first_usable()
            if is_done:
                maybe_complete_first_usable()
                on_complete()
                return
            QTimer.singleShot(0, run_next)

        QTimer.singleShot(0, run_next)

    @staticmethod
    def _schedule_next_projected_build_step(
        *,
        workflow_id: str,
        pending_build_count: int,
        callback: Callable[[], None],
    ) -> None:
        """Schedule the next projected build step and emit prompt-safe diagnostics."""

        log_panel_projection_event(
            "hidden_build.scheduled",
            workflow_id=workflow_id,
            pending_build_count=pending_build_count,
            build_delay_ms=_PROJECTED_CUBE_BUILD_STEP_DELAY_MS,
        )
        QTimer.singleShot(
            _PROJECTED_CUBE_BUILD_STEP_DELAY_MS,
            callback,
        )
