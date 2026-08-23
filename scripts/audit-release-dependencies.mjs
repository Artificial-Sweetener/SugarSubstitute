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

const ignoredAdvisoryIds = new Set([1124334]);
const ignoredAdvisoryUrls = new Set([
  // These affect runtime paths in npm, an unused nested semantic-release plugin.
  "https://github.com/advisories/GHSA-mh99-v99m-4gvg",
  "https://github.com/advisories/GHSA-rgw5-rvv9-x895",
  "https://github.com/advisories/GHSA-mwp4-54f8-5fhr",
]);
const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const audit = spawnSync(npmCommand, ["audit", "--json"], {
  encoding: "utf8",
  shell: process.platform === "win32",
});

if (audit.error) {
  throw audit.error;
}

let report;
try {
  report = JSON.parse(audit.stdout);
} catch (error) {
  throw new Error("npm audit did not produce a JSON report.", { cause: error });
}

const unresolvedFindings = Object.values(report.vulnerabilities ?? []).flatMap(
  (vulnerability) =>
    vulnerability.via.filter(
      (finding) =>
        typeof finding === "object" &&
        ["high", "critical"].includes(finding.severity) &&
        !ignoredAdvisoryIds.has(finding.source) &&
        !ignoredAdvisoryUrls.has(finding.url),
    ),
);

if (unresolvedFindings.length > 0) {
  console.error("Release dependency audit found unapproved high or critical vulnerabilities.");
  console.error(JSON.stringify(unresolvedFindings, null, 2));
  process.exitCode = 1;
} else {
  console.log("Release dependency audit found no unapproved high or critical vulnerabilities.");
}
