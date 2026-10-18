import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

data = json.load(open("harvest_all.json", encoding="utf-8"))

def year_of(p):
    m = re.match(r"(\d{4})", p.get("published", ""))
    return int(m.group(1)) if m else 0

for p in data:
    p["year"] = year_of(p)

# category keyword weights (on title+abstract, lowercase)
CATS = {
    "survey": [
        "survey", "review", "overview", "a tour", "perspective", "challenge and",
        "state of the art", "roadmap", "retrospective", "bibliography", "tutorial",
    ],
    "traditional": [
        "superposition", "saturation", "resolution", "first-order", "tableau",
        "vampire", "e prover", "tptp", "connection calculus", "instantiation",
        "term rewriting", "rewrite", "unification", "induction", "confluence",
        "knuth-bendix", "ordered resolution", "smt", "sat solver", "satisfiability modulo",
        "automated reasoning", "automated deduction", "resolution calculus",
    ],
    "neural": [
        "neural", "deep learning", "language model", "large language model", "llm",
        "gpt", "transformer", "graph neural network", "machine learning", "chatgpt",
        "foundation model", "natural language", "copilot", "autoformalization",
        "informal", "generative", "llm-based", "neural-symbolic", "neuro-symbolic",
    ],
    "proof_assistant": [
        "lean", "isabelle", "coq", "hol", "mathlib", "proof assistant", "tactic",
        "formalization", "formalised", "formalized", "library", "metaprogramming",
        "dependent type", "type theory", "kernel", "itp", "interactive theorem",
        "proof assistant", "agda", "metamath",
    ],
    "search": [
        "proof search", "monte carlo", "mcts", "tree search", "beam search",
        "best-first", "policy", "planning", "reinforcement learning", "search",
        "exploration", "alpha", "imitation", "best first", "heuristic search",
        "a*", "rrt", "muzero", "alphago",
    ],
    "benchmark": [
        "benchmark", "dataset", "data set", "corpus", "evaluation", "minif2f",
        "proofnet", "benchmarks", "test set", "test suite", "leaderboard",
        "dataset for", "open dataset", "fimo", "compcert benchmark",
    ],
    "application": [
        "verification", "verifier", "security", "hardware", "software",
        "cryptograph", "protocol", "compiler", "operating system", "sel4",
        "smart contract", "program verification", "model checking", "certified",
        "verified", "microkernel", "memory safety", "side-channel", "blockchain",
    ],
}

# manual priority when multiple categories tie (higher first)
PRIORITY = ["benchmark", "survey", "neural", "search", "proof_assistant",
            "traditional", "application"]

def score(p, kw):
    text = (p.get("title", "") + " " + p.get("abstract", "")).lower()
    return sum(1 for k in kw if k in text)

for p in data:
    scores = {c: score(p, kws) for c, kws in CATS.items()}
    best = None
    bs = -1
    for c in PRIORITY:
        s = scores[c]
        if s > bs:
            bs = s
            best = c
    p["cat"] = best
    p["score"] = bs
    p["scores"] = scores

json.dump(data, open("auto_classified.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

os.makedirs("shortlists", exist_ok=True)

# write compact shortlists for review
for c in ["survey", "traditional", "neural", "proof_assistant", "search",
          "benchmark", "application"]:
    cands = [p for p in data if p["cat"] == c]
    cands.sort(key=lambda p: (p["score"], p["year"]), reverse=True)
    lines = [f"===== {c} ({len(cands)}) ====="]
    for p in cands[:60]:
        y = p["year"]
        t = p["title"][:100]
        lines.append(f"{p['id']} | {y} | s={p['score']} | {t}")
    open(f"shortlists/{c}.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"{c}: {len(cands)} candidates (top 60 written)")
