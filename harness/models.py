"""可插拔的模型后端。

设计目标是**离线优先**：

* `MockModel` 是一等公民，不联网、不花钱、确定性输出，用来验证整条回路
  与做 A/B 对照；
* `DeepSeekClient` 只在 `.env` 配好且网络可达时启用；配置缺失时由
  `build_model()` 自动降级为 Mock，并在运行记录里写明 `fallback`。

不依赖 `openai` SDK（本机未安装且无法联网安装），直接用 `requests`
打 OpenAI 兼容的 `/chat/completions`。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

import requests

from . import config
from .problems import Problem


@dataclass
class Attempt:
    source: str
    proof: str
    status: str
    error_kind: str = "none"
    diagnostics: str = ""


@dataclass
class ProposeRequest:
    problem: Problem
    attempt_index: int
    history: list[Attempt] = field(default_factory=list)
    goals: str | None = None
    budget_hint: str = ""
    #: 是否把「诊断 → 对策」提示注入 prompt（M3 的 A 组）。默认关，
    #: 这样历史运行不受后续改动影响。见 ADR-0006。
    hints: bool = False


@dataclass
class ModelResponse:
    proof: str
    tokens_in: int = 0
    tokens_out: int = 0
    raw: str = ""


@runtime_checkable
class ModelClient(Protocol):
    name: str

    def propose(self, req: ProposeRequest) -> ModelResponse: ...


# --------------------------------------------------------------------- mock
_MOCK_LADDER = (
    "rfl",
    "simp",
    "norm_num",
    "linarith",
    "nlinarith",
    "omega",
    "ring",
    "field_simp; ring",
    "aesop",
)


class MockModel:
    """确定性模型：按轮次依次吐出级联里的下一个 tactic。

    它不是为了「证出题」，而是为了让 runner / 审计 / 日志在没有网络、
    没有 API key 的情况下能被完整测试。
    """

    name = "mock"

    def propose(self, req: ProposeRequest) -> ModelResponse:
        idx = req.attempt_index % len(_MOCK_LADDER)
        return ModelResponse(proof=_MOCK_LADDER[idx], raw=f"mock:{idx}")


# ----------------------------------------------------------------- deepseek
_ENV_FILE = config.REPO_ROOT / ".env"
_CODE_FENCE = re.compile(r"```(?:lean4?)?\s*\n?(.*?)```", re.S)


def load_dotenv(path: Path = _ENV_FILE) -> dict[str, str]:
    """极简 .env 解析，避免为一行配置引入依赖。"""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


class ModelError(RuntimeError):
    """模型调用失败，带可读的 `kind`。

    `kind` 取值：`connection` / `timeout` / `auth` / `rate_limit` / `server` /
    `bad_response` / `unknown`。runner 用它决定「这一题本轮算失败，但整轮继续」。
    """

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(f"{kind}: {message}")
        self.kind = kind
        self.detail = message


class DeepSeekClient:
    """OpenAI 兼容的 DeepSeek 客户端。

    配置项（`.env` 或环境变量）：

    * ``DEEPSEEK_BASE_URL`` 例如 ``https://api.deepseek.com/v1``
    * ``DEEPSEEK_API_KEY``
    * ``DEEPSEEK_MODEL`` 例如 ``deepseek-v4-flash``
    * ``DEEPSEEK_MAX_TOKENS`` 默认 1024
    * ``DEEPSEEK_PROXY`` 可选，本地代理
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout_s: int = 120,
        proxy: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        thinking: str | None = "disabled",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.name = model
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self.temperature = temperature
        # DeepSeek V4 默认是「思考模式」：推理内容计入 max_tokens，且常常把预算耗尽后
        # 一字符答案都不给（实测 16384 token 全是 reasoning、content 为空）。
        # 传 {"type":"disabled"} 可以关掉，2 秒内直接给答案。见 ADR-0005。
        self.thinking = thinking
        # 本机曾配置 127.0.0.1:7897 的本地代理；代理开启时通过 DEEPSEEK_PROXY 传入。
        self.proxies = {"http": proxy, "https": proxy} if proxy else None

    def propose(self, req: ProposeRequest) -> ModelResponse:
        payload = {
            "model": self.name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": render_prompt(req)},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.thinking:
            payload["thinking"] = {"type": self.thinking}
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                data=json.dumps(payload),
                timeout=self.timeout_s,
                proxies=self.proxies,
            )
        except requests.exceptions.Timeout as exc:
            raise ModelError("timeout", f"请求超时（{self.timeout_s}s）：{exc}") from exc
        except requests.exceptions.ConnectionError as exc:
            raise ModelError("connection", f"连不上 {self.base_url}：{exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise ModelError("unknown", str(exc)) from exc

        status = resp.status_code
        if status == 401 or status == 403:
            raise ModelError("auth", f"HTTP {status}：API key 无效或无权访问")
        if status == 429:
            raise ModelError("rate_limit", "HTTP 429：被限流")
        if status >= 500:
            raise ModelError("server", f"HTTP {status}：{resp.text[:200]}")
        if status >= 400:
            raise ModelError("unknown", f"HTTP {status}：{resp.text[:200]}")

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ModelError("bad_response", f"响应结构不符合预期：{resp.text[:200]}") from exc

        usage = data.get("usage") or {}
        return ModelResponse(
            proof=extract_proof(content or ""),
            tokens_in=int(usage.get("prompt_tokens", 0)),
            tokens_out=int(usage.get("completion_tokens", 0)),
            raw=content or "",
        )


SYSTEM_PROMPT = (
    "你是 Lean 4 的 tactic 生成器。给定一个定理的声明（header）和当前的编译错误，"
    "只输出可以直接接在 `:= by` 之后的 tactic 代码块，不要重复定理声明，不要解释，"
    "不要使用 sorry / admit / native_decide / axiom。"
)

PROMPT_TEMPLATE = """## 定理声明
```lean4
{header}
```

## 历史尝试
{history}

## 当前诊断
{diagnostics}
{hints}
请给出下一步的 tactic 代码（可以多行）。只输出代码块。"""

HINTS_TEMPLATE = """
## 建议（按当前诊断给出，供参考，不保证正确）
{hints_text}
"""


def _hint_block(req: ProposeRequest) -> str:
    """按最近几次失败的类型拼提示；`hints=False` 时返回空串。"""
    if not req.hints or not req.history:
        return ""
    from .hints import render_hints

    kinds = [a.error_kind for a in req.history[-2:] if a.error_kind and a.error_kind != "none"]
    if not kinds:
        return ""
    return HINTS_TEMPLATE.format(hints_text=render_hints(kinds))


def render_prompt(req: ProposeRequest) -> str:
    if req.history:
        hist = "\n\n".join(
            f"尝试 {i + 1}（{a.source}, {a.status}）：\n```lean4\n{a.proof}\n```\n诊断：\n{a.diagnostics or '(无)'}"
            for i, a in enumerate(req.history[-3:])
        )
    else:
        hist = "(无)"
    diagnostics = req.goals or (req.history[-1].diagnostics if req.history else "(无)")
    return PROMPT_TEMPLATE.format(
        header=req.problem.header,
        history=hist,
        diagnostics=diagnostics,
        hints=_hint_block(req),
    )


#: 裸的围栏语言标签行，例如模型输出被截断时剩下的 `lean4`
_LANG_TAG_LINE = re.compile(r"^\s*`{0,3}\s*(lean4?|Lean4?)\s*$")


def extract_proof(text: str) -> str:
    """从模型输出里抠出 tactic 代码。

    模型有三种常见输出形态，都要处理：

    1. 正常闭合的代码块：```lean4 ... ```；
    2. **围栏没闭合**（被 max_tokens 截断）：此时正则匹配不到，
       去掉 ``` 之后会残留一行语言标签 `lean4`——它会被 Lean 当成一个 tactic，
       报 `unknown tactic`。实测这直接毁掉了一道题（2026-10-21）；
    3. 完全没有围栏，纯代码。
    """
    m = _CODE_FENCE.search(text)
    body = m.group(1) if m else text

    lines = body.replace("```", "").splitlines()
    # 去掉开头的空行与裸语言标签行
    while lines and (_LANG_TAG_LINE.match(lines[0]) or not lines[0].strip()):
        lines.pop(0)
    # 去掉 `--` 注释行与结尾的空行
    lines = [ln for ln in lines if not ln.strip().startswith("--")]
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip()


DEFAULT_BASE_URL = "https://api.deepseek.com/v1"


def build_model(env: dict[str, str] | None = None, *, allow_network: bool = True) -> tuple[ModelClient, str]:
    """按配置构造模型；返回 `(client, note)`，`note` 记录是否降级。

    `DEEPSEEK_BASE_URL` 有默认值（官方 OpenAI 兼容端点），所以**只缺 key 就会降级**——
    用户只需要在 `.env` 里填一行 `DEEPSEEK_API_KEY=...`。

    **显式传入 `env` 时完全替代 `.env` 文件**（不再合并），这样测试不会被仓库里
    真实的 `.env` 影响。
    """
    env = dict(env) if env is not None else load_dotenv()
    key = env.get("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY", "")
    base = env.get("DEEPSEEK_BASE_URL") or os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)
    model = env.get("DEEPSEEK_MODEL") or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
    proxy = env.get("DEEPSEEK_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or None
    max_tokens = int(env.get("DEEPSEEK_MAX_TOKENS") or os.environ.get("DEEPSEEK_MAX_TOKENS", "1024"))
    thinking = (env.get("DEEPSEEK_THINKING") or os.environ.get("DEEPSEEK_THINKING", "disabled")).strip() or None

    if not allow_network:
        return MockModel(), "no-network-requested"
    if not key:
        return MockModel(), "missing-key-fallback-mock"
    return (
        DeepSeekClient(
            base_url=base,
            api_key=key,
            model=model,
            proxy=proxy,
            max_tokens=max_tokens,
            thinking=thinking,
        ),
        "deepseek",
    )
