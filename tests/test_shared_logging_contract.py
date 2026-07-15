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

"""Contract tests for shared structured logging helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from substitute.shared.logging import logger as shared_logger


class _CaptureLogger:
    """Capture emitted logging payloads for assertions."""

    def __init__(self) -> None:
        self.records: list[tuple[str, str]] = []

    def debug(self, message: str) -> None:
        """Capture debug messages."""
        self.records.append(("debug", message))

    def info(self, message: str) -> None:
        """Capture info messages."""
        self.records.append(("info", message))

    def warning(self, message: str) -> None:
        """Capture warning messages."""
        self.records.append(("warning", message))

    def error(self, message: str) -> None:
        """Capture error messages."""
        self.records.append(("error", message))

    def exception(self, message: str) -> None:
        """Capture exception messages."""
        self.records.append(("exception", message))


def test_configure_default_logging_runs_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Logging bootstrap should call basicConfig only for first invocation."""

    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def _fake_basic_config(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(logging, "basicConfig", _fake_basic_config)
    monkeypatch.setattr(shared_logger, "_LOGGING_CONFIGURED", False)

    shared_logger.configure_default_logging(level=logging.DEBUG)
    shared_logger.configure_default_logging(level=logging.ERROR)

    assert len(calls) == 1
    assert calls[0][1]["level"] == logging.DEBUG


def test_configure_default_logging_defaults_to_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default logging should avoid verbose INFO output unless requested."""

    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def _fake_basic_config(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(logging, "basicConfig", _fake_basic_config)
    monkeypatch.setattr(shared_logger, "_LOGGING_CONFIGURED", False)

    shared_logger.configure_default_logging()

    assert calls[0][1]["level"] == logging.WARNING


def test_configure_file_logging_adds_rotating_handler_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """File logging should create one durable handler per resolved log path."""

    handlers: list[Any] = []
    monkeypatch.setattr(shared_logger, "_LOGGING_CONFIGURED", False)
    monkeypatch.setattr(shared_logger, "_FILE_LOG_PATHS", set())
    monkeypatch.setattr(logging, "basicConfig", lambda **_kwargs: None)
    monkeypatch.setattr(
        logging.getLogger(),
        "addHandler",
        lambda handler: handlers.append(handler),
    )

    first = shared_logger.configure_file_logging(tmp_path)
    second = shared_logger.configure_file_logging(tmp_path)

    assert first == second
    assert first == tmp_path.resolve() / "sugarsubstitute.log"
    assert tmp_path.exists()
    assert len(handlers) == 1
    assert handlers[0].level == logging.WARNING


def test_configure_file_logging_respects_explicit_level(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """File logging can still opt into INFO diagnostics for targeted sessions."""

    handlers: list[Any] = []
    monkeypatch.setattr(shared_logger, "_LOGGING_CONFIGURED", False)
    monkeypatch.setattr(shared_logger, "_FILE_LOG_PATHS", set())
    monkeypatch.setattr(logging, "basicConfig", lambda **_kwargs: None)
    monkeypatch.setattr(
        logging.getLogger(),
        "addHandler",
        lambda handler: handlers.append(handler),
    )

    shared_logger.configure_file_logging(tmp_path, level=logging.INFO)

    assert handlers[0].level == logging.INFO


def test_configure_prompt_observability_logging_targets_prompt_debug_records(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Prompt observability should persist prompt debug logs without global debug noise."""

    handlers: list[Any] = []
    base_logger = logging.getLogger("sugarsubstitute")
    application_logger = logging.getLogger("sugarsubstitute.application.prompt_editor")
    presentation_logger = logging.getLogger(
        "sugarsubstitute.presentation.editor.prompt_editor"
    )
    monkeypatch.setattr(shared_logger, "_LOGGING_CONFIGURED", False)
    monkeypatch.setattr(shared_logger, "_PROMPT_OBSERVABILITY_FILE_PATHS", set())
    monkeypatch.setattr(logging, "basicConfig", lambda **_kwargs: None)
    monkeypatch.setattr(
        base_logger, "addHandler", lambda handler: handlers.append(handler)
    )
    monkeypatch.setattr(application_logger, "level", logging.NOTSET)
    monkeypatch.setattr(presentation_logger, "level", logging.WARNING)

    first = shared_logger.configure_prompt_observability_logging(tmp_path)
    second = shared_logger.configure_prompt_observability_logging(tmp_path)

    assert first == second
    assert first == tmp_path.resolve() / "prompt-editor-observability.log"
    assert len(handlers) == 1
    assert handlers[0].level == logging.DEBUG
    assert application_logger.level == logging.DEBUG
    assert presentation_logger.level == logging.DEBUG
    prompt_record = logging.LogRecord(
        "sugarsubstitute.application.prompt_editor.prompt_syntax_service",
        logging.DEBUG,
        "",
        1,
        "prompt_lora_resolution.result",
        (),
        None,
    )
    unrelated_record = logging.LogRecord(
        "sugarsubstitute.infrastructure.comfy.websocket_listener",
        logging.DEBUG,
        "",
        1,
        "unrelated",
        (),
        None,
    )
    assert handlers[0].filters[0].filter(prompt_record)
    assert not handlers[0].filters[0].filter(unrelated_record)


def test_prompt_observability_logging_writes_filtered_debug_records(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Prompt observability should write prompt debug records to its durable file."""

    base_logger = logging.getLogger("sugarsubstitute")
    existing_handlers = list(base_logger.handlers)
    application_logger = logging.getLogger("sugarsubstitute.application.prompt_editor")
    presentation_logger = logging.getLogger(
        "sugarsubstitute.presentation.editor.prompt_editor"
    )
    prompt_logger = logging.getLogger(
        "sugarsubstitute.application.prompt_editor.contract"
    )
    unrelated_logger = logging.getLogger("sugarsubstitute.infrastructure.contract")
    monkeypatch.setattr(shared_logger, "_LOGGING_CONFIGURED", False)
    monkeypatch.setattr(shared_logger, "_PROMPT_OBSERVABILITY_FILE_PATHS", set())
    monkeypatch.setattr(application_logger, "level", logging.NOTSET)
    monkeypatch.setattr(presentation_logger, "level", logging.NOTSET)
    try:
        log_path = shared_logger.configure_prompt_observability_logging(tmp_path)

        prompt_logger.debug("prompt_lora_resolution.result")
        unrelated_logger.debug("unrelated_debug_noise")
        for handler in base_logger.handlers:
            handler.flush()

        written_text = log_path.read_text(encoding="utf-8")
    finally:
        for handler in list(base_logger.handlers):
            if handler not in existing_handlers:
                base_logger.removeHandler(handler)
                handler.close()

    assert "prompt_lora_resolution.result" in written_text
    assert "unrelated_debug_noise" not in written_text


def test_log_info_serializes_context_sorted_and_redacts_sensitive_values() -> None:
    """Context serializer should sort keys and redact known sensitive key fragments."""

    logger: Any = _CaptureLogger()

    shared_logger.log_info(
        logger,
        "message",
        zeta="last",
        token="secret-token",
        Authorization="Bearer abc",
        alpha="first",
    )

    assert logger.records == [
        (
            "info",
            "message | Authorization=[REDACTED] alpha=first token=[REDACTED] zeta=last",
        )
    ]


def test_log_info_preserves_safe_token_count_metric() -> None:
    """Numeric token counts should remain visible while token values are redacted."""

    logger: Any = _CaptureLogger()

    shared_logger.log_info(
        logger,
        "message",
        session_token="secret-token",
        token_count=7,
    )

    assert logger.records == [
        ("info", "message | session_token=[REDACTED] token_count=7")
    ]


def test_log_exception_keeps_message_and_context_suffix() -> None:
    """Exception helper should emit serialized context with redaction semantics."""

    logger: Any = _CaptureLogger()

    shared_logger.log_exception(
        logger,
        "failed",
        workflow_id="wf-1",
        api_key="abc",
    )

    assert logger.records == [
        ("exception", "failed | api_key=[REDACTED] workflow_id=wf-1")
    ]


def test_log_warning_serializes_context_sorted_and_redacts_sensitive_values() -> None:
    """Warning helper should preserve sorted context and sensitive-key redaction."""

    logger: Any = _CaptureLogger()

    shared_logger.log_warning(
        logger,
        "warned",
        zeta="last",
        session_token="secret-token",
        alpha="first",
    )

    assert logger.records == [
        ("warning", "warned | alpha=first session_token=[REDACTED] zeta=last")
    ]


def test_log_warning_exception_preserves_traceback_without_exception_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Exception warning helper should keep traceback context without error text."""

    logger = logging.getLogger("tests.shared_logging.exception_warning")
    caplog.set_level(logging.WARNING, logger=logger.name)
    prompt_like_error_message = "prompt text should not be logged"

    try:
        raise RuntimeError(prompt_like_error_message)
    except RuntimeError as error:
        shared_logger.log_warning_exception(
            logger,
            "failed safely",
            error=error,
            source_length=22,
            api_key="secret",
        )

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.exc_info is not None
    assert "failed safely" in record.message
    assert "error_type=RuntimeError" in record.message
    assert "source_length=22" in record.message
    assert "api_key=[REDACTED]" in record.message
    assert prompt_like_error_message not in caplog.text


def test_elapsed_ms_since_uses_non_negative_monotonic_delta() -> None:
    """Elapsed helper should report milliseconds and clamp negative clock drift."""

    assert shared_logger.elapsed_ms_since(1.0, clock=lambda: 1.125) == 125.0
    assert shared_logger.elapsed_ms_since(2.0, clock=lambda: 1.0) == 0.0


def test_log_timing_emits_elapsed_context_at_requested_level() -> None:
    """Timing helper should add formatted elapsed milliseconds to structured logs."""

    logger: Any = _CaptureLogger()

    elapsed_ms = shared_logger.log_timing(
        logger,
        "timed",
        started_at=10.0,
        clock=lambda: 10.25,
        level="debug",
        workflow_id="wf-a",
    )

    assert elapsed_ms == 250.0
    assert logger.records == [("debug", "timed | elapsed_ms=250.000 workflow_id=wf-a")]
