"""Loogle 检索的离线单测：不联网。

覆盖：正常解析、缓存、网络失败降级、查询词抽取。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from harness import retrieval


class FakeLoogle(retrieval.LoogleClient):
    """把网络层换成固定返回。"""

    def __init__(self, payload, *, cache=None):
        super().__init__(cache=cache or retrieval._Cache(Path(__file__).parent / "_tmp_cache.jsonl"))
        self.payload = payload
        self.calls: list[str] = []

    def _fetch(self, q):  # noqa: ANN001
        self.calls.append(q)
        return self.payload


def _cleanup(path: Path) -> None:
    if path.exists():
        path.unlink()


def test_search_parses_hits():
    cache = Path(__file__).parent / "_tmp_cache1.jsonl"
    _cleanup(cache)
    c = FakeLoogle(
        [{"name": "Nat.add_comm", "type": " n m : ℕ", "module": "Init"}],
        cache=retrieval._Cache(cache),
    )
    hits = c.search("Nat.add_comm", limit=3)
    assert hits[0].name == "Nat.add_comm"
    assert "`Nat.add_comm`" in hits[0].render()
    _cleanup(cache)


def test_cache_prevents_second_fetch():
    cache = Path(__file__).parent / "_tmp_cache2.jsonl"
    _cleanup(cache)
    c = FakeLoogle([{"name": "Foo.bar", "type": "", "module": "M"}], cache=retrieval._Cache(cache))
    c.search("Foo.bar")
    c.search("Foo.bar")
    assert len(c.calls) == 1  # 第二次走缓存
    _cleanup(cache)


def test_offline_returns_empty():
    cache = Path(__file__).parent / "_tmp_cache3.jsonl"
    _cleanup(cache)
    c = FakeLoogle(None, cache=retrieval._Cache(cache))  # _fetch 返回 None = 失败
    assert c.search("Nat.add_comm") == []
    _cleanup(cache)


def test_retrieve_for_budget_and_dedup():
    cache = Path(__file__).parent / "_tmp_cache4.jsonl"
    _cleanup(cache)
    c = FakeLoogle(
        [{"name": "A.b", "type": "", "module": "M"}, {"name": "C.d", "type": "", "module": "M"}],
        cache=retrieval._Cache(cache),
    )
    res = c.retrieve_for(terms=["A.b", "C.d", "E.f"], max_queries=2)
    assert res.queries == ["A.b", "C.d"]
    assert len(c.calls) == 2
    block = res.as_prompt_block()
    assert "`A.b`" in block and "`C.d`" in block
    assert res.as_record()["queries"] == 2
    _cleanup(cache)


def test_extract_query_terms_skips_noise():
    terms = retrieval.extract_query_terms("⊢ Real.log (Finset.sum s f) = 0", limit=3)
    assert "Real.log" in terms
    assert all(not t.startswith(("Lean.", "Mathlib.")) for t in terms)


def test_cache_survives_corrupt_file():
    path = Path(__file__).parent / "_tmp_cache5.jsonl"
    path.write_text("not json\n", encoding="utf-8")
    cache = retrieval._Cache(path)
    assert cache.data == {}
    path.unlink(missing_ok=True)
