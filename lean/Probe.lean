import Mathlib

/-- 冒烟：确认 Mathlib 完整可用（`import Mathlib` 能解析到根模块）。 -/
theorem probe_smoke (n : Nat) : n + 0 = n := rfl

/-- 冒烟：确认 tactic 可运行。 -/
theorem probe_tactic (a b : ℝ) (h : a ≤ b) : a ≤ b := by linarith
