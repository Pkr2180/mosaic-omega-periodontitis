"""MOSAIC-Omega applied to periodontal spatial-omics data synthesis.

This casts a realistic *synthetic* periodontal spatial-transcriptomics pipeline
as a constraint-satisfaction mission. Each constraint is a real methodological
decision (which simulator, which normalisation, which deconvolution reference,
which host-microbe colocalisation test, ...) with a discrete set of candidate
options and one ground-truth *methodologically-correct* choice for spatial
periodontal data. MOSAIC-Omega must provision agents, route the decisions,
falsify, adjudicate and converge on the correct pipeline.

Honesty note: this is a deterministic synthetic benchmark, not an analysis of
real patient tissue. "ground_truth_accuracy" measures whether the architecture
recovered the pre-registered correct methodological choices -- the system's own
scorers never see them.
"""
from __future__ import annotations

from typing import Dict, List

from mosaic_omega import MetricsEngine, MosaicConfig, MosaicOmega
from mosaic_omega.problem import Problem, _Constraint
from mosaic_omega.types import RiskLevel, StageSpec


# (constraint_id, capability, [candidate options], correct_option, weight, human description)
PIPELINE: List[tuple] = [
    # ---- Stage S0: data synthesis & quality control (LOW risk) --------------
    ("syn_generative_model", "data_synthesis",
     ["scDesign3", "splatter", "SRTsim", "ZINB_WaVE"], "SRTsim", 1.0,
     "Generative model for synthetic spatial transcriptomics"),
    ("syn_spatial_pattern", "spatial_statistics",
     ["random", "gaussian_process", "gradient", "hotspot"], "gaussian_process", 1.0,
     "Spatial autocorrelation structure to inject"),
    ("qc_normalization", "transcriptomics_qc",
     ["CPM", "SCTransform", "scran_pooling", "log1p_raw"], "SCTransform", 1.0,
     "Count normalisation method"),
    ("qc_min_counts_filter", "transcriptomics_qc",
     ["none", "100", "200", "500"], "200", 0.8,
     "Per-spot minimum-count filter"),
    ("batch_correction", "transcriptomics_qc",
     ["none", "harmony", "combat", "mnn"], "harmony", 1.0,
     "Batch / section integration"),

    # ---- Stage S1: spatial structure & cell composition (MEDIUM risk) -------
    ("domain_detection", "spatial_statistics",
     ["kmeans", "louvain_nonspatial", "BayesSpace", "SpaGCN"], "BayesSpace", 1.2,
     "Spatial domain / tissue-region clustering"),
    ("deconvolution_method", "cell_deconvolution",
     ["RCTD", "cell2location", "stereoscope", "NNLS"], "cell2location", 1.2,
     "Spot-level cell-type deconvolution"),
    ("reference_atlas", "cell_deconvolution",
     ["gut_atlas", "pbmc_atlas", "oral_mucosa_atlas", "generic"], "oral_mucosa_atlas", 1.3,
     "Reference atlas for deconvolution"),
    ("neighborhood_analysis", "spatial_statistics",
     ["squidpy_nhood", "kNN_graph", "delaunay", "giotto_hmrf"], "squidpy_nhood", 1.0,
     "Cellular neighbourhood enrichment"),
    ("spatial_variable_genes", "spatial_statistics",
     ["morans_I", "SpatialDE", "SPARK", "hvg_nonspatial"], "SPARK", 1.0,
     "Spatially variable gene detection"),

    # ---- Stage S2: host-microbiome interface & mechanism (HIGH risk) --------
    ("host_microbe_colocalization", "microbiome_ecology",
     ["pearson_global", "spatial_crosscorr", "join_count", "none"], "spatial_crosscorr", 1.5,
     "Host-microbe spatial colocalisation test"),
    ("immune_infiltration_signature", "immunology",
     ["xcell", "cibersortx", "MCPcounter", "marker_score"], "cibersortx", 1.5,
     "Immune infiltrate quantification"),
    ("osteoclast_RANKL_axis", "bone_biology",
     ["bulk_deseq", "spatial_ligand_receptor", "wgcna", "none"], "spatial_ligand_receptor", 1.5,
     "RANKL/OPG osteoclast signalling axis"),
    ("collagen_MMP_gradient", "pathway_inference",
     ["gradient_along_axis", "global_mean", "random", "cluster_mean"], "gradient_along_axis", 1.4,
     "Collagen-degradation / MMP spatial gradient"),
    ("cell_cell_communication", "pathway_inference",
     ["cellphonedb", "cellchat", "nichenet", "none"], "nichenet", 1.5,
     "Ligand-receptor cell-cell communication"),
]

STAGE_DEF = [
    ("S0", "Synthesise & QC periodontal spatial-omics data", RiskLevel.LOW,
     [c for c in PIPELINE if c[0] in {
         "syn_generative_model", "syn_spatial_pattern", "qc_normalization",
         "qc_min_counts_filter", "batch_correction"}]),
    ("S1", "Resolve spatial structure & cell composition", RiskLevel.MEDIUM,
     [c for c in PIPELINE if c[0] in {
         "domain_detection", "deconvolution_method", "reference_atlas",
         "neighborhood_analysis", "spatial_variable_genes"}]),
    ("S2", "Infer host-microbiome interface & disease mechanism", RiskLevel.HIGH,
     [c for c in PIPELINE if c[0] in {
         "host_microbe_colocalization", "immune_infiltration_signature",
         "osteoclast_RANKL_axis", "collagen_MMP_gradient",
         "cell_cell_communication"}]),
]


class PeriodontalSpatialOmicsProblem(Problem):
    """A ground-truth-bearing periodontal spatial-omics pipeline benchmark.

    Reuses MOSAIC-Omega's domain-agnostic proposal / verification / attack /
    scoring oracles (inherited from Problem via the shared _Constraint model);
    only the decisions, their option spaces and the correct choices are
    domain-specific.
    """

    goal = "Configure a correct periodontal spatial-omics synthesis & analysis pipeline"

    def __init__(self, seed: int = 20260807) -> None:
        self.seed = seed
        self.floor_accuracy = 0.28
        self.skill_gain = 0.66
        self.verifier_false_negative = 0.06
        self._caps = [
            "data_synthesis", "spatial_statistics", "transcriptomics_qc",
            "cell_deconvolution", "microbiome_ecology", "immunology",
            "bone_biology", "pathway_inference",
        ]
        self._constraints: Dict[str, _Constraint] = {}
        self._meta: Dict[str, str] = {}
        for cid, cap, values, truth, weight, desc in PIPELINE:
            self._constraints[cid] = _Constraint(cid, cap, list(values), truth, weight)
            self._meta[cid] = desc

        self._stages: List[StageSpec] = []
        for sid, sdesc, risk, members in STAGE_DEF:
            cids = [m[0] for m in members]
            caps: List[str] = []
            for m in members:
                if m[1] not in caps:
                    caps.append(m[1])
            self._stages.append(StageSpec(
                stage_id=sid,
                description=sdesc,
                constraint_ids=cids,
                required_capabilities=caps,
                risk=risk,
                success_predicate="verified_score >= 0.85",
                verification_intensity=0.90 if risk == RiskLevel.HIGH else 0.45,
            ))

    # -- introspection ------------------------------------------------------
    def stages(self) -> List[StageSpec]:
        return list(self._stages)

    def capability_catalog(self) -> List[str]:
        return list(self._caps)

    def value_space(self, constraint_id: str) -> List[str]:
        return list(self._constraints[constraint_id].values)

    def capability_for(self, constraint_id: str) -> str:
        return self._constraints[constraint_id].capability

    def truth_of(self, constraint_id: str) -> str:
        return self._constraints[constraint_id].truth

    # -- agent-facing oracles (skill-driven, deterministic) -----------------
    def _p_correct(self, skill: float) -> float:
        return max(0.0, min(0.99, self.floor_accuracy + self.skill_gain * skill))

    def propose(self, constraint_id: str, agent_id: str, skill: float, nonce: str) -> str:
        from mosaic_omega.rng import rng_for
        c = self._constraints[constraint_id]
        rng = rng_for("propose", self.seed, constraint_id, agent_id, nonce)
        if rng.random() < self._p_correct(skill):
            return c.truth
        wrong = [v for v in c.values if v != c.truth]
        return wrong[rng.randrange(len(wrong))]

    def verify(self, constraint_id: str, value: str, verifier_skill: float, nonce: str) -> bool:
        from mosaic_omega.rng import rng_for
        c = self._constraints[constraint_id]
        rng = rng_for("verify", self.seed, constraint_id, value, nonce)
        fn = self.verifier_false_negative * (1.0 - 0.7 * verifier_skill)
        if value == c.truth:
            return rng.random() >= fn
        return rng.random() < fn * 0.5

    def attack(self, constraint_id: str, value: str, attacker_skill: float, nonce: str) -> bool:
        from mosaic_omega.rng import rng_for
        c = self._constraints[constraint_id]
        rng = rng_for("attack", self.seed, constraint_id, value, nonce)
        if value == c.truth:
            return rng.random() < 0.05 * (1.0 - attacker_skill)
        return rng.random() < (0.35 + 0.6 * attacker_skill)

    def true_score(self, assignment: Dict[str, str]) -> float:
        total = sum(c.weight for c in self._constraints.values())
        hit = sum(c.weight for cid, c in self._constraints.items()
                  if assignment.get(cid) == c.truth)
        return hit / total if total else 0.0


def _decision_table(problem: PeriodontalSpatialOmicsProblem, assignment: Dict[str, str]) -> str:
    rows = ["", "## pipeline decisions (chosen vs. correct)",
            f"{'decision':<32}{'chosen':<22}{'correct':<22}{'ok'}"]
    rows.append("-" * 82)
    for cid, cap, values, truth, weight, desc in PIPELINE:
        chosen = assignment.get(cid, "<unresolved>")
        ok = "OK" if chosen == truth else "X"
        rows.append(f"{cid:<32}{chosen:<22}{truth:<22}{ok}")
    return "\n".join(rows)


def main() -> None:
    problem = PeriodontalSpatialOmicsProblem()

    print("=" * 82)
    print("MOSAIC-Omega  |  periodontal spatial-omics synthesis pipeline")
    print("=" * 82)

    # Clean run.
    result = MosaicOmega(MosaicConfig(max_iterations=12)).solve(problem)
    print(result.summary())
    assignment = result.final_candidate.assignment if result.final_candidate else {}
    print(_decision_table(problem, assignment))
    print("\nunresolved constraints:", result.unresolved_constraints or "none")
    print()
    print(MetricsEngine(result.trace, problem).report())

    # Fault-injection stress run (30% agent failures, 30% branch corruption).
    print("=" * 82)
    print("Fault-injection run (chaos_agent=0.30, chaos_branch=0.30)")
    print("=" * 82)
    chaos = MosaicOmega(MosaicConfig(
        max_iterations=12, chaos_agent_failure_rate=0.30,
        chaos_branch_corruption_rate=0.30,
    )).solve(problem)
    print(chaos.summary())
    cm = chaos.metrics
    for group, keys in (
        ("outcome", ["ground_truth_accuracy", "score_truth_gap", "solved"]),
        ("reliability", ["recoveries", "containment_ratio", "contract_compliance_rate"]),
        ("safety", ["safe_termination", "branch_isolation_purity",
                    "blinding_leak_rate", "anchoring_index"]),
    ):
        for k in keys:
            print(f"  {group}.{k}: {cm[group][k]}")


if __name__ == "__main__":
    main()
