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

"""Serve the external Comfy readiness boundary for clean-install proof."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Lock, Thread
from types import TracebackType

from tools.ci.installer_lifecycle_errors import InstallerLifecycleError

_LOOPBACK_HOST = "127.0.0.1"
_SYSTEM_STATS_PATH = "/system_stats"


class ExternalComfyReadinessServer:
    """Own a bounded loopback server that models Comfy's readiness boundary."""

    def __init__(self) -> None:
        """Bind an operating-system-assigned port and prepare request evidence."""

        self._request_paths: list[str] = []
        self._request_lock = Lock()
        self._server = ThreadingHTTPServer(
            (_LOOPBACK_HOST, 0),
            self._handler_type(),
        )
        self._server.daemon_threads = True
        self._thread = Thread(
            target=self._server.serve_forever,
            name="installer-external-comfy-readiness",
            daemon=True,
        )

    @property
    def host(self) -> str:
        """Return the literal loopback host supplied to onboarding."""

        return _LOOPBACK_HOST

    @property
    def port(self) -> int:
        """Return the port retained by the live server socket."""

        return int(self._server.server_address[1])

    def require_readiness_probe(self) -> None:
        """Require the installed application to observe the external boundary."""

        with self._request_lock:
            observed = tuple(self._request_paths)
        if _SYSTEM_STATS_PATH not in observed:
            raise InstallerLifecycleError(
                "Clean-install qualification never probed external Comfy readiness."
            )

    def __enter__(self) -> ExternalComfyReadinessServer:
        """Start serving before the installer begins its onboarding handoff."""

        self._thread.start()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop accepting requests and join the sole server owner thread."""

        del exception_type, exception, traceback
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=10.0)
        if self._thread.is_alive():
            raise InstallerLifecycleError(
                "External Comfy readiness server did not stop cleanly."
            )

    def _handler_type(self) -> type[BaseHTTPRequestHandler]:
        """Build one request handler bound to this server's evidence owner."""

        owner = self

        class _ReadinessHandler(BaseHTTPRequestHandler):
            """Respond only to the public Comfy readiness route."""

            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:  # noqa: N802
                """Return deterministic readiness or reject unrelated routes."""

                with owner._request_lock:
                    owner._request_paths.append(self.path)
                if self.path != _SYSTEM_STATS_PATH:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                payload = json.dumps(
                    {"system": {"comfyui_version": "installer-qualification-boundary"}},
                    sort_keys=True,
                ).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: object) -> None:
                """Suppress routine loopback request output."""

                del format, args

        return _ReadinessHandler


__all__ = ["ExternalComfyReadinessServer"]
