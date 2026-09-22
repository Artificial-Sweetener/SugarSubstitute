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

"""Verify mounted prompt-editor scene publication sequencing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable

from substitute.presentation.editor.prompt_editor.scene_facade import (
    PromptEditorSceneBindings,
    PromptEditorSceneFacade,
)


@dataclass(slots=True)
class _SceneRecorder:
    """Record scene facade publications."""

    metadata_value: object
    calls: list[object] = field(default_factory=list)

    def metadata(self) -> object:
        """Return configured field metadata."""

        return self.metadata_value

    def set_identity(
        self,
        *,
        cube_context_id: Hashable | None,
        scene_context_id: Hashable | None,
    ) -> None:
        """Record one context identity publication."""

        self.calls.append(("identity", cube_context_id, scene_context_id))

    def set_titles(self, titles: tuple[str, ...]) -> None:
        """Record scene autocomplete titles."""

        self.calls.append(("titles", titles))

    def set_queueable(self, keys: frozenset[str]) -> None:
        """Record queueable scene keys."""

        self.calls.append(("queueable", keys))

    def refresh(self) -> None:
        """Record dependent autocomplete refresh."""

        self.calls.append("refresh")


def test_titles_publish_identity_before_refreshing_active_autocomplete() -> None:
    """Scene title changes must refresh using the new editor identity."""

    recorder = _SceneRecorder(
        {
            "cube_alias": "Portrait",
            "node_name": "Positive",
            "key": "prompt",
        }
    )
    facade = _facade(recorder)

    facade.set_autocomplete_titles(("Close Up", "Wide"))

    identity = ("Portrait", "Positive", "prompt")
    assert recorder.calls == [
        ("identity", identity, identity),
        ("titles", ("Close Up", "Wide")),
        "refresh",
    ]


def test_queueable_keys_do_not_restart_autocomplete() -> None:
    """Queue-action changes must not invalidate title autocomplete queries."""

    recorder = _SceneRecorder(None)
    facade = _facade(recorder)

    facade.set_queueable_keys(frozenset({"wide"}))

    assert recorder.calls == [
        ("identity", None, None),
        ("queueable", frozenset({"wide"})),
    ]


def test_partial_metadata_preserves_the_existing_identity_shape() -> None:
    """Missing metadata fields remain explicit identity tuple members."""

    recorder = _SceneRecorder(
        {
            "cube_alias": None,
            "node_name": "Positive",
        }
    )
    facade = _facade(recorder)

    facade.set_queueable_keys(frozenset())

    identity = (None, "Positive", None)
    assert recorder.calls[0] == ("identity", identity, identity)


def _facade(recorder: _SceneRecorder) -> PromptEditorSceneFacade:
    """Bind one recorder to the production scene facade."""

    return PromptEditorSceneFacade(
        PromptEditorSceneBindings(
            metadata=recorder.metadata,
            set_context_identity=recorder.set_identity,
            set_autocomplete_titles=recorder.set_titles,
            set_queueable_keys=recorder.set_queueable,
            refresh_active_autocomplete_session=recorder.refresh,
        )
    )
