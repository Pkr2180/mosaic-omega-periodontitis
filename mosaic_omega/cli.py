"""Command-line entry point:  python -m mosaic_omega.cli --help"""
from __future__ import annotations

import argparse
import json
import sys

from .config import MosaicConfig
from .metrics import MetricsEngine
from .orchestrator import MosaicOmega
from .problem import SyntheticConstraintProblem


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mosaic-omega",
                                description="Run the MOSAIC-Omega agentic architecture.")
    p.add_argument("--seed", type=int, default=20260807)
    p.add_argument("--stages", type=int, default=3)
    p.add_argument("--constraints", type=int, default=5, help="constraints per stage")
    p.add_argument("--universes", type=int, default=3)
    p.add_argument("--max-iterations", type=int, default=10)
    p.add_argument("--jurors", type=int, default=5)
    p.add_argument("--blinding", choices=["strict", "partial", "none"], default="strict")
    p.add_argument("--chaos-agent", type=float, default=0.0,
                   help="probability an agent call is faulted (reliability testing)")
    p.add_argument("--chaos-branch", type=float, default=0.0,
                   help="probability a branch invariant is corrupted")
    p.add_argument("--json", action="store_true", help="emit metrics as JSON")
    p.add_argument("--report", action="store_true", help="print the markdown report")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = MosaicConfig(
        seed=args.seed,
        n_universes=args.universes,
        max_iterations=args.max_iterations,
        n_jurors=args.jurors,
        blinding_level=args.blinding,
        chaos_agent_failure_rate=args.chaos_agent,
        chaos_branch_corruption_rate=args.chaos_branch,
    )
    problem = SyntheticConstraintProblem(
        n_stages=args.stages, constraints_per_stage=args.constraints, seed=args.seed
    )
    result = MosaicOmega(cfg).solve(problem)
    engine = MetricsEngine(result.trace, problem)

    print(result.summary())
    if result.unresolved_constraints:
        print(f"explicitly unresolved: {result.unresolved_constraints}")
    if args.json:
        print(json.dumps(engine.compute(), indent=2, default=str))
    elif args.report:
        print()
        print(engine.report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
