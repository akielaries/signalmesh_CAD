import sys, json, subprocess
def q(kw, n=6):
    d = json.dumps({"keyword": kw, "currentPage": 1, "pageSize": n})
    out = subprocess.run(["curl","-s","-m","25","-A","Mozilla/5.0","-H","Content-Type: application/json","-X","POST",
        "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList","-d",d],capture_output=True,text=True).stdout
    try:
        j = json.loads(out)
        lst = j["data"]["componentPageInfo"]["list"] or []
    except Exception as e:
        print(kw, "ERR", out[:200]); return
    print("== %s (total %s)" % (kw, j["data"]["componentPageInfo"]["total"]))
    for c in lst:
        p = c.get("componentPrices") or []
        p1 = p[0]["productPrice"] if p else None
        print("  %s | %s | %s | %s | stock %s | %s | $%s | %s" % (c["componentCode"], c["componentModelEn"], c.get("componentBrandEn"), c.get("componentSpecificationEn"), c["stockCount"], c["componentLibraryType"], p1, (c.get("describe") or "")[:70]))
for kw in sys.argv[1:]:
    q(kw)
