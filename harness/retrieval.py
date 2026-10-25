"""引理检索：Loogle 的公开 JSON 接口。

## 为什么是 Loogle

* 公开、**不需要 key**（Numina-Lean-Agent 用 LeanExplore，但要 API key）；
* 支持「名字片段」和「类型模式」两种查询，正好补我们缺的**定位 gap**；
* 返回结构化 JSON，便于离线测试。

## 设计约束

* **离线/超时/限流一律返回空列表**，绝不抛异常——检索只是锦上添花，
  不能因为它挂掉拖死主循环（这是 2026-10-24 那次 60 题终审超时事故的教训）；
* 磁盘缓存，避免同一 query 反复打网络；
* 只返回 `name / type / module`，不返回完整签名，控制 prompt 体积。
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from . import config

#: Lean 标识符（用于从目标里抽查询词）
_IDENT_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_']+)+)\b")
#: 常见的无信息前缀，抽查询词时跳过
_NOISE = frozenset({"Lean", "Mathlib", "Init", "Std"})


@dataclass
class LemmaHit:
    name: str
    type: str = ""
    module: str = ""

    def render(self) -> str:
        t = (self.type or "").strip()
        if len(t) > 120:
            t = t[:120] + "…"
        return f"- `{self.name}`" + (f" : {t}" if t else "")


@dataclass
class RetrievalResult:
    queries: list[str] = field(default_factory=list)
    hits: list[LemmaHit] = field(default_factory=list)
    failed: int = 0

    def as_prompt_block(self, limit: int = 5) -> str:
        seen: set[str] = set()
        lines: list[str] = []
        for h in self.hits:
            if h.name in seen:
                continue
            seen.add(h.name)
            lines.append(h.render())
            if len(lines) >= limit:
                break
        return "\n".join(lines)

    def as_record(self) -> dict:
        return {"queries": len(self.queries), "hits": len(self.hits), "failed": self.failed}


def extract_query_terms(*texts: str, limit: int = 2) -> list[str]:
    """从目标/诊断里抽可检索的标识符（如 `Real.log`, `Finset.sum_sub_distrib`）。"""
    out: list[str] = []
    for text in texts:
        for m in _IDENT_RE.finditer(text or ""):
            name = m.group(1)
            if name.split(".")[0] in _NOISE:
                continue
            if name not in out:
                out.append(name)
            if len(out) >= limit:
                return out
    return out


class _Cache:
    """极简 JSONL 缓存：query → hits。"""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or config.RETRIEVAL_CACHE)
        self.data: dict[str, list[dict]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                self.data[rec["q"]] = rec["hits"]
        except Exception:  # noqa: BLE001 缓存坏了就当没有
            self.data = {}

    def get(self, q: str) -> list[dict] | None:
        return self.data.get(q)

    def put(self, q: str, hits: list[dict]) -> None:
        self.data[q] = hits
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"q": q, "hits": hits}, ensure_ascii=False) + "\n")
        except OSError:
            pass


class LoogleClient:
    """Loogle 查询客户端；所有失败都降级为空结果。"""

    def __init__(
        self,
        *,
        url: str | None = None,
        timeout_s: float | None = None,
        cache: _Cache | None = None,
    ) -> None:
        self.url = url or config.LOOGLE_URL
        self.timeout_s = timeout_s or config.RETRIEVAL_TIMEOUT_S
        self.cache = cache if cache is not None else _Cache()

    def search(self, query: str, *, limit: int = 5) -> list[LemmaHit]:
        q = (query or "").strip()
        if not q:
            return []
        cached = self.cache.get(q)
        if cached is not None:
            return [LemmaHit(**h) for h in cached[:limit]]
        payload = self._fetch(q)
        if payload is None:
            return []
        hits = [
            LemmaHit(
                name=str(h.get("name", "")),
                type=str(h.get("type", "")),
                module=str(h.get("module", "")),
            )
            for h in payload
            if h.get("name")
        ]
        self.cache.put(q, [{"name": h.name, "type": h.type, "module": h.module} for h in hits])
        return hits[:limit]

    def _fetch(self, q: str) -> list[dict] | None:
        url = f"{self.url}?q={urllib.parse.quote(q)}"
        # **必须带 User-Agent**：Loogle 对默认的 `Python-urllib/x.y` 直接拒绝
        # （实测没有 UA 时返回空，加上 UA 立刻 200）。
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "dsh-lean-harness/0.6", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310
                if getattr(resp, "status", 200) != 200:
                    return None
                data = json.loads(resp.read().decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001 网络/解析错误都当"没有结果"
            return None
        hits = data.get("hits")
        return hits if isinstance(hits, list) else None

    def retrieve_for(self, *, terms: list[str], max_queries: int | None = None) -> RetrievalResult:
        """按候选词逐个查，去重后返回。"""
        result = RetrievalResult()
        budget = max_queries if max_queries is not None else config.RETRIEVAL_MAX_QUERIES
        for term in terms[:budget]:
            result.queries.append(term)
            hits = self.search(term, limit=config.RETRIEVAL_MAX_HITS)
            if not hits:
                result.failed += 1
            result.hits.extend(hits)
        return result


_ = time  # 预留：限流/退避时用
