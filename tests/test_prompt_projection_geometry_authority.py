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

"""Regression tests for prompt projection geometry ownership."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import PromptSyntaxSpanView
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.projection.snapshot import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.prompt_projection_surface_test_helpers import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "prompt geometry authority tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


_REPORTED_PROMPT = """best quality, score_7, ppw, masterpiece, very aesthetic, character portrait, faux figurine, garden,

1girl, (mature female:1.10), floating, black bident, parted lips, contrapposto, holding double helix spear, planted spear, skinny,

(small:1.20) breasts, flat chest, sparkling blue sash, sparkling blue bralette, (pale skin:1.20),

empty eyes, pointy ears, sharp teeth, too many rabbits, backlighting, see-through silhouette,

1girl

white dress, wrathful, pink bridal garter, sparkling dress,

glowing red eyes, long white hair, swept bangs, elegant seductive pose, twintails, white eyebrows, pink hair ribbon, see-through dress, iridescent belt, spaghetti strap, short white oni horns,

convenient censoring, barefoot, cloudy sky, blue sky, golden hour, night sky, column, black and white roses, halo behind head,

<lora:Anima\\style\\People'sWorks_v10_Animabasev1.0_test3-000008:1.00>"""


@dataclass(frozen=True, slots=True)
class _FragmentGeometry:
    """Describe geometry for one fragment without retaining Qt objects."""

    kind: str
    run_id: str
    token_id: str | None
    projection_start: int
    projection_end: int
    rect: tuple[float, float, float, float]
    baseline: float | None


@dataclass(frozen=True, slots=True)
class _LineGeometry:
    """Describe geometry for one logical visual line."""

    index: int
    source_start: int
    source_end: int
    top: float
    height: float
    text: str
    fragments: tuple[_FragmentGeometry, ...]


@dataclass(frozen=True, slots=True)
class _GeometrySignature:
    """Describe the layout geometry relevant to one prompt-editor assertion."""

    content_size: tuple[float, float]
    viewport_size: tuple[int, int]
    scroll_value: int
    lines: tuple[_LineGeometry, ...]


def test_comma_after_standalone_1girl_does_not_move_lower_rows(
    widgets: list[QWidget],
) -> None:
    """Typing comma after the standalone tag must not move unrelated lower rows."""

    app = ensure_qapp()
    box = _show_reported_prompt_without_second_1girl(widgets)
    _move_cursor_to_second_1girl_insertion_point(box)
    QTest.keyClicks(box, "1girl")
    process_events(app)
    before = _signature_for_needles(
        box,
        "1girl",
        "convenient censoring",
        "<lora:Anima\\style\\People'sWorks",
    )

    QTest.keyClicks(box, ",")
    process_events(app)
    after = _signature_for_needles(
        box,
        "1girl,",
        "convenient censoring",
        "<lora:Anima\\style\\People'sWorks",
    )

    assert after.scroll_value == before.scroll_value
    assert after.viewport_size == before.viewport_size
    assert (
        _line_by_text(after, "convenient censoring").top
        == _line_by_text(
            before,
            "convenient censoring",
        ).top
    )
    assert (
        _line_by_text(after, "convenient censoring").height
        == _line_by_text(
            before,
            "convenient censoring",
        ).height
    )
    assert _fragment_baselines(after, "convenient censoring") == _fragment_baselines(
        before,
        "convenient censoring",
    )
    assert (
        _line_by_text(after, "People'sWorks_v10").top
        == _line_by_text(
            before,
            "People'sWorks_v10",
        ).top
    )


def test_active_span_refresh_does_not_change_layout_geometry(
    widgets: list[QWidget],
) -> None:
    """Active syntax highlighting must not change canonical layout geometry."""

    box = _show_reported_prompt(widgets)
    surface = surface_for(box)
    before = _signature_for_needles(
        box,
        "1girl,",
        "convenient censoring",
        "<lora:Anima\\style\\People'sWorks",
    )
    active_start = _REPORTED_PROMPT.index("<lora:Anima\\style\\People'sWorks")
    active_end = len(_REPORTED_PROMPT)

    surface.set_active_span(
        PromptSyntaxSpanView(
            kind="lora",
            start=active_start,
            end=active_end,
            depth=0,
        ),
        cursor_position=active_start,
    )
    process_events(ensure_qapp())
    after = _signature_for_needles(
        box,
        "1girl,",
        "convenient censoring",
        "<lora:Anima\\style\\People'sWorks",
    )

    assert after == before


def test_caret_motion_does_not_change_layout_geometry(
    widgets: list[QWidget],
) -> None:
    """Moving the caret through the prompt must not change line geometry."""

    app = ensure_qapp()
    box = _show_reported_prompt(widgets)
    before = _signature_for_needles(
        box,
        "1girl,",
        "convenient censoring",
        "<lora:Anima\\style\\People'sWorks",
    )

    cursor = box.textCursor()
    cursor.setPosition(_REPORTED_PROMPT.index("1girl,"))
    box.setTextCursor(cursor)
    process_events(app)
    cursor.setPosition(_REPORTED_PROMPT.index("1girl,") + len("1girl"))
    box.setTextCursor(cursor)
    process_events(app)
    after = _signature_for_needles(
        box,
        "1girl,",
        "convenient censoring",
        "<lora:Anima\\style\\People'sWorks",
    )

    assert after == before


def test_paint_state_application_does_not_replace_layout_snapshot_geometry(
    widgets: list[QWidget],
) -> None:
    """Applying active paint state must not replace canonical layout geometry."""

    box = _show_reported_prompt(widgets)
    surface = surface_for(box)
    layout = cast(Any, surface)._layout
    before_snapshot_id = id(layout._snapshot)
    before_document_id = id(layout.projection_document)
    before = _signature_for_needles(
        box,
        "1girl,",
        "convenient censoring",
        "<lora:Anima\\style\\People'sWorks",
    )

    surface.set_active_span(
        None,
        cursor_position=_REPORTED_PROMPT.index("1girl,"),
    )
    process_events(ensure_qapp())
    after = _signature_for_needles(
        box,
        "1girl,",
        "convenient censoring",
        "<lora:Anima\\style\\People'sWorks",
    )

    assert id(layout._snapshot) == before_snapshot_id
    assert id(layout.projection_document) == before_document_id
    assert after == before


def _show_reported_prompt(widgets: list[QWidget]) -> PromptEditor:
    """Create one editor containing the reported prompt."""

    return show_prompt_editor(
        widgets,
        text=_REPORTED_PROMPT,
        width=749,
        height=430,
        syntaxes=("emphasis", "wildcard", "lora"),
    )


def _show_reported_prompt_without_second_1girl(
    widgets: list[QWidget],
) -> PromptEditor:
    """Create one editor with the second standalone `1girl` removed."""

    return show_prompt_editor(
        widgets,
        text=_REPORTED_PROMPT.replace("\n1girl\n\nwhite dress", "\n\nwhite dress"),
        width=749,
        height=430,
        syntaxes=("emphasis", "wildcard", "lora"),
    )


def _move_cursor_to_second_1girl_insertion_point(box: PromptEditor) -> None:
    """Place the editor cursor where the reported standalone `1girl` is typed."""

    source_text = box.toPlainText()
    insertion_position = source_text.index("\n\nwhite dress") + 1
    cursor = box.textCursor()
    cursor.setPosition(insertion_position, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    box.setFocus()


def _signature_for_needles(
    box: PromptEditor,
    *needles: str,
) -> _GeometrySignature:
    """Return a geometry signature for lines containing the supplied source text."""

    surface = surface_for(box)
    layout = cast(Any, surface)._layout
    snapshot = layout._snapshot
    source_text = box.toPlainText()
    selected_lines = tuple(
        _line_geometry(layout, line, line_index)
        for line_index, line in enumerate(
            cast(tuple[PromptProjectionLineSnapshot, ...], snapshot.lines)
        )
        if any(
            _line_contains_source_needle(source_text, line, needle)
            for needle in needles
        )
    )
    return _GeometrySignature(
        content_size=(
            round(float(snapshot.content_size.width()), 6),
            round(float(snapshot.content_size.height()), 6),
        ),
        viewport_size=(surface.viewport().width(), surface.viewport().height()),
        scroll_value=surface.verticalScrollBar().value(),
        lines=selected_lines,
    )


def _line_contains_source_needle(
    source_text: str,
    line: PromptProjectionLineSnapshot,
    needle: str,
) -> bool:
    """Return whether a visual line intersects one source-text needle."""

    needle_start = source_text.index(needle)
    needle_end = needle_start + len(needle)
    return line.source_start < needle_end and needle_start < line.source_end


def _line_geometry(
    layout: object,
    line: PromptProjectionLineSnapshot,
    index: int,
) -> _LineGeometry:
    """Return stable geometry data for one prompt projection line."""

    return _LineGeometry(
        index=index,
        source_start=line.source_start,
        source_end=line.source_end,
        top=round(line.top, 6),
        height=round(line.height, 6),
        text=_line_text(layout, line),
        fragments=tuple(_fragment_geometry(fragment) for fragment in line.fragments),
    )


def _line_text(layout: object, line: PromptProjectionLineSnapshot) -> str:
    """Return visible text for one line, including inline-object display text."""

    projection_document = cast(Any, layout).projection_document
    line_text = ""
    for fragment in line.fragments:
        if isinstance(fragment, PromptProjectionTextFragment):
            line_text += fragment.text
            continue
        run = projection_document.run_by_id(fragment.run_id)
        line_text += "" if run is None else run.display_text
    return line_text


def _fragment_geometry(
    fragment: PromptProjectionTextFragment | PromptProjectionInlineObjectFragment,
) -> _FragmentGeometry:
    """Return stable geometry data for one prompt projection fragment."""

    baseline = (
        fragment.baseline
        if isinstance(fragment, PromptProjectionTextFragment)
        else None
    )
    return _FragmentGeometry(
        kind="text" if isinstance(fragment, PromptProjectionTextFragment) else "inline",
        run_id=fragment.run_id,
        token_id=fragment.token_id,
        projection_start=fragment.projection_start,
        projection_end=fragment.projection_end,
        rect=_rect_tuple(fragment.rect),
        baseline=None if baseline is None else round(baseline, 6),
    )


def _rect_tuple(rect: QRectF) -> tuple[float, float, float, float]:
    """Return a stable tuple for one QRectF."""

    return (
        round(rect.x(), 6),
        round(rect.y(), 6),
        round(rect.width(), 6),
        round(rect.height(), 6),
    )


def _line_by_text(signature: _GeometrySignature, needle: str) -> _LineGeometry:
    """Return the selected line containing visible text."""

    return next(line for line in signature.lines if needle in line.text)


def _fragment_baselines(
    signature: _GeometrySignature,
    needle: str,
) -> tuple[float | None, ...]:
    """Return fragment baselines for the selected line containing visible text."""

    return tuple(
        fragment.baseline for fragment in _line_by_text(signature, needle).fragments
    )
