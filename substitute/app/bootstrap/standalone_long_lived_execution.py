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

"""Own standalone long-lived task starts outside the main execution runtime."""

from __future__ import annotations

from typing import TypeVar

from substitute.application.execution import ExecutionContext, TaskIdentity
from substitute.infrastructure.execution import LongLivedTaskHandle
from substitute.infrastructure.execution.long_lived_task import (
    LongLivedDispatcher,
    LongLivedWork,
)

TResult = TypeVar("TResult")


class StandaloneLongLivedExecutionOwner:
    """Start long-lived tasks for pre-runtime and helper-process boundaries."""

    def __init__(self, *, dispatcher: LongLivedDispatcher) -> None:
        """Store the dispatcher used by this standalone execution owner."""

        self._dispatcher = dispatcher

    def start(
        self,
        *,
        identity: TaskIdentity,
        context: ExecutionContext,
        work: LongLivedWork[TResult],
        thread_name: str,
    ) -> LongLivedTaskHandle[TResult]:
        """Start one long-lived task under this standalone owner."""

        return LongLivedTaskHandle(
            identity=identity,
            context=context,
            work=work,
            dispatcher=self._dispatcher,
            thread_name=thread_name,
        )


__all__ = ["StandaloneLongLivedExecutionOwner"]
