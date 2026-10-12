# model/price

Live, hourly price board for four model providers: **OpenCode Zen, Nous Portal, OpenRouter, Command Code**.
Six static pages, sorted cheapest first, with offers and price drops flagged on a side rail.

| Page | Path | What it shows |
|---|---|---|
| Overview | `/` | live counts per provider, the price ladder of models on all four |
| OpenCode Zen | `/zen/` | every Zen model, sortable, with offers |
| Nous Portal | `/nous/` | every Nous model, sortable, with offers |
| OpenRouter | `/openrouter/` | every OpenRouter model, sortable, with offers and `:free` |
| Command Code | `/commandcode/` | every Command Code model, sortable, with deals and peak pricing |
| Common | `/common/` | models offered by two or more providers. Default: all four. Toggle: two or more |

## How it updates

`.github/workflows/pages.yml` runs **hourly at :17 UTC**:

1. `scripts/fetch_prices.py` pulls the four providers' prices and writes `site/data/*.json`.
2. `scripts/build_pages.py` rebuilds the pages.
3. The refreshed data is committed back to `main` (only when something changed).
4. `site/` is deployed to GitHub Pages.

If one provider fails, its last good data is kept and the page shows a **stale** notice. The other providers still update.

Scheduled runs can be delayed by GitHub under load, so "hourly" means roughly hourly.

## Setup (one time, not yet done)

- Repo needs to be on branch `main` (the local repo was created as `master`).
- Settings → Pages → **Source: GitHub Actions**.

## Run locally

```bash
python scripts/fetch_prices.py        # refresh data (stdlib only, no installs)
python scripts/build_pages.py         # regenerate HTML
python -m http.server 8000 -d site    # then open http://localhost:8000
python -m unittest scripts/test_fetch_prices.py -v   # parsing / matching tests
```

## Where the numbers come from

| Provider | Source | Notes |
|---|---|---|
| OpenRouter | `openrouter.ai/api/v1/models` (JSON) | expiry dates and `:free` variants |
| Nous Portal | `inference-api.nousresearch.com/v1/models` (JSON) | the Portal site itself is bot-protected, so the inference API price list is used |
| OpenCode Zen | pricing table on `opencode.ai/docs/zen` (HTML), IDs from `/zen/v1/models` | scraped; fails loudly if the layout changes |
| Command Code | model table on `commandcode.ai/models` (HTML) | scraped; deal and peak-hour notes included |

All prices are USD per 1M tokens. **Blended** = (3 × input + output) / 4, the default sort key.

## Price drops

Offers come straight from each provider (e.g. "50% off"). **Price drops** are detected from this site's own hourly history (`site/data/history.json`), so they appear only after the second hourly run. The history is kept for 90 days.

## Matching models across providers

Names are normalised (provider prefix, dots vs dashes, case). `:free` variants are never matched to paid models. Manual overrides go in `scripts/aliases.json`.

## Caveats

- Scraped sources (Zen, Command Code) can break when the sites change. Check the stale notice.
- Prices are list prices. Check the provider before you commit spend.
