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

"""Serve one exact temporary release channel over trusted loopback HTTPS."""

from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import subprocess
from threading import Thread
from typing import Any, Self

LOCAL_RELEASE_PORT = 44_443
LOCAL_RELEASE_BASE_URL = f"https://localhost:{LOCAL_RELEASE_PORT}"


class LocalReleaseServer:
    """Serve immutable candidate artifacts from a fixed CI-only HTTPS origin."""

    def __init__(self, *, release_root: Path, certificate_root: Path) -> None:
        """Validate the release root and prepare its trusted localhost endpoint."""

        self.release_root = release_root.resolve()
        if not (self.release_root / "manifest.json").is_file():
            raise FileNotFoundError(
                f"Candidate release manifest is missing: {self.release_root}"
            )
        certificate_root = certificate_root.resolve()
        certificate_root.mkdir(parents=True, exist_ok=True)
        self.certificate_path, key_path = _create_localhost_certificate(
            certificate_root
        )
        self._server = ThreadingHTTPServer(
            ("127.0.0.1", LOCAL_RELEASE_PORT),
            self._handler_class(),
        )
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(certfile=self.certificate_path, keyfile=key_path)
        self._server.socket = tls.wrap_socket(self._server.socket, server_side=True)
        self._thread: Thread | None = None

    @property
    def manifest_url(self) -> str:
        """Return the fixed manifest URL encoded into non-release candidate assets."""

        return f"{LOCAL_RELEASE_BASE_URL}/manifest.json"

    def __enter__(self) -> Self:
        """Start serving the candidate channel."""

        self._thread = Thread(
            target=self._server.serve_forever,
            name="candidate-release-https",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        """Stop the endpoint and release its fixed port."""

        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _handler_class(self) -> type[SimpleHTTPRequestHandler]:
        """Bind standard file serving to the exact candidate directory."""

        release_root = self.release_root

        class _Handler(SimpleHTTPRequestHandler):
            """Serve candidate files without noisy request logging."""

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                """Initialize one request against the immutable release root."""

                super().__init__(*args, directory=str(release_root), **kwargs)

            def log_message(self, _format: str, *_args: object) -> None:
                """Suppress routine local qualification request output."""

        return _Handler


def _create_localhost_certificate(certificate_root: Path) -> tuple[Path, Path]:
    """Create a one-day localhost CA certificate trusted only by the harness."""

    config_path = certificate_root / "openssl-local-release.cnf"
    certificate_path = certificate_root / "localhost.pem"
    key_path = certificate_root / "localhost-key.pem"
    config_path.write_text(
        "\n".join(
            (
                "[req]",
                "distinguished_name = dn",
                "x509_extensions = v3_req",
                "prompt = no",
                "[dn]",
                "CN = localhost",
                "[v3_req]",
                "basicConstraints = critical, CA:TRUE",
                "keyUsage = critical, digitalSignature, keyEncipherment, keyCertSign",
                "extendedKeyUsage = serverAuth",
                "subjectAltName = @alt_names",
                "[alt_names]",
                "DNS.1 = localhost",
                "IP.1 = 127.0.0.1",
                "",
            )
        ),
        encoding="utf-8",
    )
    subprocess.run(
        (
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-keyout",
            str(key_path),
            "-out",
            str(certificate_path),
            "-config",
            str(config_path),
            "-sha256",
        ),
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return certificate_path, key_path


__all__ = ["LOCAL_RELEASE_BASE_URL", "LOCAL_RELEASE_PORT", "LocalReleaseServer"]
