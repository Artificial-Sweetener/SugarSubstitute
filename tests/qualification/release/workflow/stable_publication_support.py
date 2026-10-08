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

"""Own disposable Git repositories and qualified channels for Stable publication."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


class StablePublicationRepository:
    """Provide a real local release repository, remote, and checksummed channel."""

    def __init__(self, directory: Path) -> None:
        """Initialize a tagged beta repository with one unreleased correction."""

        self.root = directory / "source"
        self.remote = directory / "remote.git"
        self.channel = self.root / ".local-release-channel"
        self.root.mkdir()
        files = {
            "package.json": json.dumps(
                {"name": "release-fixture", "version": "0.27.1"}
            ),
            "package-lock.json": json.dumps(
                {"version": "0.27.1", "packages": {"": {"version": "0.27.1"}}}
            ),
            "CHANGELOG.md": "## Previous release\n\nPreserved history.\n",
            "launcher/sugarsubstitute_launcher/__init__.py": '__version__ = "0.27.1"\n',
            "launcher/sugarsubstitute_launcher/build_metadata.py": 'RELEASE_CHANNEL = "stable"\n',
            "substitute/_version.py": '__version__ = "0.27.1"\n',
            "runtime.txt": "original\n",
        }
        for name, content in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Release Fixture")
        self.git("config", "user.email", "release-fixture@example.invalid")
        self.git("add", ".")
        self.git("commit", "-m", "chore: initialize release fixture")
        self.git("tag", "v0.27.1")
        (self.root / "runtime.txt").write_text("corrected\n", encoding="utf-8")
        self.git("add", "runtime.txt")
        self.git("commit", "-m", "fix: preserve selected image")
        self.source_commit = self.git("rev-parse", "HEAD").strip()
        self.git("init", "--bare", str(self.remote))
        self.git("push", str(self.remote), "HEAD:refs/heads/main")
        self.channel.mkdir()
        assets = {
            "SugarSubstitute-0.27.2-Windows-x64-Setup.exe": b"installer",
            "SugarSubstitute-app-v0.27.2.zip": b"application",
            "SugarSubstitute-installer-payload-windows-x64-v0.27.2.zip": b"payload",
            "manifest.json": b'{"version":"0.27.2","channel":"stable"}',
            "manifest.signed.json": b"qualified signed metadata",
        }
        for name, asset_bytes in assets.items():
            (self.channel / name).write_bytes(asset_bytes)
        (self.channel / "checksums.txt").write_text(
            "".join(
                f"{hashlib.sha256(content).hexdigest()}  {name}\n"
                for name, content in assets.items()
                if name.endswith((".zip", ".exe"))
            ),
            encoding="utf-8",
        )

    def git(self, *arguments: str) -> str:
        """Run Git against the disposable repository and preserve diagnostics."""

        return subprocess.run(
            ["git", *arguments],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout

    def release_context(self) -> dict[str, str]:
        """Return explicit publication authority for the disposable remote."""

        return {
            "root": str(self.root),
            "directory": str(self.channel),
            "version": "0.27.2",
            "repository": "Fixture/Release",
            "pushUrl": str(self.remote),
            "branch": "main",
        }
