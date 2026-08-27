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

"""Contract tests for token-aware projection layout geometry and hit testing."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import replace


from PySide6.QtCore import QRectF, QSizeF
from PySide6.QtGui import QColor, QFont, QFontMetricsF

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import PromptReorderChipView
from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
)
from substitute.presentation.editor.prompt_editor.projection.edit_to_frame import (
    PromptLayoutEditToFrameCoordinator,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)
from substitute.presentation.editor.prompt_editor.layout.models import (
    PromptProjectionLayoutSnapshot,
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)
from substitute.presentation.editor.prompt_editor.layout.contracts import (
    PromptLayoutOutput,
)
from substitute.presentation.editor.prompt_editor.projection.tokens import (
    PromptEmphasisPrefixRenderer,
    PromptEmphasisSuffixRenderer,
)
from tests.support.prompt_editor.projection_engine_support import ensure_qapp

_REGION_TEXT_COLOR = QColor(222, 223, 224)


def _line_texts(layout: PromptLayoutEditToFrameCoordinator) -> tuple[str, ...]:
    """Return visible line text, including inline-object display text."""

    line_texts: list[str] = []
    for line in layout.frame.output.snapshot.lines:  # noqa: SLF001
        line_text = ""
        for fragment in line.fragments:
            if isinstance(fragment, PromptProjectionTextFragment):
                line_text += fragment.text
                continue
            run = layout.frame.output.projection_document.run_by_id(fragment.run_id)
            line_text += "" if run is None else run.display_text
        line_texts.append(line_text)
    return tuple(line_texts)


def _assert_line_fragments_match_current_runs(
    layout: PromptLayoutEditToFrameCoordinator,
    line: PromptProjectionLineSnapshot,
) -> None:
    """Assert every fragment on one line resolves to its current run slice."""

    for fragment in line.fragments:
        run = layout.frame.paint_input.effective_run(fragment.run_id)
        assert run is not None
        if not isinstance(fragment, PromptProjectionTextFragment):
            continue
        local_start = fragment.projection_start - run.projection_start
        local_end = fragment.projection_end - run.projection_start
        assert run.display_text[local_start:local_end] == fragment.text


def _blank_line_break_ranges(prompt: str) -> tuple[tuple[int, int], ...]:
    """Return newline ranges that own visual blank rows in consecutive breaks."""

    return tuple(
        (index + 1, index + 2)
        for index in range(len(prompt) - 1)
        if prompt[index] == "\n" and prompt[index + 1] == "\n"
    )


def _line_has_selection_rect(
    line: PromptProjectionLineSnapshot,
    selection_rects: tuple[QRectF, ...],
) -> bool:
    """Return whether a selection rect intersects one layout line."""

    line_bottom = line.top + line.height
    for rect in selection_rects:
        rect_center_y = rect.top() + rect.height() / 2.0
        if line.top <= rect_center_y <= line_bottom:
            return True
    return False


def _layout_geometry_signature(
    layout: PromptLayoutEditToFrameCoordinator,
) -> tuple[
    tuple[float, float, int, int, tuple[tuple[float, float, float, float], ...]],
    ...,
]:
    """Return stable row and text-fragment geometry for layout comparisons."""

    signature = []
    for line in layout.frame.output.snapshot.lines:  # noqa: SLF001
        signature.append(
            (
                round(line.top, 3),
                round(line.height, 3),
                line.source_start,
                line.source_end,
                tuple(
                    (
                        round(fragment.rect.x(), 3),
                        round(fragment.rect.y(), 3),
                        round(fragment.rect.width(), 3),
                        round(fragment.rect.height(), 3),
                    )
                    for fragment in line.fragments
                ),
            )
        )
    return tuple(signature)


class _NonIterableCaretRectMapping(Mapping[int, QRectF]):
    """Raise if a trailing edit tries to clone prior caret rects by iteration."""

    def __init__(self, backing: dict[int, QRectF]) -> None:
        """Store caret rects available only through direct key lookup."""

        self._backing = backing

    def __len__(self) -> int:
        """Return the number of available caret rects."""

        return len(self._backing)

    def __iter__(self) -> Iterator[int]:
        """Reject broad iteration of the prior caret-rect map."""

        raise AssertionError("caret rect mapping was iterated")

    def __getitem__(self, key: int) -> QRectF:
        """Return one caret rect by exact projection position."""

        return self._backing[key]


def _install_non_iterable_caret_rect_mapping(
    output: PromptLayoutOutput,
) -> PromptLayoutOutput:
    """Return layout output whose prior caret mapping forbids broad scans."""

    snapshot = output.snapshot
    backing = {
        caret_stop.projection_position: QRectF(caret_stop.rect)
        for line in snapshot.lines
        for caret_stop in line.caret_stops
    }
    return replace(
        output,
        snapshot=replace(
            snapshot,
            caret_rects_by_projection_position=_NonIterableCaretRectMapping(backing),
        ),
    )


class _CountingEmphasisPrefixRenderer(PromptEmphasisPrefixRenderer):
    """Count prefix measurement calls made by geometry reuse checks."""

    def __init__(self) -> None:
        """Initialize measurement counters."""

        super().__init__()
        self.measure_calls = 0

    def measure_inline_object(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        *,
        base_font: QFont,
    ) -> QSizeF:
        """Count one prefix measurement and delegate to the real renderer."""

        self.measure_calls += 1
        return super().measure_inline_object(run, token, base_font=base_font)


class _CountingEmphasisSuffixRenderer(PromptEmphasisSuffixRenderer):
    """Count suffix measurement calls made by geometry reuse checks."""

    def __init__(self) -> None:
        """Initialize measurement counters."""

        super().__init__()
        self.measure_calls = 0

    def measure_inline_object(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        *,
        base_font: QFont,
    ) -> QSizeF:
        """Count one suffix measurement and delegate to the real renderer."""

        self.measure_calls += 1
        return super().measure_inline_object(run, token, base_font=base_font)


def _assert_all_projection_caret_rects_resolve(
    layout: PromptLayoutEditToFrameCoordinator,
    projection: PromptProjectionDocument,
) -> None:
    """Assert every projection boundary resolves to a caret rect."""

    caret_rects = layout.frame.output.snapshot.caret_rects_by_projection_position  # noqa: SLF001
    assert len(caret_rects) == projection.mapping.projection_length + 1
    for projection_position in range(projection.mapping.projection_length + 1):
        assert caret_rects[projection_position].height() > 0.0


def _assert_snapshot_caret_rects_resolve(
    snapshot: PromptProjectionLayoutSnapshot,
    projection: PromptProjectionDocument,
) -> None:
    """Assert every projection boundary resolves in one engine-owned snapshot."""

    caret_rects = snapshot.caret_rects_by_projection_position
    assert len(caret_rects) == projection.mapping.projection_length + 1
    for projection_position in range(projection.mapping.projection_length + 1):
        assert caret_rects[projection_position].height() > 0.0


def _assert_word_not_split_across_lines(
    line_texts: tuple[str, ...],
    word: str,
) -> None:
    """Assert that no adjacent visual lines divide one normal word."""

    for previous_line, next_line in zip(line_texts, line_texts[1:], strict=False):
        for split_index in range(1, len(word)):
            assert not (
                previous_line.endswith(word[:split_index])
                and next_line.startswith(word[split_index:])
            ), line_texts


def _line_indices_for_source_range(
    layout: PromptLayoutEditToFrameCoordinator,
    *,
    start: int,
    end: int,
) -> set[int]:
    """Return wrapped line indices touched by a source range."""

    line_indices: set[int] = set()
    for line_index, line in enumerate(layout.frame.output.snapshot.lines):  # noqa: SLF001
        for fragment in line.fragments:
            if any(
                start <= source_position < end
                for source_position in fragment.source_positions
            ):
                line_indices.add(line_index)
                break
    return line_indices


def _plain_text_wrap_width(*fragments: str) -> float:
    """Return a host-font-aware width that fits each supplied fragment."""

    ensure_qapp()
    widest_fragment = max(
        QFontMetricsF(QFont()).horizontalAdvance(fragment) for fragment in fragments
    )
    return widest_fragment + 9.0


def _reorder_geometry_inputs_for_text(
    text: str,
) -> tuple[
    PromptReorderLayoutView,
    tuple[PromptReorderChipView, ...],
    dict[int, tuple[int, int]],
    dict[int, tuple[tuple[int, int], ...]],
]:
    """Return application-owned reorder metadata keyed by semantic chip index."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    chips = document_service.reorder_chips(document_view)
    layout_view = document_service.build_reorder_layout_view(document_view)
    rendered_ranges = {
        chip.index: (chip.selection_start, chip.selection_end) for chip in chips
    }
    owned_ranges: dict[int, tuple[tuple[int, int], ...]] = {
        chip.index: ((chip.selection_start, chip.selection_end),) for chip in chips
    }
    return layout_view, chips, rendered_ranges, owned_ranges
