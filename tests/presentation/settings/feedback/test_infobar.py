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

"""Widget contract tests for SettingsInfoBar."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from substitute.presentation.settings.settings_infobar import (
    SettingsInfoBar,
    SettingsInfoBarSeverity,
)
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


@pytest.fixture()
def settings_infobar() -> Iterator[SettingsInfoBar]:
    """Create one infobar with an explicit application and teardown owner."""

    application = ensure_qt_application()
    bar = SettingsInfoBar()
    yield bar
    destroy_qt_object(bar)
    del application


def test_settings_infobar_starts_hidden(settings_infobar: SettingsInfoBar) -> None:
    """Keep feedback absent until a settings operation publishes a message."""

    assert settings_infobar.isHidden() is True
    assert settings_infobar.title_label.text() == ""
    assert settings_infobar.message_label.text() == ""


@pytest.mark.parametrize("severity", ("info", "success", "warning", "error"))
def test_settings_infobar_renders_message_and_severity(
    settings_infobar: SettingsInfoBar,
    severity: SettingsInfoBarSeverity,
) -> None:
    """Render owned feedback text and retain each supported semantic severity."""

    settings_infobar.show_message(
        severity=severity,
        title="Sync failed",
        message="The target did not return a pack.",
    )

    assert settings_infobar.isHidden() is False
    assert settings_infobar.severity() == severity
    assert settings_infobar.title_label.text() == "Sync failed"
    assert settings_infobar.message_label.text() == "The target did not return a pack."


def test_settings_infobar_clear_removes_content(
    settings_infobar: SettingsInfoBar,
) -> None:
    """Clear both feedback labels and hide the surface atomically."""

    settings_infobar.show_message(
        severity="warning",
        title="Pending",
        message="A restart is required.",
    )
    settings_infobar.clear()

    assert settings_infobar.isHidden() is True
    assert settings_infobar.title_label.text() == ""
    assert settings_infobar.message_label.text() == ""


def test_settings_infobar_dismiss_button_clears_message(
    settings_infobar: SettingsInfoBar,
) -> None:
    """Route dismissal through the same authoritative clear behavior."""

    settings_infobar.show_message(
        severity="success",
        title="Saved",
        message="Settings were saved.",
    )
    settings_infobar.dismiss_button.click()

    assert settings_infobar.isHidden() is True
    assert settings_infobar.title_label.text() == ""
    assert settings_infobar.message_label.text() == ""
