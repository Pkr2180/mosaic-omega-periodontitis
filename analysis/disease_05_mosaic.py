"""MOSAIC-Omega as an adversarial-consensus biomarker selector on real
periodontitis DE candidates.

Per cell type the architecture must commit to ONE disease biomarker from the top
single-cell-DE candidates. Its verify/attack oracles are grounded in real
leave-sample-out (LOSO) reproducibility, so falsification penalises genes whose
disease signal collapses when a patient is removed (pseudoreplication artifacts).

Headline test: does the architecture's committed signature reproduce better
(higher LOSO robustness) than the naive 'take the top-Wilcoxon gene' baseline?
"""
from __future__ import annotations
import os, json
import numpy as np
from typing import Dict, List

from mosaic_omega import MosaicConfig, MosaicOmega, MetricsEngine
from mosaic_omega.problem import Problem, _Constraint
from mosaic_omega.rng import rng_for
from mosaic_omega.types import RiskLevel, StageSpec

ROOT = r"C:\Users\Pradeep Kumar\Downloads\latest architecture -1"
CAND = os.path.join(ROOT, "tables", "disease_candidates.json")

LINEAGE = {
    "T cell (CD4)": "lymphoid", "T cell (CD8)": "lymphoid", "NK cell": "lymphoid",
    "B cell": "lymphoid", "Plasma cell": "lymphoid",
    "Dendritic cell": "myeloid", "Neutrophil": "myeloid", "Mast cell": "myeloid",
    "Macrophage": "myeloid",
    "Fibroblast": "stromal", "Endothelial": "stromal", "Epithelial": "stromal",
}
STAGE_RISK = {"stromal": RiskLevel.MEDIUM, "lymphoid": RiskLevel.HIGH, "myeloid": RiskLevel.HIGH}


class DiseaseBiomarkerProblem(Problem):
    goal = "Select a reproducible periodontitis biomarker per cell type"

    def __init__(self, cand: dict, seed: int = 20260807):
        self.seed = seed
        self.short = {ct: ct.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
                      for ct in cand}
        self.info = {}
        self._constraints: Dict[str, _Constraint] = {}
        for ct, d in cand.items():
            sid = self.short[ct]
            genes = d["candidates"]; rob = d["robustness"]
            self.info[sid] = {"cell_type": ct, "candidates": genes, "robustness": rob,
                              "truth": d["truth"], "naive": genes[0]}  # genes[0] = top-Wilcoxon
            self._constraints[sid] = _Constraint(sid, LINEAGE.get(ct, "stromal"),
                                                 list(genes), d["truth"], 1.0)
        # stages by lineage
        by_stage: Dict[str, List[str]] = {}
        for sid, meta in self.info.items():
            by_stage.setdefault(LINEAGE.get(meta["cell_type"], "stromal"), []).append(sid)
        self._stages = []
        for lin, members in by_stage.items():
            self._stages.append(StageSpec(
                stage_id=f"S_{lin}", description=f"{lin} biomarkers",
                constraint_ids=members, required_capabilities=[lin],
                risk=STAGE_RISK.get(lin, RiskLevel.MEDIUM),
                success_predicate="verified_score >= 0.85",
                verification_intensity=0.90 if STAGE_RISK.get(lin)==RiskLevel.HIGH else 0.45))

    def stages(self): return list(self._stages)
    def capability_catalog(self): return ["lymphoid", "myeloid", "stromal"]
    def value_space(self, cid): return list(self._constraints[cid].values)
    def capability_for(self, cid): return self._constraints[cid].capability
    def truth_of(self, cid): return self._constraints[cid].truth

    def _rob(self, cid, gene): return float(self.info[cid]["robustness"].get(gene, 0.0))

    def _p_correct(self, skill): return max(0.05, min(0.99, 0.30 + 0.66 * skill))

    def propose(self, cid, agent_id, skill, nonce):
        c = self._constraints[cid]; rng = rng_for("propose", self.seed, cid, agent_id, nonce)
        if rng.random() < self._p_correct(skill):
            return max(c.values, key=lambda g: self._rob(cid, g))
        others = [g for g in c.values if g != c.truth]
        w = [self._rob(cid, g) + 0.05 for g in others]; tot = sum(w); r = rng.random()*tot
        for g, wi in zip(others, w):
            r -= wi
            if r <= 0: return g
        return others[-1]

    def verify(self, cid, value, verifier_skill, nonce):
        rng = rng_for("verify", self.seed, cid, value, nonce)
        rob = self._rob(cid, value); fn = 0.06*(1-0.7*verifier_skill)
        return rng.random() >= fn if rob >= 0.8 else rng.random() < fn*0.5

    def attack(self, cid, value, attacker_skill, nonce):
        rng = rng_for("attack", self.seed, cid, value, nonce); rob = self._rob(cid, value)
        p = (1.0 - rob) * (0.35 + 0.6*attacker_skill)
        if rob >= 0.99: p = 0.05*(1-attacker_skill)
        return rng.random() < p

    def true_score(self, assignment):
        hit = sum(1 for cid, c in self._constraints.items() if assignment.get(cid) == c.truth)
        return hit / len(self._constraints) if self._constraints else 0.0

    # -- evaluation: reproducibility of a signature -------------------------
    def mean_robustness(self, assignment):
        return float(np.mean([self._rob(cid, assignment.get(cid, "")) for cid in self._constraints]))

    def naive_signature(self):
        return {cid: self.info[cid]["naive"] for cid in self._constraints}


def main():
    cand = json.load(open(CAND))
    print(f"cell types (constraints): {len(cand)}", flush=True)
    problem = DiseaseBiomarkerProblem(cand)

    accs, robs = [], []
    committed = None
    for s in range(5):
        res = MosaicOmega(MosaicConfig(max_iterations=12, seed=20260807+s)).solve(problem)
        a = res.final_candidate.assignment if res.final_candidate else {}
        accs.append(res.metrics["outcome"]["ground_truth_accuracy"])
        robs.append(problem.mean_robustness(a))
        if s == 0:
            committed = a; metrics0 = res.metrics; res0 = res

    naive = problem.naive_signature()
    naive_rob = problem.mean_robustness(naive)
    mosaic_rob = np.mean(robs)

    print("\n=== MOSAIC-Omega disease-biomarker consensus ===", flush=True)
    print(f"{'cell_type':<16}{'MOSAIC pick':<12}{'robust':<8}{'naive(WilcoxonTop)':<20}{'robust'}")
    print("-"*72)
    rows = []
    for cid in problem._constraints:
        m = committed.get(cid); n = naive[cid]
        print(f"{cid:<16}{m:<12}{problem._rob(cid,m):<8.2f}{n:<20}{problem._rob(cid,n):.2f}")
        rows.append({"cell_type": problem.info[cid]["cell_type"], "mosaic_pick": m,
                     "mosaic_robustness": problem._rob(cid, m), "naive_pick": n,
                     "naive_robustness": problem._rob(cid, n)})
    print("-"*72)
    print(f"MOSAIC accuracy (vs LOSO-robust truth): {np.mean(accs):.3f} ± {np.std(accs):.3f}")
    print(f"Mean LOSO robustness  MOSAIC={mosaic_rob:.3f}  vs  naive-Wilcoxon={naive_rob:.3f}")
    print(f"safety: blinding_leak_rate={metrics0['safety']['blinding_leak_rate']}, "
          f"anchoring_index={metrics0['safety']['anchoring_index']}, "
          f"contract_compliance={metrics0['reliability']['contract_compliance_rate']}")

    import csv
    with open(os.path.join(ROOT, "tables", "mosaic_disease_consensus.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    json.dump({"mosaic_accuracy_mean": float(np.mean(accs)),
               "mosaic_accuracy_std": float(np.std(accs)),
               "mosaic_mean_robustness": float(mosaic_rob),
               "naive_mean_robustness": float(naive_rob),
               "committed": committed, "naive": naive},
              open(os.path.join(ROOT, "tables", "mosaic_disease_result.json"), "w"), indent=1)
    print("\nwrote tables/mosaic_disease_consensus.csv + result.json", flush=True)


if __name__ == "__main__":
    main()
