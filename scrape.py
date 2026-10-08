"""dm-Filialverfuegbarkeit fuer die Laeden aus stores.json -> docs/data.json"""
import json, math, re, datetime, urllib.request, urllib.parse, urllib.error, sys

CENTER = (48.1340, 11.5666)  # Sendlinger Tor, nur fuer Entfernungsanzeige/Suchgebiet
DM_BRAND_URL = "https://www.dm.de/marken/linis-bites-2349676"
DM_FALLBACK = {"3121779": "Vanilla Cookie", "3121805": "Carrot Cake", "3121823": "Tiramisu"}
UA = {"User-Agent": "Mozilla/5.0 (private hobby tracker)", "Accept": "application/json, text/html"}

def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", "replace")

DEBUG = []
def get(url):
    try:
        data = json.loads(fetch(url)); DEBUG.append(["ok", url[:170]]); return data
    except urllib.error.HTTPError as e:
        DEBUG.append([e.code, url[:170], e.read().decode("utf-8", "replace")[:200]]); raise
    except Exception as e:
        DEBUG.append(["err", url[:170], repr(e)[:150]]); raise

def norm(s):
    s = str(s).lower().replace("ß", "ss")
    s = re.sub(r"strasse|str\.", "str", s)
    return re.sub(r"[^a-z0-9]", "", s)

def km(lat, lng):
    p = math.pi / 180; la, lo = CENTER
    a = 0.5 - math.cos((lat-la)*p)/2 + math.cos(la*p)*math.cos(lat*p)*(1-math.cos((lng-lo)*p))/2
    return 12742 * math.asin(math.sqrt(a))

def dm_search():
    prods = {}
    try:
        res = get("https://product-search.services.dmtech.com/de/search/static?" +
                  urllib.parse.urlencode({"query": "lini's bites pralinis", "pageSize": 40}))
        for p in res.get("products", []):
            dan = p.get("dan") or p.get("dmid"); t = str(p.get("title") or p.get("name") or "")
            if dan and "lini" in (str(p.get("brandName", "")) + t).lower() and "pralini" in t.lower():
                prods[str(dan)] = re.sub(r"Lini.s Bites|Pralinis|,\s*\d+ g", "", t).strip() or str(dan)
    except Exception as e:
        print("dm Suche:", e, file=sys.stderr)
    return prods

def dm_products():
    prods = dm_search()
    if prods: return {**DM_FALLBACK, **prods}
    try:
        html = fetch(DM_BRAND_URL)
        for dan in dict.fromkeys(re.findall(r"/p/d/(\d{5,8})", html)):
            try: t = re.search(r"<title>(.*?)</title>", fetch(f"https://www.dm.de/p/d/{dan}/"), re.S).group(1)
            except Exception: t = ""
            if "pralini" in t.lower() or not t:
                prods[dan] = re.sub(r"Lini.s Bites|Pralinis|\| dm.*|,\s*\d+ g", "", t).strip() or dan
    except Exception as e:
        print("dm Produktsuche:", e, file=sys.stderr)
    return prods or DM_FALLBACK

def dm_stores(wanted):
    allst = {}
    for la, lo, rad in ((CENTER[0], CENTER[1], 8), (48.1400, 11.5100, 3), (48.1195, 11.5455, 3)):
        try:
            data = get(f"https://store-data-service.services.dmtech.com/stores/nearby/{la:.5f},{lo:.5f}/{rad}?countryCode=DE")
            for x in (data.get("stores", data) if isinstance(data, dict) else data):
                allst[str(x.get("storeNumber"))] = x
        except Exception: continue
    stores = list(allst.values()); DEBUG.append(["dm_stores_gefunden", len(stores)])
    if not stores: raise RuntimeError("keine dm-Filialliste abrufbar (siehe dm_debug)")
    found, unmatched = [], []
    for w in wanted:
        hit = None
        for s in stores:
            blob = norm(" ".join(str(v) for v in (s.get("address") or {}).values()))
            if norm(w["street"]) in blob and norm(w["no"]) in blob and w["plz"] in blob:
                hit = s; break
        label = f"dm {w['street']} {w['no']}"
        if not hit: unmatched.append(label); continue
        loc = hit.get("location", {}); lat, lng = loc.get("lat"), loc.get("lon", loc.get("lng"))
        found.append({"id": str(hit.get("storeNumber")), "sid": str(hit.get("storeId") or ""), "name": label,
                      "dist": round(km(lat, lng), 2) if lat else None})
    return found, unmatched

def find(data, sid):
    """Sucht den Eintrag zu einer Filial-ID in beliebig verschachtelter Antwort."""
    if isinstance(data, dict):
        if sid in data: return data[sid]
        if sid in [str(v) for v in data.values() if isinstance(v, (str, int))]: return data
        for v in data.values():
            r = find(v, sid)
            if r is not None: return r
    elif isinstance(data, list):
        for v in data:
            r = find(v, sid)
            if r is not None: return r
    return None

def judge(v):
    txt = json.dumps(v, ensure_ascii=False).upper()
    ok = "GREEN" in txt or '"INSTOCK": TRUE' in txt
    level = None
    if isinstance(v, dict):
        for k in ("stockLevel", "stock", "quantity", "amount"):
            if isinstance(v.get(k), (int, float)): level = int(v[k]); break
        if level: ok = True
    m = re.search(r"(\d+\+?)\s*Stück", str(v.get("text", "")) if isinstance(v, dict) else "")
    qty = f"{m.group(1)} Stück" if m else (f"{level} Stück" if level else "")
    return {"inStock": ok, "level": level, "text": qty}

def dm_availability(stores, prods):
    ids = ",".join(x["sid"] for x in stores if x.get("sid"))
    for x in stores: x["items"] = {}
    first = True
    for dan, name in prods.items():
        try: data = get(f"https://products.dm.de/availability/api/v2/map/basic/DE/{dan}/{ids}")
        except Exception: continue
        if first: DEBUG.append(["dm_antwort_beispiel", json.dumps(data, ensure_ascii=False)[:700]]); first = False
        for x in stores:
            v = find(data, x["sid"])
            if v is not None: x["items"][name] = judge(v)
    return stores

LINI = "https://linisbites.com"

def pkey(title):
    t = re.sub(r"\(.*?\)", "", str(title))
    t = re.sub(r"bio pralinis|pralinis|–.*|-\s*community edition|community edition|limited edition", "", t, flags=re.I)
    return re.sub(r"[^a-z]", "", t.lower())

def lini():
    """Sorten, Bilder, Online-Status von Lini's Website (Shopify)."""
    prods = []
    try:
        prods = get(f"{LINI}/collections/pralinis/products.json?limit=250").get("products", [])
    except Exception:
        try:
            html = fetch(f"{LINI}/collections/pralinis")
            for h in list(dict.fromkeys(re.findall(r"/products/([a-z0-9\-]+)", html)))[:40]:
                try: prods.append(get(f"{LINI}/products/{h}.js"))
                except Exception: pass
        except Exception as e:
            DEBUG.append(["lini", repr(e)[:150]])
    out = {}
    for p in prods:
        title = p.get("title", ""); k = pkey(title)
        if not k: continue
        img = ""
        if p.get("images"):
            im = p["images"][0]; img = im.get("src", "") if isinstance(im, dict) else str(im)
        img = img or str(p.get("featured_image") or "")
        if img.startswith("//"): img = "https:" + img
        if img: img += ("&" if "?" in img else "?") + "width=400"
        avail = any(v.get("available") for v in p.get("variants", []))
        url = f"{LINI}/products/{p.get('handle')}"
        e = out.setdefault(k, {"name": re.sub(r"Bio Pralinis|\(.*?\)|–.*", "", title).strip(), "image": "", "url": "", "online": None})
        if img and not e["image"]: e["image"] = img
        if "12er" not in title.lower(): e["url"], e["online"] = url, avail
        else:
            if e["online"] is None: e["online"] = avail
            if not e["url"]: e["url"] = url
    DEBUG.append(["lini_sorten", len(out)])
    return out

def build_cards(dm, prods, li, old):
    cards, seen = [], set()
    for dan, name in prods.items():
        k = pkey(name); seen.add(k)
        stores = []
        for s in dm:
            it = s["items"].get(name, {})
            stores.append({"name": s["name"], "dist": s.get("dist"), "inStock": bool(it.get("inStock")), "text": it.get("text", "")})
        stores.sort(key=lambda x: (not x["inStock"], x["dist"] if x["dist"] is not None else 99))
        n = sum(1 for x in stores if x["inStock"]); l = li.get(k, {})
        c = {"name": name, "tracked": True, "count": n, "total": len(stores), "stores": stores,
             "image": l.get("image", ""), "url": l.get("url", ""), "online": l.get("online")}
        if name in old and old[name] == 0 and n > 0: c["new"] = True
        cards.append(c)
    cards.sort(key=lambda c: (-c["count"], c["name"]))
    for k, l in li.items():
        if k not in seen:
            cards.append({"name": l["name"], "tracked": False, "count": 0, "total": 0, "stores": [],
                          "image": l["image"], "url": l["url"], "online": l["online"]})
    return cards

if __name__ == "__main__":
    cfg = json.load(open("stores.json"))
    r = {"updated": datetime.datetime.utcnow().isoformat() + "Z", "dm": [], "dm_error": None,
         "dm_unmatched": [], "links": {"lini": LINI + "/collections/pralinis"}}
    try:
        prods = dm_products(); r["dm_products"] = prods
        stores, r["dm_unmatched"] = dm_stores(cfg["dm"])
        r["dm"] = dm_availability(stores, prods) if stores else []
        if r["dm"] and not any(x["items"] for x in r["dm"]): r["dm_error"] = "Bestandsantwort nicht erkannt (siehe dm_debug)"
    except Exception as e:
        r["dm_error"] = repr(e); print("dm Fehler:", e, file=sys.stderr)
    try: old = {c["name"]: c["count"] for c in json.load(open("docs/data.json")).get("cards", [])}
    except Exception: old = {}
    try: r["cards"] = build_cards(r["dm"], r.get("dm_products", {}), lini(), old)
    except Exception as e: r["cards"] = []; DEBUG.append(["cards", repr(e)[:150]])
    r["dm_debug"] = DEBUG[-20:]
    json.dump(r, open("docs/data.json", "w"), ensure_ascii=False, indent=1)
    print(len(r["dm"]), "dm-Filialen geprüft; nicht zugeordnet:", r["dm_unmatched"])
