#!/usr/bin/env python3
"""MOSAIC-Omega demo: single run + full metric report + ablation benchmark."""
from __future__ import annotations

import sys

import _paths  # noqa: F401  -- puts the repository root on sys.path

from mosaic_omega import MetricsEngine, MosaicConfig, MosaicOmega, SyntheticConstraintProblem
from mosaic_omega.benchmark import ablation_suite, comparison_table

HEADLINE = [
    "outcome.ground_truth_accuracy",
    "outcome.final_composite_score",
    "outcome.score_truth_gap",
    "outcome.iterations",
    "reasoning.mean_falsification_survival",
    "consensus.mean_jury_kappa",
    "efficiency.tokens_used",
    "efficiency.producer_utilisation",
    "reliability.contract_compliance_rate",
    "reliability.containment_ratio",
    "routing.oracle_match_rate",
    "routing.confidence_ece",
    "structure.mean_modularity",
    "safety.blinding_leak_rate",
    "safety.anchoring_index",
    "safety.branch_isolation_purity",
    "consensus.premature_consensus_index",
    "control.evoi_calibration_r",
]


def main() -> int:
    print("=" * 74)
    print("MOSAIC-Omega -- single run")
    print("=" * 74)
    problem = SyntheticConstraintProblem(n_stages=3, constraints_per_stage=5)
    result = MosaicOmega(MosaicConfig()).solve(problem)
    print(result.summary())
    if result.unresolved_constraints:
        print(f"explicitly unresolved: {result.unresolved_constraints}")
    print()
    print(MetricsEngine(result.trace, problem).report())

    print("=" * 74)
    print("Ablation benchmark (3 seeds per variant)")
    print("=" * 74)
    suite = ablation_suite(seeds=(1, 2, 3))
    for name, bench in suite.items():
        print(f"\n--- {name} ---")
        print(bench.table(HEADLINE))

    print()
    print("=" * 74)
    print("Ablation comparison (means, delta vs `full`)")
    print("=" * 74)
    print(comparison_table(suite, HEADLINE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
