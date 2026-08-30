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

"""Provide deterministic projection update and timer builders."""

from __future__ import annotations

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptSemanticSnapshot,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSemanticIdentity,
    PromptSemanticRevision,
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from substitute.presentation.editor.prompt_editor.projection.update_scheduler import (
    PendingProjectionUpdate,
)


def _pending_update(text: str, *, source_revision: int) -> PendingProjectionUpdate:
    """Build a pending update for scheduler unit tests."""

    return _pending_update_at(text, source_revision=source_revision, queued_at=None)


def _pending_update_at(
    text: str,
    *,
    source_revision: int,
    queued_at: float | None,
) -> PendingProjectionUpdate:
    """Build a pending update with an optional explicit queue time."""

    document_view = PromptDocumentView(
        source_text=text,
        segments=(),
        emphasis_spans=(),
        wildcard_spans=(),
        lora_spans=(),
        syntax_spans=(),
        region_structure=PromptRegionStructureView.empty(len(text)),
        has_trailing_comma=False,
    )
    snapshot = PromptSemanticSnapshot(
        identity=PromptSemanticIdentity(
            source=PromptSourceIdentity(source_revision, len(text)),
            semantic_revision=PromptSemanticRevision(source_revision),
        ),
        document=document_view,
        render_plan=PromptSyntaxRenderPlan(
            syntax_spans=(),
            renderer_views=(),
        ),
    )
    update = PendingProjectionUpdate.create(
        snapshot=snapshot,
        reason="test",
    )
    if queued_at is None:
        return update
    return PendingProjectionUpdate(
        snapshot=update.snapshot,
        reason="safe_typing",
        queued_at=queued_at,
        previous_snapshot=update.previous_snapshot,
    )


class _ManualClock:
    """Provide exact monotonic time for scheduler age decisions."""

    def __init__(self, seconds: float) -> None:
        """Start at one explicit monotonic timestamp."""

        self._seconds = seconds

    def __call__(self) -> float:
        """Return the current controlled timestamp."""

        return self._seconds

    def advance(self, seconds: float) -> None:
        """Advance monotonic time without waiting for the process clock."""

        self._seconds += seconds


class _RestartRecordingTimer:
    """Record timer restarts while exposing the QTimer subset under test."""

    def __init__(self, *, remaining_ms: int) -> None:
        """Initialize an inactive fake timer with deterministic remaining time."""

        self.active = False
        self.interval = 0
        self.remaining_ms = remaining_ms
        self.start_calls: list[int] = []
        self.stop_calls = 0

    def setInterval(self, interval: int) -> None:  # noqa: N802
        """Record the interval selected by the scheduler."""

        self.interval = interval

    def isActive(self) -> bool:  # noqa: N802
        """Return whether the fake timer has been started."""

        return self.active

    def start(self, interval: int | None = None) -> None:
        """Record timer starts using the current interval when omitted."""

        self.active = True
        self.start_calls.append(self.interval if interval is None else interval)

    def stop(self) -> None:
        """Record timer stops."""

        self.active = False
        self.stop_calls += 1

    def remainingTime(self) -> int:  # noqa: N802
        """Return deterministic remaining time."""

        return self.remaining_ms


def _flush_projection_update_scheduler(surface: PromptProjectionSurface) -> None:
    """Apply a delayed scheduled projection update through the production scheduler."""

    surface._projection_freshness_controller.update_scheduler.flush_now(reason="test")  # noqa: SLF001
