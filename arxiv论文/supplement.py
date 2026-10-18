import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NS = {"atom": "http://www.w3.org/2005/Atom",
      "arxiv": "http://arxiv.org/schemas/atom"}

def parse_entry(e):
    def t(name):
        el = e.find(f"atom:{name}", NS)
        return (el.text or "").strip() if el is not None and el.text else ""
    aid = t("id").split("/abs/")[-1]
    title = re.sub(r"\s+", " ", t("title")).strip()
    summary = re.sub(r"\s+", " ", t("summary")).strip()
    published = t("published")
    authors = [a.find("atom:name", NS).text.strip()
               for a in e.findall("atom:author", NS)
               if a.find("atom:name", NS) is not None and a.find("atom:name", NS).text]
    pdf = ""
    for l in e.findall("atom:link", NS):
        if l.get("title") == "pdf":
            pdf = l.get("href", "")
    comment = ""
    for c in e.findall("arxiv:comment", NS):
        if c.text:
            comment = re.sub(r"\s+", " ", c.text).strip()
    return {"id": aid, "title": title, "abstract": summary, "published": published,
            "authors": authors, "pdf": pdf, "comment": comment, "cat": ""}

def fetch_ids(ids):
    q = urllib.parse.quote(",".join(ids))
    url = f"http://export.arxiv.org/api/query?id_list={q}&max_results={len(ids)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")

IDS = ["2606.08728", "2503.17726", "1912.03028", "2005.12876", "1806.03600",
       "2505.15796", "2205.01981", "1811.00796", "2405.14414", "2402.06064"]

data = json.load(open("harvest_all.json", encoding="utf-8"))
existing = {p["id"].split("v")[0] for p in data}

xml = fetch_ids(IDS)
root = ET.fromstring(xml)
added = 0
for e in root.findall("atom:entry", NS):
    p = parse_entry(e)
    base = p["id"].split("v")[0]
    if base in existing:
        print("already have", base)
        continue
    data.append(p)
    existing.add(base)
    added += 1
    print(f"ADD {p['id']} ({p['published'][:10]}): {p['title']}  // {', '.join(p['authors'][:4])}")

json.dump(data, open("harvest_all.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"added {added}; total now {len(data)}")
