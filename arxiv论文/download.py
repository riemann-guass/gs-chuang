import json
import os
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = "ATP_Papers"
rows = json.load(open("final_list.json", encoding="utf-8"))

# folder name per category
FOLDERS = {}
for r in rows:
    FOLDERS.setdefault(r["cat"], r["folder"])

os.makedirs(ROOT, exist_ok=True)
for c in sorted(FOLDERS):
    os.makedirs(os.path.join(ROOT, FOLDERS[c]), exist_ok=True)

def fetch(url, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research batch)"})
    for k in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as ex:
            code = getattr(ex, "code", None)
            if k == tries - 1:
                raise
            wait = 4 * (k + 1)
            if code == 429:
                wait = 8 * (k + 1)
            time.sleep(wait)

ok, fail, skip = [], [], []
for r in rows:
    if not r["pdf"]:
        skip.append((r["i"], r["title"]))
        continue
    dest = os.path.join(ROOT, FOLDERS[r["cat"]], r["fname"])
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        ok.append((r["i"], r["title"], "cached"))
        continue
    try:
        data = fetch(r["pdf"])
        if len(data) < 1000:
            raise RuntimeError(f"too small ({len(data)} bytes)")
        with open(dest, "wb") as f:
            f.write(data)
        ok.append((r["i"], r["title"], f"{len(data)//1024}KB"))
        print(f"[{r['i']:3d}] OK  {r['fname']}")
    except Exception as ex:
        fail.append((r["i"], r["title"], r["pdf"], str(ex)))
        print(f"[{r['i']:3d}] FAIL {r['fname']} -> {ex}")
    time.sleep(1.2)

print(f"\nOK={len(ok)} FAIL={len(fail)} SKIP={len(skip)}")
if fail:
    print("\n--- FAILED ---")
    for i, t, u, e in fail:
        print(f"{i} | {t} | {u} | {e}")

report = [f"OK={len(ok)} FAIL={len(fail)} SKIP(no pdf)={len(skip)}"]
for i, t, info in ok:
    report.append(f"OK   {i:3d} {info:>8} {t}")
for i, t, u, e in fail:
    report.append(f"FAIL {i:3d} {u} :: {e} :: {t}")
open("download_report.txt", "w", encoding="utf-8").write("\n".join(report) + "\n")
