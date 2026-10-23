import Mathlib.Tactic

theorem probe_tactic_only (a b : ℝ) (h : a ≤ b) : a ≤ b := by linarith
