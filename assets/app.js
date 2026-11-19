/* Paper index front end: the front page's list of recently added papers, the search,
 * authors and journals pages, and the Abstract / Save / Mark read buttons of every paper
 * card (the archive's server-rendered cards get them too). Vanilla JS, no dependencies.
 *
 * Data: assets/data/feed.json (papers added in the last 30 days, small) for the front page;
 * the per-year shards in assets/data/ for search, authors and journals, loaded
 * progressively: the newest years first, older ones streamed in after.
 *
 * Everything a visitor marks (read, saved, followed journals, the last visit) is kept in
 * localStorage under "gp.idx.<index key>." because every tool on guruprakashmp.github.io
 * shares one origin. Every read and write is guarded: without storage the marks last for
 * the page only. Nothing is sent anywhere, except the Abstract button's request for one
 * abstract (OpenAlex, then Crossref), made by the browser when it is clicked. */
(function () {
  "use strict";

  var body = document.body;
  var app = document.getElementById("app");
  var KEY = body.getAttribute("data-index-key") || "index";
  var SITE = body.getAttribute("data-site-title") || document.title;
  var PAGE = app ? app.getAttribute("data-page") : (body.getAttribute("data-page") || "");
  var ROOT = app ? (app.getAttribute("data-root") || "") : (body.getAttribute("data-root") || "");
  var PAGE_SIZE = 100;      // search results per "Show more"
  var FEED_PAGE = 50;       // front page cards per "Show more"
  var INITIAL_YEARS = 3;    // shards loaded before the first render
  var AUTHORS_SHOWN = 12;
  var READ_MAX = 20000;     // read marks kept (oldest dropped first)
  var SAVED_MAX = 2000;
  var VISIT_GAP = 30 * 60 * 1000;   // a page load after 30 min without one starts a new visit

  // ---------------------------------------------------------------- utils
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function params() { return new URLSearchParams(location.search); }
  function fmt(n) { return Number(n).toLocaleString("en-US"); }
  function plural(n, one, many) { return fmt(n) + " " + (n === 1 ? one : (many || one + "s")); }
  /* Mirror of ddc.models.normalize_author. Stored names are already
   * canonical, so this only cleans the incoming ?a= value: it keeps links
   * and bookmarks made before the migration (which carry a U+2010 hyphen or
   * an honorific) resolving to the right author page. */
  function normalizeAuthor(name) {
    if (!name) return "";
    var n = String(name);
    if (n.normalize) n = n.normalize("NFC");
    n = n.replace(/\u00a0/g, " ").replace(/[\u200b-\u200d\ufeff]/g, "");
    n = n.replace(/[\u2010-\u2015\u2212\ufe58\ufe63\uff0d]/g, "-");
    n = n.replace(/\s+/g, " ").trim();
    var prev = null;
    while (prev !== n) {
      prev = n;
      n = n.replace(/^(?:prof(?:essor)?|dr|doctor|mr|mrs|ms|miss|sir|dame|rev)\.?\s+/i, "").trim();
      n = n.replace(/^[.,;\s]+/, "").trim();
    }
    n = n.replace(/[,;\s]+$/, "").trim();   // trailing "." kept: it may be an initial
    return n || String(name).replace(/\s+/g, " ").trim();
  }
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December"];
  function prettyDate(iso) {
    if (!iso) return "";
    var p = String(iso).split("-");
    if (p.length >= 3) return (+p[2]) + " " + MONTHS[+p[1] - 1] + " " + p[0];
    if (p.length === 2) return MONTHS[+p[1] - 1] + " " + p[0];
    return iso;
  }
  function scoreClass(s) { return s >= 90 ? "score-high" : s >= 70 ? "score-mid" : "score-low"; }
  function byDateDesc(a, b) { return (b.published || "").localeCompare(a.published || ""); }
  function byAddedDesc(a, b) {
    return (b.added || "").localeCompare(a.added || "") || byDateDesc(a, b) ||
      (b.id < a.id ? -1 : b.id > a.id ? 1 : 0);
  }
  function toSet(list) { var s = {}; for (var i = 0; i < list.length; i++) s[list[i]] = 1; return s; }
  function isStr(v) { return typeof v === "string" && v.length > 0; }

  /* Dates in the data are calendar days (YYYY-MM-DD), so a card says "today", "3 days
   * ago" and so on, counted against the visitor's own calendar; beyond a year (or in the
   * future, e.g. an issue date) it shows the date itself. */
  function localToday() { var d = new Date(); return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()); }
  function relDay(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
    if (!m) return "";
    var n = Math.round((localToday() - Date.UTC(+m[1], +m[2] - 1, +m[3])) / 864e5);
    if (n < 0 || n > 365) return "";
    if (n === 0) return "today";
    if (n === 1) return "yesterday";
    if (n < 14) return n + " days ago";
    if (n < 60) return Math.round(n / 7) + " weeks ago";
    var mo = Math.round(n / 30.44);
    return mo + (mo === 1 ? " month ago" : " months ago");
  }
  /* manifest.generated is "YYYY-MM-DD HH:MM UTC": a real time, so hours and minutes. */
  function parseGenerated(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(s || "");
    return m ? Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]) : NaN;
  }
  function agoTime(ms) {
    var s = (Date.now() - ms) / 1000;
    if (!(s >= -300)) return "";
    if (s < 90) return "just now";
    var min = s / 60;
    if (min < 60) return Math.round(min) + " min ago";
    var h = min / 60;
    if (h < 36) return Math.round(h) + " h ago";
    var d = Math.round(h / 24);
    return d + (d === 1 ? " day ago" : " days ago");
  }
  function visitWhen(ms) {
    var d = new Date(ms);
    var iso = d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2);
    return relDay(iso) || prettyDate(iso);
  }

  // ---------------------------------------------------------------- local storage
  var NS = "gp.idx." + KEY + ".";
  var storageOK = (function () {
    try {
      var k = NS + "probe";
      window.localStorage.setItem(k, "1");
      window.localStorage.removeItem(k);
      return true;
    } catch (e) { return false; }
  })();
  var mem = {};   // stand-in when the browser keeps no storage for the site
  function sget(name, fallback) {
    if (storageOK) {
      try {
        var v = window.localStorage.getItem(NS + name);
        return v == null ? fallback : JSON.parse(v);
      } catch (e) { return fallback; }
    }
    return Object.prototype.hasOwnProperty.call(mem, name) ? mem[name] : fallback;
  }
  function sset(name, value) {
    mem[name] = value;
    if (!storageOK) return false;
    try { window.localStorage.setItem(NS + name, JSON.stringify(value)); return true; }
    catch (e) { return false; }
  }

  // Every change re-reads storage first, so two open tabs never undo each other's marks.
  function readList() { var a = sget("read", []); return Array.isArray(a) ? a.filter(isStr) : []; }
  function savedList() {
    var a = sget("saved", []);
    return Array.isArray(a) ? a.filter(function (p) {
      return p && isStr(p.id) && typeof p.title === "string";
    }) : [];
  }
  function followList() { var a = sget("follow", []); return Array.isArray(a) ? a.filter(isStr) : []; }
  var readSet = toSet(readList());
  var savedSet = toSet(savedList().map(function (p) { return p.id; }));
  function isRead(id) { return readSet[id] === 1; }
  function isSaved(id) { return savedSet[id] === 1; }
  function setRead(ids, on) {
    var list = readList(), set = toSet(list);
    ids.forEach(function (id) {
      if (on && set[id] !== 1) { list.push(id); set[id] = 1; }
      else if (!on && set[id] === 1) { delete set[id]; }
    });
    if (!on) list = list.filter(function (id) { return set[id] === 1; });
    if (list.length > READ_MAX) list = list.slice(list.length - READ_MAX);
    sset("read", list);
    readSet = toSet(list);
  }
  function metaOf(p) {
    var m = { id: p.id, title: p.title, journal: p.journal || "", published: p.published || "",
              doi: p.doi || "", url: p.url || "", savedAt: Date.now() };
    if (Array.isArray(p.authors)) {
      m.authors = p.authors.slice(0, AUTHORS_SHOWN);
      var more = (p.na || 0) + Math.max(0, p.authors.length - AUTHORS_SHOWN);
      if (more) m.na = more;
    } else if (p.authorsText) m.authorsText = p.authorsText;
    if (p.added) m.added = p.added;
    if (typeof p.score === "number") m.score = p.score;
    if (p.source) m.source = p.source;
    if (Array.isArray(p.categories)) m.categories = p.categories.slice(0, 5);
    return m;
  }
  function setSaved(p, on) {
    var list = savedList().filter(function (s) { return s.id !== p.id; });
    if (on) list.unshift(metaOf(p));
    if (list.length > SAVED_MAX) list = list.slice(0, SAVED_MAX);
    sset("saved", list);
    savedSet = toSet(list.map(function (s) { return s.id; }));
  }
  function reloadState() {
    readSet = toSet(readList());
    savedSet = toSet(savedList().map(function (p) { return p.id; }));
  }

  // ---------------------------------------------------------------- paper cards
  var known = {};   // id -> paper, for every card rendered from data

  function paperLink(p) { return p.doi ? "https://doi.org/" + p.doi : (p.url || ""); }
  function authorsHtml(p) {
    if (!Array.isArray(p.authors)) return esc(p.authorsText || "");
    var s = p.authors.slice(0, AUTHORS_SHOWN).map(function (a) {
      return '<a href="' + ROOT + "authors.html?a=" + encodeURIComponent(a) + '">' + esc(a) + "</a>";
    }).join(", ");
    var more = (p.na || 0) + Math.max(0, p.authors.length - AUTHORS_SHOWN);
    if (more) s += " and " + more + " more";
    return s;
  }
  function timeTitle(pub, added) {
    var t = pub ? "Published " + prettyDate(pub) : "";
    if (added) t += (t ? ", " : "") + "added to the index " + prettyDate(added);
    return t;
  }
  function timeHtml(p) {
    var pub = p.published || "";
    return '<time datetime="' + esc(pub) + '" title="' + esc(timeTitle(pub, p.added)) + '">' +
      esc(relDay(pub) || prettyDate(pub)) + "</time>";
  }
  function actionButtons(id) {
    var r = isRead(id), s = isSaved(id);
    return '<button type="button" class="act" data-act="abstract" aria-expanded="false" title="Show the abstract (a)">Abstract</button>' +
      '<button type="button" class="act act-save" data-act="save" aria-pressed="' + s + '" title="' +
      (s ? "Remove from saved (s)" : "Save this paper (s)") + '">' + (s ? "Saved" : "Save") + "</button>" +
      '<button type="button" class="act act-read" data-act="read" aria-pressed="' + r + '" title="' +
      (r ? "Mark as unread (r)" : "Mark as read (r)") + '">' + (r ? "Read" : "Mark read") + "</button>";
  }
  function renderCard(p, opts) {
    known[p.id] = p;
    var link = paperLink(p);
    var title = link ? '<a href="' + esc(link) + '" target="_blank" rel="noopener">' + esc(p.title) + "</a>"
                     : esc(p.title);
    var chips = "";
    (p.categories || []).slice(0, 5).forEach(function (c) {
      chips += '<a class="chip chip-cat" href="' + ROOT + "search.html?category=" +
        encodeURIComponent(c) + '">' + esc(c) + "</a>";
    });
    (p.tags || []).slice(0, 6).forEach(function (t) {
      if ((p.categories || []).indexOf(t) === -1)
        chips += '<a class="chip" href="' + ROOT + "search.html?q=" +
          encodeURIComponent(t) + '">' + esc(t) + "</a>";
    });
    var journal = p.journal ? '<a class="badge-journal" href="' + ROOT + "journals.html?j=" +
      encodeURIComponent(p.journal) + '">' + esc(p.journal) + "</a>" : "";
    var isNew = opts && opts.isNew ? '<span class="badge-new">New</span>' : "";
    var source = p.source ? '<span class="meta-source">' + esc(p.source) + "</span>" : "";
    var score = typeof p.score === "number"
      ? '<span class="score ' + scoreClass(p.score) + '" title="Relevance score">' + p.score + "</span>" : "";
    return '<article class="card' + (isRead(p.id) ? " is-read" : "") + '" data-id="' + esc(p.id) +
      '" data-doi="' + esc(p.doi || "") + '" tabindex="-1">' +
      '<h3 class="card-title">' + title + "</h3>" +
      '<p class="card-authors">' + authorsHtml(p) + "</p>" +
      '<p class="card-meta">' + isNew + journal + timeHtml(p) + source + score + "</p>" +
      (chips ? '<p class="card-chips">' + chips + "</p>" : "") +
      '<div class="card-actions">' +
      (link ? '<a class="act act-primary" href="' + esc(link) + '" target="_blank" rel="noopener">Full text</a>' : "") +
      actionButtons(p.id) + "</div></article>";
  }
  /* A server-rendered card (archive pages) as a paper record, for Save. */
  function paperFromCard(card) {
    var id = card.getAttribute("data-id");
    if (known[id]) return known[id];
    var t = card.querySelector(".card-title"), a = card.querySelector(".card-title a");
    var j = card.querySelector(".badge-journal"), tm = card.querySelector("time");
    var au = card.querySelector(".card-authors"), sc = card.querySelector(".score");
    var src = card.querySelector(".meta-source");
    var p = {
      id: id, title: t ? t.textContent.trim() : "", authorsText: au ? au.textContent.trim() : "",
      journal: j ? j.textContent.trim() : "", published: tm ? tm.getAttribute("datetime") || "" : "",
      doi: card.getAttribute("data-doi") || "", url: a ? a.getAttribute("href") || "" : "",
      source: src ? src.textContent.trim() : "",
      categories: [].map.call(card.querySelectorAll(".chip-cat"), function (c) { return c.textContent.trim(); })
    };
    if (sc && /^\d+$/.test(sc.textContent.trim())) p.score = +sc.textContent.trim();
    known[id] = p;
    return p;
  }
  function syncCard(card) {
    var id = card.getAttribute("data-id"), r = isRead(id), s = isSaved(id);
    card.classList.toggle("is-read", r);
    var sb = card.querySelector('[data-act="save"]'), rb = card.querySelector('[data-act="read"]');
    if (sb) {
      sb.setAttribute("aria-pressed", String(s)); sb.textContent = s ? "Saved" : "Save";
      sb.title = s ? "Remove from saved (s)" : "Save this paper (s)";
    }
    if (rb) {
      rb.setAttribute("aria-pressed", String(r)); rb.textContent = r ? "Read" : "Mark read";
      rb.title = r ? "Mark as unread (r)" : "Mark as read (r)";
    }
  }
  function syncAllCards() { [].forEach.call(document.querySelectorAll(".card[data-id]"), syncCard); }

  // ---------------------------------------------------------------- abstracts
  /* Asked for on click only, by DOI: OpenAlex first (it has abstracts for more papers),
   * Crossref when OpenAlex has none. Both send Access-Control-Allow-Origin: *. The result
   * lives in this page's memory only. */
  var absCache = {};
  function getJSON(url) {
    return fetch(url).then(function (r) {
      if (r.status === 404) return null;
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }
  function doiPath(doi) { return String(doi).trim().split("/").map(encodeURIComponent).join("/"); }
  function squash(s) { return String(s || "").replace(/\s+/g, " ").trim(); }
  function cleanAbstract(t) {
    // Page furniture and labels some publisher pages put before the abstract itself.
    t = squash(t).replace(/^(?:High Resolution Image\s+)?Download MS PowerPoint Slide\s+/i, "");
    t = t.replace(/^(?:Abstract|Summary|Graphical abstract)\s*[:.]?\s+/i, "");
    return t.trim();
  }
  function fromInverted(inv) {
    if (!inv || typeof inv !== "object") return "";
    var words = [];
    Object.keys(inv).forEach(function (w) {
      var pos = inv[w];
      if (Array.isArray(pos)) pos.forEach(function (i) {
        if (typeof i === "number" && i >= 0 && i < 50000) words[i] = w;
      });
    });
    return cleanAbstract(words.filter(function (w) { return w != null; }).join(" "));
  }
  function fromJats(xml) {
    var doc;
    try { doc = new DOMParser().parseFromString("<div>" + xml + "</div>", "text/html"); }
    catch (e) { return []; }
    var out = [];
    (function walk(node) {
      for (var c = node.firstElementChild; c; c = c.nextElementSibling) {
        var n = c.tagName.toLowerCase().replace(/^jats:/, "");
        if (n === "title") {
          var tt = squash(c.textContent);
          if (tt && !/^(abstract|summary|graphical abstract)[:.]?$/i.test(tt)) out.push({ title: tt });
        } else if (n === "p") {
          var tp = squash(c.textContent);
          if (tp) out.push({ text: tp });
        } else walk(c);
      }
    })(doc.body);
    if (!out.length) {
      var all = cleanAbstract(doc.body.textContent);
      return all ? [{ text: all }] : [];
    }
    var merged = [];
    out.forEach(function (x) {
      var last = merged[merged.length - 1];
      if (x.text && last && last.title && !last.text) last.text = x.text;
      else merged.push(x);
    });
    if (merged[0] && merged[0].text && !merged[0].title) merged[0].text = cleanAbstract(merged[0].text);
    return merged.filter(function (x) { return x.text || x.title; });
  }
  function getAbstract(doi) {
    if (!doi) return Promise.resolve({ none: true });
    var k = String(doi).toLowerCase();
    if (absCache[k]) return absCache[k];
    var errors = 0, path = doiPath(doi);
    var pr = getJSON("https://api.openalex.org/works/doi:" + path + "?select=id,abstract_inverted_index")
      .then(function (j) {
        var t = j && fromInverted(j.abstract_inverted_index);
        return t ? { paras: [{ text: t }], source: "OpenAlex", href: (j.id && /^https:\/\/openalex\.org\//.test(j.id)) ? j.id : "https://openalex.org/" } : null;
      }, function () { errors++; return null; })
      .then(function (r) {
        if (r) return r;
        return getJSON("https://api.crossref.org/works/" + path).then(function (j) {
          var a = j && j.message && j.message.abstract;
          var paras = typeof a === "string" ? fromJats(a) : [];
          return paras.length ? { paras: paras, source: "Crossref", href: "https://api.crossref.org/works/" + path } : null;
        }, function () { errors++; return null; });
      })
      .then(function (r) {
        if (r) return r;
        if (errors) { delete absCache[k]; return { error: true }; }
        return { none: true };
      });
    absCache[k] = pr;
    return pr;
  }
  var absSeq = 0;
  function toggleAbstract(card, p, retry) {
    var btn = card.querySelector('[data-act="abstract"]');
    if (!btn) return;
    var box = card.querySelector(".card-abstract");
    if (!box) {
      box = document.createElement("div");
      box.className = "card-abstract";
      box.id = "abs-" + (++absSeq);
      box.setAttribute("aria-live", "polite");
      card.appendChild(box);
      btn.setAttribute("aria-controls", box.id);
    }
    if (!retry && btn.getAttribute("aria-expanded") === "true") {
      box.hidden = true; btn.setAttribute("aria-expanded", "false"); btn.textContent = "Abstract";
      return;
    }
    box.hidden = false; btn.setAttribute("aria-expanded", "true"); btn.textContent = "Hide abstract";
    if (box.getAttribute("data-state") === "done") return;
    box.innerHTML = '<p class="abs-note">Loading the abstract…</p>';
    getAbstract(p.doi).then(function (r) {
      box.innerHTML = "";
      if (r.paras) {
        r.paras.forEach(function (x) {
          var el = document.createElement("p");
          if (x.title) { var b = document.createElement("strong"); b.textContent = x.title + " "; el.appendChild(b); }
          if (x.text) el.appendChild(document.createTextNode(x.text));
          box.appendChild(el);
        });
        var src = document.createElement("p");
        src.className = "abs-src";
        src.appendChild(document.createTextNode("Abstract from "));
        var a = document.createElement("a");
        a.href = r.href; a.target = "_blank"; a.rel = "noopener"; a.textContent = r.source;
        src.appendChild(a);
        box.appendChild(src);
        box.setAttribute("data-state", "done");
      } else if (r.none) {
        box.innerHTML = '<p class="abs-note">No abstract available</p>';
        box.setAttribute("data-state", "done");
      } else {
        box.innerHTML = '<p class="abs-note">Could not reach OpenAlex or Crossref for the abstract. ' +
          '<button type="button" class="linkbtn" data-act="abstract-retry">Try again</button></p>';
        box.removeAttribute("data-state");
      }
    });
  }

  // ---------------------------------------------------------------- actions & keys
  var onChange = null;   // the front page refreshes its counts after a mark
  function act(card, what) {
    var id = card.getAttribute("data-id");
    var p = known[id] || paperFromCard(card);
    if (what === "save") { setSaved(p, !isSaved(id)); syncCard(card); }
    else if (what === "read") { setRead([id], !isRead(id)); syncCard(card); }
    else if (what === "abstract") toggleAbstract(card, p, false);
    else if (what === "abstract-retry") toggleAbstract(card, p, true);
    if ((what === "save" || what === "read") && onChange) onChange();
  }
  document.addEventListener("click", function (e) {
    var b = e.target && e.target.closest ? e.target.closest("[data-act]") : null;
    var card = e.target && e.target.closest ? e.target.closest(".card[data-id]") : null;
    if (card) setCurrent(card, false);
    if (b && card) { e.preventDefault(); act(card, b.getAttribute("data-act")); }
  });

  var current = null;
  function cards() { return [].slice.call(document.querySelectorAll("#main .card[data-id]")); }
  function setCurrent(card, scroll) {
    if (current && current !== card) current.classList.remove("is-current");
    current = card;
    if (!card) return;
    card.classList.add("is-current");
    if (scroll) {
      if (!card.hasAttribute("tabindex")) card.setAttribute("tabindex", "-1");
      try { card.focus({ preventScroll: true }); } catch (e) { card.focus(); }
      card.scrollIntoView({ block: "nearest" });
    }
  }
  document.addEventListener("keydown", function (e) {
    if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
    var t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    var k = e.key;
    if (["j", "k", "s", "r", "a", "o"].indexOf(k) === -1) return;
    var list = cards();
    if (!list.length) return;
    if (current && !current.isConnected) current = null;
    var i = current ? list.indexOf(current) : -1;
    e.preventDefault();
    if (k === "j" || k === "k") {
      if (k === "j" && i === list.length - 1) {
        var more = document.getElementById("more-btn");
        if (more) { more.click(); list = cards(); }
      }
      var next = i === -1 ? 0 : (k === "j" ? Math.min(i + 1, list.length - 1) : Math.max(i - 1, 0));
      setCurrent(list[next], true);
      return;
    }
    if (i === -1) return;
    if (k === "o") {
      var a = current.querySelector(".act-primary");
      if (a) window.open(a.href, "_blank", "noopener");
      return;
    }
    act(current, { s: "save", r: "read", a: "abstract" }[k]);
  });
  window.addEventListener("storage", function (e) {
    if (e.key && e.key.indexOf(NS) === 0) { reloadState(); syncAllCards(); if (onChange) onChange(); }
  });

  function keysHint() {
    return '<p class="keys"><kbd>j</kbd> / <kbd>k</kbd> next and previous paper · <kbd>s</kbd> save · ' +
      '<kbd>r</kbd> mark read · <kbd>a</kbd> abstract · <kbd>o</kbd> open the full text</p>';
  }

  // ---------------------------------------------------------------- data
  function fetchJSON(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(url.split("/").pop() + " " + r.status);
      return r.json();
    });
  }
  function fetchShard(file) {
    return fetch(ROOT + "assets/data/" + file).then(function (r) { return r.ok ? r.json() : []; });
  }
  /* Calls onData(papers, complete) once with the newest years, then again
   * with the full archive. */
  function loadProgressive(onData) {
    return fetchJSON(ROOT + "assets/data/manifest.json").then(function (manifest) {
      var years = (manifest.years || []).slice().sort(function (a, b) { return b.year - a.year; });
      var first = years.slice(0, INITIAL_YEARS), rest = years.slice(INITIAL_YEARS);
      return Promise.all(first.map(function (y) { return fetchShard(y.file); })).then(function (shards) {
        var recent = [].concat.apply([], shards).sort(byDateDesc);
        onData(recent, rest.length === 0);
        if (!rest.length) return;
        return Promise.all(rest.map(function (y) { return fetchShard(y.file); })).then(function (older) {
          onData(recent.concat([].concat.apply([], older)).sort(byDateDesc), true);
        });
      });
    });
  }

  // ---------------------------------------------------------------- front page
  function snapshot(papers) {
    var day = "";
    papers.forEach(function (p) { if (p.added && p.added > day) day = p.added; });
    var ids = papers.filter(function (p) { return p.added === day; }).map(function (p) { return p.id; });
    return { at: Date.now(), day: day, ids: ids.slice(0, 5000) };
  }
  /* The previous visit's snapshot (newest "added" day and the ids added that day), or null
   * on a first visit in this browser. A visit ends after VISIT_GAP without a page load. */
  function trackVisit(papers) {
    var v = sget("visit", null), now = Date.now(), base = null;
    var valid = function (s) { return s && typeof s.day === "string" && Array.isArray(s.ids) && typeof s.at === "number"; };
    if (v && typeof v.at === "number" && valid(v.cur)) base = now - v.at > VISIT_GAP ? v.cur : (valid(v.base) ? v.base : null);
    sset("visit", { at: now, base: base, cur: snapshot(papers) });
    return base;
  }

  function feedPage() {
    var S = { papers: [], base: null, newSet: {}, baseIds: {}, view: "all", journal: "", q: "",
              shown: FEED_PAGE, showAllJ: false, fallback: false, undo: null, oldest: "", generated: "" };

    function isNew(p) {
      if (!S.base || !p.added) return false;
      return p.added > S.base.day || (p.added === S.base.day && S.baseIds[p.id] !== 1);
    }
    function follows() { return followList(); }

    function build() {
      app.innerHTML =
        '<div class="feed">' +
        '<div class="feed-status" id="feed-status" aria-live="polite"></div>' +
        '<div class="feed-tools">' +
        '<input type="search" id="feed-q" placeholder="Filter by title or author" aria-label="Filter by title or author" autocomplete="off">' +
        '<div class="fchips" id="fchips" role="group" aria-label="Show"></div>' +
        "</div>" +
        '<div class="jchips" id="jchips" role="group" aria-label="Journals"></div>' +
        '<div class="follow-panel" id="follow-panel" hidden></div>' +
        '<div class="feed-bar"><span id="feed-count"></span><span class="feed-bar-r">' +
        '<span id="undo-wrap"></span><button type="button" class="btn btn-small" id="mark-all" hidden></button></span></div>' +
        '<div id="results" class="results"></div><p class="more" id="more-wrap"></p>' +
        keysHint() + "</div>";
      var timer;
      document.getElementById("feed-q").addEventListener("input", function (e) {
        clearTimeout(timer);
        timer = setTimeout(function () { S.q = e.target.value; S.shown = FEED_PAGE; render(); }, 120);
      });
      app.addEventListener("click", function (e) {
        var t = e.target.closest ? e.target.closest("button") : null;
        if (!t || !app.contains(t)) return;
        if (t.hasAttribute("data-view")) { setView(t.getAttribute("data-view")); }
        else if (t.hasAttribute("data-journal")) {
          var j = t.getAttribute("data-journal");
          S.journal = S.journal === j ? "" : j; S.shown = FEED_PAGE; render();
        }
        else if (t.id === "j-more") { S.showAllJ = !S.showAllJ; renderJournals(); }
        else if (t.id === "follow-toggle") { toggleFollowPanel(); }
        else if (t.id === "follow-done") { toggleFollowPanel(false); }
        else if (t.id === "follow-clear") { sset("follow", []); renderFollowPanel(); if (S.view === "following") S.view = "all"; render(); }
        else if (t.id === "show-new") { setView("new"); }
        else if (t.id === "mark-all") { markAll(); }
        else if (t.id === "undo-btn") { undoMarkAll(); }
        else if (t.id === "more-btn") { S.shown += FEED_PAGE; renderList(); }
      });
      app.addEventListener("change", function (e) {
        var t = e.target;
        if (!t || !t.hasAttribute || !t.hasAttribute("data-follow")) return;
        var had = follows().length, list = follows().filter(function (j) { return j !== t.value; });
        if (t.checked) list.push(t.value);
        sset("follow", list);
        if (!had && list.length && S.view === "all") S.view = "following";
        if (!list.length && S.view === "following") S.view = "all";
        sset("view", S.view);
        render();
      });
    }

    function setView(v) {
      S.view = S.view === v && v !== "all" ? "all" : v;
      sset("view", S.view);
      S.shown = FEED_PAGE;
      render();
    }

    function inView(p, view) {
      if (view === "unread") return !isRead(p.id);
      if (view === "new") return S.newSet[p.id] === 1;
      if (view === "following") { var f = follows(); return f.indexOf(p.journal) !== -1; }
      return true;
    }
    function textMatch(p, terms) {
      if (!terms.length) return true;
      var hay = (p.title + " " + (Array.isArray(p.authors) ? p.authors.join(" ") : (p.authorsText || ""))).toLowerCase();
      for (var i = 0; i < terms.length; i++) if (hay.indexOf(terms[i]) === -1) return false;
      return true;
    }
    function terms() { var q = S.q.toLowerCase().trim(); return q ? q.split(/\s+/) : []; }
    function source(view) { return view === "saved" ? savedList() : S.papers; }
    // the list for a view, text filter and journal applied
    function listFor(view, withJournal) {
      var tq = terms();
      return source(view).filter(function (p) {
        return (view === "saved" || inView(p, view)) && textMatch(p, tq) &&
          (!withJournal || !S.journal || p.journal === S.journal);
      });
    }

    function validView() {
      var f = follows();
      if (S.view === "new" && !S.base) S.view = "all";
      if (S.view === "following" && !f.length) S.view = "all";
      if (["all", "unread", "new", "saved", "following"].indexOf(S.view) === -1) S.view = "all";
    }

    function renderChips() {
      var f = follows();
      var views = [["all", "All"], ["unread", "Unread"]];
      if (S.base) views.push(["new", "New"]);
      views.push(["saved", "Saved"]);
      if (f.length) views.push(["following", "Following"]);
      document.getElementById("fchips").innerHTML = views.map(function (v) {
        var n = listFor(v[0], true).length;
        return '<button type="button" class="fchip" data-view="' + v[0] + '" aria-pressed="' + (S.view === v[0]) +
          '">' + v[1] + ' <span class="n">' + fmt(n) + "</span></button>";
      }).join("");
    }

    function renderJournals() {
      var counts = {}, f = follows();
      listFor(S.view, false).forEach(function (p) { if (p.journal) counts[p.journal] = (counts[p.journal] || 0) + 1; });
      var names = Object.keys(counts).sort(function (a, b) {
        return (f.indexOf(b) !== -1) - (f.indexOf(a) !== -1) || counts[b] - counts[a] || a.localeCompare(b);
      });
      if (S.journal && !counts[S.journal]) { names.unshift(S.journal); counts[S.journal] = 0; }
      var narrow = window.matchMedia && window.matchMedia("(max-width: 600px)").matches;
      var TOP = narrow ? 5 : 10, shown = S.showAllJ ? names : names.slice(0, TOP);
      if (!S.showAllJ && S.journal && shown.indexOf(S.journal) === -1) shown.push(S.journal);
      var html = '<span class="jchips-label">Journals</span>' + shown.map(function (j) {
        return '<button type="button" class="jchip' + (f.indexOf(j) !== -1 ? " is-followed" : "") +
          '" data-journal="' + esc(j) + '" aria-pressed="' + (S.journal === j) + '"' +
          (f.indexOf(j) !== -1 ? ' title="A journal you follow"' : "") + ">" + esc(j) +
          ' <span class="n">' + fmt(counts[j]) + "</span></button>";
      }).join("");
      if (names.length > TOP)
        html += '<button type="button" class="linkbtn" id="j-more" aria-expanded="' + S.showAllJ + '">' +
          (S.showAllJ ? "Fewer journals" : "All " + fmt(names.length) + " journals") + "</button>";
      var panel = document.getElementById("follow-panel");
      html += '<button type="button" class="linkbtn" id="follow-toggle" aria-controls="follow-panel" aria-expanded="' +
        !panel.hidden + '">' + (f.length ? "Journals you follow (" + f.length + ")" : "Choose journals to follow") + "</button>";
      document.getElementById("jchips").innerHTML = html;
    }

    function toggleFollowPanel(force) {
      var panel = document.getElementById("follow-panel");
      var open = typeof force === "boolean" ? force : panel.hidden;
      panel.hidden = !open;
      if (open) { renderFollowPanel(); var i = document.getElementById("follow-q"); if (i) i.focus(); }
      renderJournals();
      if (!open) { var b = document.getElementById("follow-toggle"); if (b) b.focus(); }
    }
    function renderFollowPanel() {
      var panel = document.getElementById("follow-panel");
      if (panel.hidden) return;
      var f = follows(), counts = {};
      S.papers.forEach(function (p) { if (p.journal) counts[p.journal] = (counts[p.journal] || 0) + 1; });
      f.forEach(function (j) { if (!counts[j]) counts[j] = 0; });
      var names = Object.keys(counts).sort(function (a, b) { return a.localeCompare(b); });
      var prevQ = document.getElementById("follow-q");
      var q = prevQ ? prevQ.value : "";
      panel.innerHTML =
        '<p class="follow-intro">Follow journals to get a <strong>Following</strong> view with only their papers. ' +
        "The list has every journal with papers here; the number is how many.</p>" +
        '<input type="search" id="follow-q" placeholder="Find a journal" aria-label="Find a journal" autocomplete="off" value="' + esc(q) + '">' +
        '<ul class="follow-list" id="follow-list">' + names.map(function (j) {
          return '<li><label><input type="checkbox" data-follow value="' + esc(j) + '"' +
            (f.indexOf(j) !== -1 ? " checked" : "") + "> <span>" + esc(j) + '</span> <span class="n">' +
            fmt(counts[j]) + "</span></label></li>";
        }).join("") + "</ul>" +
        '<p class="follow-actions"><button type="button" class="btn btn-small" id="follow-done">Done</button>' +
        (f.length ? '<button type="button" class="linkbtn" id="follow-clear">Unfollow all</button>' : "") + "</p>";
      var input = document.getElementById("follow-q");
      function filter() {
        var n = input.value.toLowerCase().trim();
        [].forEach.call(panel.querySelectorAll("#follow-list li"), function (li) {
          li.hidden = n && li.textContent.toLowerCase().indexOf(n) === -1;
        });
      }
      input.addEventListener("input", filter);
      filter();
    }

    function renderStatus() {
      var el = document.getElementById("feed-status"), html = "";
      var newCount = S.papers.filter(function (p) { return S.newSet[p.id] === 1; }).length;
      if (S.fallback) {
        html = "The list of recent additions could not be loaded, so these are the newest papers by publication date.";
      } else if (!S.base) {
        html = "<strong>Welcome.</strong> These are the " + plural(S.papers.length, "paper") +
          " added to the index since " + esc(prettyDate(S.oldest)) + ", newest first. " +
          "Mark papers read as you go and save the ones to keep: this browser remembers both, " +
          "and next time this page shows what is new since this visit.";
      } else {
        var when = visitWhen(S.base.at);
        if (S.base.day && S.oldest && S.base.day < S.oldest) {
          html = "<strong>" + plural(newCount, "paper") + "</strong> added since " + esc(prettyDate(S.oldest)) +
            ". Your last visit (" + esc(when) + ") was before this list starts.";
        } else if (newCount) {
          html = "<strong>" + fmt(newCount) + " new</strong> since your last visit (" + esc(when) + "). " +
            (S.view !== "new" ? '<button type="button" class="linkbtn" id="show-new">Show only those</button>' : "");
        } else {
          html = "Nothing new since your last visit (" + esc(when) + "). The index is updated once a day.";
        }
      }
      if (!storageOK)
        html += ' <span class="warn">This browser is not keeping data for this site, so read and saved marks last only until you leave the page.</span>';
      el.innerHTML = html;
    }

    function renderList() {
      var list = listFor(S.view, true);
      if (S.view === "saved") list = list.slice();   // newest saved first (stored order)
      var unread = [], read = [];
      list.forEach(function (p) { (isRead(p.id) ? read : unread).push(p); });
      var ordered = unread.concat(read);
      var html = "", shown = Math.min(S.shown, ordered.length);
      for (var i = 0; i < shown; i++) {
        if (i === unread.length && read.length)
          html += '<div class="caught-up" role="separator"><span>You\'re all caught up · papers you\'ve already read are below</span></div>';
        html += renderCard(ordered[i], { isNew: S.newSet[ordered[i].id] === 1 });
      }
      if (!ordered.length) {
        html = '<p class="empty">' + (S.view === "saved" && !savedList().length
          ? "No saved papers yet. Press Save on a paper (or <kbd>s</kbd>) to keep it here."
          : "No papers match.") + "</p>";
      }
      var res = document.getElementById("results");
      res.innerHTML = html;
      current = null;
      document.getElementById("feed-count").textContent = ordered.length
        ? "Showing " + fmt(shown) + " of " + plural(ordered.length, "paper") +
          (unread.length !== ordered.length ? ", " + fmt(unread.length) + " unread" : "")
        : "";
      var mb = document.getElementById("mark-all");
      mb.hidden = !unread.length;
      mb.textContent = "Mark all " + fmt(unread.length) + " as read";
      mb.setAttribute("data-n", unread.length);
      document.getElementById("more-wrap").innerHTML = ordered.length > shown
        ? '<button type="button" class="btn" id="more-btn">Show more (' + fmt(ordered.length - shown) + " more)</button>" : "";
    }

    function markAll() {
      var unread = listFor(S.view, true).filter(function (p) { return !isRead(p.id); }).map(function (p) { return p.id; });
      if (!unread.length) return;
      S.undo = unread;
      setRead(unread, true);
      S.shown = FEED_PAGE;
      render();
      document.getElementById("undo-wrap").innerHTML = "Marked " + fmt(unread.length) + " as read. " +
        '<button type="button" class="linkbtn" id="undo-btn">Undo</button>';
    }
    function undoMarkAll() {
      if (S.undo) setRead(S.undo, false);
      S.undo = null;
      render();
    }

    function render() {
      validView();
      renderStatus();
      renderChips();
      renderJournals();
      renderFollowPanel();
      document.getElementById("undo-wrap").innerHTML = "";
      renderList();
    }

    function heroUpdate(manifest) {
      var gen = (manifest && manifest.generated) || S.generated;
      var ms = parseGenerated(gen), li = document.getElementById("hero-updated");
      if (li && !isNaN(ms)) {
        var a = agoTime(ms);
        if (a) { li.textContent = "Updated " + a; li.title = "Last update: " + gen; }
      }
    }

    function start(papers) {
      S.papers = papers;
      S.oldest = papers.reduce(function (m, p) { return p.added && (!m || p.added < m) ? p.added : m; }, "");
      S.base = S.fallback ? null : trackVisit(papers);
      if (S.base) {
        S.baseIds = toSet(S.base.ids);
        papers.forEach(function (p) { if (isNew(p)) S.newSet[p.id] = 1; });
      }
      S.view = String(sget("view", "all"));
      build();
      onChange = function () { renderStatus(); renderChips(); renderJournals(); updateBar(); };
      render();
    }
    function updateBar() {
      var list = listFor(S.view, true);
      var unread = list.filter(function (p) { return !isRead(p.id); }).length;
      var mb = document.getElementById("mark-all");
      mb.hidden = !unread;
      mb.textContent = "Mark all " + fmt(unread) + " as read";
      var shown = Math.min(S.shown, list.length);
      document.getElementById("feed-count").textContent = list.length
        ? "Showing " + fmt(shown) + " of " + plural(list.length, "paper") +
          (unread !== list.length ? ", " + fmt(unread) + " unread" : "") : "";
    }

    var manifestP = fetchJSON(ROOT + "assets/data/manifest.json").catch(function () { return null; });
    fetchJSON(ROOT + "assets/data/feed.json").then(function (feed) {
      if (!feed || !Array.isArray(feed.papers)) throw new Error("feed.json has no papers");
      S.generated = feed.generated || "";
      start(feed.papers.slice().sort(byAddedDesc));
      manifestP.then(heroUpdate);
    }).catch(function () {
      // No feed.json (an older build): the newest papers by publication date from the shards.
      S.fallback = true;
      return manifestP.then(function (manifest) {
        if (!manifest) throw new Error("manifest.json missing");
        heroUpdate(manifest);
        var years = (manifest.years || []).slice().sort(function (a, b) { return b.year - a.year; }).slice(0, 2);
        return Promise.all(years.map(function (y) { return fetchShard(y.file); })).then(function (shards) {
          start([].concat.apply([], shards).sort(byDateDesc).slice(0, 500));
        });
      });
    }).catch(function (err) {
      app.innerHTML = '<p class="empty">Could not load the latest papers (' + esc(err.message) +
        '). The <a href="' + ROOT + 'archive/index.html">archive</a> lists every paper by date.</p>';
    });
  }

  // ---------------------------------------------------------------- search page
  function searchPage() {
    var q = params();
    var papers = [];
    var complete = false;
    var built = false;
    var shown = PAGE_SIZE;

    function build() {
      app.innerHTML =
        '<h1 class="page-title">Search</h1>' +
        '<div class="filter-bar">' +
        '<input type="search" id="f-q" aria-label="Search" placeholder="Search titles, authors, journals, universities, methods…" value="' +
        esc(q.get("q") || q.get("author") || "") + '">' +
        '<select id="f-year" aria-label="Year"><option value="">All years</option></select>' +
        '<select id="f-category" aria-label="Category"><option value="">All categories</option></select>' +
        '<select id="f-journal" aria-label="Journal"><option value="">All journals</option></select>' +
        '<select id="f-source" aria-label="Source"><option value="">All sources</option></select>' +
        '<select id="f-score" aria-label="Relevance"><option value="">Any relevance</option>' +
        '<option value="90">90 or more: extremely relevant</option>' +
        '<option value="70">70 or more: very relevant</option>' +
        '<option value="50">50 or more: relevant</option></select>' +
        '<select id="f-sort" aria-label="Sort"><option value="date">Newest first</option>' +
        '<option value="score">Relevance score</option></select>' +
        "</div>" +
        '<p class="result-meta"><span id="result-count"></span>' +
        '<span id="load-state" class="load-state"></span>' +
        '<a class="clear-filters" href="' + ROOT + 'search.html">Clear filters</a></p>' +
        '<div id="results" class="results"></div><p class="more" id="more-wrap"></p>' + keysHint();

      var timer;
      document.getElementById("f-q").addEventListener("input", function () {
        clearTimeout(timer); shown = PAGE_SIZE;
        timer = setTimeout(apply, 150);
      });
      ["f-year", "f-category", "f-journal", "f-source", "f-score", "f-sort"].forEach(function (id) {
        document.getElementById(id).addEventListener("change", function () { shown = PAGE_SIZE; apply(); });
      });
      app.addEventListener("click", function (e) {
        if (e.target && e.target.id === "more-btn") { shown += PAGE_SIZE; apply(); }
      });
    }

    function refreshOptions() {
      fillOptions("f-year", uniq(papers.map(function (p) {
        return String((p.published || "").slice(0, 4));
      })).sort().reverse(), q.get("year"));
      fillOptions("f-category", uniqCount(papers, "categories").sort(function (a, b) {
        return a.localeCompare(b);
      }), q.get("category"));
      fillOptions("f-journal", uniqCount(papers, "journal"), q.get("journal"));
      fillOptions("f-source", uniq(papers.map(function (p) { return p.source; })).sort(), q.get("source"));
      setSelect("f-score", q.get("minscore"));
    }

    function apply() {
      var query = val("f-q").toLowerCase().trim();
      var terms = query ? query.split(/\s+/) : [];
      var year = val("f-year"), cat = val("f-category"),
          journal = val("f-journal"), source = val("f-source"),
          minScore = +val("f-score") || 0, sort = val("f-sort");
      var out = papers.filter(function (p) {
        if (year && (p.published || "").slice(0, 4) !== year) return false;
        if (cat && (p.categories || []).indexOf(cat) === -1) return false;
        if (journal && p.journal !== journal) return false;
        if (source && p.source !== source) return false;
        if (p.score < minScore) return false;
        if (terms.length) {
          var hay = (p.title + " " + p.authors.join(" ") + " " + p.journal + " " +
            (p.publisher || "") + " " + p.doi + " " + (p.categories || []).join(" ") + " " +
            (p.tags || []).join(" ") + " " + (p.affiliations || []).join(" ") + " " +
            (p.published || "")).toLowerCase();
          for (var i = 0; i < terms.length; i++)
            if (hay.indexOf(terms[i]) === -1) return false;
        }
        return true;
      });
      if (sort === "score") out.sort(function (a, b) { return b.score - a.score; });
      document.getElementById("result-count").textContent = plural(out.length, "paper");
      document.getElementById("load-state").textContent = complete ? "" : "loading the full archive…";
      document.getElementById("results").innerHTML =
        out.slice(0, shown).map(function (p) { return renderCard(p); }).join("") ||
        '<p class="empty">No papers match these filters.</p>';
      current = null;
      document.getElementById("more-wrap").innerHTML = out.length > shown
        ? '<button type="button" class="btn" id="more-btn">Show more (' + fmt(out.length - shown) + " remaining)</button>"
        : "";
    }

    return function onData(newPapers, isComplete) {
      papers = newPapers;
      complete = isComplete;
      if (!built) { build(); built = true; }
      refreshOptions();
      apply();
    };
  }

  function val(id) { return document.getElementById(id).value; }
  function uniq(arr) {
    var seen = {};
    return arr.filter(function (v) { if (!v || seen[v]) return false; seen[v] = 1; return true; });
  }
  function uniqCount(papers, key) {
    var counts = {};
    papers.forEach(function (p) {
      var vals = key === "categories" ? (p.categories || []) : [p[key]];
      vals.forEach(function (v) { if (v) counts[v] = (counts[v] || 0) + 1; });
    });
    return Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; });
  }
  function fillOptions(id, values, urlValue) {
    var select = document.getElementById(id);
    var current = select.value || urlValue || "";
    while (select.options.length > 1) select.remove(1);
    values.forEach(function (v) {
      var opt = document.createElement("option");
      opt.value = v; opt.textContent = v;
      select.appendChild(opt);
    });
    setSelect(id, current);
  }
  function setSelect(id, value) {
    if (!value) return;
    var select = document.getElementById(id);
    for (var i = 0; i < select.options.length; i++)
      if (select.options[i].value === value) { select.value = value; return; }
  }

  // ------------------------------------------------- directory pages
  function directoryPage(kind) {
    var isAuthor = kind === "authors";
    var q = params();
    var selected = q.get(isAuthor ? "a" : "j");
    if (selected) return detailPage(kind, isAuthor ? normalizeAuthor(selected) : selected);

    var title = isAuthor ? "Authors" : "Journals";
    var papers = [];
    var complete = false;
    var built = false;
    var counts = {}, names = [];

    function build() {
      app.innerHTML = '<h1 class="page-title">' + title + "</h1>" +
        '<div class="filter-bar">' +
        '<input type="search" id="dir-q" aria-label="Filter ' + title.toLowerCase() + '" placeholder="Filter ' +
        title.toLowerCase() + '…">' +
        '<select id="dir-cat" aria-label="Category"><option value="">All categories</option></select>' +
        "</div>" +
        '<p class="result-meta"><span id="result-count"></span>' +
        '<span id="load-state" class="load-state"></span></p>' +
        '<ul class="dir-list" id="dir-list"></ul>';
      document.getElementById("dir-q").addEventListener("input", render);
      document.getElementById("dir-cat").addEventListener("change", function () { recount(); render(); });
    }

    function recount() {
      var cat = val("dir-cat");
      counts = {};
      papers.forEach(function (p) {
        if (cat && (p.categories || []).indexOf(cat) === -1) return;
        var ns = isAuthor ? p.authors : (p.journal ? [p.journal] : []);
        ns.forEach(function (n) { counts[n] = (counts[n] || 0) + 1; });
      });
      names = Object.keys(counts).sort(function (a, b) {
        return counts[b] - counts[a] || a.localeCompare(b);
      });
    }

    function render() {
      var needle = val("dir-q").toLowerCase().trim();
      var cat = val("dir-cat");
      var catParam = cat ? "&cat=" + encodeURIComponent(cat) : "";
      var out = needle
        ? names.filter(function (n) { return n.toLowerCase().indexOf(needle) !== -1; })
        : names;
      document.getElementById("result-count").textContent =
        fmt(out.length) + " " + title.toLowerCase() + (cat ? " in " + cat : "");
      document.getElementById("load-state").textContent = complete ? "" : "loading the full archive…";
      document.getElementById("dir-list").innerHTML =
        out.slice(0, 1500).map(function (n) {
          return '<li><a href="?' + (isAuthor ? "a" : "j") + "=" +
            encodeURIComponent(n) + catParam + '">' + esc(n) + "</a>" +
            '<span class="count">' + fmt(counts[n]) + "</span></li>";
        }).join("") +
        (out.length > 1500
          ? '<li class="empty">and ' + fmt(out.length - 1500) +
            " more: type above to narrow down.</li>" : "");
    }

    return function onData(newPapers, isComplete) {
      papers = newPapers;
      complete = isComplete;
      if (!built) { build(); built = true; }
      fillOptions("dir-cat", uniqCount(papers, "categories").sort(function (a, b) {
        return a.localeCompare(b);
      }), q.get("cat"));
      recount();
      render();
    };
  }

  function detailPage(kind, name) {
    var isAuthor = kind === "authors";
    var cat = params().get("cat");
    var baseName = isAuthor ? "authors" : "journals";
    return function onData(papers, complete) {
      var all = papers.filter(function (p) {
        return isAuthor ? p.authors.indexOf(name) !== -1 : p.journal === name;
      });
      var matches = cat
        ? all.filter(function (p) { return (p.categories || []).indexOf(cat) !== -1; })
        : all;
      document.title = name + " · " + SITE;
      var meta = plural(matches.length, "paper") +
        (cat ? " in " + esc(cat) : "") +
        (complete ? "" : " so far, loading the full archive…");
      var showAll = (cat && all.length > matches.length)
        ? ' · <a href="?' + (isAuthor ? "a" : "j") + "=" + encodeURIComponent(name) +
          '">show all ' + fmt(all.length) + " papers</a>"
        : "";
      app.innerHTML = '<h1 class="page-title">' + esc(name) + "</h1>" +
        '<p class="result-meta"><span>' + meta + showAll + "</span>" +
        '<a href="' + ROOT + baseName + ".html" +
        (cat ? "?cat=" + encodeURIComponent(cat) : "") + '">← All ' +
        baseName + "</a></p>" +
        '<div id="results" class="results">' + matches.map(function (p) { return renderCard(p); }).join("") + "</div>" +
        keysHint();
      current = null;
    };
  }

  // ---------------------------------------------------------------- static pages
  /* Archive month pages: the server-rendered cards get the same buttons and dimming. */
  function enhanceStatic() {
    [].forEach.call(document.querySelectorAll(".card[data-id]"), function (card) {
      var actions = card.querySelector(".card-actions");
      if (!actions || actions.querySelector("[data-act]")) return;
      var id = card.getAttribute("data-id");
      actions.insertAdjacentHTML("beforeend", actionButtons(id));
      card.setAttribute("tabindex", "-1");
      card.classList.toggle("is-read", isRead(id));
      var tm = card.querySelector("time");
      if (tm) {
        var pub = tm.getAttribute("datetime") || "";
        tm.title = timeTitle(pub, "");
        var rel = relDay(pub);
        if (rel) tm.textContent = rel;
      }
    });
  }

  // ---------------------------------------------------------------- boot
  if (PAGE === "feed") { feedPage(); return; }
  if (PAGE === "static") { enhanceStatic(); return; }
  var handler = null;
  if (PAGE === "search") handler = searchPage();
  else if (PAGE === "authors") handler = directoryPage("authors");
  else if (PAGE === "journals") handler = directoryPage("journals");
  if (!handler) return;

  loadProgressive(handler).catch(function (err) {
    app.innerHTML = '<p class="empty">Could not load the paper index (' +
      esc(err.message) + "). If you opened this page from the local filesystem, " +
      "serve it over HTTP instead (e.g. <code>python -m http.server</code>).</p>";
  });
})();
