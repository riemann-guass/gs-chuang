/-
# `Worker.lean`：常驻 Lean 会话（一次导入 Mathlib，多批服务）

## 为什么长这样

* 进程内 `Lean.Elab.runFrontend` 在导入 Mathlib 后会崩（旧工程踩过：
  `cannot evaluate [init] declaration 'Mathlib.pp.mathlib.binderPredicates'`），
  所以不用 frontend；
* 但 **elaboration 需要 Environment**，而 Environment 只能来自 olean，
  压不进 exe（ADR-0008 已否决单 exe 方案）；
* 于是：用 `run_tac` 把一段 `TacticM` 塞进一个声明里，在 **elaboration 的过程中**
  拿 IO 循环。这样进程只导入一次 Mathlib，之后每题只做一次 `elabTerm` + `runTactic`。

## 协议（JSONL，stdin ← → stdout）

请求：`{"id": "...", "type": "<命题>", "proof": "<tactic 序列>"}`
响应：`{"id": "...", "ok": true/false, "goals": n, "sorry": bool, "error": "..."}`

`{"cmd":"bye"}` 或 EOF 结束。

## 判定口径

`ok = 没有剩余目标 且 证明项已赋值 且 不含 sorryAx 且 类型对得上`。
这是**快速判定**；正式成绩仍以批量编译的四项审计为准（worker 只负责交互延迟）。

## 启动

```powershell
lake env lean Worker.lean    # 首次载入 Mathlib 约 60–240 s，之后常驻
```
-/
import Mathlib

open Lean Elab Tactic Meta

-- 与批量编译的 preamble 保持一致，否则语句里未加限定的名字（如 `sin`）会解析不到
open BigOperators Real Nat Topology Rat

set_option maxHeartbeats 0
-- worker 里比批量编译多一层嵌套（`run_tac` 内再跑 `Tactic.run`）。实测把上限调到
-- 100 万并不能救回那 3 道题（进程直接静默死亡 = 原生栈溢出，Lean 侧捕获不到），
-- 所以保持与「确定性补救」一致的 10000，语义上等价于补救档。
set_option maxRecDepth 10000
-- 抑制「run_tac 什么也没做」的 linter：它会往 stdout 打警告，干扰协议
set_option linter.unusedTactic false

namespace Worker

/-- 解析一个语法范畴，失败时抛出带原文的错误。 -/
def parseCat (env : Environment) (cat : Name) (text : String) (what : String) : TermElabM Syntax := do
  match Parser.runParserCategory env cat text with
  | .ok stx => return stx
  | .error e => throwError "解析 {what} 失败：{e}"

/-- 表达式里是否出现 `sorryAx`。 -/
def usesSorry (e : Expr) : Bool :=
  e.find? (fun
    | .const n _ => n == ``sorryAx
    | _ => false) |>.isSome

/-- 按声明的方式建目标：先把前 `n` 个 `∀` 绑定引入**局部上下文**，再在剩余类型上开目标。

这一步是必须的：批量编译时定理参数是局部假设（`theorem foo (a : ℂ) : P a`），
直接拿 `∀ (a : ℂ), P a` 当目标会让 `ring` / `linarith` 这类 tactic 失败。 -/
partial def mkGoal (n : Nat) (type : Expr) : MetaM Expr := do
  if n == 0 then
    mkFreshExprMVar (some type)
  else
    match type with
    | .forallE _ dom body _ =>
      withLocalDeclD `arg dom fun x => do
        mkGoal (n - 1) (body.instantiate1 x)
    | _ => mkFreshExprMVar (some type)

/-- 判定「`proof` 是 `type` 的一篇完整证明」。

`nbinders` 是定理头部里参数的个数（由调用方数好）。 -/
def checkOne (typeText proofText : String) (nbinders : Nat) : TacticM (Bool × Nat × Bool × String) := do
  let env ← getEnv

  -- 1) 命题：必须落在 Prop 里
  let typeStx ← parseCat env `term typeText "命题"
  let prop ← liftM (elabTerm typeStx (some (mkSort levelZero)))
  let prop ← instantiateMVars prop
  unless (← liftMetaM (isProp prop)) do
    throwError "语句不是命题（类型不是 Prop）"

  -- 2) 目标：前 nbinders 个绑定进局部上下文
  let goal ← liftMetaM (mkGoal nbinders prop)
  let mvarId := goal.mvarId!

  -- 3) 跑证明脚本。
  -- 注意：`tacticSeq` 不是 runParserCategory 能直接查的范畴（实测 unknown parser
  -- category），所以把整段包成 `by …` 按 term 解析，再取出里面的 tactic 序列。
  let byStx ← parseCat env `term s!"by\n{proofText}" "证明"
  let seqStx := match byStx with
    | .node _ _ args => args.back!
    | _ => byStx
  let goalsLeft ← liftM (Tactic.run mvarId (Tactic.evalTactic seqStx))

  -- 4) 闭合性 + sorry
  let proof ← liftMetaM (instantiateMVars goal)
  let solved := proof.isMVar
  let hasSorry := !solved && usesSorry proof
  return (!solved && !hasSorry && goalsLeft.isEmpty, goalsLeft.length, hasSorry, "")

/-- 取 JSON 对象里的字符串字段；缺失或类型不对时返回空串。 -/
def strField (j : Json) (key : String) : String :=
  match j.getObjVal? key with
  | .ok v => (v.getStr?.toOption).getD ""
  | .error _ => ""

/-- 按**字符**截断。用 `List` 而不是 `String.take`，避免踩 UTF-8 边界。 -/
def truncChars (s : String) (n : Nat) : String :=
  String.ofList (s.toList.take n)

/-- 一条请求 → 一行 JSON。

响应统一用 `Json.compress` 序列化：它自己处理引号与换行的转义，我们不用手写字符串拼装，
也就避开了 Lean 4.28 里对多字节字符串做 `replace` 会 panic 的坑。 -/
def handle (line : String) : TacticM String := do
  match Json.parse line with
  | .error _ => return "{\"id\":\"\",\"ok\":false,\"error\":\"bad-json\"}"
  | .ok j =>
    let id := strField j "id"
    if strField j "cmd" == "bye" then
      return (Json.mkObj [("id", .str id), ("ok", .bool true), ("bye", .bool true)]).compress
    else
      let typeText := strField j "type"
      let proofText := strField j "proof"
      let nb := (strField j "nbinders").toNat?.getD 0
      try
        let (ok, goals, hasSorry, _) ← checkOne typeText proofText nb
        let err := if hasSorry then "sorry" else if goals > 0 then "unsolved" else ""
        return (Json.mkObj [
          ("id", .str id), ("ok", .bool ok), ("goals", .num goals),
          ("sorry", .bool hasSorry), ("error", .str err)]).compress
      catch ex =>
        let raw ← ex.toMessageData.toString
        let msg := truncChars raw 400
        return (Json.mkObj [
          ("id", .str id), ("ok", .bool false), ("goals", .num (-1 : Int)),
          ("sorry", .bool false), ("error", .str msg)]).compress

/-- 常驻循环：轮询目录里的 `req_*.json`，把结果写成 `resp_*.json`。

**为什么不用 stdin/stdout**：`run_tac` 里的 `IO.getStdin` 在 `lean file.lean` 下
拿到的永远是 EOF（实测 `GOT len=0`），所以走文件。顺便也躲开了 Lean 自己往
stdout 打诊断导致的协议污染。 -/
partial def serve : TacticM Unit := do
  let dir ← liftM do
    match ← IO.getEnv "WORKER_DIR" with
    | some d => pure d
    | none => pure "."
  let root : System.FilePath := dir
  let rec loop (seen : Array String) : TacticM Unit := do
    let entries ← liftM root.readDir
    let mut seen := seen
    for entry in entries do
      let name := entry.fileName
      -- 文件名统一是 `req_<6 位序号>`（纯 ASCII）。不用 `endsWith`：
      -- `Slice.endsWith` 在多字节文件名上会踩到同一个 UTF-8 边界 panic。
      if "req_".isPrefixOf name && !seen.contains name then
        let content ← liftM (IO.FS.readFile (root / name))
        let resp ← handle content
        let outName := s!"rsp_{name.drop 4}"
        liftM (IO.FS.writeFile (root / outName) resp)
        seen := seen.push name
    liftM (IO.sleep 25)
    loop seen
  loop #[]

end Worker

example : True := by
  run_tac Worker.serve
  trivial
