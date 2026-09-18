#!/usr/bin/env python3
"""Cached read-only client for JLCPCB's public SMT-parts search API.

Why not the jlcparts sqlite dump: as of 2026-09-16 the published
https://yaqwsx.github.io/jlcparts/data/cache.zip is a partially bootstrapped
database (148 000 rows, all library_type='expand', all preferred=0, stock>0 on
only 2 907 rows, LCSC ids 6 374 508 and up -- no classic low-numbered Basic
parts). See README.md (component sourcing section).

Endpoint (the one jlcpcb.com/parts itself calls):
  POST https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList
  body {"currentPage":1,"pageSize":N,"keyword":"...",
        "componentLibraryType":"base"|"expand",      # optional filter
        "preferredComponentFlag":true}               # optional filter

Responses are cached under $JLC_CACHE (default ~/.cache/jlcparts/api) keyed by
the request body, so re-running the audit costs no network traffic.

  python3 tools/jlc/jlc_api.py "100nF 0402 X7R 16V" --base
  python3 tools/jlc/jlc_api.py C1525 --raw
"""
import argparse, hashlib, json, os, sys, time, urllib.request, urllib.error

URL = ("https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/"
       "smtGood/selectSmtComponentList")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")
CACHE = os.environ.get("JLC_CACHE", os.path.expanduser("~/.cache/jlcparts/api"))
DELAY = float(os.environ.get("JLC_DELAY", "0.7"))
_last = [0.0]


def _throttle():
    dt = time.time() - _last[0]
    if dt < DELAY:
        time.sleep(DELAY - dt)
    _last[0] = time.time()


def raw_search(keyword, page=1, size=25, library_type=None, preferred=None,
               refresh=False):
    """One API page. Returns the parsed JSON 'data' block."""
    body = {"currentPage": page, "pageSize": size, "keyword": keyword}
    if library_type:
        body["componentLibraryType"] = library_type
    if preferred is not None:
        body["preferredComponentFlag"] = bool(preferred)
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"))
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, hashlib.sha1(blob.encode()).hexdigest() + ".json")
    if os.path.exists(path) and not refresh:
        with open(path) as f:
            return json.load(f)
    _throttle()
    req = urllib.request.Request(
        URL, data=blob.encode(),
        headers={"Content-Type": "application/json", "User-Agent": UA,
                 "Accept": "application/json", "Origin": "https://jlcpcb.com",
                 "Referer": "https://jlcpcb.com/parts"})
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                doc = json.loads(r.read().decode())
            break
        except Exception as e:                                   # noqa: BLE001
            last = e
            time.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError(f"JLC API failed for {blob}: {last}")
    if doc.get("code") != 200:
        raise RuntimeError(f"JLC API code {doc.get('code')}: {doc.get('message')}")
    data = doc["data"]
    data["_query"] = body
    data["_fetched_at"] = int(time.time())
    with open(path, "w") as f:
        json.dump(data, f)
    return data


def price_at(item, qty=10):
    """Unit price at the given order quantity, from componentPrices tiers."""
    for t in item.get("componentPrices") or []:
        lo, hi = t["startNumber"], t["endNumber"]
        if qty >= lo and (hi in (-1, None) or qty <= hi):
            return t["productPrice"]
    tiers = item.get("componentPrices") or []
    return tiers[0]["productPrice"] if tiers else None


def attrs(item):
    return {a["attribute_name_en"]: a["attribute_value_name"]
            for a in (item.get("attributes") or [])}


def norm(item):
    """Flatten one API record to the fields the audit needs."""
    return dict(
        lcsc=item["componentCode"],
        mfr=item.get("componentModelEn") or "",
        brand=item.get("componentBrandEn") or "",
        lib=item.get("componentLibraryType") or "",          # base | expand
        preferred=bool(item.get("preferredComponentFlag")),
        stock=item.get("stockCount") or 0,
        pkg=item.get("componentSpecificationEn") or "",
        desc=item.get("describe") or "",
        price10=price_at(item, 10),
        price1=price_at(item, 1),
        min_qty=item.get("minPurchaseNum"),
        least_patch=item.get("leastPatchNumber"),
        loss=item.get("lossNumber"),
        attrs=attrs(item),
        url="https://jlcpcb.com/partdetail/" + (item.get("urlSuffix") or ""),
    )


def search(keyword, library_type=None, preferred=None, pages=1, size=25,
           refresh=False):
    out = []
    for p in range(1, pages + 1):
        d = raw_search(keyword, page=p, size=size, library_type=library_type,
                       preferred=preferred, refresh=refresh)
        lst = d["componentPageInfo"]["list"] or []
        out += [norm(i) for i in lst]
        if len(out) >= (d["componentPageInfo"]["total"] or 0):
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keyword")
    ap.add_argument("--base", action="store_true", help="Basic library only")
    ap.add_argument("--expand", action="store_true", help="Extended library only")
    ap.add_argument("--preferred", action="store_true", help="Preferred flag only")
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--size", type=int, default=25)
    ap.add_argument("--min-stock", type=int, default=0)
    ap.add_argument("--pkg", default=None, help="require this package string")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--raw", action="store_true")
    a = ap.parse_args()
    lt = "base" if a.base else ("expand" if a.expand else None)
    res = search(a.keyword, library_type=lt, preferred=a.preferred or None,
                 pages=a.pages, size=a.size, refresh=a.refresh)
    res = [r for r in res if r["stock"] >= a.min_stock]
    if a.pkg:
        res = [r for r in res if r["pkg"].lower() == a.pkg.lower()]
    if a.raw:
        json.dump(res, sys.stdout, indent=1)
        return
    res.sort(key=lambda r: (r["lib"] != "base", not r["preferred"], -r["stock"]))
    for r in res:
        flag = "BASIC" if r["lib"] == "base" else ("PREF" if r["preferred"] else "ext")
        pr = f"{r['price10']:.4f}" if r["price10"] is not None else "   -  "
        print(f"{r['lcsc']:<11} {flag:<5} {r['stock']:>9} {pr:>8} "
              f"{r['pkg'][:14]:<14} {r['mfr'][:26]:<26} {r['desc'][:64]}")
    print(f"-- {len(res)} rows", file=sys.stderr)


if __name__ == "__main__":
    main()
