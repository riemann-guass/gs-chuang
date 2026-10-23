"""L0 tactic 级联。

## 为什么整套级联写在一个 `first` 里

一道题只需要**一次** elaboration，而不是「每个 tactic 编译一遍」。配合批量编译
（见 `leanenv.py`），10 道题的 L0 基线总共只有一次 Mathlib 载入。

每个分支都写成 `(tac; done)`：`done` 在还有残留目标时失败，从而让 `first` 正确
回溯到下一个 tactic。如果只写 `simp`，它「成功但没证完」会让 `first` 不再回溯，
级联就失效了。

## 为什么分成 cheap / deep 两档

实测（10 题，2026-10-19）：把 `grind`、`aesop` 放进同一档，单轮编译从 ~240 s
涨到 **567 s**，而 10 题里它们一题都没证出来。这与 L0 的定位（「自动 tactic
组合，成本极低」）冲突，所以：

* **L0 = cheap**：`rfl … positivity`，全部是便宜的判定过程与重写；
* **deep**（`grind`、`aesop`）留给 L1/L2，并应该配预算。

`deep=True` 时仍然可用，只是不作为默认基线。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    name: str
    tactic: str


#: L0：便宜、确定性、几乎不搜索。顺序参考 lean4-skills 的 solver cascade。
CASCADE_STEPS: tuple[Step, ...] = (
    Step("rfl", "rfl"),
    Step("assumption", "assumption"),
    Step("simp", "simp"),
    Step("norm_num", "norm_num"),
    Step("norm_cast", "norm_cast"),
    Step("ring", "ring"),
    Step("field_simp_ring", "field_simp; ring"),
    Step("linarith", "linarith"),
    Step("nlinarith", "nlinarith"),
    Step("omega", "omega"),
    Step("positivity", "positivity"),
)

#: 搜索型 tactic，成本显著更高，不应属于 L0。
DEEP_STEPS: tuple[Step, ...] = (
    Step("grind", "grind"),
    Step("aesop", "aesop"),
)


def cascade_proof(*, deep: bool = False) -> str:
    """渲染成一条 `first` 表达式。

    末尾加一个 `fail "cascade_exhausted"` 哨兵分支：`first` 在全部失败时只会转述
    **最后一个**分支的错误（实测是 `not a positivity goal`，毫无信息量）；哨兵让
    失败原因稳定变成一条可分类的消息，同时把 goal state 留在诊断里。

    注意用 `fail`（tactic）而不是 `throwError`（term 层的命令）——后者会让整条
    `first` 表达式解析失败，实测导致 10 题全灭。
    """
    steps = CASCADE_STEPS + DEEP_STEPS if deep else CASCADE_STEPS
    branches = " | ".join(f"({s.tactic}; done)" for s in steps)
    return f'first | {branches} | (fail "cascade_exhausted")'


def step_proofs(*, deep: bool = False) -> list[tuple[str, str]]:
    """单步版本，用于事后归因（哪一步真正解出了题）。"""
    steps = CASCADE_STEPS + DEEP_STEPS if deep else CASCADE_STEPS
    return [(s.name, f"{s.tactic}; done") for s in steps]
