"""Global configuration for MOSAIC-Omega."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Any


@dataclass
class MosaicConfig:
    # --- determinism -------------------------------------------------------
    seed: int = 20260807

    # --- loop control ------------------------------------------------------
    max_iterations: int = 10
    max_delegation_depth: int = 4
    min_evoi: float = 0.0                 # continue only if EVOI > this
    evoi_quality_weight: float = 1.0
    evoi_risk_weight: float = 0.35

    # --- budgets -----------------------------------------------------------
    token_budget: int = 250_000
    tool_call_budget: int = 600
    wall_clock_budget_s: float = 600.0
    per_agent_token_budget: int = 14_000
    per_agent_wall_clock_s: float = 45.0
    token_cost_per_unit: float = 5.0e-7   # quality-units per token
    time_cost_per_second: float = 5.0e-4

    # --- provisioning / pruning -------------------------------------------
    max_active_agents: int = 24
    min_active_agents: int = 3
    prune_utility_threshold: float = 0.30
    redundancy_jaccard: float = 0.75
    prune_grace_iterations: int = 1       # agents are immune for N iterations
    micro_agent_ttl: int = 1              # ephemeral micro-agents expire fast
    max_micro_agents_per_iteration: int = 3

    # --- sovereignty -------------------------------------------------------
    sovereignty_hysteresis: float = 0.12
    sovereignty_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "domain_match": 0.40,
            "reputation": 0.30,
            "verification_pass": 0.20,
            "failure_penalty": 0.10,
        }
    )

    # --- topology ----------------------------------------------------------
    edge_learning_rate: float = 0.35      # gradient-descent step size eta on J
    edge_prune_threshold: float = 0.18
    max_degree: int = 6
    topology_add_top_k: int = 2
    contamination_penalty: float = 0.45

    # --- free-energy structural control (FESC) -----------------------------
    fe_kappa: float = 1.0                 # wiring cost; kappa=1 => legacy update
    fe_lambda_U: float = 0.15             # price of residual belief uncertainty

    # --- universes ---------------------------------------------------------
    n_universes: int = 3
    universe_strategies: tuple = ("conservative", "exploratory", "adversarial")

    # --- adjudication ------------------------------------------------------
    n_jurors: int = 5
    jury_margin_threshold: float = 0.04
    falsifiers_per_candidate: int = 2
    attacks_per_falsifier: int = 3
    minority_entropy_floor: float = 0.35   # reporting threshold for entropy collapse
    consensus_share_ceiling: float = 0.60  # top cluster share that counts as consensus
    evidence_sufficiency_floor: float = 0.60

    # --- verification ------------------------------------------------------
    base_verification_fraction: float = 0.45
    high_risk_verification_fraction: float = 0.90
    verifier_false_negative_rate: float = 0.06

    # --- guards ------------------------------------------------------------
    duplicate_loop_k: int = 3
    oscillation_window: int = 8
    oscillation_min_period: int = 2
    oscillation_max_period: int = 4
    oscillation_min_repeats: int = 2
    stagnation_window: int = 3
    stagnation_epsilon: float = 0.01
    max_recovery_attempts: int = 3
    watchdog_heartbeat_s: float = 30.0

    # --- blinding ----------------------------------------------------------
    blinding_level: str = "strict"         # strict | partial | none
    anchor_susceptibility: float = 0.55    # P(adopt a visible peer answer | unblinded)

    # --- chaos / fault injection (reliability benchmarking) ----------------
    chaos_agent_failure_rate: float = 0.0      # P(agent call raises)
    chaos_branch_corruption_rate: float = 0.0  # P(branch invariant is broken)

    # --- execution ---------------------------------------------------------
    parallel_universes: bool = False       # thread pool; results stay deterministic
    verbose: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["universe_strategies"] = list(self.universe_strategies)
        return d
