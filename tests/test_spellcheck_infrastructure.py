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

"""Import-safe tests for spellcheck infrastructure gateways."""

from __future__ import annotations

import sys
from threading import Thread

import pytest

from substitute.infrastructure.spellcheck import build_spellcheck_gateway
from substitute.infrastructure.spellcheck.disabled_spellcheck_gateway import (
    DisabledSpellCheckGateway,
)
from substitute.infrastructure.spellcheck.enchant_gateway import (
    EnchantSpellCheckGateway,
)
from substitute.infrastructure.spellcheck.macos_spellcheck_gateway import (
    MacOSSpellCheckGateway,
)
from substitute.infrastructure.spellcheck.windows_spellcheck_gateway import (
    WindowsSpellCheckGateway,
)


def test_disabled_spellcheck_gateway_accepts_everything() -> None:
    """Disabled spellcheck should never create false diagnostics."""

    gateway = DisabledSpellCheckGateway("disabled")

    assert gateway.is_available() is False
    assert gateway.availability_reason() == "disabled"
    assert gateway.check_word("typo") is True
    assert gateway.suggest("typo") == ()
    assert gateway.add_to_dictionary("typo") is False


def test_spellcheck_factory_respects_disabled_preference() -> None:
    """The backend factory should return the disabled gateway for user opt-out."""

    gateway = build_spellcheck_gateway(enabled=False, language_tag="en_US")

    assert isinstance(gateway, DisabledSpellCheckGateway)
    assert gateway.availability_reason() == "Prompt spellcheck is disabled in settings."


def test_platform_spellcheck_modules_are_import_safe() -> None:
    """Platform gateway modules should import without native dependencies loaded."""

    assert EnchantSpellCheckGateway.__name__ == "EnchantSpellCheckGateway"
    assert MacOSSpellCheckGateway.__name__ == "MacOSSpellCheckGateway"
    assert WindowsSpellCheckGateway.__name__ == "WindowsSpellCheckGateway"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows COM backend only")
def test_windows_spellcheck_gateway_can_check_from_worker_thread() -> None:
    """Windows spellcheck should create COM checkers in the calling thread."""

    gateway = WindowsSpellCheckGateway(language_tag="en-US")
    if not gateway.is_available():
        pytest.skip(gateway.availability_reason() or "Windows spellcheck unavailable")
    errors: list[BaseException] = []
    results: list[bool] = []

    def check_word() -> None:
        """Run a spellcheck call in a non-creating thread."""

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
