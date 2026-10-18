import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def clean_tex(s):
    s = s.replace(r"$\heartsuit$", "♥")
    s = re.sub(r"\$[^$]*\$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def slug(s, n=45):
    s = re.sub(r'[<>:"/\\|?*]', "-", s)
    s = re.sub(r"\s+", " ", s).strip().strip(".")
    return s[:n].strip()

CATS = {
    1: ("01_Survey综述", "综述类 Survey/Review"),
    2: ("02_Traditional_ATP传统符号自动定理证明", "传统符号ATP Traditional ATP"),
    3: ("03_Neural_ATP神经定理证明", "神经定理证明 Neural ATP"),
    4: ("04_Proof_Assistant证明助手", "证明助手工程 Proof Assistant"),
    5: ("05_Proof_Search证明搜索算法", "搜索/规划算法 Proof Search"),
    6: ("06_Benchmark_Dataset基准数据集", "基准与数据集 Benchmark/Dataset"),
    7: ("07_Application应用", "应用类 Application"),
}

harvest = json.load(open("harvest_all.json", encoding="utf-8"))
by_base = {}
for p in harvest:
    by_base.setdefault(p["id"].split("v")[0], p)

cur = json.load(open("curated.json", encoding="utf-8"))

rows = []
missing = []
for i, e in enumerate(cur, 1):
    cat = e["cat"]
    folder, label = CATS[cat]
    if e["kind"] == "arxiv":
        base = e["id"].split("v")[0]
        p = by_base.get(base)
        if p is None:
            missing.append(base)
            continue
        title = clean_tex(p["title"])
        authors = ", ".join(p["authors"])
        year = (p["published"] or "")[:4]
        date = (p["published"] or "")[:10]
        ident = f"arXiv:{base}"
        home = f"https://arxiv.org/abs/{base}"
        pdf = f"https://arxiv.org/pdf/{base}"
        fname = f"{i:03d}_{base}.pdf"
        rows.append(dict(i=i, cat=cat, label=label, folder=folder, title=title,
                         authors=authors, date=date, year=year, ident=ident,
                         home=home, pdf=pdf, sum=e["sum"], fname=fname))
    else:
        rows.append(dict(i=i, cat=cat, label=label, folder=folder, title=clean_tex(e["title"]),
                         authors=e["authors"], date=str(e["year"]), year=str(e["year"]),
                         ident=f"DOI:{e['doi']}", home=e["url"], pdf=e.get("pdf", ""),
                         sum=e["sum"],
                         fname=f"{i:03d}_{slug(e['title'])}.pdf"))

if missing:
    print("MISSING ARXIV:", missing)
else:
    print(f"All {len(rows)} entries resolved ({len(cur)} curated).")

json.dump(rows, open("final_list.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- Markdown ----
def md_link(text, url):
    return f"[{text}]({url})" if url else text

lines = []
lines.append("# 自动定理证明（ATP）领域文献清单")
lines.append("")
lines.append(f"共 **{len(rows)} 篇**，来源以 arXiv 为主（93 篇），辅以 7 篇高影响力经典文献（DOI）。")
lines.append("分类：综述 / 传统符号ATP / 神经定理证明 / 证明助手 / 证明搜索 / 基准数据集 / 应用。")
lines.append("")
lines.append("## 目录结构")
lines.append("")
lines.append("```")
lines.append("ATP_Papers/")
for c in range(1, 8):
    lines.append(f"├─ {CATS[c][0]}")
lines.append("└─ 文献清单.md")
lines.append("```")
lines.append("")
lines.append("## 文献总表")
lines.append("")
lines.append("| 序号 | 分类 | 标题 | 作者 | 时间 | 编号/DOI | 主页 | PDF | 一句话摘要 |")
lines.append("|---|---|---|---|---|---|---|---|---|")
for r in rows:
    title = r["title"].replace("|", "\\|")
    auth = r["authors"].replace("|", "\\|")
    s = r["sum"].replace("|", "\\|")
    home = md_link("主页", r["home"])
    pdf = md_link("PDF", r["pdf"]) if r["pdf"] else "—"
    lines.append(f"| {r['i']} | {r['label']} | {title} | {auth} | {r['date']} | {r['ident']} | {home} | {pdf} | {s} |")

lines.append("")
lines.append("## 批量下载 PDF 链接（可直接整段复制）")
lines.append("")
for r in rows:
    if r["pdf"]:
        lines.append(r["pdf"])
lines.append("")

open("final_list.md", "w", encoding="utf-8").write("\n".join(lines))

# ---- batch download urls (one per line) ----
urls = [r["pdf"] for r in rows if r["pdf"]]
open("download_urls.txt", "w", encoding="utf-8").write("\n".join(urls) + "\n")

print(f"wrote final_list.md ({len(rows)} rows), download_urls.txt ({len(urls)} urls)")
