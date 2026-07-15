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

const { writeFileSync } = require("node:fs");

const DEFAULT_REPOSITORY = "Artificial-Sweetener/SugarSubstitute";

/**
 * Build the installer guidance prepended to every GitHub Release description.
 *
 * @param {string} repository GitHub repository in owner/name form.
 * @param {string} version Dotted numeric release version without a tag prefix.
 * @returns {string} Markdown release guidance.
 */
function createInstallerReleaseNotes(repository, version) {
  const normalizedRepository = validateRepository(repository);
  const normalizedVersion = validateVersion(version);
  const assetRoot = `https://github.com/${normalizedRepository}/releases/download/v${normalizedVersion}`;
  const iconRoot = `https://raw.githubusercontent.com/${normalizedRepository}/v${normalizedVersion}/docs/release/platforms`;

  return [
    "## Install SugarSubstitute",
    "",
    "Download the installer for your platform:",
    "",
    `- <img src="${iconRoot}/windows.svg" width="18" height="18" alt=""> [Windows x64 installer](${assetRoot}/SugarSubstitute-Installer-Windows-x64.exe)`,
    `- <img src="${iconRoot}/apple.svg" width="18" height="18" alt=""> [macOS Apple Silicon installer](${assetRoot}/SugarSubstitute-Installer-macOS-Apple-Silicon.dmg)`,
    `- <img src="${iconRoot}/linux.svg" width="18" height="18" alt=""> [Linux x86_64 AppImage installer](${assetRoot}/SugarSubstitute-Installer-Linux-x86_64.AppImage) or [Debian package](${assetRoot}/SugarSubstitute-Installer-Linux-amd64.deb)`,
    "",
    "The macOS installer is ad-hoc signed but not notarized. macOS will warn that it cannot verify the developer, so allow it through Privacy & Security after downloading it from this repository.",
    "",
    "**Already installed?** Open SugarSubstitute normally. It checks for application updates when it starts, usually once per day, and installs newer application versions automatically. You normally do not need another installer.",
    "",
  ].join("\n");
}

/**
 * Reject repository values that cannot safely form GitHub asset URLs.
 *
 * @param {string} repository Candidate owner/name value.
 * @returns {string} Validated repository value.
 */
function validateRepository(repository) {
  const normalized = String(repository).trim();
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(normalized)) {
    throw new Error(`Expected GitHub repository in owner/name form: ${repository}`);
  }
  return normalized;
}

/**
 * Reject version values that cannot safely form the release tag and asset URLs.
 *
 * @param {string} version Candidate semantic version.
 * @returns {string} Validated version without a tag prefix.
 */
function validateVersion(version) {
  const normalized = String(version).trim().replace(/^v/, "");
  if (!/^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/.test(normalized)) {
    throw new Error(`Expected a semantic release version: ${version}`);
  }
  return normalized;
}

/**
 * Parse the small command surface used by the first-release workflow.
 *
 * @param {string[]} args Process arguments following the script path.
 * @returns {{repository: string, version: string, output: string}} Parsed options.
 */
function parseArguments(args) {
  const values = new Map();
  for (let index = 0; index < args.length; index += 2) {
    const name = args[index];
    const value = args[index + 1];
    if (!name?.startsWith("--") || value === undefined) {
      throw new Error("Expected --repository, --version, and --output values.");
    }
    values.set(name, value);
  }
  const repository = values.get("--repository");
  const version = values.get("--version");
  const output = values.get("--output");
  if (!repository || !version || !output) {
    throw new Error("Expected --repository, --version, and --output values.");
  }
  return { repository, version, output };
}

if (require.main === module) {
  const options = parseArguments(process.argv.slice(2));
  writeFileSync(
    options.output,
    createInstallerReleaseNotes(options.repository, options.version),
    "utf8",
  );
}

module.exports = {
  createInstallerReleaseNotes,
  DEFAULT_REPOSITORY,
};
