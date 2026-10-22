/* model/price :: page logic. Vanilla JS, no build step.
   SECURITY: every provider-supplied string (model names, ids, notes, deal text) is
   passed through esc() before it is placed in innerHTML; all other interpolated values are numbers.
   Pages: home | zen | nous | openrouter | common
   Reads ../data/*.json relative to the page (set via <body data-base>). */
(function () {
  "use strict";

  const body = document.body;
  const BASE = body.dataset.base || "./";
  const PAGE = body.dataset.page;
  const PROVIDERS = {
    zen: { name: "OpenCode Zen", short: "Zen" },
    nous: { name: "Nous Portal", short: "Nous" },
    openrouter: { name: "OpenRouter", short: "OpenRouter" },
  };
  const ORDER = ["zen", "nous", "openrouter"];
  const PROVIDER_COUNT = ORDER.length;

  // ------------------------------------------------------------ utils
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function money(v) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    if (v === 0) return "free";
    const d = v >= 1 ? 2 : v >= 0.1 ? 3 : v >= 0.01 ? 3 : 4;
    return "$" + v.toFixed(d);
  }
  function ctxFmt(n) {
    if (!n) return "—";  // provider did not publish a window
    if (n >= 1e6) return (n / 1e6).toFixed(n % 1e6 ? 1 : 0).replace(/\.0$/, "") + "M";
    if (n >= 1e3) return Math.round(n / 1e3) + "K";
    return String(n);
  }
  function ago(iso) {
    if (!iso) return "never";
    const s = Math.max(0, (Date.now() - Date.parse(iso)) / 1000);
    if (s < 90) return "just now";
    if (s < 3600) return Math.round(s / 60) + "m ago";
    if (s < 86400) return Math.round(s / 3600) + "h ago";
    return Math.round(s / 86400) + "d ago";
  }
  async function load(name) {
    const r = await fetch(BASE + "data/" + name, { cache: "no-cache" });
    if (!r.ok) throw new Error(name + " HTTP " + r.status);
    return r.json();
  }
  function say(msg) {
    let el = $("#live");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("on");
    clearTimeout(say._t);
    say._t = setTimeout(() => el.classList.remove("on"), 1800);
  }
  const cmp = (a, b, dir) => {
    const na = a === null || a === undefined || Number.isNaN(a);
    const nb = b === null || b === undefined || Number.isNaN(b);
    if (na && nb) return 0;
    if (na) return 1;          // blanks always last
    if (nb) return -1;
    if (typeof a === "string") return dir * a.localeCompare(b);
    return dir * (a - b);
  };

  // ----------------------------------------------------------- theme / fx
  const prefs = JSON.parse(localStorage.getItem("mpc-prefs") || "{}");
  const THEMES = ["signal", "ember", "ice"];
  function applyPrefs() {
    body.dataset.fx = prefs.fx === false ? "off" : "on";
    document.documentElement.dataset.theme = prefs.theme && prefs.theme !== "signal" ? prefs.theme : "";
    const fx = $("#fx");
    if (fx) fx.setAttribute("aria-pressed", String(prefs.fx !== false));
    const th = $("#theme");
    if (th) th.textContent = "theme: " + (prefs.theme || "signal");
  }
  function savePrefs() { localStorage.setItem("mpc-prefs", JSON.stringify(prefs)); applyPrefs(); }
  function bindTools() {
    const fx = $("#fx");
    if (fx) fx.addEventListener("click", () => { prefs.fx = prefs.fx === false; savePrefs(); if (prefs.fx !== false) startRain(); say(prefs.fx === false ? "fx off" : "fx on"); });
    const th = $("#theme");
    if (th) th.addEventListener("click", () => { const i = THEMES.indexOf(prefs.theme || "signal"); prefs.theme = THEMES[(i + 1) % THEMES.length]; savePrefs(); });
    document.addEventListener("keydown", (e) => {
      if (e.target.closest && e.target.closest("input,select,textarea")) return;
      if (e.key === "r" && fx) fx.click();
      if (e.key === "t" && th) th.click();
    });
  }

  // ------------------------------------------------------------- rain
  let rainRaf = 0;
  function startRain() {
    const cv = $("#rain");
    if (!cv || prefs.fx === false || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const ctx = cv.getContext("2d");
    const glyphs = "01ｦｱｲｳｴｵｶｷｸｹｺ<>/$%#+*=ǀ";
    let cols = [], w = 0, h = 0, dpr = Math.min(2, devicePixelRatio || 1);
    function size() {
      w = innerWidth; h = innerHeight;
      cv.width = w * dpr; cv.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const n = Math.ceil(w / 22);
      cols = Array.from({ length: n }, () => ({ y: Math.random() * h, v: 0.4 + Math.random() * 1.1, s: 14 + Math.random() * 4 }));
    }
    size(); addEventListener("resize", size);
    let last = 0;
    function frame(t) {
      rainRaf = requestAnimationFrame(frame);
      if (t - last < 60) return;  // ~16fps: calm, not busy
      last = t;
      ctx.fillStyle = "rgba(5,7,10,0.16)";
      ctx.fillRect(0, 0, w, h);
      ctx.font = "14px " + getComputedStyle(document.documentElement).getPropertyValue("--mono");
      const lime = getComputedStyle(document.documentElement).getPropertyValue("--lime").trim() || "#c6ff3d";
      cols.forEach((c, i) => {
        const g = glyphs[(Math.random() * glyphs.length) | 0];
        ctx.fillStyle = Math.random() < 0.02 ? "#ffffff" : lime;
        ctx.globalAlpha = 0.25 + Math.random() * 0.35;
        ctx.fillText(g, i * 22, c.y);
        ctx.globalAlpha = 1;
        c.y += c.v * c.s * 0.5;
        if (c.y > h + 40 && Math.random() > 0.975) { c.y = -20; c.v = 0.4 + Math.random() * 1.1; }
      });
    }
    cancelAnimationFrame(rainRaf);
    rainRaf = requestAnimationFrame(frame);
  }

  // ----------------------------------------------------------- sync pill
  let META = null;
  async function showSync() {
    const el = $("#sync");
    try {
      META = META || (await load("meta.json"));
    } catch (e) {
      if (el) { el.textContent = "data unavailable"; el.parentElement.classList.add("bad"); }
      return;
    }
    if (el) {
      const bad = Object.values(META.providers).filter((p) => !p.ok).length;
      el.innerHTML = `<span class="led"></span>synced <b>${ago(META.synced)}</b>${bad ? ` · ${bad} stale` : ""}`;
      el.parentElement.classList.toggle("bad", bad > 0);
    }
  }

  // ------------------------------------------------------- provider page
  const KIND_LABEL = { text: "text / chat", all: "everything", embedding: "embeddings", image: "image / audio" };

  function spark(vals) {
    const v = (vals || []).filter((x) => x !== null && x !== undefined);
    if (v.length < 2) return '<span class="muted">—</span>';
    const lo = Math.min(...v), hi = Math.max(...v), span = hi - lo || 1;
    const W = 96, H = 26, pad = 3;
    const pts = v.map((y, i) => [(i / (v.length - 1)) * W, pad + (1 - (y - lo) / span) * (H - pad * 2)]);
    const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
    const last = pts[pts.length - 1];
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="price trend, ${v.length} points"><path d="${d}"/><circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="2.2"/></svg>`;
  }

  function signalTags(r) {
    const t = [];
    if (r.offer && r.offer.label !== "free") t.push(`<span class="tag offer">◆ ${esc(r.offer.label)}</span>`);
    if (r.free) t.push('<span class="tag free">free</span>');
    if (r.drop) t.push(`<span class="tag drop">▼ ${r.drop.pct}% drop</span>`);
    if (r.rise) t.push(`<span class="tag rise">▲ ${Math.abs(r.rise.pct)}% rise</span>`);
    if (r.new) t.push('<span class="tag new">new</span>');
    return t.join(" ");
  }

  async function providerPage(prov) {
    const cols = [
      { k: "name", label: "Model", cls: "" },
      { k: "ctx", label: "Context", cls: "num" },
      { k: "in", label: "Input /1M", cls: "num" },
      { k: "out", label: "Output /1M", cls: "num" },
      { k: "cr", label: "Cache read", cls: "num" },
      { k: "blend", label: "Blended", cls: "num" },
      { k: "spark", label: "Trend", cls: "" },
      { k: "signal", label: "Signal", cls: "" },
    ];
    const state = { q: "", kind: "text", free: false, offers: false, key: "blend", dir: 1 };
    const doc = await load(prov + ".json");
    const all = doc.models;
    const deals = doc.deals || [];
    const meta = (META && META.providers[prov]) || {};
    $("#count-total").textContent = all.length;
    $("#sub").innerHTML = `${all.length} models from ${esc(PROVIDERS[prov].name)} · prices per 1M tokens, cheapest first · updated <b>${ago(doc.fetched)}</b>`;
    if (!meta.ok && meta.error) {
      $("#stale").hidden = false;
      $("#stale").textContent = "stale: last sync failed, showing last good data (" + meta.error.slice(0, 120) + ")";
    }

    // table head
    const thead = $("#t thead");
    thead.innerHTML = "<tr>" + cols.map((c) => {
      const sortable = c.k !== "spark" && c.k !== "signal";
      return `<th class="${c.cls}" data-k="${c.k}" ${sortable ? "" : 'data-nosort="1"'}>${sortable ? `<button type="button" data-k="${c.k}">${c.label}</button>` : `<span style="padding:10px 12px;display:block;font-size:11.5px;letter-spacing:.1em;text-transform:uppercase">${c.label}</span>`}</th>`;
    }).join("") + "</tr>";

    function sortVal(r, k) {
      switch (k) {
        case "name": return (r.name || r.id).toLowerCase();
        case "signal": return r.drop ? -r.drop.pct : r.offer ? -(r.offer.pct || 0) : 0;
        default: return r[k];
      }
    }
    function visible() {
      const q = state.q.trim().toLowerCase();
      let rows = all.filter((r) => {
        if (state.kind !== "all" && r.kind !== state.kind) return false;
        if (state.free && !r.free) return false;
        if (state.offers && !(r.drop || r.rise || (r.offer && r.offer.label !== "free"))) return false;  // same definition as the rail
        if (q && !(`${r.name} ${r.id}`.toLowerCase().includes(q))) return false;
        return true;
      });
      rows.sort((a, b) => cmp(sortVal(a, state.key), sortVal(b, state.key), state.dir) || cmp(a.blend, b.blend, 1));
      return rows;
    }
    function row(r) {
      const cls = r.drop ? "drop" : r.offer && r.offer.label !== "free" ? "offer" : "";
      const rowCls = r.kind !== "text" ? "muted" : "";
      const link = r.url ? `<a href="${esc(r.url)}" rel="noopener">${esc(r.name)}</a>` : esc(r.name);
      return `<tr class="${cls} ${rowCls}">
        <td class="name">${link}<div class="id">${esc(r.id)}${r.note ? " · " + esc(r.note) : ""}</div></td>
        <td class="num" title="${r.ctx ? "" : "provider does not publish a context length"}">${ctxFmt(r.ctx)}</td>
        <td class="num price">${money(r.in)}${r.tiered && r.tiered.in !== undefined && r.tiered.in !== null ? `<small>>${ctxFmt(r.tiered.above)}: ${money(r.tiered.in)}</small>` : ""}</td>
        <td class="num price">${money(r.out)}${r.tiered && r.tiered.out !== undefined && r.tiered.out !== null ? `<small>>${ctxFmt(r.tiered.above)}: ${money(r.tiered.out)}</small>` : ""}</td>
        <td class="num price">${money(r.cr)}</td>
        <td class="num blend">${money(r.blend)}${r.offer && r.offer.was ? `<small class="was" style="display:block">was ${money(r.offer.was.in && r.offer.was.out ? (3 * r.offer.was.in + r.offer.was.out) / 4 : null)}</small>` : ""}</td>
        <td class="sparkc">${spark(r.spark)}</td>
        <td>${signalTags(r)}</td>
      </tr>`;
    }
    function render() {
      const rows = visible();
      $("#rows").innerHTML = rows.length ? rows.map(row).join("") : `<tr><td colspan="${cols.length}" class="empty">no models match. widen the filters.</td></tr>`;
      $("#shown").textContent = rows.length;
      $$("#t thead th[data-k]").forEach((th) => {
        const k = th.dataset.k;
        if (k === state.key) th.setAttribute("aria-sort", state.dir > 0 ? "ascending" : "descending");
        else th.removeAttribute("aria-sort");
      });
    }
    function renderRail() {
      // real offers and moves only: a plain 'free' tier is a price, not a deal
      const items = all.filter((r) => r.drop || r.rise || (r.offer && r.offer.label !== "free"))
        .map((r) => ({ r, score: r.drop ? r.drop.pct : r.rise ? -r.rise.pct : (r.offer.pct || 0) }))
        .sort((a, b) => b.score - a.score);
      const ul = $("#rail-deals");
      ul.innerHTML = items.length ? items.map(({ r }) => {
        const kind = r.drop ? "drop" : r.rise ? "rise" : "offer";
        const tag = r.drop ? `▼ ${r.drop.pct}%` : r.rise ? `▲ ${Math.abs(r.rise.pct)}%` : esc(r.offer.label);
        return `<li><button class="deal ${kind}" type="button" data-id="${esc(r.id)}" aria-label="filter table to ${esc(r.name)}">
          <span class="n">${esc(r.name)}</span>
          <span class="m"><span class="tag ${kind === "offer" ? "offer" : kind}">${tag}</span>
          <span class="p">${money(r.in)} / ${money(r.out)}</span></span></button></li>`;
      }).join("") : '<li><p class="none">no live offers or price drops right now.</p></li>';
      $("#rail-count").textContent = items.length;
      if (deals.length) {
        $("#rail-notes").innerHTML = `<p><b>Provider notes</b></p>` + deals.slice(0, 6).map((d) => `<p>· ${esc(d.text)}</p>`).join("");
        $("#rail-notes").hidden = false;
      }
    }

    // wiring
    $("#q").addEventListener("input", (e) => { state.q = e.target.value; render(); });
    $("#kind").addEventListener("change", (e) => { state.kind = e.target.value; render(); });
    $$("[data-chip]").forEach((b) => b.addEventListener("click", () => {
      state[b.dataset.chip] = !state[b.dataset.chip];
      b.setAttribute("aria-pressed", String(state[b.dataset.chip]));
      render();
    }));
    $("#t thead").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-k]");
      if (!b) return;
      const k = b.dataset.k;
      if (state.key === k) state.dir *= -1; else { state.key = k; state.dir = k === "name" ? 1 : 1; }
      render();
    });
    $("#rail-deals").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-id]");
      if (!b) return;
      state.q = b.dataset.id; $("#q").value = state.q;
      render();
      $("#t").scrollIntoView({ block: "start", behavior: "smooth" });
    });
    render();
    renderRail();
    $("#loading") && ($("#loading").hidden = true);
  }

  // ------------------------------------------------------------ common
  async function commonPage() {
    const doc = await load("common.json");
    const meta = META || {};
    const models = doc.models;
    const state = { mode: "all3", q: "", offers: false, key: "best", dir: 1 };
    const total3 = models.filter((m) => m.n === PROVIDER_COUNT).length;
    $("#sub").innerHTML = `Models offered by at least two of the three providers. <b>${total3}</b> are on all three. Prices per 1M tokens, blended 3 input : 1 output.`;
    $("#c3").textContent = total3;
    $("#c2").textContent = models.length;
    $("#synced-line").textContent = "updated " + ago(doc.fetched);

    const colDefs = [
      { k: "name", label: "Model" },
      ...ORDER.map((p) => ({ k: p, label: PROVIDERS[p].short, num: true })),
      { k: "best", label: "Cheapest", num: true },
      { k: "spread", label: "Spread", num: true },
    ];
    $("#t thead").innerHTML = "<tr>" + colDefs.map((c) => `<th class="${c.num ? "num" : ""}" data-k="${c.k}"><button type="button" data-k="${c.k}">${c.label}</button></th>`).join("") + "</tr>";

    const val = (m, k) => {
      if (k === "name") return m.name.toLowerCase();
      if (k === "best") return m.min;
      if (k === "spread") return m.spread;
      return m.p[k] ? m.p[k].blend : null;
    };
    const visible = () => {
      const q = state.q.trim().toLowerCase();
      const rows = models.filter((m) => {
        if (state.mode === "all3" && m.n !== PROVIDER_COUNT) return false;
        if (state.offers && !Object.values(m.p).some((p) => p.drop || (p.offer && p.offer.label !== "free"))) return false;
        if (q && !m.name.toLowerCase().includes(q) && !m.key.includes(q)) return false;
        return true;
      });
      rows.sort((a, b) => cmp(val(a, state.key), val(b, state.key), state.dir) || cmp(a.min, b.min, 1));
      return rows;
    };
    const cell = (m, p) => {
      const pr = m.p[p];
      if (!pr) return `<td class="num"><div class="pcell none"><span class="b">—</span><span class="io">not listed</span></div></td>`;
      const isBest = m.best.includes(p) && m.n > 1;
      const tg = pr.drop ? `<span class="tg">▼ ${pr.drop.pct}% drop</span>` : pr.offer && pr.offer.label !== "free" ? `<span class="tg" style="color:var(--lime)">◆ ${esc(pr.offer.label)}</span>` : pr.offer ? `<span class="tg" style="color:var(--cyan)">free</span>` : "";
      return `<td class="num"><div class="pcell ${isBest ? "best" : ""}"><span class="b">${money(pr.blend)}</span><span class="io">in ${money(pr.in)} · out ${money(pr.out)}</span>${tg}</div></td>`;
    };
    const render = () => {
      const rows = visible();
      $("#rows").innerHTML = rows.length ? rows.map((m) => `<tr class="${m.spread >= 30 ? "hit" : ""}" ${m.spread >= 30 ? 'title="spread ≥ 30%: provider choice matters"' : ""}>
        <td class="name">${esc(m.name)}<div class="id">${esc(m.key)} · ${m.n}/${PROVIDER_COUNT} providers</div></td>
        ${ORDER.map((p) => cell(m, p)).join("")}
        <td class="num best">${money(m.min)}<div class="id" style="max-width:none">${m.best.map((p) => PROVIDERS[p].short).join(", ")}</div></td>
        <td class="num">${m.spread ? m.spread + "%" : "—"}</td>
      </tr>`).join("") : `<tr><td colspan="${colDefs.length}" class="empty">no models match. widen the filters.</td></tr>`;
      $("#shown").textContent = rows.length;
      $$("#t thead th[data-k]").forEach((th) => {
        if (th.dataset.k === state.key) th.setAttribute("aria-sort", state.dir > 0 ? "ascending" : "descending");
        else th.removeAttribute("aria-sort");
      });
    };
    const renderRail = () => {
      const scope = models.filter((m) => state.mode !== "all3" || m.n === PROVIDER_COUNT);  // rail follows the same mode as the table
      const items = scope.filter((m) => Object.values(m.p).some((p) => p.drop || (p.offer && p.offer.label !== "free")))
        .map((m) => {
          const best = Math.max(0, ...Object.values(m.p).map((p) => (p.drop ? p.drop.pct : p.offer && p.offer.pct) || 0));
          return { m, best };
        })
        .sort((a, b) => b.best - a.best);
      $("#rail-deals").innerHTML = items.length ? items.slice(0, 80).map(({ m, best }) => {
        const who = Object.entries(m.p).filter(([, p]) => p.drop || (p.offer && p.offer.label !== "free")).map(([k]) => PROVIDERS[k].short).join(", ");
        return `<li><button class="deal offer" type="button" data-id="${esc(m.key)}"><span class="n">${esc(m.name)}</span>
          <span class="m"><span class="tag offer">${best ? "◆ up to " + best + "%" : "offer"}</span><span>${esc(who)}</span><span class="p">${money(m.min)}</span></span></button></li>`;
      }).join("") : '<li><p class="none">no offers or drops among these models.</p></li>';
      $("#rail-count").textContent = items.length;
    };

    $("#q").addEventListener("input", (e) => { state.q = e.target.value; render(); });
    $$("[data-mode]").forEach((b) => b.addEventListener("click", () => {
      state.mode = b.dataset.mode;
      $$("[data-mode]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      render();
      renderRail();
    }));
    $("[data-chip=offers]").addEventListener("click", (e) => {
      state.offers = !state.offers;
      e.currentTarget.setAttribute("aria-pressed", String(state.offers));
      render();
    });
    $("#t thead").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-k]");
      if (!b) return;
      if (state.key === b.dataset.k) state.dir *= -1; else { state.key = b.dataset.k; state.dir = 1; }
      render();
    });
    $("#rail-deals").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-id]");
      if (!b) return;
      state.q = b.dataset.id; $("#q").value = state.q; render();
      $("#t").scrollIntoView({ block: "start", behavior: "smooth" });
    });
    render();
    renderRail();
    $("#loading") && ($("#loading").hidden = true);
  }

  // -------------------------------------------------------------- home
  function ladderSvg(models) {
    // every common model, cheapest to priciest (blended), log scale: a real price ladder
    const v = models.map((m) => m.min).filter((x) => x > 0).sort((a, b) => a - b);
    if (v.length < 2) return "";
    const W = 600, H = 110, lo = Math.log(v[0]), hi = Math.log(v[v.length - 1]), span = hi - lo || 1;
    const pts = v.map((y, i) => [(i / (v.length - 1)) * W, 6 + (1 - (Math.log(y) - lo) / span) * (H - 12)]);
    const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
    const area = d + ` L${W} ${H} L0 ${H} Z`;
    return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="price ladder of ${v.length} models, cheapest to priciest">
      <defs><linearGradient id="fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity=".28"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>
      <path class="area" d="${area}"/><path d="${d}"/></svg>`;
  }
  async function homePage() {
    const meta = META || (await load("meta.json"));
    const common = await load("common.json");
    const n3 = common.models.filter((m) => m.n === PROVIDER_COUNT).length;
    const n2 = common.models.length;
    const cheapest3 = common.models.filter((m) => m.n === PROVIDER_COUNT).sort((a, b) => a.min - b.min)[0];
    const ladder = $("#ladder");
    if (ladder) ladder.innerHTML = ladderSvg(common.models.filter((m) => m.n === PROVIDER_COUNT));
    if ($("#home-sync")) $("#home-sync").innerHTML = `<span class="led"></span>${Object.values(meta.providers).filter((p) => p.ok).length}/${PROVIDER_COUNT} providers live · synced <b>${ago(meta.synced)}</b>`;
    if ($("#c-n3")) $("#c-n3").textContent = n3;
    if ($("#c-n2")) $("#c-n2").textContent = n2;
    if (cheapest3 && $("#c-cheap")) $("#c-cheap").textContent = `${cheapest3.name} · ${money(cheapest3.min)} /1M blended · best at ${cheapest3.best.map((p) => PROVIDERS[p].short).join(", ")}`;
    for (const p of ORDER) {
      const pm = meta.providers[p] || {};
      const set = (k, v) => { const el = $("#" + p + "-" + k); if (el) el.textContent = v; };
      set("count", pm.count ?? "—");
      set("offers", pm.offers ?? "—");
      set("drops", pm.drops ?? "—");
      set("free", pm.free ?? "—");
      const st = $("#" + p + "-status");
      if (st) {
        st.className = "tag " + (pm.ok ? "free" : "stale");
        st.textContent = pm.ok ? "live" : "stale";
      }
      set("synced", ago(pm.fetched));
    }
    $("#loading") && ($("#loading").hidden = true);
  }

  // -------------------------------------------------------------- boot
  document.addEventListener("DOMContentLoaded", async () => {
    applyPrefs();
    bindTools();
    startRain();
    await showSync();
    setInterval(showSync, 60 * 1000);
    try {
      if (PAGE === "home") await homePage();
      else if (PAGE === "common") await commonPage();
      else if (PROVIDERS[PAGE]) await providerPage(PAGE);
    } catch (e) {
      const l = $("#loading");
      if (l) { l.hidden = false; l.textContent = "could not load data: " + e.message; }
      console.error(e);
    }
  });
})();
