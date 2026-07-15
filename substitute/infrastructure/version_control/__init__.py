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

"""Expose self-contained repository operations for infrastructure adapters."""

from substitute.infrastructure.version_control.pygit2_repository import (
    Pygit2RepositoryService,
)
from substitute.infrastructure.version_control.repository import (
    RepositoryOperationError,
    RepositoryService,
)
from substitute.infrastructure.version_control.service_provider import (
    repository_service,
)

__all__ = [
    "Pygit2RepositoryService",
    "RepositoryOperationError",
    "RepositoryService",
    "repository_service",
]
