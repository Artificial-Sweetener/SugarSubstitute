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

"""Own autocomplete acceptance transactions across session and command boundaries."""

from __future__ import annotations

from .autocomplete_acceptance import PromptAutocompleteAcceptanceController
from .autocomplete_session_publication import PromptAutocompleteSessionPublication


class PromptAutocompleteAcceptanceLifecycle:
    """Execute selected completions and close their prepared session transaction."""

    def __init__(
        self,
        *,
        acceptance_controller: PromptAutocompleteAcceptanceController,
        session_publication: PromptAutocompleteSessionPublication,
    ) -> None:
        """Store the command and session owners for one acceptance transaction."""

        self._acceptance_controller = acceptance_controller
        self._session_publication = session_publication

    def accept_selection(self, *, add_comma: bool) -> None:
        """Accept the selected session row through its mode-specific command."""

        self._acceptance_controller.accept_session(
            self._session_publication.session,
            source_identity=self._session_publication.source_identity,
            add_comma=add_comma,
        )
        self._session_publication.dismiss_autocomplete("accepted")

    def accept_scene_selection(self) -> None:
        """Accept the selected scene row and close its session."""

        self._acceptance_controller.accept_scene_session(
            self._session_publication.session,
            source_identity=self._session_publication.source_identity,
        )
        self._session_publication.dismiss_autocomplete("accepted")

    def accept_wildcard_selection(self) -> None:
        """Accept the selected wildcard row and close its session."""

        self._acceptance_controller.accept_wildcard_session(
            self._session_publication.session,
            source_identity=self._session_publication.source_identity,
        )
        self._session_publication.dismiss_autocomplete("accepted")

    def accept_lora_selection(self) -> None:
        """Accept the selected LoRA row and close its session."""

        self._acceptance_controller.accept_lora_session(
            self._session_publication.session,
            source_identity=self._session_publication.source_identity,
        )
        self._session_publication.dismiss_autocomplete("accepted")

    def activate_suggestion(self, index: int) -> None:
        """Select and accept one clicked ordinary suggestion."""

        self._session_publication.select_index(index)
        self.accept_selection(add_comma=False)

    def activate_lora_candidate(self, index: int) -> None:
        """Select and accept one clicked LoRA candidate."""

        self._session_publication.select_index(index)
        self.accept_lora_selection()


__all__ = ["PromptAutocompleteAcceptanceLifecycle"]
