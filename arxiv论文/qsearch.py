import sys, re, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
NS = {"atom": "http://www.w3.org/2005/Atom"}

def run(q, n=8):
    url = ("http://export.arxiv.org/api/query?search_query=" +
           urllib.parse.quote(q) + f"&max_results={n}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        xml = r.read().decode("utf-8", "replace")
    root = ET.fromstring(xml)
    print(f"===== {q} =====")
    for e in root.findall("atom:entry", NS):
        t = re.sub(r"\s+", " ", e.find("atom:title", NS).text or "").strip()
        aid = e.find("atom:id", NS).text.split("/abs/")[-1]
        d = (e.find("atom:published", NS).text or "")[:10]
        print(f"{aid} | {d} | {t[:95]}")
    time.sleep(1)

for q in sys.argv[1:]:
    try:
        run(q)
    except Exception as ex:
        print("ERR", q, ex)
