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

"""Verify Windows-native spellcheck gateway behavior."""

from __future__ import annotations

from threading import Thread

import pytest

from substitute.infrastructure.spellcheck.windows_spellcheck_gateway import (
    WindowsSpellCheckGateway,
)

pytestmark = pytest.mark.platforms("windows")


def test_windows_spellcheck_gateway_can_check_from_worker_thread() -> None:
    """Create COM checkers in the calling worker thread."""

    gateway = WindowsSpellCheckGateway(language_tag="en-US")
    assert gateway.is_available(), (
        gateway.availability_reason() or "Windows spellcheck unavailable"
    )
    errors: list[BaseException] = []
    results: list[bool] = []

    def check_word() -> None:
        """Run a spellcheck call from a non-creating thread."""

        try:
            results.append(gateway.check_word("testeded"))
        except BaseException as error:
            errors.append(error)

    thread = Thread(target=check_word)
    thread.start()
    thread.join(timeout=5.0)

    assert not thread.is_alive()
    assert errors == []
    assert results and isinstance(results[0], bool)
