import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

NS = {"atom": "http://www.w3.org/2005/Atom",
      "arxiv": "http://arxiv.org/schemas/atom"}

def fetch(query, start, max_results, sort_by="relevance"):
    q = urllib.parse.quote(query)
    url = ("http://export.arxiv.org/api/query?search_query=" + q +
           f"&start={start}&max_results={max_results}&sortBy={sort_by}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")

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
    cat = ""
    pc = e.find("arxiv:primary_category", NS)
    if pc is not None:
        cat = pc.get("term", "")
    return {
        "id": aid,
        "title": title,
        "abstract": summary,
        "published": published,
        "authors": authors,
        "pdf": pdf,
        "comment": comment,
        "cat": cat,
    }

def parse_feed(xml):
    root = ET.fromstring(xml)
    entries = []
    for e in root.findall("atom:entry", NS):
        try:
            entries.append(parse_entry(e))
        except Exception as ex:
            print("parse err", ex, file=sys.stderr)
    return entries

QUERIES = [
    'all:"automated theorem proving"',
    'all:"interactive theorem proving"',
    'all:"neural theorem proving"',
    'all:"theorem proving" AND all:"language model"',
    'all:"large language model" AND all:"formal proof"',
    'all:"large language model" AND all:"theorem proving"',
    'all:"formal proof"',
    'all:"formal verification"',
    'all:"formal mathematics"',
    'all:"proof assistant"',
    'all:"Lean" AND all:"theorem proving"',
    'all:"Lean 4"',
    'all:"Isabelle"',
    'all:"Coq" AND all:"proof"',
    'all:"HOL4"',
    'all:"proof search" AND all:"theorem"',
    'all:"Monte Carlo tree search" AND all:"proof"',
    'all:"automated reasoning" AND all:"theorem"',
    'all:"superposition" AND all:"theorem"',
    'all:"saturation" AND all:"first-order"',
    'all:"Vampire" AND all:"theorem"',
    'all:"tableau" AND all:"proof"',
    'all:"reinforcement learning" AND all:"theorem proving"',
    'all:"autoformalization"',
    'all:"mathlib"',
    'all:"program verification" AND all:"proof"',
    'all:"proof generation" AND all:"language model"',
]

def main():
    out = {}
    for qi, q in enumerate(QUERIES):
        start = 0
        step = 30
        max_results = 40
        got = 0
        while start < max_results:
            try:
                xml = fetch(q, start, step)
            except Exception as ex:
                print(f"[{qi}] {q}: ERROR {ex}", file=sys.stderr)
                time.sleep(2)
                break
            entries = parse_feed(xml)
            if not entries:
                break
            for e in entries:
                out.setdefault(e["id"], e)
            got += len(entries)
            if len(entries) < step:
                break
            start += step
            time.sleep(1.5)
        print(f"[{qi}] {q}: collected {got}")
        time.sleep(1.5)
    with open("harvest_all.json", "w", encoding="utf-8") as f:
        json.dump(list(out.values()), f, ensure_ascii=False, indent=1)
    print(f"TOTAL unique: {len(out)}")

if __name__ == "__main__":
    main()
