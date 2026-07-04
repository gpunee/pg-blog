/**
 * Client-side search for PG Blog (see docs/plans/sections-tags-search.md §3.3, §3a).
 *
 * SECURITY: post content and the query string are untrusted input. All result
 * text is rendered via textContent / createElement / createTextNode — never by
 * assigning raw HTML — and the query is never eval'd or written into the DOM
 * as markup.
 */
(function () {
  "use strict";

  var MAX_RESULTS = 20;

  var app = document.getElementById("search-app");
  var input = document.getElementById("search-input");
  var resultsEl = document.getElementById("search-results");

  if (!input || !resultsEl) {
    return;
  }

  var indexUrl = (app && app.getAttribute("data-index")) || "/index.json";
  var fuse = null;

  function clearResults() {
    while (resultsEl.firstChild) {
      resultsEl.removeChild(resultsEl.firstChild);
    }
  }

  function renderNoResults(query) {
    clearResults();
    var li = document.createElement("li");
    li.textContent = "No results for “" + query + "”";
    resultsEl.appendChild(li);
  }

  function renderResults(matches) {
    clearResults();
    matches.slice(0, MAX_RESULTS).forEach(function (match) {
      var item = match.item;
      var li = document.createElement("li");

      var a = document.createElement("a");
      a.href = item.url;
      a.textContent = item.title;
      li.appendChild(a);

      var p = document.createElement("p");
      p.textContent = item.summary;
      li.appendChild(p);

      resultsEl.appendChild(li);
    });
  }

  function runSearch(rawQuery) {
    var query = (rawQuery || "").trim();

    if (!query) {
      clearResults();
      return;
    }

    if (!fuse) {
      // Index hasn't loaded yet (or failed to load); nothing to search.
      return;
    }

    var matches = fuse.search(query);

    if (matches.length === 0) {
      renderNoResults(query);
      return;
    }

    renderResults(matches);
  }

  function init(posts) {
    fuse = new Fuse(posts, {
      keys: [
        { name: "title", weight: 0.5 },
        { name: "tags", weight: 0.3 },
        { name: "categories", weight: 0.2 },
        { name: "summary", weight: 0.2 },
        { name: "content", weight: 0.1 },
      ],
      includeScore: true,
      threshold: 0.4,
      ignoreLocation: true,
    });

    var params = new URLSearchParams(window.location.search);
    var initialQuery = params.get("q") || "";
    if (initialQuery) {
      input.value = initialQuery;
    }
    runSearch(input.value);
  }

  input.addEventListener("input", function () {
    runSearch(input.value);
  });

  fetch(indexUrl)
    .then(function (response) {
      return response.json();
    })
    .then(init)
    .catch(function (err) {
      // Degrade gracefully: search stays inert, no crash, no leaked internals.
      window.console && console.error && console.error("Search index failed to load", err);
    });
})();
