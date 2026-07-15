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

"""Coordinate ready-shell restore work after the shell is visible."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol, cast

from substitute.app.bootstrap.startup_policy import (
    HIDDEN_GUI_PREHYDRATION_BUDGET_SECONDS,
)
from substitute.app.bootstrap.startup_summary import build_visible_loading_summary
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_warning,
)
from substitute.app.bootstrap.startup_trace import trace_mark, trace_span

_LOGGER = get_logger("app.bootstrap.ready_shell_restore_controller")


class PrehydrationStartupTimerProtocol(Protocol):
    """Record startup prehydration timing phases."""

    def phase(self, name: str) -> AbstractContextManager[None]:
        """Measure one startup phase."""


class HydrationStartupTimerProtocol(Protocol):
    """Record startup hydration milestones."""

    def mark(self, name: str) -> object:
        """Mark one startup milestone."""


@dataclass(frozen=True)
class ReadyShellPrehydrationResult:
    """Report whether pre-show workspace prehydration ran."""

    attempted: bool
    succeeded: bool


def prehydrate_initial_workspace_before_show(
    *,
    startup_cancelled: bool,
    shell_frame: object | None,
    main_window_for_shell: Callable[[object], object],
    workspace: object | None,
    startup_timer: PrehydrationStartupTimerProtocol,
    workspace_workflow_count: Callable[[object | None], int],
    trace_fields: Callable[[], Mapping[str, object]],
    clock: Callable[[], float] = perf_counter,
    budget_seconds: float = HIDDEN_GUI_PREHYDRATION_BUDGET_SECONDS,
) -> ReadyShellPrehydrationResult:
    """Prehydrate safe restored workspace chrome before shell reveal."""

    trace_mark("prehydrate_initial_workspace_task.start", **dict(trace_fields()))
    if startup_cancelled or shell_frame is None:
        trace_mark(
            "prehydrate_initial_workspace_task.skip",
            reason="startup_cancelled" if startup_cancelled else "no_shell_frame",
        )
        return ReadyShellPrehydrationResult(attempted=False, succeeded=False)
    if workspace is None:
        trace_mark(
            "prehydrate_initial_workspace_task.skip",
            reason="no_initial_workspace",
        )
        return ReadyShellPrehydrationResult(attempted=False, succeeded=False)

    main_window = main_window_for_shell(shell_frame)
    workspace_restore_controller = getattr(
        main_window,
        "workspace_restore_controller",
        None,
    )
    prehydrate = _callable_attr(
        workspace_restore_controller,
        "prehydrate_initial_workspace",
    )
    if prehydrate is None:
        trace_mark(
            "prehydrate_initial_workspace_task.skip",
            reason="no_prehydration_callable",
        )
        return ReadyShellPrehydrationResult(attempted=False, succeeded=False)

    prehydrate_started_at = clock()
    with startup_timer.phase("startup.prehydrate_initial_workspace"):
        with trace_span(
            "prehydrate_initial_workspace_task.prehydrate",
            workflow_count=workspace_workflow_count(workspace),
        ):
            succeeded = bool(prehydrate(workspace))
    prehydrate_elapsed_seconds = clock() - prehydrate_started_at
    if prehydrate_elapsed_seconds > budget_seconds:
        log_warning(
            _LOGGER,
            "Hidden workspace prehydration exceeded budget",
            elapsed_ms=f"{prehydrate_elapsed_seconds * 1000.0:.3f}",
            budget_ms=f"{budget_seconds * 1000.0:.3f}",
            prehydration_succeeded=succeeded,
        )
    trace_mark("prehydrate_initial_workspace_task.end", **dict(trace_fields()))
    return ReadyShellPrehydrationResult(attempted=True, succeeded=succeeded)


def hydrate_initial_workspace_after_show(
    *,
    startup_cancelled: bool,
    shell_frame: object | None,
    main_window_for_shell: Callable[[object], object],
    workspace: object | None,
    hidden_restore_runtime_prepared: bool,
    prehydration_succeeded: bool,
    startup_timer: HydrationStartupTimerProtocol,
    schedule_warmups: Callable[[str], None],
    schedule_visible_summary: Callable[[], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> None:
    """Hydrate restored workspace surfaces after the shell is visible."""

    if startup_cancelled:
        trace_mark("post_show.hydration.skip", reason="startup_cancelled")
        return
    if shell_frame is None:
        trace_mark("post_show.hydration.skip", reason="no_shell_frame")
        return

    main_window = main_window_for_shell(shell_frame)
    workspace_restore_controller = getattr(
        main_window,
        "workspace_restore_controller",
        None,
    )
    hydrate = _callable_attr(
        workspace_restore_controller,
        "hydrate_initial_workspace",
    )
    prehydrated_restore_controller = getattr(
        main_window,
        "shell_prehydrated_restore_controller",
        None,
    )
    finalize = _callable_attr(
        prehydrated_restore_controller,
        "finalize_initial_workspace_restore",
    )
    finish_layout = _callable_attr(
        prehydrated_restore_controller,
        "finish_initial_workspace_restore_layout",
    )

    startup_timer.mark("hydration_started")
    trace_mark("post_show.hydration.start", **dict(trace_fields()))
    if (
        hidden_restore_runtime_prepared
        and prehydration_succeeded
        and finish_layout is not None
    ):
        with trace_span("post_show.hydration.finish_restore_layout"):
            if not bool(finish_layout()):
                trace_mark("post_show.hydration.finish_restore_layout.fallback")
                if finalize is not None:
                    finalize(workspace)
    elif prehydration_succeeded and finalize is not None:
        with trace_span("post_show.hydration.finalize_prehydrated"):
            finalize(workspace)
    elif hydrate is not None:
        with trace_span(
            "post_show.hydration.full_hydrate",
            workspace_present=workspace is not None,
        ):
            if workspace is None:
                hydrate()
            else:
                hydrate(workspace)
    else:
        trace_mark("post_show.hydration.skip", reason="no_hydration_callable")
        schedule_warmups("no_hydration_callable")
        return

    startup_timer.mark("hydration_completed")
    trace_mark("post_show.hydration.end", **dict(trace_fields()))
    restore_finalization_pending = _callable_attr(
        prehydrated_restore_controller,
        "restore_layout_finalization_pending",
    )
    if restore_finalization_pending is not None and bool(
        restore_finalization_pending()
    ):
        trace_mark(
            "post_comfy.nonessential_warmups.waiting_after_hydration",
            **dict(trace_fields()),
        )
    else:
        trace_mark(
            "post_comfy.nonessential_warmups.fallback_after_hydration",
            **dict(trace_fields()),
        )
        schedule_warmups("fallback_after_hydration")
    trace_mark(
        "post_show.visible_startup_summary",
        delay_ms=0,
    )
    schedule_visible_summary()


def log_visible_startup_summary(
    *,
    startup_timer: StartupTimer,
    workspace: object | None,
    trace_fields: Callable[[], Mapping[str, object]],
) -> None:
    """Log aggregate post-splash startup timing and restore context."""

    summary = build_visible_loading_summary(
        startup_timer=startup_timer,
        workspace=workspace,
    )
    log_info(
        _LOGGER,
        "Startup visible loading summary",
        **summary.log_fields(),
    )
    trace_mark(
        "startup.visible_loading.summary",
        **summary.log_fields(),
        **dict(trace_fields()),
    )


def prepare_hidden_restore_runtime_before_show(
    *,
    main_window: object,
    comfy_http_ready: bool,
    prehydration_succeeded: bool,
    startup_timer: PrehydrationStartupTimerProtocol,
) -> bool:
    """Prepare restored workspace runtime before shell reveal when possible."""

    prehydrated_restore_controller = getattr(
        main_window,
        "shell_prehydrated_restore_controller",
        None,
    )
    prepare_restore_runtime = _callable_attr(
        prehydrated_restore_controller,
        "prepare_initial_workspace_restore_runtime",
    )
    if (
        not comfy_http_ready
        or not prehydration_succeeded
        or prepare_restore_runtime is None
    ):
        trace_mark(
            "post_comfy.hidden_restore_runtime_prepare.skip",
            reason="backend_not_ready"
            if not comfy_http_ready
            else "prehydration_not_succeeded"
            if not prehydration_succeeded
            else "no_prepare_callable",
        )
        return False
    try:
        with startup_timer.phase("startup.hidden_restore_runtime_prepare"):
            with trace_span("post_comfy.hidden_restore_runtime_prepare"):
                return bool(prepare_restore_runtime())
    except Exception:
        log_exception(
            _LOGGER,
            "Failed to prepare restored workspace runtime before reveal",
        )
        return False


def schedule_post_show_hydration_after_reveal(
    *,
    startup_cancelled: bool,
    hydration_started: bool,
    mark_hydration_started: Callable[[], None],
    queue_hydration_task: Callable[[], None],
    start_queue: Callable[[], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> bool:
    """Queue post-show hydration after the shell is visible."""

    if startup_cancelled:
        trace_mark("post_show.hydration.skip", reason="startup_cancelled")
        return False
    if hydration_started:
        trace_mark("post_show.hydration.skip", reason="already_started")
        return False
    mark_hydration_started()
    trace_mark("post_show.hydration.queued", **dict(trace_fields()))
    queue_hydration_task()
    start_queue()
    return True


def mark_minimum_shell_ready(
    *,
    startup_cancelled: bool,
    mark_ready: Callable[[], None],
    try_show_main_window: Callable[[], None],
    trace_fields: Callable[[], Mapping[str, object]],
    after_mark_ready: Callable[[], object] | None = None,
) -> bool:
    """Mark minimum shell readiness and request shell reveal."""

    trace_mark("mark_minimum_shell_ready_task.start", **dict(trace_fields()))
    if startup_cancelled:
        trace_mark(
            "mark_minimum_shell_ready_task.skip",
            reason="startup_cancelled",
        )
        return False
    mark_ready()
    trace_mark("mark_minimum_shell_ready_task.end", **dict(trace_fields()))
    try_show_main_window()
    if after_mark_ready is not None:
        after_mark_ready()
    return True


def warm_prompt_editor_gui_before_reveal(
    *,
    startup_cancelled: bool,
    shell_frame: object | None,
    main_window_for_shell: Callable[[object], object | None],
    warm_prompt_editor_gui: Callable[[object], object],
    trace_fields: Callable[[], Mapping[str, object]],
) -> bool:
    """Warm prompt editor GUI construction before the shell is revealed."""

    trace_mark("warm_prompt_editor_gui_task.start", **dict(trace_fields()))
    if startup_cancelled or shell_frame is None:
        trace_mark(
            "warm_prompt_editor_gui_task.skip",
            reason="startup_cancelled" if startup_cancelled else "no_shell_frame",
        )
        return False
    main_window = main_window_for_shell(shell_frame)
    if main_window is None:
        trace_mark("warm_prompt_editor_gui_task.end", **dict(trace_fields()))
        return False
    with trace_span("warm_prompt_editor_gui_task.run"):
        warm_prompt_editor_gui(main_window)
    trace_mark("warm_prompt_editor_gui_task.end", **dict(trace_fields()))
    return True


def attach_restore_asset_preload_to_shell(
    *,
    main_window: object,
    restore_asset_preload: object | None,
    trace_fields: Callable[[], Mapping[str, object]],
) -> bool:
    """Attach preloaded restore assets to the built shell when available."""

    if restore_asset_preload is None:
        trace_mark(
            "build_shell_task.restore_asset_preload.skip",
            reason="no_restore_asset_preload",
            **dict(trace_fields()),
        )
        return False
    restore_image_adapter = getattr(
        main_window,
        "workspace_restore_image_adapter",
        None,
    )
    set_restore_asset_preload = _callable_attr(
        restore_image_adapter,
        "set_restore_asset_preload",
    )
    if set_restore_asset_preload is None:
        trace_mark(
            "build_shell_task.restore_asset_preload.skip",
            reason="no_restore_asset_preload_port",
            **dict(trace_fields()),
        )
        return False
    set_restore_asset_preload(restore_asset_preload)
    trace_mark(
        "build_shell_task.restore_asset_preload.attached",
        **dict(trace_fields()),
    )
    return True


def update_shell_backend_state(
    *,
    state: str,
    startup_cancelled: bool,
    shell_frame: object | None,
    main_window_for_shell: Callable[[object], object],
    trace_fields: Callable[[], Mapping[str, object]],
) -> bool:
    """Project backend readiness state into the built shell."""

    if startup_cancelled or shell_frame is None:
        return False
    main_window = main_window_for_shell(shell_frame)
    generation_action_controller = getattr(
        main_window,
        "generation_action_controller",
        None,
    )
    set_backend_state = _callable_attr(
        generation_action_controller,
        "set_backend_state",
    )
    if set_backend_state is None:
        return False
    trace_mark(
        "shell_backend_state.update",
        state=state,
        **dict(trace_fields()),
    )
    set_backend_state(state)
    return True


def _callable_attr(owner: object | None, name: str) -> Callable[..., object] | None:
    """Return a callable attribute from a duck-typed startup collaborator."""

    value = getattr(owner, name, None)
    if callable(value):
        return cast(Callable[..., object], value)
    return None


__all__ = [
    "HydrationStartupTimerProtocol",
    "PrehydrationStartupTimerProtocol",
    "ReadyShellPrehydrationResult",
    "attach_restore_asset_preload_to_shell",
    "hydrate_initial_workspace_after_show",
    "log_visible_startup_summary",
    "mark_minimum_shell_ready",
    "prepare_hidden_restore_runtime_before_show",
    "prehydrate_initial_workspace_before_show",
    "schedule_post_show_hydration_after_reveal",
    "update_shell_backend_state",
    "warm_prompt_editor_gui_before_reveal",
]
