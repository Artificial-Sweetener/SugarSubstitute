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

"""Own scene diagnostic projection state and rebuild publication."""

from __future__ import annotations

from collections.abc import Callable


class PromptSceneDiagnosticsOwner:
    """Own scene-error identity consumed by every projection build path."""

    def __init__(
        self,
        *,
        flush_pending_projection: Callable[[str], None],
        clear_hovered_token: Callable[[], None],
        rebuild_projection: Callable[[], None],
    ) -> None:
        """Create empty diagnostics and bind their atomic rebuild effects."""

        self._flush_pending_projection = flush_pending_projection
        self._clear_hovered_token = clear_hovered_token
        self._rebuild_projection = rebuild_projection
        self._keys: frozenset[str] = frozenset()

    @property
    def keys(self) -> frozenset[str]:
        """Return scene keys currently projected as errors."""

        return self._keys

    def set_keys(self, scene_error_keys: frozenset[str]) -> None:
        """Publish changed scene diagnostics through one canonical rebuild."""

        if self._keys == scene_error_keys:
            return
        self._flush_pending_projection("set_scene_error_keys")
        self._keys = scene_error_keys
        self._clear_hovered_token()
        self._rebuild_projection()


__all__ = ["PromptSceneDiagnosticsOwner"]
