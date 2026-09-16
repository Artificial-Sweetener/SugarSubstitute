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

"""Publish the configuration and version selected by a durable activation decision."""

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_activation_journal import (
    UpdateActivationJournal,
)


def publish_committed_activation(
    layout: InstallLayout, journal: UpdateActivationJournal
) -> None:
    """Repeat state publication safely while the committed journal remains durable."""
    if journal.successful_config is not None:
        journal.successful_config.save(layout.config_path)
    journal.successful_state.save(layout.state_path)
