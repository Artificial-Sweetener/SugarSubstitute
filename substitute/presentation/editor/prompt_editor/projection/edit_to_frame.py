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

"""Own prompt layout transitions from one edit or configuration change to a frame."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtGui import QFont

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from .prepared_frame import PromptProjectionPreparedFrame
from .tokens import PromptProjectionInlineObjectRendererRegistry
from ..layout.canonical_engine import (
    PromptCanonicalLayoutEngine,
    PromptLineReuseMismatchObserver,
)
from ..layout.configuration import PromptLayoutConfigurationFactory
from ..layout.contracts import (
    PromptLayoutConfiguration,
    PromptLayoutDamage,
    PromptLayoutEdit,
    PromptLayoutOutcome,
    PromptLayoutOutput,
    PromptLayoutRequest,
    PromptLayoutStatus,
)
from ..layout.hard_line_engine import PromptHardLineLayoutEngine
from ..layout.same_line_engine import PromptSameLineLayoutEngine
from ..layout.trailing_engine import PromptTrailingLayoutEngine


@dataclass(frozen=True, slots=True)
class PromptIncrementalFrameApplyResult:
    """Report one incremental publication result without mutable side channels."""

    damage: PromptLayoutDamage | None
    rejection_reason: str

    @property
    def applied(self) -> bool:
        """Return whether the incremental outcome was published."""

        return self.damage is not None


class PromptLayoutEditToFrameCoordinator:
    """Coordinate canonical and incremental layout transitions into one frame."""

    __slots__ = (
        "_canonical_engine",
        "_configuration_factory",
        "_frame",
        "_hard_line_engine",
        "_incremental_rejection_observer",
        "_same_line_engine",
        "_trailing_engine",
    )

    def __init__(
        self,
        inline_object_renderers: PromptProjectionInlineObjectRendererRegistry,
    ) -> None:
        """Create an initial empty frame and its edit engines."""

        self._configuration_factory = PromptLayoutConfigurationFactory(
            inline_object_renderers
        )
        self._canonical_engine = PromptCanonicalLayoutEngine(inline_object_renderers)
        self._same_line_engine = PromptSameLineLayoutEngine()
        self._hard_line_engine = PromptHardLineLayoutEngine()
        self._trailing_engine = PromptTrailingLayoutEngine()
        self._incremental_rejection_observer: Callable[[str], None] | None = None
        initial_outcome = self._canonical_engine.build(
            PromptLayoutRequest(
                previous=None,
                projection_document=PromptProjectionDocument.empty(),
                prompt_document_view=None,
                configuration=self._configuration_factory.create(
                    base_font=QFont(),
                    text_width=1.0,
                ),
            )
        )
        self._frame = PromptProjectionPreparedFrame(
            _required_applied_output(initial_outcome, operation="initial")
        )

    @property
    def frame(self) -> PromptProjectionPreparedFrame:
        """Return the sole prepared-frame publication owner."""

        return self._frame

    def set_base_font(self, font: QFont) -> None:
        """Rebuild only when the canonical base font changes."""

        configuration = self._frame.output.configuration
        base_font = configuration.base_font
        if base_font == font or base_font.toString() == font.toString():
            return
        self._rebuild(
            projection_document=self._frame.output.projection_document,
            prompt_document_view=self._frame.output.prompt_document_view,
            configuration=self._configuration_factory.update(
                configuration,
                base_font=font,
            ),
        )

    def set_projection(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None = None,
    ) -> None:
        """Publish a canonical frame for one projection document."""

        self._rebuild(
            projection_document=projection_document,
            prompt_document_view=prompt_document_view,
            configuration=self._frame.output.configuration,
            reset_paint_state=True,
        )

    def set_projection_after_source_edit(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView,
        edit_start: int,
        edit_end: int,
        replacement_text: str,
    ) -> PromptLayoutDamage:
        """Publish one bounded canonical recovery result for a source edit."""

        previous = self._frame.output
        outcome = self._canonical_engine.reflow(
            PromptLayoutRequest(
                previous=previous,
                projection_document=projection_document,
                prompt_document_view=prompt_document_view,
                configuration=previous.configuration,
                edit=PromptLayoutEdit(
                    start=edit_start,
                    end=edit_end,
                    replacement_text=replacement_text,
                    first_dirty_projection_position=0,
                ),
            )
        )
        _required_applied_output(outcome, operation="canonical reflow")
        if outcome.damage is None:
            raise AssertionError("canonical prompt reflow omitted damage")
        return self._frame.publish(outcome, reset_paint_state=True)

    def set_projection_and_text_width(
        self,
        projection_document: PromptProjectionDocument,
        text_width: float,
        *,
        prompt_document_view: PromptDocumentView | None = None,
    ) -> None:
        """Publish projection and wrapping width in one canonical rebuild."""

        configuration = self._frame.output.configuration
        self._rebuild(
            projection_document=projection_document,
            prompt_document_view=prompt_document_view,
            configuration=self._configuration_factory.update(
                configuration,
                text_width=self._configuration_factory.normalize_text_width(text_width),
            ),
            reset_paint_state=True,
        )

    def try_apply_same_line_plain_text_edit(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None = None,
        edit_start: int,
        edit_end: int,
        replacement_text: str,
        first_dirty_projection_position: int,
        editable_token_id: str | None = None,
        projection_edit_start: int | None = None,
        projection_edit_end: int | None = None,
        projection_replacement_text: str | None = None,
    ) -> PromptIncrementalFrameApplyResult:
        """Attempt and report one same-line incremental transition."""

        return self._publish_incremental(
            self._same_line_engine.apply_same_line(
                PromptLayoutRequest(
                    previous=self._frame.output,
                    projection_document=projection_document,
                    prompt_document_view=prompt_document_view,
                    configuration=self._frame.output.configuration,
                    edit=PromptLayoutEdit(
                        start=edit_start,
                        end=edit_end,
                        replacement_text=replacement_text,
                        first_dirty_projection_position=(
                            first_dirty_projection_position
                        ),
                        editable_token_id=editable_token_id,
                        projection_edit_start=projection_edit_start,
                        projection_edit_end=projection_edit_end,
                        projection_replacement_text=projection_replacement_text,
                    ),
                )
            )
        )

    def try_apply_hard_line_break_edit(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None = None,
        edit_start: int,
        edit_end: int,
        replacement_text: str,
        first_dirty_projection_position: int,
    ) -> PromptIncrementalFrameApplyResult:
        """Attempt and report one hard-line incremental transition."""

        return self._publish_incremental(
            self._hard_line_engine.apply_hard_line(
                PromptLayoutRequest(
                    previous=self._frame.output,
                    projection_document=projection_document,
                    prompt_document_view=prompt_document_view,
                    configuration=self._frame.output.configuration,
                    edit=PromptLayoutEdit(
                        start=edit_start,
                        end=edit_end,
                        replacement_text=replacement_text,
                        first_dirty_projection_position=(
                            first_dirty_projection_position
                        ),
                    ),
                )
            )
        )

    def try_apply_trailing_plain_delete(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None = None,
    ) -> bool:
        """Publish a valid one-character trailing plain-text deletion."""

        return self._publish_incremental(
            self._trailing_engine.apply_trailing_plain_delete(
                self._incremental_request(
                    projection_document,
                    prompt_document_view=prompt_document_view,
                )
            )
        ).applied

    def try_apply_trailing_newline_delete(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None = None,
    ) -> bool:
        """Publish a valid trailing hard-line deletion."""

        return self._publish_incremental(
            self._trailing_engine.apply_trailing_newline_delete(
                self._incremental_request(
                    projection_document,
                    prompt_document_view=prompt_document_view,
                )
            )
        ).applied

    def try_apply_trailing_plain_insert(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None = None,
    ) -> bool:
        """Publish a valid trailing plain-text insertion."""

        return self._publish_incremental(
            self._trailing_engine.apply_trailing_plain_insert(
                self._incremental_request(
                    projection_document,
                    prompt_document_view=prompt_document_view,
                )
            )
        ).applied

    def try_apply_trailing_newline_insert(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None = None,
    ) -> bool:
        """Publish a valid trailing hard-line insertion."""

        return self._publish_incremental(
            self._trailing_engine.apply_trailing_newline_insert(
                self._incremental_request(
                    projection_document,
                    prompt_document_view=prompt_document_view,
                )
            )
        ).applied

    def set_text_width(self, width: float) -> None:
        """Publish a canonical frame only when wrapping width changes."""

        width = self._configuration_factory.normalize_text_width(width)
        configuration = self._frame.output.configuration
        if abs(configuration.text_width - width) < 0.01:
            return
        self._rebuild(
            projection_document=self._frame.output.projection_document,
            prompt_document_view=self._frame.output.prompt_document_view,
            configuration=self._configuration_factory.update(
                configuration,
                text_width=width,
            ),
        )

    def set_content_left_inset(self, inset: float) -> None:
        """Publish a canonical frame only when its content inset changes."""

        inset = self._configuration_factory.normalize_content_left_inset(inset)
        configuration = self._frame.output.configuration
        if abs(configuration.content_left_inset - inset) < 0.01:
            return
        self._rebuild(
            projection_document=self._frame.output.projection_document,
            prompt_document_view=self._frame.output.prompt_document_view,
            configuration=self._configuration_factory.update(
                configuration,
                content_left_inset=inset,
            ),
        )

    def set_reflow_mismatch_observer(
        self,
        observer: PromptLineReuseMismatchObserver | None,
    ) -> None:
        """Install failure-only canonical convergence diagnostics."""

        self._canonical_engine.set_reflow_mismatch_observer(observer)

    def set_incremental_rejection_observer(
        self,
        observer: Callable[[str], None] | None,
    ) -> None:
        """Install failure-only incremental publication diagnostics."""

        self._incremental_rejection_observer = observer

    def _incremental_request(
        self,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None,
    ) -> PromptLayoutRequest:
        """Build one trailing-edit request from the current frame."""

        return PromptLayoutRequest(
            previous=self._frame.output,
            projection_document=projection_document,
            prompt_document_view=prompt_document_view,
            configuration=self._frame.output.configuration,
        )

    def _publish_incremental(
        self,
        outcome: PromptLayoutOutcome,
    ) -> PromptIncrementalFrameApplyResult:
        """Publish one accepted incremental outcome and report rejection explicitly."""

        if (
            outcome.status is not PromptLayoutStatus.APPLIED
            or outcome.output is None
            or outcome.damage is None
        ):
            rejection_reason = outcome.reason.value
            observer = self._incremental_rejection_observer
            if observer is not None:
                observer(rejection_reason)
            return PromptIncrementalFrameApplyResult(
                damage=None,
                rejection_reason=rejection_reason,
            )
        return PromptIncrementalFrameApplyResult(
            damage=self._frame.publish(outcome),
            rejection_reason="",
        )

    def _rebuild(
        self,
        *,
        projection_document: PromptProjectionDocument,
        prompt_document_view: PromptDocumentView | None,
        configuration: PromptLayoutConfiguration,
        reset_paint_state: bool = False,
    ) -> None:
        """Publish one canonical frame after a non-incremental transition."""

        outcome = self._canonical_engine.build(
            PromptLayoutRequest(
                previous=None,
                projection_document=projection_document,
                prompt_document_view=prompt_document_view,
                configuration=configuration,
            )
        )
        _required_applied_output(outcome, operation="canonical build")
        self._frame.publish(outcome, reset_paint_state=reset_paint_state)


def _required_applied_output(
    outcome: PromptLayoutOutcome,
    *,
    operation: str,
) -> PromptLayoutOutput:
    """Return an applied output or raise for an impossible engine rejection."""

    if outcome.status is not PromptLayoutStatus.APPLIED or outcome.output is None:
        raise AssertionError(
            f"{operation} rejected prompt layout: {outcome.reason.value}"
        )
    return outcome.output


__all__ = [
    "PromptIncrementalFrameApplyResult",
    "PromptLayoutEditToFrameCoordinator",
]
