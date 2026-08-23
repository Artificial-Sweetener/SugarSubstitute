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

"""Tests for prompt-safe prompt projection observability helpers."""

from __future__ import annotations

import logging

import pytest
import substitute.presentation.editor.prompt_editor.projection.observability as projection_observability

from substitute.presentation.editor.prompt_editor.projection.observability import (
    log_projection_timing,
    projection_observability_started_at,
)

_LOGGER_NAME = (
    "sugarsubstitute.presentation.editor.prompt_editor.projection.observability"
)


@pytest.fixture(autouse=True)
def _fixed_elapsed_ms(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make observability duration assertions independent of wall-clock timing."""

    monkeypatch.setattr(projection_observability, "elapsed_ms_since", lambda _: 1.25)


def test_projection_timing_logs_prompt_safe_source_metrics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Projection timing should expose source metrics without source text."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    elapsed_ms = log_projection_timing(
        "source_change.prepare_document_view",
        started_at=0.0,
        text_length=42,
        emit_text_changed=True,
    )

    assert elapsed_ms >= 0.0
    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "source_change.prepare_document_view" in messages[0]
    assert "elapsed_ms=" in messages[0]
    assert "text_length=42" in messages[0]
    assert "emit_text_changed=True" in messages[0]
    assert "source_text" not in messages[0].lower()


def test_projection_timing_logs_apply_path_without_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Projection apply diagnostics should log decisions, not prompt content."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    log_projection_timing(
        "incremental_apply.source_change",
        started_at=projection_observability_started_at(),
        text_length=11,
        apply_path="incremental",
        fast_projection_applied=True,
        wrap_reflow_deferred=False,
        incremental_plain_edit_attempted=True,
    )

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "incremental_apply.source_change" in messages[0]
    assert "apply_path=incremental" in messages[0]
    assert "fast_projection_applied=True" in messages[0]
    assert "wrap_reflow_deferred=False" in messages[0]
    assert "incremental_plain_edit_attempted=True" in messages[0]


@pytest.mark.parametrize(
    "unsafe_field_name",
    [
        "prompt_text",
        "source_text",
        "selected_text",
        "token_payload",
        "trigger_words",
        "file_path",
        "api_key",
        "authorization_header",
        "cookie_value",
        "credential_name",
        "exception_message",
        "field_value",
        "raw_exception",
    ],
)
def test_projection_timing_rejects_content_bearing_field_names(
    unsafe_field_name: str,
) -> None:
    """Projection source/rebuild logs should reject prompt-sensitive fields."""

    with pytest.raises(ValueError, match="not prompt-safe"):
        log_projection_timing(
            "source_change.prepare_document_view",
            started_at=projection_observability_started_at(),
            **{unsafe_field_name: "leak"},
        )


def test_projection_timing_rejects_content_bearing_event_names() -> None:
    """Projection event names should not describe prompt content."""

    with pytest.raises(ValueError, match="not prompt-safe"):
        log_projection_timing(
            "source_text.probe",
            started_at=projection_observability_started_at(),
            text_length=1,
        )
