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

"""Drain managed process output independently of startup cancellation."""

from __future__ import annotations

from collections.abc import Iterator
from codecs import getincrementaldecoder
import os
from time import perf_counter
from typing import IO, Callable

from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_warning_exception,
)

from substitute.infrastructure.comfy.managed_process_state import (
    ManagedTaskFactory,
    ManagedLongLivedTaskHandle,
)

LogCallback = Callable[[str], None]
_LOGGER = get_logger("infrastructure.comfy.managed_output_pump")
_STARTUP_HARNESS_ENV = "SUGAR_SUBSTITUTE_STARTUP_HARNESS"


def start_output_pump_task(
    *,
    request_id: int,
    task_factory: ManagedTaskFactory,
    stdout_stream: IO[bytes],
    on_log: LogCallback,
) -> ManagedLongLivedTaskHandle:
    """Start one process-pump task for managed Comfy output."""

    def pump_output(cancellation: CancellationSource) -> None:
        """Forward ComfyUI output records into the provided log callback."""

        record_count = 0
        max_on_log_ms = 0.0
        total_on_log_ms = 0.0
        started_at = perf_counter()
        try:
            for record in _iter_output_records(stdout_stream):
                if cancellation.is_cancelled:
                    return
                record_count += 1
                on_log_started_at = perf_counter()
                _emit_process_output_record(
                    on_log=on_log,
                    record=record,
                    request_id=request_id,
                    record_count=record_count,
                    diagnostic=False,
                )
                on_log_ms = (perf_counter() - on_log_started_at) * 1000.0
                total_on_log_ms += on_log_ms
                max_on_log_ms = max(max_on_log_ms, on_log_ms)
        finally:
            try:
                if _managed_output_pump_diagnostics_enabled() and record_count:
                    _emit_process_output_record(
                        on_log=on_log,
                        record=(
                            "Substitute startup diagnostic "
                            "event=managed_output_pump_timing "
                            f"total_duration_ms="
                            f"{round((perf_counter() - started_at) * 1000.0, 3)} "
                            f"record_count={record_count} "
                            f"total_on_log_ms={round(total_on_log_ms, 3)} "
                            f"max_on_log_ms={round(max_on_log_ms, 3)}"
                        ),
                        request_id=request_id,
                        record_count=record_count,
                        diagnostic=True,
                    )
            finally:
                stdout_stream.close()

    return task_factory(
        TaskIdentity(
            request_id=request_id,
            domain="managed_comfy_output_pump",
        ),
        ExecutionContext(
            operation="managed_comfy_output_pump",
            reason="managed_process_output",
            lane="process_pump",
        ),
        pump_output,
        "substitute-managed-comfy-output-pump",
    )


def _emit_process_output_record(
    *,
    on_log: LogCallback,
    record: str,
    request_id: int,
    record_count: int,
    diagnostic: bool,
) -> None:
    """Forward one process-output record without letting consumers stop pipe drain."""

    try:
        on_log(record)
    except Exception as error:
        log_warning_exception(
            _LOGGER,
            "Managed Comfy output consumer failed; continuing pipe drain",
            error=error,
            request_id=request_id,
            record_count=record_count,
            diagnostic=diagnostic,
        )


def _managed_output_pump_diagnostics_enabled() -> bool:
    """Return whether harness output-pump diagnostics should be emitted."""

    return os.environ.get(_STARTUP_HARNESS_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _iter_output_records(
    stdout_stream: IO[bytes], *, chunk_size: int = 4096
) -> Iterator[str]:
    """Decode one byte stream into newline- and carriage-return-delimited records."""

    decoder = getincrementaldecoder("utf-8")("replace")
    pending_text = ""
    while True:
        chunk = stdout_stream.read(chunk_size)
        if not chunk:
            break
        pending_text += decoder.decode(chunk)
        extracted_records, pending_text = _split_complete_output_records(pending_text)
        yield from extracted_records

    pending_text += decoder.decode(b"", final=True)
    extracted_records, pending_text = _split_complete_output_records(pending_text)
    yield from extracted_records
    if pending_text:
        yield pending_text


def _split_complete_output_records(text: str) -> tuple[tuple[str, ...], str]:
    """Split decoded terminal text into complete records plus one trailing partial."""

    record_start = 0
    cursor = 0
    records: list[str] = []
    text_length = len(text)
    while cursor < text_length:
        character = text[cursor]
        if character == "\r":
            if cursor + 1 < text_length and text[cursor + 1] == "\n":
                records.append(text[record_start : cursor + 2])
                cursor += 2
                record_start = cursor
                continue
            records.append(text[record_start : cursor + 1])
            cursor += 1
            record_start = cursor
            continue
        if character == "\n":
            records.append(text[record_start : cursor + 1])
            cursor += 1
            record_start = cursor
            continue
        cursor += 1
    return tuple(records), text[record_start:]
