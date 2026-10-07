"""Rossmann: Filialbestand direkt ueber die Rossmann-Filialsuche (XML), kein Browser noetig -> docs/rossmann.json"""
import json, re, sys, time, datetime, urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

def norm(s):
    s = str(s).lower().replace("ß", "ss")
    return re.sub(r"[^a-z0-9]", "", re.sub(r"strasse|str\.", "str", s))

def api(q, dan):
    url = "https://www.rossmann.de/storefinder/.rest/store?" + urllib.parse.urlencode({"q": q, "dan": dan})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/xml, text/xml;q=0.9, */*;q=0.8",
                                               "Accept-Language": "de-DE,de;q=0.9", "Referer": "https://www.rossmann.de/"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def parse(xml):
    out = []
    for st in ET.fromstring(xml).iter("store"):
        g = lambda t: (st.findtext(t) or "").strip()
        pi = st.find("productInfos/productInfo")
        stock = (pi.findtext("stock") or "").strip() if pi is not None else ""
        ok = stock not in ("", "0")
        out.append({"street": g("street"), "plz": g("postcode"), "pickup": g("pickupStation") == "true",
                    "inStock": ok, "text": f"{stock} Stück" if ok else "nicht verfügbar"})
    return out

def check(dan, name, wanted, query):
    res = {"name": name, "dan": dan, "url": "", "stores": [], "missing": []}
    found = {}
    def run(q):
        try:
            for t in parse(api(q, dan)):
                for w in wanted:
                    if norm(w["street"]) == norm(t["street"]): found[norm(w["street"])] = t
        except urllib.error.HTTPError as e:
            res["error"] = f"HTTP {e.code}: " + e.read().decode("utf-8", "replace")[:200]
        except Exception as e:
            res["error"] = repr(e)[:200]
        time.sleep(1)
    run(query)
    for _ in range(2):  # Zusatzsuchen fuer Laeden, die in der ersten Liste fehlen
        miss = [w for w in wanted if norm(w["street"]) not in found]
        if not miss or res.get("error"): break
        run(f"{miss[0]['street']}, {miss[0]['plz']} München")
    res["stores"] = list(found.values())
    res["missing"] = [w["street"] for w in wanted if norm(w["street"]) not in found]
    return res

if __name__ == "__main__":
    cfg = json.load(open("stores.json"))
    out = {"updated": datetime.datetime.utcnow().isoformat() + "Z", "products": [], "error": None}
    for dan, name in cfg["rossmann_products"].items():
        out["products"].append(check(dan, name, cfg["rossmann"], cfg["rossmann_search"]))
    errs = [p["error"] for p in out["products"] if p.get("error")]
    if errs: out["error"] = errs[0]
    json.dump(out, open("docs/rossmann.json", "w"), ensure_ascii=False, indent=1)
    print(len(out["products"]), "Rossmann-Produkte geprüft", "| Fehler:" if errs else "", errs[:1])
