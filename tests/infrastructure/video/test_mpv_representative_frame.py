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

"""Verify source-frame publication for changed paused playback positions."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from substitute.application.ports.video import VideoPlaybackState
from tests.support.mpv_video_player import create_video_player


def test_player_publishes_each_changed_paused_source_frame_once(
    tmp_path: Path,
) -> None:
    """Capture paused positions while ignoring unchanged and playing positions."""

    adapter, native, events, video = create_video_player(tmp_path)
    media_id = uuid4()
    adapter.load(media_id, video)
    adapter.set_output_active(True)
    native.emit("time-pos", 0.5)
    native.emit("width", 2)
    native.emit("height", 1)
    native.emit("core-idle", False)

    adapter.poll_playback_state()
    first_event_count = len(events)
    adapter.poll_playback_state()

    assert len(events) == first_event_count
    assert events[-1].snapshot.state is VideoPlaybackState.READY
    assert events[-1].representative_frame is not None
    assert events[-1].representative_frame.time_seconds == 0.5
    assert events[-1].representative_frame.pixels == bytes((0, 0, 255, 0)) * 2

    adapter.set_playing(True)
    native.emit("time-pos", 0.75)
    adapter.poll_playback_state()
    assert events[-1].representative_frame is None

    adapter.set_playing(False)
    adapter.poll_playback_state()
    paused_frames = tuple(
        event.representative_frame
        for event in events
        if event.representative_frame is not None
    )
    assert tuple(frame.time_seconds for frame in paused_frames) == (0.5, 0.75)
    assert native.commands.count(("screenshot-raw", ("video",))) == 2
    adapter.close()


def test_representative_frame_failure_does_not_break_playback(tmp_path: Path) -> None:
    """Treat an unavailable screenshot as a skipped tile refresh, not playback failure."""

    adapter, native, events, video = create_video_player(tmp_path)
    adapter.load(uuid4(), video)
    adapter.set_output_active(True)
    native.emit("time-pos", 0.5)
    native.emit("core-idle", False)
    native.fail_command = "screenshot-raw"

    adapter.poll_playback_state()

    assert adapter.snapshot().state is VideoPlaybackState.READY
    assert events[-1].representative_frame is None
    adapter.close()
