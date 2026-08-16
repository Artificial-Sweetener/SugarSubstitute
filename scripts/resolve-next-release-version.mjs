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

import { appendFileSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const releaseConfig = require("../.releaserc.cjs");
const { createCanaryVersion, nextPatchVersion } = require(
  "./canary-release-version.cjs",
);
const { selectVersionResolutionPlugins } = require(
  "./release-version-plugins.cjs",
);
const FIRST_RELEASE_VERSION = "0.9.0";
const qualificationVersion = process.env.SUGAR_SUBSTITUTE_QUALIFICATION_VERSION;
const canaryRunNumber = process.env.SUGAR_SUBSTITUTE_CANARY_RUN_NUMBER?.trim();
const projectRoot = resolve(fileURLToPath(new URL("../", import.meta.url)));
const releaseTags = git(["tag", "--list", "v[0-9]*"])
  .split(/\r?\n/)
  .map((tag) => tag.trim())
  .filter(Boolean);

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
  const firstReleaseVersion = readFirstReleaseVersion();
  version = canaryRunNumber
    ? createCanaryVersion(firstReleaseVersion, canaryRunNumber)
    : firstReleaseVersion;
  shouldRelease = true;
  firstRelease = !canaryRunNumber;
} else {
  const { default: semanticRelease } = await import("semantic-release");
  const result = await semanticRelease({
    ...(canaryRunNumber
      ? { branches: [process.env.GITHUB_REF_NAME ?? "canary"] }
      : {}),
    ci: false,
    dryRun: true,
    plugins: selectVersionResolutionPlugins(releaseConfig),
  });
  const nextStableVersion =
    result?.nextRelease?.version ??
    (canaryRunNumber ? nextPatchVersion(releaseTags) : "");
  version = canaryRunNumber
    ? createCanaryVersion(nextStableVersion, canaryRunNumber)
    : nextStableVersion;
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

function readFirstReleaseVersion() {
  const packagePath = resolve(projectRoot, "package.json");
  const metadata = JSON.parse(readFileSync(packagePath, "utf8"));
  if (metadata.version !== FIRST_RELEASE_VERSION) {
    throw new Error(
      `The first release must be ${FIRST_RELEASE_VERSION}; package.json contains ${metadata.version ?? "<missing>"}.`,
    );
  }
  return FIRST_RELEASE_VERSION;
}

function git(args) {
  const result = spawnSync("git", args, {
    cwd: projectRoot,
    encoding: "utf8",
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(
      `git ${args.join(" ")} failed.\n${result.stdout ?? ""}\n${result.stderr ?? ""}`,
    );
  }
  return result.stdout ?? "";
}
