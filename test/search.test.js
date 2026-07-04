/**
 * Automated acceptance test for client-side search (increment 02, see
 * docs/plans/sections-tags-search.md §3.3 / §4.1).
 *
 * Runs against the built `public/index.json` using the same vendored Fuse.js
 * build the browser uses (no npm install required — Fuse ships UMD/CommonJS).
 *
 * Usage: `hugo --gc --minify && node test/search.test.js`
 * Exit code 0 on pass, non-zero (with a message) on any failure.
 */

"use strict";

const fs = require("fs");
const path = require("path");

const Fuse = require("../assets/js/fuse.min.js");

const INDEX_PATH = path.join(__dirname, "..", "public", "index.json");

function loadIndex() {
  if (!fs.existsSync(INDEX_PATH)) {
    throw new Error(
      `Missing ${INDEX_PATH} — run "hugo --gc --minify" before this test.`
    );
  }
  const raw = fs.readFileSync(INDEX_PATH, "utf8");
  return JSON.parse(raw);
}

function urlsFor(matches) {
  return matches.map((m) => m.item.url);
}

function includesUrlContaining(urls, needle) {
  return urls.some((u) => u.includes(needle));
}

function main() {
  const posts = loadIndex();

  const fuse = new Fuse(posts, {
    keys: ["title", "tags", "categories", "content"],
    includeScore: true,
    threshold: 0.4,
    ignoreLocation: true,
  });

  let failures = 0;

  function assertCase(label, query, expectedUrlFragments) {
    const matches = fuse.search(query);
    const urls = urlsFor(matches);
    let ok = true;

    expectedUrlFragments.forEach((fragment) => {
      if (!includesUrlContaining(urls, fragment)) {
        ok = false;
      }
    });

    if (ok) {
      console.log(`PASS  ${label} — query "${query}" matched: ${urls.join(", ") || "(none)"}`);
    } else {
      failures += 1;
      console.log(
        `FAIL  ${label} — query "${query}" expected URLs containing [${expectedUrlFragments.join(
          ", "
        )}] but got: ${urls.join(", ") || "(none)"}`
      );
    }
  }

  function assertNoResults(label, query) {
    const matches = fuse.search(query);
    const urls = urlsFor(matches);

    if (matches.length === 0) {
      console.log(`PASS  ${label} — query "${query}" returned zero results`);
    } else {
      failures += 1;
      console.log(
        `FAIL  ${label} — query "${query}" expected zero results but got: ${urls.join(", ")}`
      );
    }
  }

  assertCase("docker (both languages)", "docker", ["/posts/6-", "/posts/7-"]);
  assertCase("sqlalchemy (python ORM post)", "sqlalchemy", ["/posts/9-"]);
  assertCase("hibernate (java ORM post)", "hibernate", ["/posts/8-"]);
  assertNoResults("nonsense query", "zzznotarealword");

  console.log("");
  if (failures > 0) {
    console.error(`${failures} assertion(s) failed.`);
    process.exit(1);
  }

  console.log("All search assertions passed.");
  process.exit(0);
}

main();
