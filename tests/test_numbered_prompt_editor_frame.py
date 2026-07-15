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

"""Tests for the managed text asset numbered prompt editor frame."""

from __future__ import annotations

import os

import pytest

from substitute.application.prompt_editor import (
    PromptEditorFeature,
    wildcard_management_prompt_feature_profile,
)
from substitute.presentation.managed_text_assets import NumberedPromptEditorFrame
from tests.prompt_autocomplete_test_helpers import EmptyPromptAutocompleteGateway
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
)
from tests.execution_test_helpers import immediate_prompt_task_executor_factory

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "prompt editor Qt frame tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_numbered_prompt_editor_frame_delegates_text_and_counts_lines() -> None:
    """The frame should keep source text ownership in the wrapped PromptEditor."""

    app = ensure_qapp()
    frame = _frame()
    frame.show()
    frame.setPlainText("first\nsecond\nthird")
    process_events(app)

    assert frame.toPlainText() == "first\nsecond\nthird"
    assert frame.line_count() == 3
    assert frame.formatted_line_number(0) == "01"
    assert frame.formatted_line_number(2) == "03"


def test_numbered_prompt_editor_frame_expands_gutter_after_99_lines() -> None:
    """The gutter should grow when source line numbers require more digits."""

    app = ensure_qapp()
    frame = _frame()
    frame.show()
    frame.setPlainText("\n".join(str(index) for index in range(99)))
    process_events(app)
    two_digit_width = frame.gutter_width()

    frame.setPlainText("\n".join(str(index) for index in range(100)))
    process_events(app)

    assert frame.formatted_line_number(99) == "100"
    assert frame.gutter_width() > two_digit_width


def test_numbered_prompt_editor_frame_uses_projection_source_line_geometry() -> None:
    """Zebra helpers should read visible logical lines from prompt projection geometry."""

    app = ensure_qapp()
    frame = _frame()
    frame.resize(520, 260)
    frame.show()
    frame.setPlainText("alpha\n{nested/hair}\nomega")
    process_events(app)

    source_line_rects = frame.editor().source_line_rects()

    assert tuple(rect.line_index for rect in source_line_rects)[:3] == (0, 1, 2)
    assert 1 in frame.zebra_line_indexes()
    assert frame._gutter.parent() is frame.editor()
    assert frame.editor().viewportMargins().left() == frame.gutter_width()
    assert frame._gutter.x() == frame.editor().contentsRect().left() - 4
    assert frame._gutter.width() > frame.gutter_width()
    assert (
        frame._gutter.x() + frame._gutter.width()
        == frame.editor().contentsRect().left() + frame.gutter_width()
    )
    assert frame.editor().cursorRect().left() < frame.editor().viewport().width()


def test_numbered_prompt_editor_frame_counts_trailing_empty_source_line() -> None:
    """A trailing newline should produce a separate final numbered row."""

    app = ensure_qapp()
    frame = _frame()
    frame.resize(520, 260)
    frame.show()
    frame.setPlainText("alpha\n")
    process_events(app)

    source_line_rects = frame.editor().source_line_rects()

    assert frame.line_count() == 2
    assert tuple(rect.line_index for rect in source_line_rects) == (0, 1)
    assert source_line_rects[1].rect.top() > source_line_rects[0].rect.top()


def test_wildcard_management_feature_profile_disables_non_wildcard_ui() -> None:
    """Wildcard management should avoid the legacy syntax path's broad defaults."""

    profile = wildcard_management_prompt_feature_profile()

    assert profile.supports(PromptEditorFeature.EMPHASIS) is True
    assert profile.supports(PromptEditorFeature.WILDCARD_SYNTAX) is True
    assert profile.supports(PromptEditorFeature.WILDCARD_AUTOCOMPLETE) is True
    assert profile.supports(PromptEditorFeature.SEGMENT_REORDER) is False
    assert profile.supports(PromptEditorFeature.LORA_PICKER) is False
    assert profile.supports(PromptEditorFeature.LORA_TRIGGER_WORDS) is False


def _frame() -> NumberedPromptEditorFrame:
    """Create a numbered prompt editor frame with deterministic test gateways."""

    return NumberedPromptEditorFrame(
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=StaticPromptWildcardCatalogGateway({}),
        prompt_feature_profile=wildcard_management_prompt_feature_profile(),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
