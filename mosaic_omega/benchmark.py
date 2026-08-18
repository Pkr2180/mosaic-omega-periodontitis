"""Multi-seed benchmark harness.

Runs MOSAIC-Omega across seeds (and optionally across ablations) and aggregates
every numeric metric with mean / std / min / max, so architecture changes can be
compared against a fixed protocol rather than a single lucky run.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .config import MosaicConfig
from .orchestrator import MosaicOmega, RunResult
from .problem import Problem, SyntheticConstraintProblem


def fmt_number(value: Optional[float]) -> str:
    """Compact fixed-width-friendly rendering: big numbers lose decimals."""
    if value is None:
        return "n/a"
    a = abs(value)
    if a >= 10000:
        return f"{value:,.0f}"
    if a >= 100:
        return f"{value:.2f}"
    return f"{value:.4f}"


@dataclass
class BenchmarkResult:
    label: str
    runs: List[RunResult] = field(default_factory=list)
    aggregate: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def table(self, keys: Optional[Sequence[str]] = None) -> str:
        keys = [k for k in (keys or sorted(self.aggregate)) if k in self.aggregate]
        width = max((len(k) for k in keys), default=10) + 2
        cells = {
            k: [fmt_number(self.aggregate[k][f]) for f in ("mean", "std", "min", "max")]
            for k in keys
        }
        num_w = max([len(c) for row in cells.values() for c in row] + [6]) + 2
        head = "".join(h.rjust(num_w) for h in ("mean", "std", "min", "max"))
        lines = [f"{'metric'.ljust(width)}{head}"]
        for k in keys:
            lines.append(k.ljust(width) + "".join(c.rjust(num_w) for c in cells[k]))
        return "\n".join(lines)


class Benchmark:
    def __init__(self, seeds: Sequence[int] = (1, 2, 3, 4, 5),
                 problem_factory: Optional[Callable[[int], Problem]] = None) -> None:
        self.seeds = list(seeds)
        self.problem_factory = problem_factory or (
            lambda seed: SyntheticConstraintProblem(seed=seed)
        )

    def run(self, config: Optional[MosaicConfig] = None,
            label: str = "default") -> BenchmarkResult:
        base = config or MosaicConfig()
        result = BenchmarkResult(label=label)
        for seed in self.seeds:
            cfg = MosaicConfig(**{**base.to_dict(),
                                  "seed": seed,
                                  "universe_strategies": base.universe_strategies})
            problem = self.problem_factory(seed)
            result.runs.append(MosaicOmega(cfg).solve(problem))
        result.aggregate = self._aggregate(result.runs)
        return result

    def compare(self, variants: Dict[str, MosaicConfig]) -> Dict[str, BenchmarkResult]:
        return {name: self.run(cfg, label=name) for name, cfg in variants.items()}

    @staticmethod
    def _aggregate(runs: Sequence[RunResult]) -> Dict[str, Dict[str, float]]:
        buckets: Dict[str, List[float]] = {}
        for r in runs:
            for group, values in r.metrics.items():
                for key, value in values.items():
                    if isinstance(value, bool):
                        value = float(value)
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        if value is None or (isinstance(value, float) and math.isnan(value)):
                            continue
                        buckets.setdefault(f"{group}.{key}", []).append(float(value))
        out: Dict[str, Dict[str, float]] = {}
        for key, vals in buckets.items():
            out[key] = {
                "mean": statistics.fmean(vals),
                "std": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
                "min": min(vals),
                "max": max(vals),
                "n": float(len(vals)),
            }
        return out


ABLATIONS: Dict[str, Dict[str, Any]] = {
    "full": {},
    "no_blinding": {"blinding_level": "none"},
    "single_universe": {"n_universes": 1},
    "no_falsification": {"falsifiers_per_candidate": 0, "attacks_per_falsifier": 0},
    "no_pruning": {"prune_utility_threshold": -1.0, "redundancy_jaccard": 2.0},
    "small_jury": {"n_jurors": 1},
    "chaos_25": {"chaos_agent_failure_rate": 0.25, "chaos_branch_corruption_rate": 0.25},
}


def comparison_table(results: Dict[str, "BenchmarkResult"],
                     keys: Sequence[str],
                     baseline: str = "full") -> str:
    """Render variants side by side (means), with delta against the baseline."""
    names = [n for n in results if n != baseline]
    names = ([baseline] if baseline in results else []) + names
    label_w = max((len(k) for k in keys), default=10) + 2
    col_w = max([len(n) for n in names] + [10]) + 2

    def cell(name: str, key: str) -> str:
        agg = results[name].aggregate.get(key)
        if not agg:
            return "n/a"
        text = fmt_number(agg["mean"])
        base = results.get(baseline)
        if base is not None and name != baseline:
            b = base.aggregate.get(key)
            if b:
                d = agg["mean"] - b["mean"]
                if abs(d) >= 1e-9:
                    text += f" ({'+' if d > 0 else ''}{fmt_number(d)})"
        return text

    rows = {k: [cell(n, k) for n in names] for k in keys}
    col_w = max([col_w] + [len(c) + 2 for row in rows.values() for c in row])
    lines = ["metric".ljust(label_w) + "".join(n.rjust(col_w) for n in names)]
    lines.append("-" * (label_w + col_w * len(names)))
    for k in keys:
        lines.append(k.ljust(label_w) + "".join(c.rjust(col_w) for c in rows[k]))
    return "\n".join(lines)


def ablation_suite(seeds: Sequence[int] = (1, 2, 3),
                   base: Optional[MosaicConfig] = None) -> Dict[str, BenchmarkResult]:
    base = base or MosaicConfig(max_iterations=6)
    variants: Dict[str, MosaicConfig] = {}
    for name, overrides in ABLATIONS.items():
        d = base.to_dict()
        d.update(overrides)
        d["universe_strategies"] = base.universe_strategies
        variants[name] = MosaicConfig(**d)
    return Benchmark(seeds).compare(variants)
