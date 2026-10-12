#!/usr/bin/env python3
"""One-off page generator: writes the six static HTML pages under site/.
The pages are plain HTML; all data is loaded at runtime from site/data/*.json."""
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"

HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="color-scheme" content="dark">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%2305070a'/%3E%3Ctext x='7' y='23' font-size='19' fill='%23c6ff3d'%3E%24%3C/text%3E%3C/svg%3E">
<link rel="stylesheet" href="{base}assets/app.css">
<script defer src="{base}assets/app.js"></script>
</head>
<body data-page="{page}" data-base="{base}">
<canvas id="rain" aria-hidden="true"></canvas>
<div class="scan" aria-hidden="true"></div>
<header class="top">
  <div class="wrap">
    <a class="brand" href="{base}"><span class="mark">$</span><span>model<em>/</em>price</span></a>
    <nav class="nav" aria-label="pages">
      {nav}
    </nav>
    <div class="tools">
      <span class="pill"><span id="sync">syncing…</span></span>
      <button class="btn" id="theme" type="button" aria-label="cycle colour theme">theme: signal</button>
      <button class="btn" id="fx" type="button" aria-pressed="true" aria-label="toggle glyph rain and scanlines">fx</button>
    </div>
  </div>
</header>
<div id="live" class="live" role="status" aria-live="polite"></div>
'''

FOOT = '''<footer class="foot">
  <div class="wrap">
    <span>Prices are list prices, USD per 1M tokens, taken from each provider's own pages or API. Check the provider before you commit spend.</span>
    <span>keys: <b>r</b> toggle fx · <b>t</b> cycle theme</span>
    <span>refreshed hourly · GitHub Actions</span>
  </div>
</footer>
</body>
</html>
'''

PAGES = [
    ("home", "", "model/price :: who is cheapest right now",
     "Live, hourly price board for OpenCode Zen, Nous Portal, OpenRouter and Command Code."),
    ("zen", "zen/", "model/price :: OpenCode Zen",
     "OpenCode Zen model prices, cheapest first, with offers and price drops."),
    ("nous", "nous/", "model/price :: Nous Portal",
     "Nous Portal model prices, cheapest first, with offers and price drops."),
    ("openrouter", "openrouter/", "model/price :: OpenRouter",
     "OpenRouter model prices, cheapest first, with offers and price drops."),
    ("commandcode", "commandcode/", "model/price :: Command Code",
     "Command Code model prices, cheapest first, with deals and price drops."),
    ("common", "common/", "model/price :: models on more than one provider",
     "Models offered by two or more of the four providers, compared side by side."),
]
NAV = [("home", "Overview", ""), ("zen", "Zen", "zen/"), ("nous", "Nous", "nous/"),
       ("openrouter", "OpenRouter", "openrouter/"), ("commandcode", "Cmd Code", "commandcode/"),
       ("common", "Common", "common/")]


def nav_html(page: str, base: str) -> str:
    out = []
    for key, label, path in NAV:
        cur = ' aria-current="page"' if key == page else ""
        out.append(f'<a href="{base}{path}"{cur}>{label}</a>')
    return "\n      ".join(out)


def provider_body(title: str, kicker: str, blurb: str) -> str:
    return f'''<main class="wrap">
  <section class="hero rise-in">
    <p class="kicker">{kicker}</p>
    <h1><span class="grad">{title}</span><span class="cursor" aria-hidden="true"></span></h1>
    <p class="lede" id="sub">loading…</p>
    <div class="hero-meta"><span class="pill">{blurb}</span></div>
  </section>
  <div class="layout rise-in d1">
    <section class="panel" aria-label="model table">
      <div class="toolbar">
        <label class="sr" for="q">search models</label>
        <input id="q" type="search" placeholder="filter by name or id…" autocomplete="off">
        <label class="sr" for="kind">model kind</label>
        <select id="kind">
          <option value="text">text / chat</option>
          <option value="all">everything</option>
          <option value="embedding">embeddings</option>
          <option value="image">image / audio</option>
        </select>
        <div class="chips">
          <button class="chip" type="button" data-chip="free" aria-pressed="false">free only</button>
          <button class="chip" type="button" data-chip="offers" aria-pressed="false">offers &amp; drops</button>
        </div>
        <span class="count"><b id="shown">0</b> of <span id="count-total">0</span> shown</span>
      </div>
      <div id="stale" class="tag stale" hidden style="margin:10px 14px;display:block;white-space:normal"></div>
      <div class="legend" aria-label="legend">
        <span><i class="sw edge lime"></i>row edge: provider offer</span>
        <span><i class="sw edge mag"></i>row edge: price drop</span>
        <span><b class="lg-t lime">◆ 50% off</b> discount set by the provider</span>
        <span><b class="lg-t mag">▼ drop</b> / <b class="lg-t amber">▲ rise</b> price moved in the last 7 days</span>
        <span><b class="lg-t cyan">new</b> listed in the last 7 days</span>
        <span><b class="lg-t lime">free</b> $0 in and out</span>
        <span><i class="sw spark"></i>trend: blended price history, dot = now</span>
        <span><b class="lg-t dim">&gt;272K: $x</b> price above a context-length band</span>
        <span><b class="lg-t dim">was $x</b> blended price before the offer</span>
        <span><b class="lg-t dim">—</b> not published by the provider</span>
        <span><b class="lg-t faint">grey row</b> not a text model (shown with “everything”)</span>
      </div>
      <p id="loading" class="empty">loading prices…</p>
      <div class="tablewrap">
        <table id="t"><thead></thead><tbody id="rows"></tbody></table>
      </div>
    </section>
    <aside class="rail" aria-label="offers and price drops">
      <h2>offers &amp; drops · <span id="rail-count">0</span></h2>
      <ul id="rail-deals"></ul>
      <div class="notes" id="rail-notes" hidden></div>
      <div class="notes">
        <p>Lists provider offers and price moves (lime = offer, magenta = drop, amber = rise). Plain free models are not deals, so they are left out; use “free only” to see them.</p>
        <p>Click a deal to filter the table to that model.</p>
        <p>Blended = (3 × input + output) / 4, per 1M tokens. Sorted cheapest first by default. Click any column header to sort; click again to reverse.</p>
      </div>
    </aside>
  </div>
</main>
'''


def common_body() -> str:
    return '''<main class="wrap">
  <section class="hero rise-in">
    <p class="kicker">cross-provider · same model, several prices</p>
    <h1><span class="grad">Who has it cheapest</span><span class="cursor" aria-hidden="true"></span></h1>
    <p class="lede" id="sub">loading…</p>
    <div class="hero-meta"><span class="pill" id="synced-line">loading…</span></div>
  </section>
  <div class="layout rise-in d1">
    <section class="panel" aria-label="common models table">
      <div class="toolbar">
        <label class="sr" for="q">search models</label>
        <input id="q" type="search" placeholder="filter by model…" autocomplete="off">
        <div class="seg" role="group" aria-label="which models">
          <button type="button" data-mode="all4" aria-pressed="true">on all four · <span id="c4">–</span></button>
          <button type="button" data-mode="two" aria-pressed="false">two or more · <span id="c2">–</span></button>
        </div>
        <div class="chips">
          <button class="chip" type="button" data-chip="offers" aria-pressed="false">offers &amp; drops</button>
        </div>
        <span class="count"><b id="shown">0</b> shown</span>
      </div>
      <div class="legend" aria-label="legend">
        <span><b class="lg-t lime">◆ $0.175</b> cheapest provider for that model</span>
        <span><i class="sw edge lime"></i>row edge: spread ≥ 30%, provider choice matters</span>
        <span><b class="lg-t lime">◆ 20% off</b> provider offer</span>
        <span><b class="lg-t mag">▼ drop</b> price fell in the last 7 days</span>
        <span><b class="lg-t cyan">free</b> free on that provider</span>
        <span><b class="lg-t dim">— not listed</b> provider does not offer it</span>
        <span><b class="lg-t dim">spread</b> how much cheaper the best is than the dearest</span>
      </div>
      <p id="loading" class="empty">loading prices…</p>
      <div class="tablewrap">
        <table id="t"><thead></thead><tbody id="rows"></tbody></table>
      </div>
    </section>
    <aside class="rail" aria-label="offers and drops across providers">
      <h2>offers &amp; drops · <span id="rail-count">0</span></h2>
      <ul id="rail-deals"></ul>
      <div class="notes">
        <p>Models with an offer or a price drop on at least one provider, biggest first. Follows the “on all four / two or more” toggle.</p>
        <p>Matched by model name across providers. A model counts only when the names resolve to the same key; the id line under each model shows that key.</p>
        <p>Big price = blended (3 × input + output) / 4; small line = input and output, per 1M tokens.</p>
      </div>
    </aside>
  </div>
</main>
'''


def home_body() -> str:
    cards = [
        ("zen", "01 / opencode", "OpenCode Zen",
         "Curated OpenCode models with per-request prices, including its free tier.", "zen/"),
        ("nous", "02 / nous", "Nous Portal",
         "Nous inference API price list, for the models it serves.", "nous/"),
        ("openrouter", "03 / openrouter", "OpenRouter",
         "The full OpenRouter index, including :free variants and expiring models.", "openrouter/"),
        ("commandcode", "04 / command code", "Command Code",
         "Models on the Command Code table, with plan deals and peak-hour pricing.", "commandcode/"),
    ]
    parts = []
    for key, idx, name, desc, path in cards:
        parts.append(f'''    <a class="card rise-in" href="{{base}}{path}">
      <span class="idx">{idx}</span>
      <h2>{name}</h2>
      <p>{desc}</p>
      <div class="stat"><b id="{key}-count">–</b><span>models priced</span></div>
      <div class="row">
        <span class="tag" id="{key}-status">…</span>
        <span class="pill">offers <b id="{key}-offers">–</b></span>
        <span class="pill">drops <b id="{key}-drops">–</b></span>
        <span class="pill">free <b id="{key}-free">–</b></span>
      </div>
      <span class="go">open the table →</span>
    </a>''')
    cards_html = "\n".join(parts)
    return f'''<main class="wrap">
  <section class="hero hero-grid rise-in">
    <div>
      <p class="kicker">live price board · refreshed hourly</p>
      <h1>Same models.<br><span class="grad">Four prices.</span><span class="cursor" aria-hidden="true"></span></h1>
      <p class="lede">Compare OpenCode Zen, Nous Portal, OpenRouter and Command Code side by side. Every table sorts cheapest first, and every discount and price move is flagged on the side. Pick the cheapest door before you start the work.</p>
      <div class="hero-meta"><span class="pill" id="home-sync">loading…</span></div>
    </div>
    <figure class="ladder" aria-labelledby="ladder-cap">
      <figcaption id="ladder-cap"><span>the ladder</span> every model on all four providers, cheapest → priciest, blended $/1M, log scale</figcaption>
      <div id="ladder" class="ladder-svg"></div>
    </figure>
  </section>
  <section class="grid four" aria-label="provider tables">
{cards_html}
    <a class="card feature rise-in d2" href="{{base}}common/">
      <div class="body">
        <span class="idx">05 / on more than one provider</span>
        <h2>Same model, cheapest provider</h2>
        <p>Every model offered by two or more of the four providers, with each provider's price. Default view is models on all four.</p>
        <div class="stat"><b id="c-n4">–</b><span>on all four · <span id="c-n2">–</span> on two or more</span></div>
        <p class="lede" style="margin:0;font-size:12.5px" id="c-cheap"></p>
        <span class="go">compare the models →</span>
      </div>
    </a>
  </section>
  <div class="notes" style="max-width:86ch;margin:18px 0 0">
    <p><b class="lg-t lime">live</b> the last hourly fetch succeeded · <b class="lg-t amber">stale</b> it failed and the table shows the last good data.</p>
    <p><b>offers</b> models with a provider discount · <b>drops</b> models whose price fell in the last 7 days · <b>free</b> models at $0 in and out.</p>
  </div>
  <p class="notes" style="max-width:76ch;margin:12px 0 48px">Nothing on this board is hand-entered. Every page is rebuilt from the providers' own price data each hour by GitHub Actions, and the ladder is drawn from the same numbers as the tables.</p>
</main>
'''


def main() -> None:
    for key, path, title, desc in PAGES:
        base = "./" if path == "" else "../"
        if key == "home":
            body = home_body()
        elif key == "common":
            body = common_body()
        else:
            t, k, b = {
                "zen": ("OpenCode Zen", "provider 01 · opencode", "Curated list, per-request billing"),
                "nous": ("Nous Portal", "provider 02 · nous", "Nous inference API price list"),
                "openrouter": ("OpenRouter", "provider 03 · openrouter", "Full index incl. :free"),
                "commandcode": ("Command Code", "provider 04 · command code", "Table incl. plan deals & peak hours"),
            }[key]
            body = provider_body(t, k, b)
        head = HEAD.format(title=title, desc=desc, base=base, page=key, nav=nav_html(key, base))
        html = head + body.replace("{base}", base) + FOOT
        out = SITE / path / "index.html" if path else SITE / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(out.relative_to(SITE.parent), len(html))


if __name__ == "__main__":
    main()
