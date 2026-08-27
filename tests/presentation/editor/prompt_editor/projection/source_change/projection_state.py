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

"""Provide projection-state recorders for source-change contracts."""

from __future__ import annotations


from substitute.presentation.editor.prompt_editor.projection.edit_pipeline_contracts import (
    PromptProjectionApplyPath,
    PromptProjectionSourceChangeApplyOutcome,
    PromptProjectionSourceChangeApplyRequest,
)


class _SignalRecorder:
    """Record no-arg signal emissions."""

    def __init__(self) -> None:
        """Create an empty signal recorder."""

        self.count = 0

    def emit(self) -> None:
        """Record one signal emission."""

        self.count += 1


class _ViewportRecorder:
    """Record viewport repaint requests."""

    def __init__(self) -> None:
        """Create an empty viewport recorder."""

        self.update_count = 0
        self._width = 320
        self._height = 120

    def width(self) -> int:
        """Return a stable viewport width."""

        return self._width

    def height(self) -> int:
        """Return a stable viewport height."""

        return self._height

    def update(self) -> None:
        """Record one viewport update request."""

        self.update_count += 1


class _ScrollBarRecorder:
    """Record scrollbar value changes."""

    def __init__(self) -> None:
        """Create an empty scrollbar recorder."""

        self.values: list[int] = []

    def setValue(self, value: int) -> None:  # noqa: N802
        """Record one scrollbar value."""

        self.values.append(value)


class _ProjectionDocument:
    """Carry committed projection source text for deferred checks."""

    def __init__(self, source_text: str) -> None:
        """Store committed source text."""

        self.source_text = source_text
        self.tokens: tuple[object, ...] = ()

    def token_by_id(self, token_id: str | None) -> None:
        """Return no focused token from the minimal test document."""

        _ = token_id
        return None


class _EditPipelineRecorder:
    """Record source-change execution through the edit-pipeline owner."""

    def __init__(self) -> None:
        """Create a controller fake with incremental success defaults."""

        self.requests: list[PromptProjectionSourceChangeApplyRequest] = []

    def apply(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> PromptProjectionSourceChangeApplyOutcome:
        """Record the request and report incremental catch-up."""

        self.requests.append(request)
        return PromptProjectionSourceChangeApplyOutcome(
            apply_path=PromptProjectionApplyPath.INCREMENTAL,
            fast_projection_applied=True,
        )
