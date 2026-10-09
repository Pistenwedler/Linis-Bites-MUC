"""dm-Filialverfuegbarkeit fuer die Laeden aus stores.json -> docs/data.json"""
import json, math, os, re, time, datetime, urllib.request, urllib.parse, urllib.error, sys

CENTER = (48.13333, 11.53361)  # Heimeranplatz (Wikipedia, S-/U-Bahnhof): Ausgangspunkt fuer die Entfernungen
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

def dm_match(stores, w):
    for s in stores:
        blob = norm(" ".join(str(v) for v in (s.get("address") or {}).values()))
        if norm(w["street"]) in blob and norm(w["no"]) in blob and w["plz"] in blob:
            return s
    return None

def dm_list(text):
    """dm-Filialsuche nach Adresse (wie im Dialog auf dm.de)."""
    url = ("https://store-data-service.services.dmtech.com/stores/list/DE/0/10?addressPrefix=" +
           urllib.parse.quote_plus(text) + "&fields=storeId,storeNumber,address,storeUrlPath,location")
    data = get(url)
    return data.get("stores", data) if isinstance(data, dict) else data

def dm_stores(wanted):
    """Jede Wunschfiliale wird einzeln ueber ihre Adresse gesucht (unabhaengig vom Entfernungs-Ausgangspunkt)."""
    allst, hits = {}, {}
    for w in wanted:
        try:
            for x in dm_list(f"{w['street']} {w['no']}, {w['plz']} München"):
                allst[str(x.get("storeNumber"))] = x
        except Exception: pass
        hits[w["street"] + w["no"]] = dm_match(list(allst.values()), w)
    if any(v is None for v in hits.values()):   # Reserve: Umkreissuche
        for la, lo, rad in ((CENTER[0], CENTER[1], 8), (48.1400, 11.5100, 3), (48.1195, 11.5455, 3), (48.1185, 11.5800, 3)):
            try:
                data = get(f"https://store-data-service.services.dmtech.com/stores/nearby/{la:.5f},{lo:.5f}/{rad}?countryCode=DE")
                for x in (data.get("stores", data) if isinstance(data, dict) else data):
                    allst[str(x.get("storeNumber"))] = x
            except Exception: continue
    stores = list(allst.values()); DEBUG.append(["dm_stores_gefunden", len(stores)])
    if not stores: raise RuntimeError("keine dm-Filialliste abrufbar (siehe dm_debug)")
    found, unmatched = [], []
    for w in wanted:
        hit = dm_match(stores, w)
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
    """Pro Sorte eine Abfrage (mit Wiederholung). Gibt (stores, fehlgeschlagene Sorten) zurueck."""
    ids = ",".join(x["sid"] for x in stores if x.get("sid"))
    for x in stores: x["items"] = {}
    failed, first = [], True
    for dan, name in prods.items():
        data = None
        for attempt in range(3):
            try: data = get(f"https://products.dm.de/availability/api/v2/map/basic/DE/{dan}/{ids}"); break
            except Exception: time.sleep(2)
        if data is None: failed.append(name); continue
        if first: DEBUG.append(["dm_antwort_beispiel", json.dumps(data, ensure_ascii=False)[:700]]); first = False
        found = 0
        for x in stores:
            v = find(data, x["sid"])
            if v is not None: x["items"][name] = judge(v); found += 1
        if not found: failed.append(name)
    return stores, failed

def dm_diag(stores, prods):
    """Einmal-Diagnose (Workflow mit Haken 'Diagnose'): wo steckt die Stueckzahl pro Filiale?"""
    st = next((x for x in stores if x.get("sid") == "D5A3"), stores[0]); sid = st["sid"]
    dans = ",".join(prods); d0 = next(iter(prods))
    urls = [f"https://products.dm.de/availability/api/v2/tiles/DE/{dans}?storeId={sid}",
            f"https://products.dm.de/availability/api/v2/tiles/DE/{dans}?storeIds={sid}",
            f"https://products.dm.de/availability/api/v2/tiles/DE/{dans}?storeNumber={st['id']}",
            f"https://products.dm.de/availability/api/v2/map/detail/DE/{d0}/{sid}",
            "https://product-search.services.dmtech.com/de/search/static?" + urllib.parse.urlencode(
                {"query": "lini's bites", "brandName": "Lini's Bites", "storeIdsWithAvailability": sid, "pageSize": 40})]
    out = [["store", st["name"], sid]]
    for u in urls:
        try: out.append([u[:230], fetch(u)[:900]])
        except Exception as e: out.append([u[:230], repr(e)[:120]])
    return out

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

HIST = "docs/history.json"

def update_history(dm, prods):
    """Haelt nur Aenderungen fest: [Minute, Sorte, Filiale, 1=da/0=weg, (1=Startwert)]."""
    try: h = json.load(open(HIST))
    except Exception: h = {"v": 1, "first": None, "products": [], "stores": [], "cur": {}, "events": []}
    now = int(datetime.datetime.utcnow().timestamp() // 60)
    if h["first"] is None: h["first"] = now
    def idx(lst, x):
        if x not in lst: lst.append(x)
        return lst.index(x)
    for name in prods.values():
        pi = idx(h["products"], name)
        for s in dm:
            si = idx(h["stores"], s["name"]); k = f"{pi}|{si}"
            v = 1 if s["items"].get(name, {}).get("inStock") else 0
            if k not in h["cur"]:
                h["cur"][k] = v
                if v: h["events"].append([now, pi, si, 1, 1])
            elif h["cur"][k] != v:
                h["cur"][k] = v; h["events"].append([now, pi, si, v])
    json.dump(h, open(HIST, "w"), separators=(",", ":"))

def ntfy(title, msg, click=None, prio=3, tags=None):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        print("ntfy: NTFY_TOPIC nicht gesetzt, keine Push-Nachricht"); return
    body = {"topic": topic, "title": title, "message": msg, "priority": prio, "tags": tags or []}
    click = click or os.environ.get("DASHBOARD_URL", "").strip()
    if click: body["click"] = click
    req = urllib.request.Request("https://ntfy.sh", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=20).read(); print("ntfy gesendet:", title)
    except Exception as e: print("ntfy Fehler:", e, file=sys.stderr)

def compute_events(old_cards, new_cards):
    oc = {c["name"]: c for c in old_cards}; ev = []
    for c in new_cards:
        o = oc.get(c["name"])
        if not o: continue
        if c.get("tracked") and o.get("tracked") and o.get("count", 0) == 0 and c["count"] > 0:
            ins = [x for x in c["stores"] if x["inStock"]]
            shown = ", ".join(x["name"].replace("dm ", "", 1) + (f" ({x['text']})" if x.get("text") else "") for x in ins[:4])
            more = f" und {len(ins) - 4} weitere" if len(ins) > 4 else ""
            ev.append({"title": f"🍫 {c['name']} ist wieder da", "msg": f"dm: {shown}{more}", "prio": 4,
                       "tags": ["chocolate_bar"]})
        if o.get("online") is False and c.get("online") is True:
            ev.append({"title": f"🛒 {c['name']} wieder im Online-Shop", "msg": "Bei Lini's wieder bestellbar.",
                       "click": c.get("url"), "prio": 3, "tags": ["shopping_cart"]})
    return ev

def send_events(ev):
    if len(ev) > 4:
        ntfy(f"🍫 {len(ev)} Neuigkeiten bei Lini's Bites", "; ".join(e["title"].split(" ", 1)[1] for e in ev)[:400], prio=4)
    else:
        for e in ev: ntfy(e["title"], e["msg"], e.get("click"), e.get("prio", 3), e.get("tags"))

if __name__ == "__main__":
    cfg = json.load(open("stores.json"))
    r = {"updated": datetime.datetime.utcnow().isoformat() + "Z", "dm": [], "dm_error": None,
         "dm_unmatched": [], "links": {"lini": LINI + "/collections/pralinis"}}
    try:
        prods = dm_products(); r["dm_products"] = prods
        stores, r["dm_unmatched"] = dm_stores(cfg["dm"])
        r["dm"], r["dm_partial"] = dm_availability(stores, prods) if stores else ([], [])
        if os.environ.get("DM_DIAG") == "true" and stores: r["dm_diag"] = dm_diag(stores, prods)
        if r["dm"] and not any(x["items"] for x in r["dm"]): r["dm_error"] = "Bestandsantwort nicht erkannt (siehe dm_debug)"
    except Exception as e:
        r["dm_error"] = repr(e); print("dm Fehler:", e, file=sys.stderr)
    try: old_data = json.load(open("docs/data.json"))
    except Exception: old_data = {}
    old_cards = old_data.get("cards", [])
    old = {c["name"]: c["count"] for c in old_cards}
    events = []
    if r["dm_error"]:
        # Bei dm-Fehler alten Stand behalten, damit es keine falschen "wieder da"-Meldungen gibt
        if old_cards:
            r["dm_error"] += " - zeige Stand von " + str(old_data.get("updated", "?"))[:16].replace("T", " ") + " UTC"
            r["cards"] = old_cards
        else: r["cards"] = []
        if not old_data.get("dm_error"):
            ntfy("⚠️ dm-Abfrage fehlgeschlagen", str(r["dm_error"])[:200], prio=3, tags=["warning"])
    else:
        try:
            partial = set(r.get("dm_partial", []))
            oc = {c["name"]: c for c in old_cards}
            r["cards"] = [dict(oc[c["name"]], stale=True) if c["name"] in partial and c["name"] in oc else c
                          for c in build_cards(r["dm"], r.get("dm_products", {}), lini(), old)]
            if old_cards: events = compute_events(old_cards, r["cards"])
            try: update_history(r["dm"], {d: n for d, n in r.get("dm_products", {}).items() if n not in partial})
            except Exception as e: DEBUG.append(["history", repr(e)[:150]])
        except Exception as e: r["cards"] = old_cards; DEBUG.append(["cards", repr(e)[:150]])
    r["dm_debug"] = DEBUG[-40:]
    json.dump(r, open("docs/data.json", "w"), ensure_ascii=False, indent=1)
    if os.environ.get("NTFY_TEST") == "true":
        ntfy("✅ Test erfolgreich", "Push-Nachrichten vom Lini's Bites Tracker funktionieren.", prio=3, tags=["white_check_mark"])
    send_events(events)
    print(len(r["dm"]), "dm-Filialen geprüft; nicht zugeordnet:", r["dm_unmatched"])
