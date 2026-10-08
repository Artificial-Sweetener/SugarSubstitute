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

import { appendFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { createCanaryVersion } = require(
  "./canary-release-version.cjs",
);
import { git as runGit } from "./release-git.mjs";
import { resolveStableVersion } from "./stable-release-version.mjs";
const qualificationVersion = process.env.SUGAR_SUBSTITUTE_QUALIFICATION_VERSION;
const canaryRunNumber = process.env.SUGAR_SUBSTITUTE_CANARY_RUN_NUMBER?.trim();
const projectRoot = resolve(fileURLToPath(new URL("../", import.meta.url)));
const pendingStableVersion = process.env.SUGAR_SUBSTITUTE_PENDING_STABLE_VERSION;
if (pendingStableVersion && !/^0\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(pendingStableVersion)) {
  throw new Error("Pending Stable publication requires a plain beta version.");
}
const releaseTags = git(["tag", "--list", "v[0-9]*"])
  .split(/\r?\n/)
  .map((tag) => tag.trim())
  .filter((tag) => tag && tag !== `v${pendingStableVersion}`);

let version;
let shouldRelease;
let firstRelease;

if (qualificationVersion) {
  if (!/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(qualificationVersion)) {
    throw new Error(
      "SUGAR_SUBSTITUTE_QUALIFICATION_VERSION must be an exact semantic version.",
    );
  }
  version = qualificationVersion;
  shouldRelease = true;
  firstRelease = false;
} else if (releaseTags.length === 0) {
  const firstReleaseVersion = resolveStableVersion(projectRoot, releaseTags);
  version = canaryRunNumber
    ? createCanaryVersion(firstReleaseVersion, canaryRunNumber)
    : firstReleaseVersion;
  shouldRelease = true;
  firstRelease = !canaryRunNumber;
} else {
  const resolvedStableVersion = resolveStableVersion(
    projectRoot,
    releaseTags,
    canaryRunNumber ? "patch" : undefined,
  );
  version = canaryRunNumber
    ? createCanaryVersion(resolvedStableVersion, canaryRunNumber)
    : resolvedStableVersion;
  shouldRelease = canaryRunNumber ? true : version.length > 0;
  firstRelease = false;
}

if (process.env.GITHUB_OUTPUT) {
  appendFileSync(
    process.env.GITHUB_OUTPUT,
    `version=${version}\nshould_release=${shouldRelease}\nfirst_release=${firstRelease}\n`,
    "utf8",
  );
} else {
  process.stdout.write(
    JSON.stringify({ version, shouldRelease, firstRelease }, null, 2) + "\n",
  );
}

/** Run Git in the version resolver's repository. */
function git(args) {
  return runGit(projectRoot, args);
}
