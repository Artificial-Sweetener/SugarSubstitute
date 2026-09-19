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

"""Own the splash helper's parent cancellation notification."""

from __future__ import annotations

import json
from typing import Protocol, TextIO


class QuitApplication(Protocol):
    """Describe the application operation required by splash cancellation."""

    def quit(self) -> None:
        """Stop the application event loop."""


def encode_splash_helper_event(message: dict[str, str]) -> str:
    """Return one compact helper-to-parent splash event."""

    return json.dumps(message, ensure_ascii=True, separators=(",", ":"))


def notify_cancel_requested(*, app: QuitApplication, stream: TextIO) -> None:
    """Notify the parent process and stop the splash event loop."""

    try:
        stream.write(encode_splash_helper_event({"type": "cancel"}) + "\n")
        stream.flush()
    except OSError:
        pass
    app.quit()


__all__ = ["QuitApplication", "encode_splash_helper_event", "notify_cancel_requested"]
