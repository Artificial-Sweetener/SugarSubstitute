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

"""Verify prompt-editor construction observability stays timing-only."""

from __future__ import annotations

import logging
from time import perf_counter

import pytest

from substitute.presentation.editor.prompt_editor.composition.wiring import (
    PromptEditorConstructionObserver,
)


def test_prompt_editor_construction_observer_logs_safe_timing_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Construction timing logs should expose safe metrics without prompt data."""

    logger = logging.getLogger(
        "sugarsubstitute.presentation.editor.prompt_editor.construction_test"
    )
    logger.setLevel(logging.DEBUG)
    observer = PromptEditorConstructionObserver(logger)
    started_at = perf_counter()

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        elapsed_ms = observer.log_timing(
            "Initialized prompt editor host shell",
            started_at=started_at,
            maximum_visible_lines=10,
            has_lora_catalog=False,
            level="debug",
        )

    assert elapsed_ms >= 0.0
    assert "Initialized prompt editor host shell" in caplog.text
    assert "maximum_visible_lines=10" in caplog.text
    assert "has_lora_catalog=False" in caplog.text
    assert "elapsed_ms=" in caplog.text


@pytest.mark.parametrize(
    "field_name",
    [
        "prompt_text",
        "selected_text",
        "source_text",
        "token_payload",
        "local_path",
        "api_key",
        "authorization_header",
        "cookie_value",
        "credential_name",
        "exception_message",
        "field_value",
        "raw_exception",
        "trigger_words",
    ],
)
def test_prompt_editor_construction_observer_rejects_prompt_sensitive_fields(
    field_name: str,
) -> None:
    """Construction timing context should fail closed for prompt-sensitive fields."""

    observer = PromptEditorConstructionObserver(logging.getLogger(__name__))

    with pytest.raises(ValueError, match=field_name):
        observer.log_timing(
            "Rejected unsafe prompt-editor construction field",
            started_at=perf_counter(),
            level="debug",
            **{field_name: "secret"},
        )
