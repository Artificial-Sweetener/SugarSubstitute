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

"""Qualify real generated-video behavior from an installed application layout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import tomllib
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Callable


_TIMEOUT_SECONDS = 10.0


def main(argv: list[str] | None = None) -> int:
    """Run native probe and playback acceptance and write machine-readable evidence."""

    arguments = _parse_arguments(argv)
    application_root = arguments.application_root.expanduser().resolve()
    fixture_root = arguments.fixture_root.expanduser().resolve()
    evidence_dir = arguments.evidence_dir.expanduser().resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    os.environ["PATH"] = ""
    sys.path.insert(0, str(application_root))

    from substitute.domain.generation import VideoPlaybackSettings
    from substitute.infrastructure.video.mpv_runtime import MpvRuntime
    from substitute.infrastructure.video.mpv_video_player import MpvVideoPlayer
    from substitute.infrastructure.video.mpv_video_probe import (
        MpvVideoProbe,
        VideoProbeError,
    )

    imported_root = (
        Path(sys.modules["substitute"].__file__ or "").resolve().parent.parent
    )
    if imported_root != application_root:
        raise RuntimeError(
            f"Application imported outside installed root: {imported_root}"
        )

    playback_root = evidence_dir / "media path üñîçødé with spaces"
    playback_root.mkdir(parents=True, exist_ok=True)
    fixtures = _verified_fixture_paths(fixture_root)
    installed_fixtures = {
        name: Path(shutil.copy2(path, playback_root / path.name))
        for name, path in fixtures.items()
    }

    runtime = MpvRuntime.bundled(application_root=application_root)
    probe = MpvVideoProbe(runtime)
    print("Qualifying packaged probe corpus...", flush=True)
    probe_evidence = _qualify_probe(
        probe,
        fixtures=installed_fixtures,
        video_probe_error=VideoProbeError,
        playback_root=playback_root,
    )
    print("Qualifying packaged playback controls...", flush=True)
    playback_evidence = _qualify_playback(
        runtime=runtime,
        fixtures=installed_fixtures,
        settings=VideoPlaybackSettings(),
        player_type=MpvVideoPlayer,
    )
    payload = {
        "schema_version": "1",
        "application_root": str(application_root),
        "runtime_path": str(runtime.library_path),
        "ambient_path": os.environ["PATH"],
        "probe": probe_evidence,
        "playback": playback_evidence,
    }
    evidence_path = evidence_dir / "packaged-video-runtime.json"
    evidence_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(evidence_path)
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    """Parse installed-root, fixture, and evidence paths."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--application-root", required=True, type=Path)
    parser.add_argument("--fixture-root", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    return parser.parse_args(argv)


def _verified_fixture_paths(root: Path) -> dict[str, Path]:
    """Verify every synthetic fixture against its committed manifest."""

    manifest_path = root / "manifest.toml"
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    fixtures: dict[str, Path] = {}
    for record in manifest["fixture"]:
        name = str(record["path"])
        path = (root / name).resolve()
        if path.parent != root or not path.is_file():
            raise RuntimeError(f"Fixture is unavailable: {name}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != str(record["sha256"]):
            raise RuntimeError(f"Fixture checksum mismatch: {name}")
        fixtures[name] = path
    return fixtures


def _qualify_probe(
    probe: Any,
    *,
    fixtures: dict[str, Path],
    video_probe_error: type[Exception],
    playback_root: Path,
) -> dict[str, object]:
    """Decode every fixture, extract posters, and reject truncated input."""

    results: dict[str, object] = {}
    for name, path in fixtures.items():
        result = probe.probe(path)
        if result.width <= 0 or result.height <= 0:
            raise RuntimeError(f"Invalid decoded geometry: {name}")
        if not result.poster_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError(f"Invalid poster encoding: {name}")
        results[name] = {
            "codec": result.codec,
            "duration_seconds": result.duration_seconds,
            "height": result.height,
            "mime_type": result.mime_type,
            "pixel_format": result.pixel_format,
            "poster_bytes": len(result.poster_bytes),
            "width": result.width,
        }

    truncated = playback_root / "truncated-video.mp4"
    truncated.write_bytes(fixtures["cfr-h264-silent.mp4"].read_bytes()[:512])
    try:
        probe.probe(truncated)
    except video_probe_error:
        results["truncated_rejected"] = True
    else:
        raise RuntimeError("Truncated video was accepted by the production probe.")
    return results


def _qualify_playback(
    *,
    runtime: Any,
    fixtures: dict[str, Path],
    settings: Any,
    player_type: Any,
) -> dict[str, object]:
    """Exercise real frame, loop, audio, and hidden-page behavior."""

    events: list[Any] = []
    player = player_type(
        runtime=runtime,
        player_generation=1,
        event_callback=events.append,
        settings=settings,
    )
    try:
        print("  CFR frame stepping", flush=True)
        cfr = _step_round_trip(player, fixtures["cfr-h264-silent.mp4"])
        representative_frame = _representative_frame_evidence(player, events)
        print("  VFR frame stepping", flush=True)
        vfr = _step_vfr(player, fixtures["vfr-vp9-silent.webm"])
        print("  B-frame stepping", flush=True)
        bframes = _step_round_trip(player, fixtures["bframes-h264-silent.mp4"])
        print("  loop policy", flush=True)
        loop = _exercise_loop_policy(player, fixtures["cfr-h264-silent.mp4"])
        print("  audio and visibility", flush=True)
        audio = _exercise_audio_and_visibility(player, fixtures["h264-aac.mp4"])
        return {
            "audio_visibility": audio,
            "bframe_step": bframes,
            "cfr_step": cfr,
            "loop": loop,
            "representative_frame": representative_frame,
            "vfr_step": vfr,
        }
    finally:
        print("  closing native player", flush=True)
        player.close()
        print("  native player closed", flush=True)


def _representative_frame_evidence(
    player: Any,
    events: list[Any],
) -> dict[str, object]:
    """Prove native paused-position events carry the last decoded source frame."""

    frames = tuple(
        event.representative_frame
        for event in events
        if event.representative_frame is not None
    )
    if len(frames) < 3:
        raise RuntimeError("Paused playback did not publish representative frames.")
    frame = frames[-1]
    paused_time = player.snapshot().time_seconds
    if paused_time is None or abs(frame.time_seconds - paused_time) > 0.001:
        raise RuntimeError("Representative frame did not match the paused position.")
    return {
        "captured_positions": len(frames),
        "height": frame.height,
        "pixel_sha256": hashlib.sha256(frame.pixels).hexdigest(),
        "stride": frame.stride,
        "time_seconds": frame.time_seconds,
        "width": frame.width,
    }


def _load_ready(player: Any, path: Path) -> None:
    """Load one local artifact and wait for decoded metadata."""

    player.load(uuid4(), path)
    player.set_output_active(True)
    _wait_until(
        lambda: (
            player.snapshot().duration_seconds is not None
            and player.snapshot().width is not None
            and player.snapshot().height is not None
        ),
        label=f"metadata for {path.name}",
        poll=player.poll_playback_state,
    )


def _step_round_trip(player: Any, path: Path) -> dict[str, float]:
    """Advance and retreat one decoded frame while playback remains paused."""

    _load_ready(player, path)
    player.seek(0.5)
    _wait_until(
        lambda: (player.snapshot().time_seconds or 0.0) >= 0.45,
        label=f"seek for {path.name}",
        poll=player.poll_playback_state,
    )
    before = float(player.snapshot().time_seconds or 0.0)
    player.step_next_frame()
    _wait_until(
        lambda: (player.snapshot().time_seconds or 0.0) > before + 0.001,
        label=f"next frame for {path.name}",
        poll=player.poll_playback_state,
    )
    after_next = float(player.snapshot().time_seconds or 0.0)
    player.step_previous_frame()
    _wait_until(
        lambda: (player.snapshot().time_seconds or after_next) < after_next - 0.001,
        label=f"previous frame for {path.name}",
        poll=player.poll_playback_state,
    )
    after_previous = float(player.snapshot().time_seconds or 0.0)
    if not player.snapshot().paused:
        raise RuntimeError(f"Frame stepping resumed playback: {path.name}")
    return {
        "before": before,
        "after_next": after_next,
        "after_previous": after_previous,
    }


def _step_vfr(player: Any, path: Path) -> dict[str, object]:
    """Observe decoded VFR timestamps instead of assuming a constant rate."""

    _load_ready(player, path)
    timestamps = [float(player.snapshot().time_seconds or 0.0)]
    for _index in range(9):
        previous = timestamps[-1]
        player.step_next_frame()

        def advanced() -> bool:
            """Return whether native playback published the next VFR timestamp."""

            observed = player.snapshot().time_seconds
            return observed is not None and float(observed) > previous + 0.001

        _wait_until(
            advanced,
            label="VFR next frame",
            poll=player.poll_playback_state,
        )
        timestamps.append(float(player.snapshot().time_seconds or 0.0))
    deltas = {
        round(current - previous, 3)
        for previous, current in zip(timestamps, timestamps[1:])
    }
    if len(deltas) < 2:
        raise RuntimeError(f"VFR fixture exposed constant timestamps: {timestamps}")
    return {"timestamps": timestamps, "distinct_deltas": sorted(deltas)}


def _exercise_loop_policy(player: Any, path: Path) -> dict[str, object]:
    """Reach EOF with looping off, then restart and observe a real loop."""

    _load_ready(player, path)
    if not player.snapshot().loop_enabled:
        raise RuntimeError("Video did not default to looping.")
    duration = float(player.snapshot().duration_seconds or 0.0)
    player.set_loop_enabled(False)
    player.seek(max(duration - 0.15, 0.0))
    player.set_playing(True)
    _wait_until(
        lambda: str(player.snapshot().state) == "ended",
        label="loop-off EOF",
        poll=player.poll_playback_state,
    )
    ended_time = player.snapshot().time_seconds

    player.set_loop_enabled(True)
    player.set_playing(True)
    maximum = 0.0
    wrapped_at: float | None = None
    deadline = time.monotonic() + _TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        player.poll_playback_state()
        current = float(player.snapshot().time_seconds or 0.0)
        if maximum > duration * 0.75 and current < duration * 0.35:
            wrapped_at = current
            break
        maximum = max(maximum, current)
        time.sleep(0.01)
    if wrapped_at is None:
        raise TimeoutError("Loop-on playback did not wrap to the beginning.")
    player.set_playing(False)
    return {
        "default_enabled": True,
        "ended_time": ended_time,
        "loop_maximum": maximum,
        "wrapped_at": wrapped_at,
    }


def _exercise_audio_and_visibility(player: Any, path: Path) -> dict[str, object]:
    """Retain user audio choices while hidden playback becomes safe."""

    _load_ready(player, path)
    player.set_volume(37)
    player.set_user_muted(False)
    player.set_playing(True)
    _wait_until(
        lambda: not player.snapshot().paused,
        label="audio fixture playback",
        poll=player.poll_playback_state,
    )
    player.set_output_active(False)
    hidden = player.snapshot()
    if not hidden.paused or not hidden.effectively_muted:
        raise RuntimeError("Hidden playback remained active or audible.")
    if hidden.user_muted or hidden.volume != 37:
        raise RuntimeError("Hidden playback overwrote user audio choices.")
    return {
        "effectively_muted": hidden.effectively_muted,
        "paused": hidden.paused,
        "user_muted": hidden.user_muted,
        "volume": hidden.volume,
    }


def _wait_until(
    predicate: Callable[[], bool],
    *,
    label: str,
    poll: Callable[[], None] | None = None,
) -> None:
    """Wait for one native observation with a bounded diagnostic timeout."""

    deadline = time.monotonic() + _TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if poll is not None:
            poll()
        if predicate():
            return
        time.sleep(0.01)
    raise TimeoutError(f"Timed out waiting for {label}.")


if __name__ == "__main__":
    raise SystemExit(main())
