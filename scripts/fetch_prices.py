#!/usr/bin/env python3
"""Fetch model prices from OpenCode Zen, Nous Portal, and OpenRouter.

Standard library only. Writes, under site/data/:
  zen.json, nous.json, openrouter.json  per-provider tables
  common.json                                               cross-provider matches
  meta.json                                                 sync status per provider
  history.json                                              price change log (drives "price drop")

All prices are normalised to USD per 1M tokens.
A provider that fails keeps its last good file and is flagged stale in meta.json.
Exit code is non-zero only when every provider failed.
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data"
ALIASES = ROOT / "scripts" / "aliases.json"

UA = "Mozilla/5.0 (model-price-compare; +https://github.com/) Python-urllib"
HISTORY_DAYS = 90          # change log retention
DROP_WINDOW_DAYS = 7       # "price drop" look-back
NEW_WINDOW_DAYS = 7        # "new model" look-back

PROVIDERS = {
    "zen": {"name": "OpenCode Zen", "url": "https://opencode.ai/docs/zen/"},
    "nous": {"name": "Nous Portal", "url": "https://portal.nousresearch.com/"},
    "openrouter": {"name": "OpenRouter", "url": "https://openrouter.ai/models"},
}


# ----------------------------------------------------------------- fetch utils
def get(url: str, *, tries: int = 3, timeout: int = 40) -> str:
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001 - retry any network error
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


def per_m(v) -> float | None:
    """OpenRouter-style per-token string -> USD per 1M tokens."""
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f < 0:  # routers report -1 = variable
        return None
    return round(f * 1_000_000, 6)


MONEY = re.compile(r"\$\s*([0-9]*\.?[0-9]+)")


def money(text: str) -> float | None:
    t = (text or "").strip()
    if not t or t in {"-", "—", "–"}:
        return None
    if t.lower().startswith("free"):
        return 0.0
    m = MONEY.search(t)
    return float(m.group(1)) if m else None


def blended(inp, out):
    """3:1 input:output blend, the default sort key."""
    if inp is None or out is None:
        return None
    return round((3 * inp + out) / 4, 6)


def strip_tags(s: str) -> str:
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


# ------------------------------------------------------------ model matching
_aliases: dict = {}


def load_aliases():
    global _aliases
    if ALIASES.exists():
        _aliases = json.loads(ALIASES.read_text(encoding="utf-8"))


def match_key(provider: str, raw_id: str) -> str:
    """Canonical cross-provider key. 'anthropic/claude-opus-5.5' and 'claude-opus-5-5'
    both become 'claudeopus55'. Free variants keep a ':free' tag so a free tier never
    matches the paid model. Other variants (':batch', ':nitro', regions) keep their tag."""
    over = _aliases.get(provider, {}).get(raw_id)
    if over:
        return over
    s = raw_id.lower().strip()
    s = s.split("/")[-1]
    variant = ""
    if ":" in s:
        s, variant = s.split(":", 1)
    if re.search(r"[-_ ]free$", s):
        s = re.sub(r"[-_ ]free$", "", s)
        variant = "free"
    s = re.sub(r"\((latest|exp|preview)\)", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    if variant:
        s += ":" + re.sub(r"[^a-z0-9]", "", variant)
    return _aliases.get("_global", {}).get(s, s)


def kind_of(arch: dict | None) -> str:
    outs = (arch or {}).get("output_modalities") or []
    if "embeddings" in outs:
        return "embedding"
    if "image" in outs:
        return "image"
    if "audio" in outs and "text" not in outs:
        return "audio"
    if "text" in outs or not outs:
        return "text"
    return outs[0]


def row(**kw) -> dict:
    r = {
        "id": kw["id"], "name": kw.get("name") or kw["id"], "key": kw["key"],
        "ctx": kw.get("ctx"), "in": kw.get("inp"), "out": kw.get("out"),
        "cr": kw.get("cr"), "cw": kw.get("cw"),
        "kind": kw.get("kind", "text"), "tiered": kw.get("tiered"),
        "note": kw.get("note"), "offer": kw.get("offer"), "url": kw.get("url"),
        "expires": kw.get("expires"),
    }
    r["blend"] = blended(r["in"], r["out"])
    r["free"] = r["in"] == 0 and r["out"] == 0
    return r


# ----------------------------------------------------------- OpenRouter / Nous
def parse_or_style(provider: str, url: str, link_tpl: str) -> list[dict]:
    data = json.loads(get(url))["data"]
    rows = []
    for m in data:
        p = m.get("pricing") or {}
        inp, out = per_m(p.get("prompt")), per_m(p.get("completion"))
        offer = None
        orig = p.get("original")
        if isinstance(orig, dict):
            oi, oo = per_m(orig.get("prompt")), per_m(orig.get("completion"))
            ob, nb = blended(oi, oo), blended(inp, out)
            if ob and nb is not None and nb < ob:
                offer = {"label": f"{round(100 * (1 - nb / ob))}% off",
                         "pct": round(100 * (1 - nb / ob)),
                         "was": {"in": oi, "out": oo, "cr": per_m(orig.get("input_cache_read"))}}
        tiered = None
        ov = p.get("overrides")
        if isinstance(ov, list) and ov:
            o = ov[0]
            tiered = {"above": o.get("min_prompt_tokens"),
                      "in": per_m(o.get("prompt")), "out": per_m(o.get("completion"))}
        mid = m["id"]
        is_free = mid.endswith(":free")
        if is_free and not offer:
            offer = {"label": "free", "pct": 100, "was": None}  # one label everywhere: a free tier is a price, not a deal
        rows.append(row(
            id=mid, name=m.get("name"), key=match_key(provider, mid),
            ctx=m.get("context_length"), inp=inp, out=out,
            cr=per_m(p.get("input_cache_read")), cw=per_m(p.get("input_cache_write")),
            kind=kind_of(m.get("architecture")), tiered=tiered, offer=offer,
            url=link_tpl.format(id=mid.split(":")[0]),
            expires=m.get("expiration_date"),
        ))
    return rows


def fetch_openrouter():
    return parse_or_style("openrouter", "https://openrouter.ai/api/v1/models",
                          "https://openrouter.ai/{id}")


def fetch_nous():
    return parse_or_style("nous", "https://inference-api.nousresearch.com/v1/models",
                          "https://portal.nousresearch.com/models")


# ------------------------------------------------------------------ Zen
def html_tables(page: str) -> list[list[list[str]]]:
    """Return every <table> as rows of raw cell HTML."""
    out = []
    for tb in re.findall(r"<table.*?</table>", page, flags=re.S):
        rows = []
        for tr in re.findall(r"<tr.*?</tr>", tb, flags=re.S):
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)
            rows.append(cells)
        out.append(rows)
    return out


def split_was(cell: str) -> tuple[float | None, float | None]:
    """'<del>$1.36</del> $0.68' -> (now=0.68, was=1.36). Works for <del> and <s>."""
    m = re.search(r"<(del|s)\b[^>]*>(.*?)</\1>", cell, flags=re.S)
    if m:
        was = money(strip_tags(m.group(2)))
        now = money(strip_tags(cell[:m.start()] + cell[m.end():]))
        return now, was
    return money(strip_tags(cell)), None


def fetch_zen() -> list[dict]:
    page = get("https://opencode.ai/docs/zen/")
    tables = html_tables(page)
    ids, price_tbl = {}, None
    for t in tables:
        head = [strip_tags(c).lower() for c in (t[0] if t else [])]
        if "model id" in head:
            for r in t[1:]:
                if len(r) >= 2:
                    ids[strip_tags(r[0])] = strip_tags(r[1])
        elif head[:3] == ["model", "input", "output"]:
            price_tbl = t
    if not price_tbl:
        raise RuntimeError("zen: pricing table not found (page layout changed?)")
    live = {m["id"] for m in json.loads(get("https://opencode.ai/zen/v1/models"))["data"]}

    def resolve(name: str) -> str:
        if name in ids:
            return ids[name]
        base = re.sub(r"\s+free$", "", name, flags=re.I)
        if base != name and base in ids:
            return ids[base] + "-free"
        guess = re.sub(r"[^a-z0-9.]+", "-", name.lower()).strip("-")
        for cand in (guess, guess.replace(".", "-")):
            if cand in live:
                return cand
        return guess

    rows: dict[str, dict] = {}
    for r in price_tbl[1:]:
        if len(r) < 4:
            continue
        label = strip_tags(r[0])
        pct = re.search(r"\((\d+)%\s*off\)", label, flags=re.I)
        tier = re.search(r"\((≤|<=|>|&gt;)\s*([\d.]+)\s*K tokens\)", label)
        name = re.sub(r"\s*\(.*?\)\s*", " ", label).strip()
        inp, wi = split_was(r[1])
        out, wo = split_was(r[2])
        cr, wc = split_was(r[3])
        cw = split_was(r[4])[0] if len(r) > 4 else None
        mid = resolve(name)
        if tier and tier.group(1) not in ("≤", "<="):   # upper context band
            if mid in rows:
                rows[mid]["tiered"] = {"above": int(float(tier.group(2)) * 1000), "in": inp, "out": out}
            continue
        offer = None
        if wi is not None or wo is not None:
            p = int(pct.group(1)) if pct else None
            ob, nb = blended(wi, wo), blended(inp, out)
            if p is None and ob and nb is not None:
                p = round(100 * (1 - nb / ob))
            offer = {"label": f"{p}% off" if p else "discount", "pct": p, "was": {"in": wi, "out": wo, "cr": wc}}
        elif inp == 0 and out == 0:
            offer = {"label": "free", "pct": 100, "was": None}
        if mid in rows:  # duplicate display name (e.g. 'Jev 1.13' free + paid)
            mid = mid + ("-free" if inp == 0 and out == 0 else "-paid")
        rows[mid] = row(id=mid, name=name, key=match_key("zen", mid), inp=inp, out=out, cr=cr, cw=cw,
                        offer=offer, url="https://opencode.ai/docs/zen/#pricing")
    for m in rows.values():
        m["listed"] = m["id"] in live
    return list(rows.values())


# ------------------------------------------------------------- history & drops
def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def update_history(hist: dict, provider: str, rows: list[dict], ts: str) -> None:
    ph = hist.setdefault(provider, {"since": ts, "models": {}})
    models = ph["models"]
    cutoff = parse_iso(ts) - timedelta(days=HISTORY_DAYS)
    for r in rows:
        point = [ts, r["in"], r["out"], r["cr"]]
        h = models.setdefault(r["id"], {"first": ts, "pts": []})
        if not h["pts"] or h["pts"][-1][1:] != point[1:]:
            h["pts"].append(point)
        h["seen"] = ts
        # keep the newest point older than the cutoff so the series still has a baseline
        old = [p for p in h["pts"] if parse_iso(p[0]) < cutoff]
        if len(old) > 1:
            h["pts"] = h["pts"][len(old) - 1:]


def annotate(hist: dict, provider: str, rows: list[dict], ts: str) -> None:
    ph = hist.get(provider, {})
    since = parse_iso(ph.get("since", ts))
    now = parse_iso(ts)
    for r in rows:
        h = ph.get("models", {}).get(r["id"])
        if not h:
            continue
        pts = h["pts"]
        r["spark"] = [blended(p[1], p[2]) for p in pts[-24:]]
        first = parse_iso(h["first"])
        # 'new' only when the model appeared after we started watching this provider
        if first > since + timedelta(hours=2) and now - first <= timedelta(days=NEW_WINDOW_DAYS):
            r["new"] = h["first"]
        # price drop: latest change inside the window lowered the blended price
        if len(pts) >= 2:
            cur, prev = pts[-1], pts[-2]
            when = parse_iso(cur[0])
            bc, bp = blended(cur[1], cur[2]), blended(prev[1], prev[2])
            if bc is not None and bp and now - when <= timedelta(days=DROP_WINDOW_DAYS):
                pct = round(100 * (1 - bc / bp))
                # moves under 1% are noise (a '0% drop' label reads as a bug); flag only real moves
                if bc < bp and pct >= 1:
                    r["drop"] = {"at": cur[0], "pct": pct, "was": {"in": prev[1], "out": prev[2]}}
                elif bc > bp and pct <= -1:
                    r["rise"] = {"at": cur[0], "pct": pct, "was": {"in": prev[1], "out": prev[2]}}


# ------------------------------------------------------------------- common
def build_common(tables: dict[str, list[dict]]) -> list[dict]:
    by_key: dict[str, dict] = {}
    for prov, rows in tables.items():
        for r in rows:
            if r.get("kind") != "text" or r.get("blend") is None:
                continue
            k = r["key"]
            slot = by_key.setdefault(k, {"key": k, "name": r["name"], "p": {}})
            cur = slot["p"].get(prov)
            # several rows can share a key inside one provider: keep the cheapest
            if cur is None or (r["blend"] < cur["blend"]):
                slot["p"][prov] = {f: r.get(f) for f in
                                   ("id", "in", "out", "cr", "blend", "offer", "drop", "url", "note")}
            # prefer the cleanest display name (no 'Vendor:' prefix)
            if ":" in slot["name"] and ":" not in r["name"]:
                slot["name"] = r["name"]
    out = []
    for slot in by_key.values():
        n = len(slot["p"])
        if n < 2:
            continue
        prices = {k: v["blend"] for k, v in slot["p"].items()}
        lo = min(prices.values())
        hi = max(prices.values())
        slot["n"] = n
        slot["best"] = sorted(k for k, v in prices.items() if v == lo)
        slot["min"] = lo
        slot["max"] = hi
        slot["spread"] = round(100 * (1 - lo / hi)) if hi else 0
        out.append(slot)
    out.sort(key=lambda s: (-s["n"], s["min"]))
    return out


# --------------------------------------------------------------------- main
def write(name: str, obj) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = DATA / (name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(DATA / name)


def read(name: str, default):
    p = DATA / name
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return default


def main() -> int:
    load_aliases()
    ts = now_iso()
    meta = read("meta.json", {"providers": {}})
    hist = read("history.json", {})
    fetchers = {"zen": fetch_zen, "nous": fetch_nous, "openrouter": fetch_openrouter}
    tables: dict[str, list[dict]] = {}
    ok = 0
    for prov, fn in fetchers.items():
        pm = meta["providers"].setdefault(prov, {})
        pm.update(name=PROVIDERS[prov]["name"], url=PROVIDERS[prov]["url"])
        t0 = time.time()
        try:
            rows = fn()
            update_history(hist, prov, rows, ts)
            annotate(hist, prov, rows, ts)
            rows.sort(key=lambda r: (r["blend"] is None, r["blend"] if r["blend"] is not None else 0, r["name"].lower()))
            doc = {"provider": prov, "name": PROVIDERS[prov]["name"], "fetched": ts, "models": rows}
            write(f"{prov}.json", doc)
            tables[prov] = rows
            pm.update(ok=True, fetched=ts, count=len(rows), error=None,
                      ms=int(1000 * (time.time() - t0)),
                      text=sum(1 for r in rows if r["kind"] == "text"),
                      # same definition as the site's rail: a plain free tier is not an offer
                      offers=sum(1 for r in rows if r.get("offer") and r["offer"].get("label") != "free"),
                      drops=sum(1 for r in rows if r.get("drop")),
                      free=sum(1 for r in rows if r.get("free")))
            ok += 1
            print(f"[ok]   {prov:12s} {len(rows):4d} models  {pm['ms']} ms")
        except Exception as e:  # noqa: BLE001 - keep last good data for this provider
            pm.update(ok=False, error=str(e)[:300], failed=ts)
            prev = read(f"{prov}.json", None)
            if prev:
                tables[prov] = prev["models"]
            print(f"[FAIL] {prov:12s} {e}", file=sys.stderr)
    if ok == 0:
        print("all providers failed; nothing written", file=sys.stderr)
        return 1
    common = build_common(tables)
    write("common.json", {"fetched": ts, "providers": list(fetchers), "models": common})
    meta["synced"] = ts
    meta["schedule"] = "hourly at :17 UTC (GitHub Actions cron)"
    meta["providers"].pop("commandcode", None)
    write("meta.json", meta)
    hist.pop("commandcode", None)
    write("history.json", hist)
    n3 = sum(1 for c in common if c["n"] == 3)
    print(f"[ok]   common       {n3} on all three, {len(common)} on two or more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
