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

"""Define the startup splash presentation port and local adapters."""

from __future__ import annotations

from typing import Protocol
from sugarsubstitute_shared.launch_splash.activity import SplashActivity
from sugarsubstitute_shared.launch_splash.progress import SplashProgress


class SplashPresentationPort(Protocol):
    """Describe operation feedback shared by native and remote splash surfaces."""

    def set_progress(self, progress: SplashProgress, *, status: str) -> None:
        """Display completed producer units with localized operation copy."""

    def append_log(self, line: str) -> None:
        """Append one status or log line to the launch splash."""

    def start_activity(self, activity: SplashActivity) -> None:
        """Start or replace one independently animated splash activity."""

    def clear_activity(self) -> None:
        """Stop the active splash activity and remove its transient row."""


class LaunchSplashClient(SplashPresentationPort, Protocol):
    """Expose the transport-independent splash lifecycle used by startup."""

    def close(self) -> None:
        """Close the launch splash if it is still available."""


class InProcessSplashPort(SplashPresentationPort, Protocol):
    """Accept the native close acknowledgement at the local widget boundary."""

    def dismiss(self) -> None:
        """Dismiss the native surface without requesting startup cancellation."""


class NullLaunchSplashClient:
    """Ignore launch-splash calls when the helper is unavailable."""

    def set_progress(self, progress: SplashProgress, *, status: str) -> None:
        """Accept completion updates when no presentation surface is available."""

    def append_log(self, line: str) -> None:
        """Discard one splash line."""

        _ = line

    def start_activity(self, activity: SplashActivity) -> None:
        """Discard one splash activity."""

        _ = activity

    def clear_activity(self) -> None:
        """Complete a no-op activity clear."""

    def close(self) -> None:
        """Complete a no-op close."""


class InProcessLaunchSplashClient:
    """Adapt an existing in-process splash widget to the launch-splash protocol."""

    def __init__(self, splash_window: InProcessSplashPort) -> None:
        """Store the concrete splash widget used by fallback and tests."""

        self._splash_window = splash_window

    def set_progress(self, progress: SplashProgress, *, status: str) -> None:
        """Forward completion to the in-process presentation owner."""
        self._splash_window.set_progress(progress, status=status)

    def append_log(self, line: str) -> None:
        """Append one line to the in-process splash widget."""

        self._splash_window.append_log(line)

    def start_activity(self, activity: SplashActivity) -> None:
        """Start an activity on the in-process splash widget."""

        self._splash_window.start_activity(activity)

    def clear_activity(self) -> None:
        """Clear the in-process splash activity."""

        self._splash_window.clear_activity()

    def close(self) -> None:
        """Close the in-process splash widget."""

        self._splash_window.dismiss()
