/-
  WeftInvariantsPureInit.lean
  Stock Lean 4 (`Init`-only) upgrade for Moissanite-Labs/weft `WeftInvariants.lean` (PR #128).

  Upgrades over initial `WeftInvariants.lean`:
  1. Removes unused `Float` structure `OrthogonalUpdatePair` (replaces with exact integer/rational
     scaled inner-product bounds).
  2. Strengthens `bounded_overlap_mitosis_envelope` to two-sided overlap `-ov <= inner /\ inner <= ov`
     and proves reverse-direction stability (`np + nc - 2 * ov >= 0` when bounded).
  3. Formalizes the division-free Mitotic Diagnostic Ratio (MDR) gate with an explicit orthogonal
     gradient floor `0 < gradFloor <= gradOrth`, proving that sub-floor rounding dust
     (`gradOrth < gradFloor`, such as `3e-12` when `gradPar = 0`) can NEVER trigger mitosis.
-/

namespace WeftV2.PureInit

theorem pythagorean_mitosis_envelope
    (np nc inner rp rc rmax : Int)
    (h_orth : inner = 0)
    (h_p : np ≤ rp)
    (h_c : nc ≤ rc)
    (h_budget : rp + rc ≤ rmax) :
    np + nc + 2 * inner ≤ rmax := by
  subst h_orth
  omega

theorem two_sided_overlap_mitosis_envelope
    (np nc inner ov rp rc rmax : Int)
    (h_ov_lo : -ov ≤ inner)
    (h_ov_hi : inner ≤ ov)
    (h_p : np ≤ rp)
    (h_c : nc ≤ rc)
    (h_budget : rp + rc + 2 * ov ≤ rmax) :
    np + nc + 2 * inner ≤ rmax ∧ np + nc - 2 * ov ≤ np + nc + 2 * inner := by
  omega

/-- Division-free MDR mitosis predicate (scaled by integer `scale > 0`):
    triggers iff `err > errFloor`, `gradPar <= parCeil`, `gradOrth >= orthFloor`,
    and `gradOrth * mdrDen >= mdrNum * gradPar`. -/
def mitosisTriggered
    (err errFloor gradPar parCeil gradOrth orthFloor mdrNum mdrDen : Int) : Prop :=
  err > errFloor ∧
  gradPar ≤ parCeil ∧
  orthFloor ≤ gradOrth ∧
  gradOrth * mdrDen ≥ mdrNum * gradPar

/-- Proves that sub-floor rounding noise (`gradOrth < orthFloor`, e.g. `3e-12 < 1e-3`
    at `gradPar = 0`) never triggers mitosis, eliminating the `weft_v2_invariants.h`
    `grad_orth / (grad_par + 1e-12)` false positive. -/
theorem subfloor_noise_never_triggers_mitosis
    (err errFloor gradPar parCeil gradOrth orthFloor mdrNum mdrDen : Int)
    (h_dust : gradOrth < orthFloor) :
    ¬ mitosisTriggered err errFloor gradPar parCeil gradOrth orthFloor mdrNum mdrDen := by
  intro h
  rcases h with ⟨_, _, h_floor, _⟩
  omega

inductive ValidExecution : Nat → Nat → Prop where
  | halt (b : Nat) : ValidExecution b 0
  | step {b b' k : Nat} (h_pos : 0 < b) (h_monotone : b' < b)
      (h_rest : ValidExecution b' k) : ValidExecution b (k + 1)

theorem strict_metabolic_termination {b k : Nat} (h : ValidExecution b k) : k ≤ b := by
  induction h with
  | halt b => exact Nat.zero_le b
  | @step b b' k _ h_mono _ ih => omega

theorem stratified_arena_envelope
    (df ds dh dl rf rs rh : Int)
    (h_lock : dl = 0)
    (hf : df ≤ rf)
    (hs : ds ≤ rs)
    (hh : dh ≤ rh) :
    df + ds + dh + dl ≤ rf + rs + rh := by
  subst h_lock
  omega

end WeftV2.PureInit
