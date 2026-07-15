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

"""Own the process-wide self-contained repository service instance."""

from __future__ import annotations

from functools import lru_cache

from substitute.infrastructure.version_control.pygit2_repository import (
    Pygit2RepositoryService,
)
from substitute.infrastructure.version_control.repository import RepositoryService


@lru_cache(maxsize=1)
def repository_service() -> RepositoryService:
    """Return the shared libgit2-backed repository service."""

    return Pygit2RepositoryService()
