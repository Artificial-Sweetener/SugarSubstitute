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
import { spawnSync } from "node:child_process";

import { unresolvedReleaseFindings } from "./release-dependency-audit.mjs";

const manifest = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
const lock = JSON.parse(readFileSync(new URL("../package-lock.json", import.meta.url), "utf8"));
const root = lock.packages?.[""];
if (manifest.private !== true || manifest.name !== "sugarsubstitute-release" ||
    manifest.scripts?.release !== "semantic-release" ||
    ["dependencies", "optionalDependencies", "devDependencies"].some((field) =>
      JSON.stringify(Object.entries(manifest[field] ?? {}).sort()) !==
      JSON.stringify(Object.entries(root?.[field] ?? {}).sort()))) {
  throw new Error("Release audit requires the private, locked semantic-release toolchain.");
}

const npmCommand = process.platform === "win32" ? "corepack.cmd" : "corepack";
const audit = spawnSync(npmCommand, ["npm", "audit", "--json"], {
  encoding: "utf8",
  shell: process.platform === "win32",
});

if (audit.error) {
  throw audit.error;
}
if (![0, 1].includes(audit.status)) {
  throw new Error(`npm audit failed before completing its report: ${audit.stderr ?? ""}`);
}

let report;
try {
  report = JSON.parse(audit.stdout);
} catch (error) {
  throw new Error("npm audit did not produce a JSON report.", { cause: error });
}

const unresolvedFindings = unresolvedReleaseFindings(report, lock);

if (unresolvedFindings.length > 0) {
  console.error("Release dependency audit found unapproved high or critical vulnerabilities.");
  console.error(JSON.stringify(unresolvedFindings, null, 2));
  process.exitCode = 1;
} else {
  console.log("Release dependency audit found no unapproved high or critical vulnerabilities; reviewed CI-only exceptions remain.");
}
