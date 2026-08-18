"""MOSAIC-Omega on REAL periodontal (gingival) single-cell omics data.

Datasets (CZ CELLxGENE, Human Oral & Craniofacial Cell Atlas):
  primary/train : Mucosal Immune Atlas, gingiva subset  (~14k cells, 8 immune types)
  validation    : Mucosal Atlas,        gingiva subset  (~15k gingival cells)

Task: identify the canonical marker gene for each gingival immune cell type.
The proposal / verification / falsification / scoring oracles are all grounded
in real Wilcoxon differential expression computed on the primary dataset
(see precompute_markers.py -> data/perio_task.json); an independent replication
is then measured on the validation dataset. No ground truth is ever shown to the
architecture's own scorers.

Run:  python precompute_markers.py   (once, builds data/perio_task.json)
      python run_periodontal_real.py
"""
from __future__ import annotations

import json
import os
from typing import Dict, List

import _paths  # noqa: F401  -- puts the repository root on sys.path

from mosaic_omega import MetricsEngine, MosaicConfig, MosaicOmega
from mosaic_omega.problem import Problem, _Constraint
from mosaic_omega.rng import rng_for
from mosaic_omega.types import RiskLevel, StageSpec

TASK_PATH = os.path.join(os.path.dirname(__file__), "data", "perio_task.json")

# cell type -> agent capability (real immunology domains)
CAP = {
    "CD8_T": "T_cell_biology", "CD4_T": "T_cell_biology",
    "B_cell": "B_plasma_biology", "plasma_cell": "B_plasma_biology",
    "mast_cell": "granulocyte_biology", "neutrophil": "granulocyte_biology",
    "dendritic_cell": "myeloid_biology", "macrophage": "myeloid_biology",
}
# two disease-relevant stages
STAGES = [
    ("S0_lymphoid", "Assign lymphoid-lineage markers (T / B / plasma)",
     RiskLevel.MEDIUM, ["CD8_T", "CD4_T", "B_cell", "plasma_cell"]),
    ("S1_myeloid", "Assign myeloid / granulocyte markers (DC / macrophage / mast / neutrophil)",
     RiskLevel.HIGH, ["dendritic_cell", "macrophage", "mast_cell", "neutrophil"]),
]


class PeriodontalMarkerProblem(Problem):
    """Real-data marker-identification mission driven by DE oracles."""

    goal = "Identify the correct marker gene for each gingival immune cell type"

    def __init__(self, task: dict) -> None:
        self.task = task
        self.seed = task["provenance"]["seed"]
        self.short = task["short"]                      # long label -> short id
        self.long = {v: k for k, v in self.short.items()}
        self._by_short = {}                             # short id -> per-type spec
        for long in task["types"]:
            s = self.short[long]
            self._by_short[s] = {
                "truth": task["truth"][long],
                "candidates": task["candidates"][long],
                "train_score": task["train_score"][long],
                "train_sig": task["train_sig"][long],
                "val_topk": task["val_topk"][long],
            }
        # normalise train enrichment to [0,1] per constraint for oracle math
        self._norm = {}
        for s, d in self._by_short.items():
            vals = list(d["train_score"].values())
            lo, hi = min(vals), max(vals)
            rng = (hi - lo) or 1.0
            self._norm[s] = {g: (d["train_score"][g] - lo) / rng for g in d["candidates"]}

        self._constraints: Dict[str, _Constraint] = {}
        for s, d in self._by_short.items():
            self._constraints[s] = _Constraint(s, CAP[s], list(d["candidates"]),
                                               d["truth"], 1.0)
        self._stages: List[StageSpec] = []
        for sid, desc, risk, members in STAGES:
            members = [m for m in members if m in self._by_short]
            caps: List[str] = []
            for m in members:
                if CAP[m] not in caps:
                    caps.append(CAP[m])
            self._stages.append(StageSpec(
                stage_id=sid, description=desc, constraint_ids=members,
                required_capabilities=caps, risk=risk,
                success_predicate="verified_score >= 0.85",
                verification_intensity=0.90 if risk == RiskLevel.HIGH else 0.45,
            ))

    # -- introspection ------------------------------------------------------
    def stages(self): return list(self._stages)
    def capability_catalog(self): return sorted(set(CAP.values()))
    def value_space(self, cid): return list(self._constraints[cid].values)
    def capability_for(self, cid): return self._constraints[cid].capability
    def truth_of(self, cid): return self._constraints[cid].truth

    # -- oracles grounded in real differential expression -------------------
    def _p_correct(self, skill: float) -> float:
        return max(0.05, min(0.99, 0.30 + 0.66 * skill))

    def propose(self, cid, agent_id, skill, nonce):
        """Skill-weighted pick over candidates using real train enrichment.

        High-skill agents converge on the genuinely most-enriched gene (the
        data-derived truth); low-skill agents scatter across the distractors.
        """
        c = self._constraints[cid]
        rng = rng_for("propose", self.seed, cid, agent_id, nonce)
        if rng.random() < self._p_correct(skill):
            # the empirically top-enriched candidate for this cell type
            return max(c.values, key=lambda g: self._norm[cid][g])
        others = [g for g in c.values if g != c.truth]
        # weight wrong picks by (residual) enrichment so it stays data-driven
        weights = [self._norm[cid][g] + 0.05 for g in others]
        tot = sum(weights)
        r = rng.random() * tot
        for g, w in zip(others, weights):
            r -= w
            if r <= 0:
                return g
        return others[-1]

    def verify(self, cid, value, verifier_skill, nonce):
        """True iff the gene is significantly enriched for this type (real DE)."""
        c = self._constraints[cid]
        rng = rng_for("verify", self.seed, cid, value, nonce)
        sig = self._by_short[cid]["train_sig"].get(value, False)
        fn = 0.06 * (1.0 - 0.7 * verifier_skill)        # occasional false negative
        if sig:
            return rng.random() >= fn
        return rng.random() < fn * 0.5                  # rare false positive

    def attack(self, cid, value, attacker_skill, nonce):
        """Falsification succeeds when the gene is NOT specific to this type.

        Specificity comes straight from the normalised Wilcoxon enrichment.
        """
        rng = rng_for("attack", self.seed, cid, value, nonce)
        specificity = self._norm[cid].get(value, 0.0)   # 1.0 for the true marker
        # true marker: only a spurious attack (scaled down by attacker skill) lands;
        # distractor: attacks land often.
        p_break = (1.0 - specificity) * (0.35 + 0.6 * attacker_skill)
        if specificity >= 0.99:
            p_break = 0.05 * (1.0 - attacker_skill)
        return rng.random() < p_break

    def true_score(self, assignment: Dict[str, str]) -> float:
        if not self._constraints:
            return 0.0
        hit = sum(1 for cid, c in self._constraints.items()
                  if assignment.get(cid) == c.truth)
        return hit / len(self._constraints)

    # -- independent external validation (validation dataset) ---------------
    def external_replication(self, assignment: Dict[str, str]) -> Dict[str, bool]:
        """For each committed marker, does it appear in the validation dataset's
        top-K enriched genes for that same cell type? (real cross-dataset test)."""
        out = {}
        for cid in self._constraints:
            chosen = assignment.get(cid)
            out[cid] = bool(chosen in self._by_short[cid]["val_topk"])
        return out


def _table(problem, assignment):
    rows = ["", "## committed markers  (chosen vs. data-derived truth vs. external validation)",
            f"{'cell_type':<16}{'chosen':<12}{'DE-truth':<12}{'correct':<9}{'replicates_in_validation'}",
            "-" * 74]
    rep = problem.external_replication(assignment)
    for cid in problem._constraints:
        chosen = assignment.get(cid, "<unresolved>")
        truth = problem.truth_of(cid)
        ok = "OK" if chosen == truth else "X"
        rows.append(f"{cid:<16}{chosen:<12}{truth:<12}{ok:<9}{'YES' if rep[cid] else 'no'}")
    n_rep = sum(rep.values())
    rows.append("-" * 74)
    rows.append(f"external replication rate: {n_rep}/{len(rep)} = {n_rep/len(rep):.3f}")
    return "\n".join(rows)


def main():
    with open(TASK_PATH) as f:
        task = json.load(f)
    prov = task["provenance"]
    problem = PeriodontalMarkerProblem(task)

    print("=" * 74)
    print("MOSAIC-Omega  |  REAL periodontal gingival single-cell omics")
    print("=" * 74)
    print("primary (train/truth):", prov["primary"])
    print("  gingival cells:", prov["n_primary_gingiva"])
    print("validation (external): ", prov["validation"])
    print("  gingival cells:", prov["n_valid_gingiva"], "| common genes:", prov["common_genes"])
    print("cell types / constraints:", len(task["types"]))

    result = MosaicOmega(MosaicConfig(max_iterations=12)).solve(problem)
    print("\n" + result.summary())
    assignment = result.final_candidate.assignment if result.final_candidate else {}
    print(_table(problem, assignment))
    print("\nunresolved constraints:", result.unresolved_constraints or "none")
    print()
    print(MetricsEngine(result.trace, problem).report())


if __name__ == "__main__":
    main()
