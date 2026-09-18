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

"""Keep repair progress transport bounded and independent of socket chunking."""

import pytest

from launcher.sugarsubstitute_launcher.repair_execution_protocol import (
    MAXIMUM_REPAIR_FRAME_BYTES,
    RepairFrameDecoder,
    encode_repair_frame,
)


@pytest.mark.parametrize("chunk_size", [1, 7, 4096])
def test_repair_frames_preserve_unicode_and_partial_messages(chunk_size: int) -> None:
    """Deliver complete observations across arbitrary transport fragmentation."""
    messages: list[dict[str, object]] = [
        {"kind": "output", "details": "æ—¥æœ¬èªž\nline two"},
        {"kind": "progress", "completed": 2, "total": 7},
        {"kind": "succeeded"},
    ]
    wire = b"".join(encode_repair_frame(message) for message in messages)
    decoder = RepairFrameDecoder()
    received = []
    for offset in range(0, len(wire), chunk_size):
        received.extend(decoder.feed(wire[offset : offset + chunk_size]))
    decoder.finish()
    assert received == messages


@pytest.mark.parametrize(
    "payload",
    [b"[]\n", b"true\n", b"\xff\n", b"{\n", b"\n", b"[" * 2000 + b"]" * 2000 + b"\n"],
)
def test_repair_frames_reject_invalid_objects(payload: bytes) -> None:
    """Reject malformed observations without unbounded recursion or object loading."""
    with pytest.raises(ValueError):
        RepairFrameDecoder().feed(payload)


def test_repair_frames_bound_incomplete_input() -> None:
    """Stop an unterminated frame at its byte limit instead of retaining more input."""
    decoder = RepairFrameDecoder()
    decoder.feed(b" " * MAXIMUM_REPAIR_FRAME_BYTES)
    with pytest.raises(ValueError, match="size limit"):
        decoder.feed(b" ")


def test_repair_frame_end_requires_a_complete_message() -> None:
    """Do not treat a truncated terminal message as successful execution."""
    decoder = RepairFrameDecoder()
    decoder.feed(b'{"kind":"succeeded"}')
    with pytest.raises(ValueError, match="incomplete"):
        decoder.finish()


def test_repair_encoder_rejects_oversized_output() -> None:
    """Bound producer memory before any transport write begins."""
    with pytest.raises(ValueError, match="size limit"):
        encode_repair_frame({"details": "x" * MAXIMUM_REPAIR_FRAME_BYTES})
