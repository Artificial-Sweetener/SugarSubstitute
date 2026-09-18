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

"""Verify the public startup failure presentation boundary."""

from substitute.presentation.errors import (
    present_startup_failure_report,
    startup_failure_presenter,
)


def test_startup_failure_presenter_exports_public_function() -> None:
    """Expose the startup report owner through the errors package."""
    assert (
        present_startup_failure_report
        is startup_failure_presenter.present_startup_failure_report
    )
