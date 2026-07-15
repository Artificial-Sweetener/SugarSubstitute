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

import { spawnSync } from "node:child_process";
import { existsSync, rmSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { updateReleaseVersions } from "./update-release-versions.mjs";

const nextVersion = process.argv[2];

if (!nextVersion) {
  throw new Error("Expected the next release version as the first argument.");
}

const repository = process.env.GITHUB_REPOSITORY;
if (!repository) {
  throw new Error("GITHUB_REPOSITORY must be set to prepare release assets.");
}

const projectRoot = resolve(fileURLToPath(new URL("../", import.meta.url)));
const releaseChannelDir = join(projectRoot, ".local-release-channel");
const releaseInputsDir = join(projectRoot, "build", "release-inputs");
const windowsDir = join(releaseInputsDir, "windows");
const macosDir = join(releaseInputsDir, "macos");
const linuxDir = join(releaseInputsDir, "linux");
const setupExePath = join(windowsDir, "SugarSubstitute-Setup-Windows-x64.exe");
const windowsInstallerPayload = join(
  windowsDir,
  "installer-payload-windows-x64.zip",
);
const macosInstallerPayload = join(
  macosDir,
  "installer-payload-macos-arm64.zip",
);
const macosInstallerPath = join(
  macosDir,
  "SugarSubstitute-Installer-macOS-Apple-Silicon.dmg",
);
const linuxInstallerPayload = join(
  linuxDir,
  "installer-payload-linux-x64.zip",
);
const linuxAppImagePath = join(
  linuxDir,
  "SugarSubstitute-Installer-Linux-x86_64.AppImage",
);
const linuxDebPath = join(
  linuxDir,
  "SugarSubstitute-Installer-Linux-amd64.deb",
);
const pythonPath = resolvePythonPath(projectRoot);

assertFile(setupExePath, "setup executable");
assertFile(windowsInstallerPayload, "Windows installer payload");
assertFile(macosInstallerPayload, "Apple Silicon installer payload");
assertFile(macosInstallerPath, "Apple Silicon installer DMG");
assertFile(linuxInstallerPayload, "Linux installer payload");
assertFile(linuxAppImagePath, "Linux AppImage installer");
assertFile(linuxDebPath, "Linux Debian installer");

rmSync(releaseChannelDir, { force: true, recursive: true });
updateReleaseVersions(new URL("../", import.meta.url), nextVersion);

const assetBaseUrl = `https://github.com/${repository}/releases/download/v${nextVersion}`;
const buildResult = spawnSync(
  pythonPath,
  [
    "tools/build_release_payload.py",
    "build",
    "--version",
    nextVersion,
    "--platform-input",
    "windows_x64",
    windowsInstallerPayload,
    "--installer-input",
    "windows_x64",
    "exe",
    setupExePath,
    "--platform-input",
    "macos_arm64",
    macosInstallerPayload,
    "--installer-input",
    "macos_arm64",
    "dmg",
    macosInstallerPath,
    "--platform-input",
    "linux_x64",
    linuxInstallerPayload,
    "--installer-input",
    "linux_x64",
    "appimage",
    linuxAppImagePath,
    "--installer-input",
    "linux_x64",
    "deb",
    linuxDebPath,
    "--asset-base-url",
    assetBaseUrl,
  ],
  { cwd: projectRoot, encoding: "utf8" },
);
if (buildResult.error) {
  throw buildResult.error;
}
if (buildResult.status !== 0) {
  const stderr = buildResult.stderr ?? "";
  const stdout = buildResult.stdout ?? "";
  throw new Error(`Release payload build failed.\n${stdout}\n${stderr}`);
}

const publicInstallerPath = join(
  releaseChannelDir,
  "SugarSubstitute-Installer-Windows-x64.exe",
);
assertFile(publicInstallerPath, "public installer executable");
assertFile(join(releaseChannelDir, "manifest.json"), "release manifest");
assertFile(join(releaseChannelDir, "checksums.txt"), "release checksums");
assertFile(
  join(releaseChannelDir, `SugarSubstitute-app-v${nextVersion}.zip`),
  "app payload",
);
assertFile(
  join(
    releaseChannelDir,
    `SugarSubstitute-installer-payload-macos-arm64-v${nextVersion}.zip`,
  ),
  "Apple Silicon installer payload",
);
assertFile(
  join(
    releaseChannelDir,
    "SugarSubstitute-Installer-macOS-Apple-Silicon.dmg",
  ),
  "Apple Silicon installer DMG",
);
assertFile(
  join(releaseChannelDir, "SugarSubstitute-Installer-Linux-x86_64.AppImage"),
  "Linux AppImage installer",
);
assertFile(
  join(releaseChannelDir, "SugarSubstitute-Installer-Linux-amd64.deb"),
  "Linux Debian installer",
);
assertFile(
  join(
    releaseChannelDir,
    `SugarSubstitute-installer-payload-linux-x64-v${nextVersion}.zip`,
  ),
  "Linux installer payload",
);
assertFile(
  join(
    releaseChannelDir,
    `SugarSubstitute-installer-payload-windows-x64-v${nextVersion}.zip`,
  ),
  "Windows installer payload",
);

function resolvePythonPath(root) {
  const venvPython = join(root, ".venv", "Scripts", "python.exe");
  if (existsSync(venvPython)) {
    return venvPython;
  }
  return "python";
}

function assertFile(path, description) {
  if (!existsSync(path) || !statSync(path).isFile()) {
    throw new Error(`Missing ${description}: ${path}`);
  }
}
