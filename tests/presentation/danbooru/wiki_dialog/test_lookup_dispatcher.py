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

"""Test dialog-scoped Danbooru wiki lookup execution ownership."""

from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.dialogs.danbooru_wiki_dialog import (
    QtDanbooruWikiLookupDispatcher,
    _DialogLoadResult,
)
from tests.support.execution import QueuedTaskSubmitter
from tests.support.qt.lifecycle import destroy_qt_object


def test_dispatcher_cancels_pending_lookup_on_shutdown(
    qt_application_owner: QApplication,
) -> None:
    """Cancel dialog-scoped execution work before closing the submitter."""

    _ = qt_application_owner
    parent = QWidget()
    submitter = QueuedTaskSubmitter()
    close_calls: list[str] = []
    dispatcher = QtDanbooruWikiLookupDispatcher(
        parent,
        submitter=submitter,
        close_submitter=lambda: close_calls.append("closed"),
    )
    try:
        dispatcher.submit(
            lambda: cast(_DialogLoadResult, object()),
            completed=lambda _result: None,
            failed=lambda _error: None,
        )
        assert len(submitter.handles) == 1
        assert submitter.cancellations[0].is_cancelled is False

        dispatcher._shutdown()  # noqa: SLF001

        assert submitter.cancellations[0].is_cancelled is True
        assert submitter.cancellations[0].reason == (
            "danbooru_wiki_dialog_lookup_shutdown"
        )
        assert submitter.handles[0].cancel_reason == (
            "danbooru_wiki_dialog_lookup_shutdown"
        )
        assert close_calls == ["closed"]
    finally:
        destroy_qt_object(parent)
