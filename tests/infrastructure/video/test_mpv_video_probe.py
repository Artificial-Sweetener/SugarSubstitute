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

"""Verify libmpv video validation and deterministic poster extraction."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import ModuleType
from typing import cast

from PIL import Image
import pytest

from substitute.infrastructure.video.mpv_runtime import MpvRuntime
from substitute.infrastructure.video.mpv_video_probe import (
    MpvVideoProbe,
    VideoProbeError,
)


class FakePlayer:
    """Model the narrow python-mpv surface consumed by the probe."""

    def __init__(self, *, screenshot: Image.Image, **options: object) -> None:
        """Capture closed options and expose deterministic media properties."""

        self.options = options
        self.duration: object = 2.5
        self.width: object = 2048
        self.height: object = 1024
        self.video_codec: object = "vp9"
        self.video_params: object = {"pixelformat": "yuv420p"}
        self.pause: object = False
        self.screenshot = screenshot
        self.played: str | None = None
        self.timeout: float | None = None
        self.terminated = False

    def play(self, filename: str) -> None:
        """Record the only local file passed to the player."""

        self.played = filename

    def wait_until_playing(self, timeout: float) -> None:
        """Record the bounded decode wait."""

        self.timeout = timeout

    def screenshot_raw(self) -> Image.Image:
        """Return the configured decoded frame."""

        return self.screenshot

    def terminate(self) -> None:
        """Record deterministic native teardown."""

        self.terminated = True


class FakeRuntime:
    """Provide a synthetic python-mpv module to the probe."""

    def __init__(self, player: FakePlayer) -> None:
        """Store the player returned by the binding constructor."""

        self.player = player

    def load_module(self) -> ModuleType:
        """Return a module exposing the configured constructor."""

        module = ModuleType("mpv")

        def construct(**options: object) -> FakePlayer:
            """Apply constructor options to the configured player."""

            self.player.options = options
            return self.player

        module.MPV = construct  # type: ignore[attr-defined]
        return module


class FailingPlayer(FakePlayer):
    """Model libmpv rejecting a malformed artifact during decode."""

    def wait_until_playing(self, timeout: float) -> None:
        """Raise a decoder failure containing sensitive internal detail."""

        raise ValueError("decoder exposed a sensitive absolute path")


def test_probe_decodes_first_frame_and_bounds_poster(tmp_path: Path) -> None:
    """Return media facts and a longest-edge-bounded RGB PNG poster."""

    video = tmp_path / "generated.webm"
    video.write_bytes(b"media")
    source = Image.new("RGBA", (2048, 1024), (10, 20, 30, 128))
    player = FakePlayer(screenshot=source)
    probe = MpvVideoProbe(cast(MpvRuntime, FakeRuntime(player)))

    result = probe.probe(video)

    assert result.width == 2048
    assert result.height == 1024
    assert result.duration_seconds == 2.5
    assert result.mime_type == "video/webm"
    assert result.codec == "vp9"
    assert result.pixel_format == "yuv420p"
    with Image.open(BytesIO(result.poster_bytes)) as poster:
        assert poster.size == (1024, 512)
        assert poster.mode == "RGB"
    assert player.played == str(video.resolve())
    assert player.timeout == 15.0
    assert player.pause is True
    assert player.terminated


def test_probe_disables_external_configuration_and_network(tmp_path: Path) -> None:
    """Construct libmpv with no user config, scripts, discovery, or URLs."""

    video = tmp_path / "generated.mp4"
    video.write_bytes(b"media")
    player = FakePlayer(screenshot=Image.new("RGB", (8, 6)))
    probe = MpvVideoProbe(cast(MpvRuntime, FakeRuntime(player)))

    probe.probe(video)

    assert player.options["config"] is False
    assert player.options["load_scripts"] is False
    assert "ytdl" not in player.options
    assert player.options["autoload_files"] == "no"
    assert player.options["audio_file_auto"] == "no"
    assert player.options["sub_auto"] == "no"
    assert player.options["access_references"] is False
    assert player.options["demuxer_lavf_o"] == "protocol_whitelist=file"
    assert player.options["background"] == "none"
    assert player.options["background_color"] == "#00000000"


def test_probe_redacts_parent_directories_from_decode_error(tmp_path: Path) -> None:
    """Keep user-facing failures useful without exposing parent path segments."""

    video = tmp_path / "secret-parent" / "broken.mov"
    video.parent.mkdir()
    video.write_bytes(b"broken")
    player = FailingPlayer(screenshot=Image.new("RGB", (8, 6)))
    probe = MpvVideoProbe(cast(MpvRuntime, FakeRuntime(player)))

    with pytest.raises(VideoProbeError) as raised:
        probe.probe(video)

    assert "broken.mov" in str(raised.value)
    assert "secret-parent" not in str(raised.value)
    assert player.terminated


def test_probe_rejects_missing_artifact_before_player_creation(tmp_path: Path) -> None:
    """Fail early when the local generated artifact is unavailable."""

    player = FakePlayer(screenshot=Image.new("RGB", (8, 6)))
    probe = MpvVideoProbe(cast(MpvRuntime, FakeRuntime(player)))

    with pytest.raises(VideoProbeError, match="missing.webm"):
        probe.probe(tmp_path / "missing.webm")

    assert player.played is None
