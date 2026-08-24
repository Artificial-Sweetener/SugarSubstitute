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
import json
from pathlib import Path
import ssl
import subprocess
from threading import Lock, Thread
import time
from typing import Any, Self, cast

import certifi

from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset, ReleaseManifest

LOCAL_RELEASE_BASE_URL_PLACEHOLDER = "https://localhost.invalid"


class LocalReleaseServer:
    """Serve immutable candidate artifacts from one owned loopback origin."""

    def __init__(self, *, release_root: Path, certificate_root: Path) -> None:
        """Validate the release root and prepare its trusted localhost endpoint."""

        self.release_root = release_root.resolve()
        if not (self.release_root / "manifest.json").is_file():
            raise FileNotFoundError(
                f"Candidate release manifest is missing: {self.release_root}"
            )
        certificate_root = certificate_root.resolve()
        certificate_root.mkdir(parents=True, exist_ok=True)
        self.request_log_path = certificate_root / "requests.jsonl"
        self.request_log_path.unlink(missing_ok=True)
        self._request_log_lock = Lock()
        self.certificate_path, key_path = _create_localhost_certificate(
            certificate_root
        )
        self.trust_bundle_path = _create_qualification_trust_bundle(
            certificate_root=certificate_root,
            certificate_path=self.certificate_path,
        )
        self._server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            SimpleHTTPRequestHandler,
        )
        self._qualification_manifest = _qualification_manifest_bytes(
            manifest_path=self.release_root / "manifest.json",
            release_root=self.release_root,
            base_url=self.base_url,
        )
        self._server.RequestHandlerClass = self._handler_class()
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(
            certfile=self.certificate_path,
            keyfile=key_path,
        )
        self._server.socket = tls.wrap_socket(self._server.socket, server_side=True)
        self._thread: Thread | None = None

    @property
    def manifest_url(self) -> str:
        """Return the manifest URL for this exact loopback endpoint."""

        return f"{self.base_url}/manifest.json"

    @property
    def base_url(self) -> str:
        """Return the dynamically allocated HTTPS origin."""

        host, port = self._server.server_address[:2]
        return f"https://localhost:{port}" if host == "127.0.0.1" else ""

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
        """Stop the endpoint and release its allocated port."""

        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _handler_class(self) -> type[SimpleHTTPRequestHandler]:
        """Bind standard file serving to the exact candidate directory."""

        release_root = self.release_root
        qualification_manifest = self._qualification_manifest
        request_log_path = self.request_log_path
        request_log_lock = self._request_log_lock

        class _Handler(SimpleHTTPRequestHandler):
            """Serve candidate files without noisy request logging."""

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                """Initialize one request against the immutable release root."""

                super().__init__(*args, directory=str(release_root), **kwargs)

            def log_message(self, _format: str, *_args: object) -> None:
                """Suppress routine local qualification request output."""

            def do_GET(self) -> None:
                """Record access and serve the loopback-qualified manifest view."""

                with request_log_lock:
                    with request_log_path.open("a", encoding="utf-8") as output:
                        output.write(
                            json.dumps(
                                {
                                    "method": "GET",
                                    "path": self.path,
                                    "time_ns": time.time_ns(),
                                },
                                sort_keys=True,
                            )
                            + "\n"
                        )
                if self.path.partition("?")[0] == "/manifest.json":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(qualification_manifest)))
                    self.end_headers()
                    self.wfile.write(qualification_manifest)
                    return
                super().do_GET()

        return _Handler


def _qualification_manifest_bytes(
    *,
    manifest_path: Path,
    release_root: Path,
    base_url: str,
) -> bytes:
    """Build an in-memory manifest view that resolves staged assets locally."""

    decoded: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    ReleaseManifest.from_json(decoded)
    if not isinstance(decoded, dict):
        raise ValueError("Candidate release manifest must be a JSON object.")
    payload = cast(dict[str, object], decoded)
    _rewrite_qualification_asset(payload.get("app"), release_root, base_url)
    for collection_name in ("launchers", "installers"):
        collection = payload.get(collection_name)
        if not isinstance(collection, dict):
            raise ValueError(
                f"Candidate release manifest field must be an object: {collection_name}"
            )
        for asset_payload in collection.values():
            _rewrite_qualification_asset(asset_payload, release_root, base_url)
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _rewrite_qualification_asset(
    asset_payload: object,
    release_root: Path,
    base_url: str,
) -> None:
    """Point one present staged asset at the trusted loopback server."""

    asset = ReleaseAsset.from_json(asset_payload)
    if Path(asset.filename).name != asset.filename:
        raise ValueError(
            f"Candidate release asset filename must not contain a path: {asset.filename}"
        )
    asset_path = release_root / asset.filename
    if not asset_path.is_file():
        return
    if not isinstance(asset_payload, dict):
        raise ValueError("Candidate release asset must be a JSON object.")
    mutable_payload = cast(dict[str, object], asset_payload)
    mutable_payload["url"] = f"{base_url}/{asset.filename}"


def _create_localhost_certificate(
    certificate_root: Path,
) -> tuple[Path, Path]:
    """Create a fast one-day EC localhost CA trusted only by the harness."""

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
                "keyUsage = critical, digitalSignature, keyCertSign",
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
            "ec",
            "-pkeyopt",
            "ec_paramgen_curve:prime256v1",
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
    return certificate_path.resolve(), key_path.resolve()


def _create_qualification_trust_bundle(
    *,
    certificate_root: Path,
    certificate_path: Path,
) -> Path:
    """Combine public roots and the loopback CA for inherited installers."""

    bundle_path = certificate_root / "qualification-ca-bundle.pem"
    public_roots = Path(certifi.where()).read_text(encoding="ascii")
    loopback_root = certificate_path.read_text(encoding="ascii")
    bundle_path.write_text(
        f"{public_roots.rstrip()}\n{loopback_root.rstrip()}\n",
        encoding="ascii",
    )
    return bundle_path.resolve()


__all__ = ["LOCAL_RELEASE_BASE_URL_PLACEHOLDER", "LocalReleaseServer"]
