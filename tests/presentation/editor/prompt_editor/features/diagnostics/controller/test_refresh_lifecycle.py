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

"""Verify diagnostics refresh lifecycle behavior."""

from __future__ import annotations

import logging
from typing import Any

from substitute.application.prompt_editor.conditioning import PromptConditioningMode
from substitute.application.prompt_editor.diagnostics.models import (
    PromptDiagnosticSnapshot,
)

from . import support


def test_controller_dispatches_refresh_through_request_channel() -> None:
    """Diagnostics refresh should use the async channel before updating surface."""

    diagnostic = support._spelling_diagnostic(0, 4, "typo")
    service = support._FakeService(diagnostic)
    surface = support._FakeSurface()
    editor = support._FakeEditor("typo")
    request_channel: support._ImmediateRequestChannel[PromptDiagnosticSnapshot] = (
        support._ImmediateRequestChannel()
    )
    controller = support._diagnostics_controller(
        editor,
        surface,
        service,
        request_channel=request_channel,
    )

    controller.refresh_now()

    assert request_channel.submitted_count == 1
    assert surface.diagnostics == (diagnostic,)
    assert (
        controller.presentation.visible_diagnostic_at_source_position(2) == diagnostic
    )


def test_controller_context_change_invalidates_old_async_identity() -> None:
    """Late diagnostics from an earlier conditioning topology must not publish."""

    diagnostic = support._spelling_diagnostic(0, 4, "typo")
    service = support._FakeService(diagnostic)
    surface = support._FakeSurface()
    editor = support._FakeEditor("typo")
    request_channel: support._DeferredRequestChannel[PromptDiagnosticSnapshot] = (
        support._DeferredRequestChannel()
    )
    controller = support._diagnostics_controller(
        editor,
        surface,
        service,
        request_channel=request_channel,
    )
    controller.refresh_now()
    first_handle = request_channel.handles[0]

    assert controller.replace_conditioning_context(
        support._conditioning_context(
            PromptConditioningMode.REGIONAL,
            topology_key=("mask",),
        )
    )
    second_handle = request_channel.handles[1]

    assert (
        first_handle.request.identity.feature_profile_id
        != second_handle.request.identity.feature_profile_id
    )
    first_handle.complete()
    assert not surface.diagnostics
    second_handle.complete()
    assert surface.diagnostics == (diagnostic,)


def test_controller_debounces_text_changes_to_latest_snapshot() -> None:
    """Text changes should schedule one diagnostics refresh for the newest source."""

    service = support._EchoService()
    surface = support._FakeSurface()
    editor = support._FakeEditor("alpha ", cursor_position=0)
    request_channel: support._ImmediateRequestChannel[PromptDiagnosticSnapshot] = (
        support._ImmediateRequestChannel()
    )
    debouncer = support._FakeDebouncer()
    controller = support._diagnostics_controller(
        editor,
        surface,
        service,
        request_channel=request_channel,
        debouncer=debouncer,
    )

    controller.handle_text_changed()
    editor.set_text("beta ")
    controller.handle_text_changed()
    assert debouncer.request_count == 2
    assert debouncer.cancel_count == 0
    assert service.snapshot_calls == []

    assert debouncer.flush(reason="test") is True

    assert service.snapshot_calls == ["beta "]
    assert request_channel.submitted_count == 1
    assert debouncer.cancel_count == 1
    assert [diagnostic.message for diagnostic in surface.diagnostics] == [
        "Possible spelling issue: beta"
    ]


def test_controller_failure_publishes_unavailable_snapshot_with_safe_log(
    caplog: Any,
) -> None:
    """Diagnostics failures should clear visible state without logging source text."""

    surface = support._FakeSurface()
    editor = support._FakeEditor("secret prompt text", cursor_position=0)
    controller = support._diagnostics_controller(
        editor, surface, support._FailingService()
    )
    caplog.set_level(
        logging.WARNING,
        logger="presentation.editor.prompt_editor.features.diagnostics",
    )

    controller.refresh_now()

    assert surface.diagnostics == ()
    assert surface.clear_count == 1
    assert controller.presentation.snapshot.unavailable_reason == "RuntimeError"
    assert controller.presentation.snapshot.identity.stale is True
    assert "prompt_diagnostics.refresh.failed" in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert "secret prompt text" not in caplog.text
