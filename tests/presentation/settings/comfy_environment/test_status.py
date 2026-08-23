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

"""Test Comfy environment status and activation presentation."""

from __future__ import annotations


from substitute.application.comfy_environment import ComfyEnvironmentService
from substitute.presentation.settings.comfy_environment_page import (
    ComfyEnvironmentPage,
)
from tests.presentation.settings.comfy_environment.backend import EnvironmentBackend
from tests.presentation.settings.comfy_environment.backend_variants import (
    CountingEnvironmentBackend,
)
from tests.presentation.settings.comfy_environment.support import (
    application,
    deliver_queued_events,
    environment_page,
    immediate_task_runner_factory,
)


def test_comfy_environment_page_renders_environment_status() -> None:
    """Comfy environment settings should render environment status."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: object(),
    )
    deliver_queued_events(app)

    assert page.restart_button.isEnabled()
    assert "Python 3.12.7" in page.python_label.text()
    assert page.inventory_label.text() == "7 installed packages"
    assert page.inventory_count_label.isHidden()
    assert "torch" in page.inventory_item_names()
    assert "manual-tool" in page.inventory_item_names()
    assert "Helper package from installed metadata." in (page.detail_text())


def test_environment_page_demotes_setup_wizard_entry_point() -> None:
    """Environment settings should point connection edits to the connection section."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: object(),
    )

    deliver_queued_events(app)

    assert page.reconfigure_button.text() == "Open setup wizard"
    assert page.reconfigure_button.text() != "Setup / Connection"


def test_environment_page_refreshes_after_settings_activation() -> None:
    """Environment loading should wait for the active Settings page lifecycle."""

    app = application()
    backend = CountingEnvironmentBackend()
    page = ComfyEnvironmentPage(
        ComfyEnvironmentService(backend),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=immediate_task_runner_factory,
    )

    deliver_queued_events(app)

    assert backend.capability_requests == 0

    page.set_settings_page_active(True)
    deliver_queued_events(app)

    assert backend.capability_requests == 1
    assert "Comfy environment management is available." in page.status_label.text()
    assert "torch" in page.inventory_item_names()
    page.close()
    page.deleteLater()
