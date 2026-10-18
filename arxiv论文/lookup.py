import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

data = json.load(open("harvest_all.json", encoding="utf-8"))
idx = {}
for p in data:
    base = p["id"].split("v")[0]
    idx.setdefault(base, p)
    idx.setdefault(p["id"], p)

def show(p):
    return (f"{p['id']}  ({p['published'][:10]})\n"
            f"  TITLE: {p['title']}\n"
            f"  AUTH: {', '.join(p['authors'])}\n"
            f"  PDF: {p['pdf']}\n"
            f"  CMT: {p['comment'][:120]}")

for a in sys.argv[1:]:
    key = a
    p = idx.get(key) or idx.get(key.split("v")[0])
    if p:
        print("FOUND:", show(p))
    else:
        print(f"MISSING: {a}")
    print("-" * 70)
