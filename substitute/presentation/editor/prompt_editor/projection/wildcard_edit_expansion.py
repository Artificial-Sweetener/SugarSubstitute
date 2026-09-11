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

"""Keep actively edited wildcard source ranges addressable in projection."""

from __future__ import annotations

from substitute.application.prompt_editor.document.views import PromptDocumentView

from .session import PromptProjectionSession


class PromptWildcardEditExpansion:
    """Expand a wildcard when semantic catch-up would hide its live caret."""

    def __init__(self, session: PromptProjectionSession) -> None:
        """Store the projection session that owns expanded-token state."""

        self._session = session

    def preserve_editable_selection(
        self,
        document_view: PromptDocumentView,
        *,
        selection_start: int,
        selection_end: int,
    ) -> bool:
        """Keep a wildcard raw while the authoritative selection is inside it."""

        if self._session.expanded_source_range is not None:
            return False
        for wildcard in document_view.wildcard_spans:
            if (
                wildcard.outer_start < selection_start < wildcard.outer_end
                and wildcard.outer_start < selection_end < wildcard.outer_end
            ):
                self._session.expanded_source_range = (
                    wildcard.outer_start,
                    wildcard.outer_end,
                )
                return True
        return False


__all__ = ["PromptWildcardEditExpansion"]
