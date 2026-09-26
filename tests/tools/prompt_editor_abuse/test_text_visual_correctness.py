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

"""Verify visual prompt replays settle authoritative owners between actions."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.prompt_editor_abuse import text_visual_correctness
from tools.prompt_editor_abuse.models import PromptAbuseAction, PromptAbuseScenario


class _Editor:
    """Expose mutable source and settlement state to the replay boundary."""

    def __init__(self, source: str) -> None:
        """Start with the mounted source awaiting baseline settlement."""

        self.source = source
        self.settled = False

    def toPlainText(self) -> str:
        """Return the source currently owned by the fake editor."""

        return self.source


class _Harness:
    """Record that visual replay releases its mounted shell."""

    def __init__(self) -> None:
        """Start with an open shell."""

        self.closed = False

    def close(self) -> None:
        """Record deterministic shell cleanup."""

        self.closed = True


def test_visual_replay_settles_each_frame_before_dispatching_the_next_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A queued owner transition must not leak into the following action."""

    scenario = PromptAbuseScenario(
        "settlement-order",
        "a",
        (
            PromptAbuseAction("type", value="b", expected_source="ab"),
            PromptAbuseAction("type", value="c", expected_source="abc"),
        ),
        "abc",
    )
    editor = _Editor(scenario.initial_text)
    harness = _Harness()
    events: list[str] = []

    def dispatch_action(
        _host: object,
        replay_editor: object,
        _target: object,
        action: PromptAbuseAction,
        *,
        action_index: int,
    ) -> tuple[object, ...]:
        """Reject dispatch while a prior visual frame remains provisional."""

        assert replay_editor is editor
        assert editor.settled
        editor.source += action.value
        editor.settled = False
        events.append(f"dispatch:{action_index}:{editor.source}")
        return ()

    def settle(replay_editor: object, expected_source: str) -> tuple[float, bool]:
        """Publish the current fake owners and record the awaited source."""

        assert replay_editor is editor
        assert editor.source == expected_source
        editor.settled = True
        events.append(f"settle:{expected_source}")
        return 0.1, True

    monkeypatch.setattr(
        text_visual_correctness,
        "create_prompt_abuse_real_shell_harness",
        lambda *_args, **_kwargs: harness,
    )
    monkeypatch.setattr(
        text_visual_correctness,
        "prepare_prompt_abuse_real_shell_mount",
        lambda *_args, **_kwargs: SimpleNamespace(
            field=SimpleNamespace(editor=editor),
            target=object(),
            action_host=object(),
        ),
    )
    monkeypatch.setattr(text_visual_correctness, "dispatch_action", dispatch_action)
    monkeypatch.setattr(
        text_visual_correctness,
        "_capture_checkpoint_violations",
        lambda *_args, **_kwargs: (),
    )

    violations = text_visual_correctness.capture_prompt_text_visual_violations(
        scenario,
        repetition=0,
        artifact_root=tmp_path,
        settle=settle,
    )

    assert violations == ()
    assert events == [
        "settle:a",
        "dispatch:0:ab",
        "settle:ab",
        "dispatch:1:abc",
        "settle:abc",
    ]
    assert harness.closed
