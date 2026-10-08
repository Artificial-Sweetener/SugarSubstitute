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

import { createReadStream, lstatSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";
import { git, releaseCommits } from "./release-git.mjs";
import { generateReleaseNotes } from "./release-history.mjs";
import { resolveStableVersion } from "./stable-release-version.mjs";
import { updateReleaseVersions } from "./update-release-versions.mjs";

const require = createRequire(import.meta.url);
const { latestStableTag } = require("./canary-release-version.cjs");
const { createInstallerReleaseNotes } = require("./release-notes-preamble.cjs");

export const RELEASE_METADATA_FILES = [
  "CHANGELOG.md", "package.json", "package-lock.json",
  "launcher/sugarsubstitute_launcher/__init__.py",
  "launcher/sugarsubstitute_launcher/build_metadata.py", "substitute/_version.py",
];

/**
 * Validate the qualified Windows Stable channel before any repository mutation.
 * @param {string} directory Qualified channel directory.
 * @param {string} version Exact candidate version.
 * @returns {Promise<string[]>} Complete verified qualified asset paths.
 */
export async function stableAssets(directory, version) {
  const expected = [
    `SugarSubstitute-${version}-Windows-x64-Setup.exe`,
    `SugarSubstitute-app-v${version}.zip`,
    `SugarSubstitute-installer-payload-windows-x64-v${version}.zip`,
    "manifest.json", "manifest.signed.json", "checksums.txt",
  ].sort();
  const actual = readdirSync(directory).filter((name) => name !== ".release-notes.md").sort();
  if (JSON.stringify(actual) !== JSON.stringify(expected) ||
      actual.some((name) => !lstatSync(join(directory, name)).isFile())) {
    throw new Error("Qualified Stable asset inventory differs from the required Windows channel.");
  }
  const manifest = JSON.parse(readFileSync(join(directory, "manifest.json"), "utf8"));
  if (manifest.version !== version || manifest.channel !== "stable") {
    throw new Error("Qualified Stable manifest does not identify this release.");
  }
  const checksums = readFileSync(join(directory, "checksums.txt"), "utf8").trim().split(/\r?\n/);
  const payloads = expected.filter((name) => name.endsWith(".zip") || name.endsWith(".exe"));
  const verified = new Set();
  for (const line of checksums) {
    const match = /^([a-f0-9]{64})  (.+)$/.exec(line);
    if (!match || !payloads.includes(match[2]) || verified.has(match[2])) {
      throw new Error("Qualified Stable checksums contain an invalid or duplicate asset.");
    }
    const hash = createHash("sha256");
    for await (const chunk of createReadStream(join(directory, match[2]))) hash.update(chunk);
    if (hash.digest("hex") !== match[1]) throw new Error(`Qualified Stable asset checksum differs: ${match[2]}`);
    verified.add(match[2]);
  }
  if (verified.size !== payloads.length) throw new Error("Qualified Stable checksums omit a payload.");
  return actual.map((name) => join(directory, name));
}

/**
 * Prepare canonical Stable history and metadata for the exact qualified version.
 * @param {{root: string, directory: string, version: string, repository: string, serverUrl?: string, date?: string}} release Qualified release context.
 * @returns {Promise<{assets: string[], notesPath: string, notes: string}>} Prepared release files.
 */
export async function prepareStableRelease(release) {
  const { root, directory, version, repository } = release;
  if (!/^0\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(version)) {
    throw new Error("SugarSubstitute Stable releases require a plain beta version.");
  }
  const preamble = createInstallerReleaseNotes(repository, version);
  const assets = await stableAssets(directory, version);
  const tags = git(root, ["tag", "--list", "v[0-9]*"]).split(/\r?\n/)
    .filter((tag) => tag && tag !== `v${version}`);
  const previousTag = tags.length ? latestStableTag(tags) : undefined;
  const commits = releaseCommits(root, previousTag);
  const packageData = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
  const resolved = resolveStableVersion(root, tags);
  if (resolved !== version) {
    throw new Error(`Qualified version ${version} differs from resolved Stable version ${resolved || "<no release>"}.`);
  }
  const notes = await generateReleaseNotes(commits, {
    version, repository, previousTag, packageData,
    serverUrl: release.serverUrl ?? "https://github.com",
    date: release.date,
  });
  const changelog = readFileSync(join(root, "CHANGELOG.md"), "utf8").trim();
  updateReleaseVersions(pathToFileURL(`${root}/`), version, "stable");
  const history = notes.trim();
  const updatedHistory = changelog.startsWith(`${history}\n`) || changelog === history
    ? `${changelog}\n` : `${history}\n${changelog ? `\n${changelog}\n` : ""}`;
  writeFileSync(join(root, "CHANGELOG.md"), updatedHistory);
  const notesPath = join(directory, ".release-notes.md");
  writeFileSync(notesPath, `${preamble}\n${notes}`);
  return { assets, notesPath, notes };
}
