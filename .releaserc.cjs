//    SugarSubstitute - The desktop native Qt front-end for ComfyUI
//    Copyright (C) 2026  Artificial Sweetener and contributors
//
//    This program is free software: you can redistribute it and/or modify
//    it under the terms of the GNU General Public License as published by
//    the Free Software Foundation, either version 3 of the License, or
//    (at your option) any later version.
//
//    This program is distributed in the hope that it will be useful,
//    but WITHOUT ANY WARRANTY; without even the implied warranty of
//    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//    GNU General Public License for more details.
//
//    You should have received a copy of the GNU General Public License
//    along with this program.  If not, see <https://www.gnu.org/licenses/>.

const githubRepository = process.env.GITHUB_REPOSITORY?.trim();
const releaseRepository =
  githubRepository || "Artificial-Sweetener/SugarSubstitute";
const repositoryUrl = githubRepository
  ? `${process.env.GITHUB_SERVER_URL ?? "https://github.com"}/${githubRepository}.git`
  : "https://github.com/Artificial-Sweetener/SugarSubstitute.git";

module.exports = {
  branches: ["main"],
  repositoryUrl,
  tagFormat: "v${version}",
  plugins: [
    [
      "@semantic-release/commit-analyzer",
      {
        releaseRules: [
          { breaking: true, release: "minor" },
          { type: "feat", release: "minor" },
          { type: "fix", release: "patch" },
          { type: "perf", release: "patch" },
        ],
      },
    ],
    "@semantic-release/release-notes-generator",
    ["@semantic-release/changelog", { changelogFile: "CHANGELOG.md" }],
    [
      "@semantic-release/exec",
      {
        verifyReleaseCmd:
          "node scripts/verify-beta-release-version.mjs ${nextRelease.version}",
        prepareCmd:
          "node scripts/prepare-release-assets.mjs ${nextRelease.version}",
      },
    ],
    [
      "@semantic-release/git",
      {
        assets: [
          "CHANGELOG.md",
          "package.json",
          "package-lock.json",
          "launcher/sugarsubstitute_launcher/__init__.py",
          "substitute/_version.py",
        ],
        message:
          "chore(release): ${nextRelease.version} [skip ci]\n\n${nextRelease.notes}",
      },
    ],
    [
      "./scripts/github-release-publisher.cjs",
      {
        repository: releaseRepository,
        assets: [
          {
            path: ".local-release-channel/SugarSubstitute-Installer-Windows-x64.exe",
            label: "SugarSubstitute Installer for Windows x64",
          },
          {
            path: ".local-release-channel/SugarSubstitute-Installer-macOS-Apple-Silicon.dmg",
            label: "SugarSubstitute Installer for macOS Apple Silicon",
          },
          {
            path: ".local-release-channel/SugarSubstitute-Installer-Linux-x86_64.AppImage",
            label: "SugarSubstitute AppImage for Linux x64",
          },
          {
            path: ".local-release-channel/SugarSubstitute-Installer-Linux-amd64.deb",
            label: "SugarSubstitute Debian package for Linux x64",
          },
          {
            path: ".local-release-channel/SugarSubstitute-app-v*.zip",
            label: "SugarSubstitute app payload",
          },
          {
            path: ".local-release-channel/SugarSubstitute-installer-payload-windows-x64-v*.zip",
            label: "SugarSubstitute installer payload for Windows x64",
          },
          {
            path: ".local-release-channel/SugarSubstitute-installer-payload-macos-arm64-v*.zip",
            label: "SugarSubstitute installer payload for macOS Apple Silicon",
          },
          {
            path: ".local-release-channel/SugarSubstitute-installer-payload-linux-x64-v*.zip",
            label: "SugarSubstitute installer payload for Linux x64",
          },
          {
            path: ".local-release-channel/manifest.json",
            label: "Update manifest",
          },
          {
            path: ".local-release-channel/checksums.txt",
            label: "Release checksums",
          },
        ],
      },
    ],
  ],
};
