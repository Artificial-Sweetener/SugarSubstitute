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

import {
  isReviewedReleaseAdvisory,
  isReviewedReleaseFinding,
  validateReleaseLock,
} from "./release-dependency-audit-policy.mjs";

const severities = ["info", "low", "moderate", "high", "critical"];

/** Return whether a value is a JSON object rather than an array or null. */
function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** Recognize canonical package names without accepting path traversal. */
function isPackageName(value) {
  return typeof value === "string" &&
    /^(?:@[a-z0-9._-]+\/)?[a-z0-9._-]+$/.test(value) &&
    value.split("/").every((part) => part !== "." && part !== "..");
}

/** Verify audit paths identify the named dependency without normalization. */
function isDependencyPath(path, name) {
  return typeof path === "string" && path.startsWith("node_modules/") &&
    path.split("node_modules/").slice(1).every((part, index, parts) =>
      isPackageName(index === parts.length - 1 ? part : part.slice(0, -1)) &&
      (index === parts.length - 1 || part.endsWith("/"))) &&
    path.slice(path.lastIndexOf("node_modules/") + "node_modules/".length) === name;
}

/** Validate direct advisory evidence before deciding whether it is reviewed. */
function isAdvisory(advisory, name) {
  if (!isObject(advisory) || advisory.name !== name ||
      advisory.dependency !== name || !Number.isSafeInteger(advisory.source) ||
      advisory.source <= 0 || !severities.includes(advisory.severity) ||
      typeof advisory.range !== "string" || advisory.range.trim() === "" ||
      typeof advisory.url !== "string") return false;
  try {
    const url = new URL(advisory.url);
    return url.protocol === "https:" && url.hostname !== "" &&
      url.username === "" && url.password === "";
  } catch {
    return false;
  }
}

/** Reject missing, malformed, dangling, or internally inconsistent evidence. */
function validatedFindings(report) {
  if (!isObject(report) || report.auditReportVersion !== 2 ||
      Object.hasOwn(report, "error") || !isObject(report.vulnerabilities)) {
    throw new Error("npm audit did not produce a valid dependency report.");
  }
  const findings = report.vulnerabilities;
  for (const [name, finding] of Object.entries(findings)) {
    if (!isPackageName(name) || !isObject(finding) || finding.name !== name ||
        !severities.includes(finding.severity) ||
        !Array.isArray(finding.via) || finding.via.length === 0 ||
        !Array.isArray(finding.nodes) || finding.nodes.length === 0 ||
        new Set(finding.nodes).size !== finding.nodes.length ||
        finding.nodes.some((path) => !isDependencyPath(path, name)) ||
        finding.via.some((cause) => typeof cause === "string"
          ? !isPackageName(cause) || !Object.hasOwn(findings, cause)
          : !isAdvisory(cause, name) ||
            severities.indexOf(cause.severity) > severities.indexOf(finding.severity))) {
      throw new Error("npm audit contains a malformed dependency finding.");
    }
  }
  if (report.metadata !== undefined) {
    const counts = report.metadata?.vulnerabilities;
    if (!isObject(report.metadata) || !isObject(counts) ||
        [...severities, "total"].some((severity) =>
          !Number.isSafeInteger(counts[severity]) || counts[severity] < 0) ||
        counts.total !== Object.keys(findings).length ||
        severities.some((severity) => counts[severity] !==
          Object.values(findings).filter((finding) => finding.severity === severity).length)) {
      throw new Error("npm audit contains inconsistent vulnerability totals.");
    }
  }
  return findings;
}

/** Propagate evidence backwards to every finding that includes that cause. */
function includeDependents(names, findings) {
  let changed = true;
  while (changed) {
    changed = false;
    for (const [name, finding] of Object.entries(findings)) {
      if (!names.has(name) && finding.via.some((cause) =>
        typeof cause === "string" && names.has(cause))) {
        names.add(name);
        changed = true;
      }
    }
  }
}

/**
 * Return high/critical findings not wholly covered by the two scoped exceptions.
 * npm's peer-derived via graph contains cycles. First require an approved leaf
 * to ground every reachable record, then propagate any unreviewed evidence to
 * all dependents. A cycle is never evidence of its own acceptability.
 * @param {unknown} report Untrusted npm audit JSON.
 * @param {unknown} lock The exact audited package-lock.json.
 * @returns {object[]} Release-blocking dependency records.
 */
export function unresolvedReleaseFindings(report, lock) {
  const findings = validatedFindings(report);
  validateReleaseLock(lock);
  const grounded = new Set();
  const blocked = new Set();
  for (const [name, finding] of Object.entries(findings)) {
    if (!isReviewedReleaseFinding(finding, lock) || finding.severity === "critical") {
      blocked.add(name);
    }
    for (const cause of finding.via) {
      if (typeof cause === "string") continue;
      if (isReviewedReleaseAdvisory(finding, cause)) grounded.add(name);
      else blocked.add(name);
    }
  }
  includeDependents(grounded, findings);
  for (const name of Object.keys(findings)) {
    if (!grounded.has(name)) blocked.add(name);
  }
  includeDependents(blocked, findings);
  return Object.entries(findings)
    .filter(([name, finding]) => blocked.has(name) &&
      ["high", "critical"].includes(finding.severity))
    .map(([, finding]) => finding);
}
