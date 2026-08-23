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

"""Tests for launch-time prompt editor GUI warmup."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import substitute.app.bootstrap.prompt_editor_gui_warmup as warmup_module
from substitute.app.bootstrap.prompt_editor_gui_warmup import (
    PromptEditorGuiWarmup,
    warm_prompt_editor_gui_from_window,
)


class _FakePromptEditor:
    """Record prompt editor warmup calls without constructing Qt widgets."""

    instances: list[_FakePromptEditor] = []

    def __init__(self, parent: object, **kwargs: object) -> None:
        """Store constructor arguments for assertions."""

        self.parent = parent
        self.kwargs = kwargs
        self.resize_calls: list[tuple[int, int]] = []
        self.polished = False
        self.text = ""
        self.deleted = False
        self.instances.append(self)

    def resize(self, width: int, height: int) -> None:
        """Record one resize request."""

        self.resize_calls.append((width, height))

    def ensurePolished(self) -> None:  # noqa: N802
        """Record polish warmup."""

        self.polished = True

    def setPlainText(self, text: str) -> None:  # noqa: N802
        """Record representative text assignment."""

        self.text = text

    def deleteLater(self) -> None:  # noqa: N802
        """Record cleanup scheduling."""

        self.deleted = True


def test_prompt_editor_gui_warmup_constructs_disposable_editor() -> None:
    """GUI warmup should build, exercise, and dispose one prompt editor."""

    _FakePromptEditor.instances.clear()
    warmup = PromptEditorGuiWarmup(
        prompt_autocomplete_gateway=object(),
        prompt_wildcard_catalog_gateway=object(),
        editor_factory=_FakePromptEditor,
    )

    assert warmup.run() is True

    [editor] = _FakePromptEditor.instances
    assert editor.parent is None
    assert editor.resize_calls == [(640, 180)]
    assert editor.polished is True
    assert "cinematic lighting" in editor.text
    assert editor.deleted is True


def test_prompt_editor_gui_warmup_forwards_composed_execution_factories() -> None:
    """GUI warmup should construct disposable editors through shared execution."""

    _FakePromptEditor.instances.clear()
    prompt_task_executor_factory = object()
    danbooru_lookup_dispatcher_factory = object()
    warmup = PromptEditorGuiWarmup(
        prompt_autocomplete_gateway=object(),
        prompt_wildcard_catalog_gateway=object(),
        editor_panel_execution_factories=SimpleNamespace(
            prompt_task_executor_factory=prompt_task_executor_factory,
            danbooru_lookup_dispatcher_factory=danbooru_lookup_dispatcher_factory,
        ),
        editor_factory=_FakePromptEditor,
    )

    assert warmup.run() is True

    [editor] = _FakePromptEditor.instances
    assert editor.kwargs["prompt_task_executor_factory"] is (
        prompt_task_executor_factory
    )
    assert editor.kwargs["danbooru_lookup_dispatcher_factory"] is (
        danbooru_lookup_dispatcher_factory
    )


def test_prompt_editor_gui_warmup_from_window_skips_missing_gateways() -> None:
    """Window helper should skip warmup until required prompt gateways exist."""

    window = SimpleNamespace(prompt_autocomplete_gateway=object())

    assert warm_prompt_editor_gui_from_window(window) is False


def test_prompt_editor_gui_warmup_from_window_uses_execution_factories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Window helper should reuse the composed editor execution factories."""

    _FakePromptEditor.instances.clear()
    monkeypatch.setattr(
        warmup_module,
        "_prompt_editor_factory",
        lambda: _FakePromptEditor,
    )
    prompt_task_executor_factory = object()
    window = SimpleNamespace(
        prompt_autocomplete_gateway=object(),
        prompt_wildcard_catalog_gateway=object(),
        editor_panel_execution_factories=SimpleNamespace(
            prompt_task_executor_factory=prompt_task_executor_factory,
            danbooru_lookup_dispatcher_factory=None,
        ),
    )

    assert warm_prompt_editor_gui_from_window(window) is True

    [editor] = _FakePromptEditor.instances
    assert editor.kwargs["prompt_task_executor_factory"] is (
        prompt_task_executor_factory
    )
