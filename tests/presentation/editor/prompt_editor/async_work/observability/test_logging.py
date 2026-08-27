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

"""Verify privacy-preserving prompt-editor asynchronous observability."""

from __future__ import annotations

import logging

import pytest

from substitute.presentation.editor.prompt_editor.async_work.execution import (
    PromptAsyncRequestContext,
)
from substitute.presentation.editor.prompt_editor.async_work.observability import (
    log_prompt_async_warning,
    prompt_async_context_log_fields,
)
from substitute.shared.logging.logger import get_logger


@pytest.mark.parametrize(
    "unsafe_field_name",
    [
        "prompt_text",
        "selected_prompt_text",
        "selected_text",
        "trigger_words",
        "api_key",
        "local_path",
    ],
)
def test_async_context_log_fields_reject_content_bearing_field_names(
    unsafe_field_name: str,
) -> None:
    """Reject fields that can contain prompts or secrets."""

    context = PromptAsyncRequestContext(
        operation="semantic_refresh",
        reason="unit",
        safe_fields=((unsafe_field_name, "unsafe"),),
    )

    with pytest.raises(ValueError, match="not prompt-safe"):
        prompt_async_context_log_fields(context)


def test_async_warning_logging_preserves_traceback_without_exception_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Keep traceback context without serializing exception messages."""

    logger = get_logger("presentation.editor.prompt_editor.async_work.test")
    caplog.set_level(logging.WARNING, logger=logger.name)

    prompt_like_error_message = "prompt secret should not be logged"
    try:
        raise RuntimeError(prompt_like_error_message)
    except RuntimeError as error:
        log_prompt_async_warning(
            logger,
            "async failure",
            error=error,
            request_id=12,
            source_length=33,
        )

    assert "async failure" in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert "request_id=12" in caplog.text
    assert "source_length=33" in caplog.text
    assert prompt_like_error_message not in caplog.text
