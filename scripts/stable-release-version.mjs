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

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
import { analyzeCommits } from "./release-history.mjs";
import { releaseCommits } from "./release-git.mjs";

const require = createRequire(import.meta.url);
const { latestStableTag, nextStableVersion } = require("./canary-release-version.cjs");
export const FIRST_RELEASE_VERSION = "0.9.0";

/**
 * Resolve a Stable version through the canonical beta history policy.
 * @param {string} root Repository root.
 * @param {string[]} tags Existing Stable tags.
 * @param {"patch" | undefined} fallback Canary's rolling release fallback.
 * @returns {string} Next version, or an empty string when no release is required.
 */
export function resolveStableVersion(root, tags, fallback) {
  if (tags.length === 0) {
    const metadata = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
    if (metadata.version !== FIRST_RELEASE_VERSION) {
      throw new Error(`The first release must be ${FIRST_RELEASE_VERSION}; package.json contains ${metadata.version ?? "<missing>"}.`);
    }
    return FIRST_RELEASE_VERSION;
  }
  const type = analyzeCommits(releaseCommits(root, latestStableTag(tags))) ?? fallback;
  return type ? nextStableVersion(tags, type) : "";
}
