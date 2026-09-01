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

"""Resolve release sources for explicit and initial launcher operations."""

from __future__ import annotations

import sys

from launcher.sugarsubstitute_launcher.release_sources import (
    GitHubReleaseSource,
    ReleaseSource,
    default_production_release_source,
)


def explicit_release_source(manifest_url: str | None) -> ReleaseSource:
    """Return the requested HTTPS source or the production release channel."""

    if manifest_url is None:
        return default_production_release_source()
    return GitHubReleaseSource(manifest_url)


def initial_install_release_source(manifest_url: str | None) -> ReleaseSource:
    """Return an explicit test source or the installer-bound release source."""

    from launcher.sugarsubstitute_launcher.application.installation.release_source_policy import (
        resolve_initial_install_release_source,
    )

    if manifest_url is not None:
        return GitHubReleaseSource(manifest_url)
    return resolve_initial_install_release_source(
        frozen_setup=bool(getattr(sys, "frozen", False))
    )


__all__ = ["explicit_release_source", "initial_install_release_source"]
