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

"""Contract tests for the shared terminal transcript model."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.terminal.output_transcript import (
    TerminalOutputTranscript,
)


def test_terminal_output_transcript_ignores_blank_records() -> None:
    """Blank terminal records should not change the visible transcript."""

    transcript = TerminalOutputTranscript(max_lines=3)

    assert transcript.apply_record("") is None
    assert transcript.apply_record("   ") is None
    assert transcript.apply_record("\r\n") is None
    assert transcript.snapshot() == ()


def test_terminal_output_transcript_appends_newline_records() -> None:
    """Newline-delimited records should append visible lines in order."""

    transcript = TerminalOutputTranscript(max_lines=3)

    transcript.apply_record("first\n")
    transcript.apply_record("second\n")

    assert transcript.snapshot() == ("first", "second")


def test_terminal_output_transcript_parses_ansi_sgr_to_styled_snapshot() -> None:
    """ANSI SGR records should keep clean text and retain renderable style spans."""

    transcript = TerminalOutputTranscript(max_lines=3)

    mutation = transcript.apply_record(
        "\x1b[32m[INFO]\x1b[0m Using pytorch attention\n"
    )

    assert mutation is not None
    assert mutation.line == "[INFO] Using pytorch attention"
    assert transcript.snapshot() == ("[INFO] Using pytorch attention",)
    styled_line = transcript.styled_snapshot()[0]
    assert styled_line.plain_text == "[INFO] Using pytorch attention"
    assert [(span.text, span.foreground, span.bold) for span in styled_line.spans] == [
        ("[INFO]", "green", False),
        (" Using pytorch attention", None, False),
    ]


def test_terminal_output_transcript_replaces_active_line_for_carriage_return() -> None:
    """Carriage-return records should redraw the active visible line."""

    transcript = TerminalOutputTranscript(max_lines=3)

    transcript.apply_record("0%\r")
    transcript.apply_record("50%\r")
    transcript.apply_record("100%\n")

    assert transcript.snapshot() == ("100%",)


def test_terminal_output_transcript_keeps_interleaved_progress_and_logs_distinct() -> (
    None
):
    """Interleaved progress redraws should not overwrite stable newline log rows."""

    transcript = TerminalOutputTranscript(max_lines=5)

    transcript.apply_records(
        (
            "  0%|          | 0/28 [00:00<?, ?it/s]\r",
            "FETCH ComfyRegistry Data: 25/134\n",
            " 21%|       | 6/28 [00:00<00:04,  5.38it/s]\r",
            "FETCH ComfyRegistry Data: 30/134\n",
            "100%|| 28/28 [00:04<00:00,  6.50it/s]\n",
        )
    )

    assert transcript.snapshot() == (
        "FETCH ComfyRegistry Data: 25/134",
        "FETCH ComfyRegistry Data: 30/134",
        "100%|| 28/28 [00:04<00:00,  6.50it/s]",
    )


def test_terminal_output_transcript_finalizes_carriage_return_crlf_records() -> None:
    """A ``\\r\\n`` record should finalize the previously redrawn active line."""

    transcript = TerminalOutputTranscript(max_lines=3)

    transcript.apply_record("step 1\r")
    transcript.apply_record("step 2\r")
    transcript.apply_record("done\r\n")

    assert transcript.snapshot() == ("done",)


def test_terminal_output_transcript_trims_history_to_max_lines() -> None:
    """The transcript should keep only the newest bounded history entries."""

    transcript = TerminalOutputTranscript(max_lines=2)

    transcript.apply_records(("first\n", "second\n", "third\n"))

    assert transcript.snapshot() == ("second", "third")


def test_terminal_output_transcript_trims_visible_history_when_progress_row_is_active() -> (
    None
):
    """An active redraw row should still respect the bounded visible history limit."""

    transcript = TerminalOutputTranscript(max_lines=2)

    transcript.apply_records(("first\n", "second\n", "0%\r"))
    assert transcript.snapshot() == ("second", "0%")

    transcript.apply_record("done\n")

    assert transcript.snapshot() == ("second", "done")
