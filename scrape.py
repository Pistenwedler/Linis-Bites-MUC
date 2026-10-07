"""dm-Filialverfuegbarkeit fuer die Laeden aus stores.json -> docs/data.json"""
import json, math, re, datetime, urllib.request, urllib.parse, sys

CENTER = (48.1340, 11.5666)  # Sendlinger Tor, nur fuer Entfernungsanzeige/Suchgebiet
DM_BRAND_URL = "https://www.dm.de/marken/linis-bites-2349676"
DM_FALLBACK = {"3121779": "Vanilla Cookie", "3121805": "Carrot Cake", "3121823": "Tiramisu"}
LINKS = {
    "Rossmann: alle Lini's Bites": "https://www.rossmann.de/de/alle-marken/linis-bites/c/online-dachmarke_17644792",
    "Edeka Marktsuche (kein Bestand abrufbar)": "https://www.edeka.de/marktsuche.jsp",
    "Alnatura Marktfinder (kein Bestand abrufbar)": "https://www.alnatura.de/de-de/maerkte/marktfinder/",
}
UA = {"User-Agent": "Mozilla/5.0 (private hobby tracker)", "Accept": "application/json, text/html"}

def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def get(url): return json.loads(fetch(url))

def norm(s):
    s = str(s).lower().replace("ß", "ss")
    s = re.sub(r"strasse|str\.", "str", s)
    return re.sub(r"[^a-z0-9]", "", s)

def km(lat, lng):
    p = math.pi / 180; la, lo = CENTER
    a = 0.5 - math.cos((lat-la)*p)/2 + math.cos(la*p)*math.cos(lat*p)*(1-math.cos((lng-lo)*p))/2
    return 12742 * math.asin(math.sqrt(a))

def dm_products():
    prods = {}
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
    d = 8 / 111.0  # ~8 km Suchgebiet, damit alle Laeden sicher drin sind
    la, lo = CENTER
    data = get(f"https://store-data-service.services.dmtech.com/stores/bbox/{la-d},{lo-d*1.5},{la+d},{lo+d*1.5}")
    stores = data.get("stores", data) if isinstance(data, dict) else data
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
        found.append({"id": str(hit.get("storeNumber")), "name": label,
                      "dist": round(km(lat, lng), 2) if lat else None})
    return found, unmatched

def dm_availability(stores, prods):
    q = urllib.parse.urlencode({"dans": ",".join(prods), "storeNumbers": ",".join(s["id"] for s in stores)})
    av = get(f"https://products.dm.de/store-availability/DE/availability?{q}")
    av = av.get("storeAvailabilities", av)
    for s in stores:
        s["items"] = {}
        for it in av.get(s["id"], []):
            n = prods.get(str(it.get("dan")))
            if n: s["items"][n] = {"inStock": bool(it.get("inStock")), "level": it.get("stockLevel")}
    return stores

if __name__ == "__main__":
    cfg = json.load(open("stores.json"))
    r = {"updated": datetime.datetime.utcnow().isoformat() + "Z", "dm": [], "dm_error": None,
         "dm_unmatched": [], "links": LINKS}
    try:
        prods = dm_products(); r["dm_products"] = prods
        stores, r["dm_unmatched"] = dm_stores(cfg["dm"])
        r["dm"] = dm_availability(stores, prods) if stores else []
    except Exception as e:
        r["dm_error"] = repr(e); print("dm Fehler:", e, file=sys.stderr)
    json.dump(r, open("docs/data.json", "w"), ensure_ascii=False, indent=1)
    print(len(r["dm"]), "dm-Filialen geprüft; nicht zugeordnet:", r["dm_unmatched"])
