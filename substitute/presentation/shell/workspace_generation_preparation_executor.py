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

"""Own detached generation preparation execution, cancellation, and callback lifetime."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.generation import GenerationPreparationResult
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.shell.workspace_generation_preparation_executor")


class GenerationPreparationExecutor:
    """Run captured generation preparation jobs off the UI thread."""

    def __init__(
        self,
        submitter: TaskSubmitter | None = None,
        *,
        close_submitter: Callable[[], None] | None = None,
    ) -> None:
        """Store the preparation execution route."""

        if submitter is None:
            raise TypeError("submitter is required for generation preparation.")
        self._task_scope = TaskScope(
            submitter=submitter,
            scope_id="generation_preparation",
        )
        self._close_submitter = close_submitter or (lambda: None)
        self._closed = False
        self._next_token = 0
        self._callbacks_by_token: dict[
            int,
            tuple[
                Callable[[GenerationPreparationResult], None],
                Callable[[BaseException], None],
            ],
        ] = {}

    def close(self) -> None:
        """Close the owned execution route when the controller is disposed."""

        if self._closed:
            return
        self._closed = True
        self._callbacks_by_token.clear()
        self._task_scope.close(reason="generation_preparation_executor_closed")
        self._close_submitter()

    def cancel_pending(self) -> None:
        """Revoke queue admission before cancelling work, keeping later submits valid."""

        pending_count = len(self._callbacks_by_token)
        self._callbacks_by_token.clear()
        self._task_scope.cancel_all(reason="generation_queue_cancelled")
        log_debug(
            _LOGGER,
            "Cancelled pending generation preparation",
            preparation_count=pending_count,
        )

    def submit(
        self,
        *,
        prepare_snapshots: Callable[[], GenerationPreparationResult],
        on_completed: Callable[[GenerationPreparationResult], None],
        on_failed: Callable[[BaseException], None],
    ) -> None:
        """Submit one detached preparation job and return immediately."""

        if self._closed:
            raise RuntimeError("Generation preparation executor is closed.")
        self._next_token += 1
        token = self._next_token
        self._callbacks_by_token[token] = (on_completed, on_failed)
        request: TaskRequest[GenerationPreparationResult] = TaskRequest(
            identity=TaskIdentity(
                request_id=token,
                domain="generation_preparation",
            ),
            context=ExecutionContext(
                operation="generation_preparation",
                reason="queue_generation_snapshots",
                lane="generation_preparation",
                safe_fields=(("request_id", token),),
            ),
            work=lambda _token: prepare_snapshots(),
        )
        try:
            handle = self._task_scope.submit(request)
        except BaseException:
            self._callbacks_by_token.pop(token, None)
            raise
        handle.add_done_callback(
            lambda outcome: self._handle_completed(token, outcome),
            reason="generation_preparation_completed",
        )

    def _handle_completed(
        self,
        token: int,
        outcome: TaskOutcome[GenerationPreparationResult],
    ) -> None:
        """Run the success callback on the bridge owner thread."""

        callbacks = self._callbacks_by_token.pop(token, None)
        if callbacks is None:
            return
        on_completed, on_failed = callbacks
        if outcome.status == "succeeded" and outcome.result is not None:
            on_completed(outcome.result)
            return
        if outcome.status == "cancelled":
            on_failed(
                RuntimeError(
                    outcome.cancellation_reason or "Generation preparation cancelled."
                )
            )
            return
        on_failed(outcome.error or RuntimeError("Generation preparation failed."))


__all__ = ["GenerationPreparationExecutor"]
