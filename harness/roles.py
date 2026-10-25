"""Critic / Strategist 两个角色的定义：闭集、prompt、解析。

## 为什么单独一个模块

角色最容易失控的地方是**输出格式漂移**：模型今天返回 `wrong_strategy`，
明天返回"策略错误：应该反证"。所以每个角色的产物都必须能**离线解析**、
并且在解析失败时落回一个安全默认值。把这些逻辑和 prompt 放在一起、单独测试。

## 与写者的边界

* Critic 只输出**分类标签 + 一句理由**，不写代码；
* Strategist 只输出**策略 + 草图文本**，草图**永远不直接编译**；
* 只有 Prover 的产物会进入 Lean。这是「写者唯一」不变式，
  由 `pipeline` 保证，`roles` 这边只做文本解析。
"""

from __future__ import annotations

import re

# ------------------------------------------------------------------ 闭集
#: Critic 允许输出的标签。顺序即优先级（用于统计展示）。
CRITIC_LABELS: tuple[str, ...] = (
    "syntax",
    "missing_lemma",
    "wrong_strategy",
    "needs_induction",
    "type_mismatch",
    "unsolved",
    "other",
)

CRITIC_LABEL_SET = frozenset(CRITIC_LABELS)

#: 只有这些标签值得升级到 Strategist（其余交给 Prover 重试即可）。
STRATEGY_LABELS = frozenset({"wrong_strategy", "needs_induction"})

#: P2-pre 探针用的策略闭集
PROBE_LABELS: tuple[str, ...] = (
    "direct",
    "contradiction",
    "induction",
    "cases",
    "construction",
    "other",
)

#: 诊断文本截断长度：太长会稀释 prompt，太短则丢掉目标状态。
MAX_DIAG_CHARS = 800

# ------------------------------------------------------------------ prompts
CRITIC_SYSTEM = (
    "你是 Lean 4 证明失败的诊断器。给定定理声明、最近几次失败的尝试和编译诊断，"
    "判断**为什么一直卡住**，并给出**下一步该怎么做**的具体建议。"
    "只输出一行，格式严格为 `<LABEL>: <不超过 60 字的可执行建议>`。"
    "LABEL 只能取：syntax（语法/拼写/截断）、missing_lemma（缺引理或引理名不对）、"
    "wrong_strategy（方向错了，例如该反证却直证）、needs_induction（该归纳/分类讨论）、"
    "type_mismatch（类型/量词/写法不匹配）、unsolved（tactic 合法但没关闭目标）、other。"
    "冒号后面必须写**下一步动作**（换哪个引理、补哪个展开、先做哪一步），"
    "不要只说'没证完'。不要写 Lean 代码块，不要解释格式。"
)

STRATEGIST_SYSTEM = (
    "你是 Lean 4 证明的策略顾问。给定定理声明、失败历史与诊断类别，"
    "给出**一个**可行的高层策略和至多 3 行关键步骤。"
    "只输出两行：\n"
    "STRATEGY: <一行策略>\n"
    "SKETCH: <至多 3 行伪代码或 Lean 关键步骤；没有就留空>\n"
    "不要输出完整证明，不要输出 ``` 代码块。"
)

CRITIC_TEMPLATE = """## 定理声明
```lean4
{header}
```

## 最近几次失败（越靠后越新）
{history}

## 最新一次诊断
{diagnostics}

请只输出一行：`<LABEL>: <下一步该怎么做>`。"""

STRATEGIST_TEMPLATE = """## 定理声明
```lean4
{header}
```

## 失败历史（最近 3 次）
{history}

## 诊断类别
{label}

请输出 STRATEGY 与 SKETCH 两行。"""

# ---------------------------------------------------------------- P2-pre 探针
#: 在实现 Strategist 之前，先花 244 次调用回答「Flash 到底会不会选策略」。
PROBE_SYSTEM = (
    "你是 Lean 4 证明的策略顾问。只判断这道题**最可能需要**的高层策略，"
    "不要写证明、不要解释过程。"
    "只输出一行：`<STRATEGY>: <0-100 的置信度>`。"
    "STRATEGY 只能取：direct（直接化简/计算）、contradiction（反证）、"
    "induction（归纳）、cases（分类讨论）、construction（构造/给出具体对象）、other。"
)

PROBE_TEMPLATE = """## 定理声明
```lean4
{header}
```

请只输出一行：`<STRATEGY>: <置信度>`。"""

# ---------------------------------------------------------------- Planner
#: 计划角色：产出一份**版本化**的证明计划，由 Prover 在每一轮消费。
#: 这是从 Numina-Lean-Agent 的 `informal_<lemma>.md` 学来的形态——
#: 关键不在"给一次建议"，而在**计划要落盘、要迭代、要带失败历史**。
PLANNER_SYSTEM = (
    "你是 Lean 4 证明的计划者。给定定理声明和（可能为空的）失败历史，"
    "写一份可执行的证明计划：分步大纲、需要用到的 Mathlib 引理名、以及已知陷阱。"
    "只输出计划，不要写完整证明，不要用 ``` 代码块。"
    "格式严格为：\n"
    "OUTLINE:\n1. ...\n2. ...\n"
    "LEMMAS: <逗号分隔的引理名，可为空>\n"
    "PITFALLS: <一句话，可为空>"
)

PLANNER_TEMPLATE = """## 定理声明
```lean4
{header}
```

## 失败历史（可能为空）
{history}

## 上一版计划（可能为空）
{prev_plan}

请按要求输出 OUTLINE / LEMMAS / PITFALLS。"""


def _clip(text: str, limit: int = MAX_DIAG_CHARS) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def planner_prompt(header: str, history: str, prev_plan: str) -> str:
    return PLANNER_TEMPLATE.format(
        header=header.strip(),
        history=_clip(history, 1600) or "(无)",
        prev_plan=_clip(prev_plan, 800) or "(无)",
    )


_OUTLINE_RE = re.compile(r"^[ \t]*OUTLINE[ \t]*[::][ \t]*(.*)$", re.I | re.M)
_LEMMAS_RE = re.compile(r"^[ \t]*LEMMAS?[ \t]*[::][ \t]*(.*)$", re.I | re.M)
_PITFALLS_RE = re.compile(r"^[ \t]*PITFALLS?[ \t]*[::][ \t]*(.*)$", re.I | re.M)


def parse_plan(text: str) -> dict:
    """解析计划。

    容错策略：认不出结构就把整段原文当 outline，**绝不返回空计划**——
    宁可给 Prover 一段散文，也不要让它以为「这题没有计划」。
    """
    raw = (text or "").strip()
    if not raw:
        return {"outline": [], "lemmas": [], "pitfalls": "", "raw": ""}

    outline: list[str] = []
    m = _OUTLINE_RE.search(raw)
    if m:
        # OUTLINE 到 LEMMAS/PITFALLS 之间的所有行
        start = m.end()
        rest = raw[start:]
        end = len(rest)
        for pat in (_LEMMAS_RE, _PITFALLS_RE):
            mm = pat.search(rest)
            if mm:
                end = min(end, mm.start())
        for line in rest[:end].splitlines():
            line = line.strip().lstrip("0123456789.)、 ").strip()
            if line:
                outline.append(_clip(line, 200))
    lemmas: list[str] = []
    m = _LEMMAS_RE.search(raw)
    if m:
        for part in re.split(r"[,，;；\n]", m.group(1)):
            part = part.strip().strip("`")
            if part and re.match(r"^[A-Za-z_][\w.']*$", part):
                lemmas.append(part)
    pitfalls = ""
    m = _PITFALLS_RE.search(raw)
    if m:
        pitfalls = _clip(m.group(1).strip(), 200)

    if not outline and not lemmas:
        outline = [_clip(ln, 200) for ln in raw.splitlines() if ln.strip()][:10]
    return {"outline": outline, "lemmas": lemmas[:8], "pitfalls": pitfalls, "raw": _clip(raw, 1500)}


def critic_prompt(header: str, history: str, diagnostics: str) -> str:
    """Critic 的输入：完整失败历史 + 最新诊断（不再只看最后一次）。"""
    return CRITIC_TEMPLATE.format(
        header=header.strip(),
        history=_clip(history, 2000) or "(无)",
        diagnostics=_clip(diagnostics) or "(无)",
    )


def strategist_prompt(header: str, history: str, label: str) -> str:
    return STRATEGIST_TEMPLATE.format(
        header=header.strip(),
        history=_clip(history, 1200) or "(无)",
        label=label or "other",
    )


def probe_prompt(header: str) -> str:
    return PROBE_TEMPLATE.format(header=header.strip())


# ------------------------------------------------------------------ 解析
_LABEL_RE = re.compile(r"^[ \t]*([A-Za-z_]+)[ \t]*[::][ \t]*(.*)$")
_STRATEGY_RE = re.compile(r"^[ \t]*STRATEGY[ \t]*[::][ \t]*(.*)$", re.I | re.M)
_SKETCH_RE = re.compile(r"^[ \t]*SKETCH[ \t]*[::][ \t]*(.*)$", re.I | re.M)


def normalize_label(raw: str) -> str:
    """把模型可能写出的各种变体收敛到闭集；认不出就 `other`。

    容忍 `"Wrong-Strategy: 应该反证"` 这种整行输入：先砍掉冒号后的解释。
    """
    head = (raw or "").splitlines()[0] if (raw or "").strip() else ""
    token = head.split(":")[0].strip().lower().replace("-", "_").replace(" ", "_")
    if token in CRITIC_LABEL_SET:
        return token
    # 常见同义词
    aliases = {
        "grammar": "syntax",
        "parse_error": "syntax",
        "syntax_error": "syntax",
        "missing_premise": "missing_lemma",
        "need_lemma": "missing_lemma",
        "unknown_lemma": "missing_lemma",
        "wrong_direction": "wrong_strategy",
        "strategy": "wrong_strategy",
        "induction": "needs_induction",
        "case_split": "needs_induction",
        "type": "type_mismatch",
        "type_error": "type_mismatch",
        "unsolved_goals": "unsolved",
        "incomplete": "unsolved",
    }
    return aliases.get(token, "other")


def parse_critic(text: str) -> tuple[str, str]:
    """解析 Critic 输出；任何格式问题都退化成 `("other", 原文摘要)`。"""
    raw = (text or "").strip()
    if not raw:
        return "other", ""
    first = raw.splitlines()[0].strip()
    m = _LABEL_RE.match(first)
    if not m:
        return "other", _clip(first, 120)
    label = normalize_label(m.group(1))
    note = _clip(m.group(2).strip(), 120)
    return label, note


def parse_strategist(text: str) -> tuple[str, str]:
    """解析 Strategist 输出，返回 `(strategy, sketch)`；缺失时返回空串。"""
    raw = (text or "").strip()
    if not raw:
        return "", ""
    strategy = ""
    sketch = ""
    m = _STRATEGY_RE.search(raw)
    if m:
        strategy = _clip(m.group(1).strip(), 300)
    m = _SKETCH_RE.search(raw)
    if m:
        sketch = _clip(m.group(1).strip(), 600)
    if not strategy and not sketch:
        # 模型没按格式来：把第一行当策略，其余当草图
        lines = [ln for ln in raw.splitlines() if ln.strip()]
        if lines:
            strategy = _clip(lines[0], 300)
            sketch = _clip("\n".join(lines[1:4]), 600)
    return strategy, sketch


def parse_probe(text: str) -> tuple[str, int]:
    """解析策略探针输出 → `(label, confidence 0-100)`。

    容忍模型不写冒号（只给一个词）的情况。
    """
    raw = (text or "").strip()
    if not raw:
        return "other", 0
    first = raw.splitlines()[0].strip()
    m = _LABEL_RE.match(first)
    if m:
        token, rest = m.group(1), m.group(2)
    else:
        words = first.split()
        token, rest = (words[0], " ".join(words[1:])) if words else ("", "")
    token = token.strip().lower().replace("-", "_")
    label = token if token in PROBE_LABELS else "other"
    digits = re.search(r"\d{1,3}", rest or "")
    if digits:
        conf = min(100, int(digits.group()))
    else:
        # 认出了标签但没给置信度 → 50；完全认不出 → 0（别假装有信号）
        conf = 50 if label != "other" else 0
    return label, conf
