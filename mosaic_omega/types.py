"""Core data types for MOSAIC-Omega."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class Phase(str, Enum):
    OBSERVE = "observe"
    PLAN = "plan"
    ROUTE = "route"
    DELEGATE = "delegate"
    EXECUTE = "execute"
    VERIFY = "verify"
    FALSIFY = "falsify"
    SCORE = "score"
    COMMIT = "commit"
    ROLLBACK = "rollback"
    REWIRE = "rewire"
    DECIDE = "decide"


class AgentRole(str, Enum):
    SPECIALIST = "specialist"
    VERIFIER = "verifier"
    FALSIFIER = "falsifier"
    CONTRADICTION = "contradiction"
    MINORITY = "minority"
    JUROR = "juror"
    MICRO = "micro"
    WATCHDOG = "watchdog"
    META = "meta"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Termination(str, Enum):
    CONVERGED = "converged"
    MAX_ITERATIONS = "max_iterations"
    BUDGET_EXHAUSTED = "budget_exhausted"
    STAGNATION = "stagnation"
    OSCILLATION = "oscillation"
    DEADLOCK = "deadlock"
    DUPLICATE_LOOP = "duplicate_loop"
    NEGATIVE_EVOI = "negative_evoi"
    UNRESOLVED = "unresolved"
    ESCALATED_UNRESOLVED = "escalated_unresolved"
    SAFE_STOP = "safe_stop"


class FailureClass(str, Enum):
    AGENT = "agent"
    TOOL = "tool"
    BRANCH = "branch"
    ORCHESTRATION = "orchestration"
    CONTRACT = "contract"


# ---------------------------------------------------------------------------
# Mission specification
# ---------------------------------------------------------------------------
@dataclass
class StageSpec:
    stage_id: str
    description: str
    constraint_ids: List[str]
    required_capabilities: List[str]
    risk: RiskLevel = RiskLevel.MEDIUM
    success_predicate: str = "verified_score >= 0.85"
    verification_intensity: float = 0.45


@dataclass
class MissionSpec:
    mission_id: str
    goal: str
    stages: List[StageSpec]
    global_constraints: List[str] = field(default_factory=list)
    capability_catalog: List[str] = field(default_factory=list)
    acceptance_threshold: float = 0.85

    @property
    def all_constraints(self) -> List[str]:
        seen, out = set(), []
        for s in self.stages:
            for c in s.constraint_ids:
                if c not in seen:
                    seen.add(c)
                    out.append(c)
        return out


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
@dataclass
class AgentSpec:
    agent_id: str
    role: AgentRole
    capabilities: Set[str]
    skill: Dict[str, float]              # capability -> latent competence [0,1]
    token_budget: int = 10_000
    wall_clock_budget_s: float = 30.0
    ttl: Optional[int] = None            # iterations before auto-expiry (micro agents)
    created_iteration: int = 0
    universe: str = "root"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["capabilities"] = sorted(self.capabilities)
        d["role"] = self.role.value
        return d


@dataclass
class AgentRuntime:
    spec: AgentSpec
    alpha: float = 1.0                   # Beta posterior successes (+prior)
    beta: float = 1.0                    # Beta posterior failures (+prior)
    tokens_used: int = 0
    time_used_s: float = 0.0
    tasks_done: int = 0
    verified_true: int = 0
    verified_false: int = 0
    falsified_claims: int = 0
    contract_violations: int = 0
    alive: bool = True
    pruned_reason: Optional[str] = None
    last_heartbeat: float = 0.0
    contributions: float = 0.0

    @property
    def agent_id(self) -> str:
        return self.spec.agent_id

    @property
    def reputation(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def verification_pass_rate(self) -> float:
        n = self.verified_true + self.verified_false
        return self.verified_true / n if n else 0.5

    @property
    def failure_rate(self) -> float:
        n = self.tasks_done
        return (self.falsified_claims + self.contract_violations) / n if n else 0.0


# ---------------------------------------------------------------------------
# Claims, candidates, verdicts
# ---------------------------------------------------------------------------
@dataclass
class Claim:
    claim_id: str
    constraint_id: str
    value: str
    author: str
    confidence: float
    universe: str
    iteration: int
    verified: Optional[bool] = None      # None = unverified
    falsified: bool = False
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Candidate:
    candidate_id: str
    universe: str
    iteration: int
    assignment: Dict[str, str]
    claims: List[Claim] = field(default_factory=list)
    authors: List[str] = field(default_factory=list)
    raw_score: float = 0.0
    verified_score: float = 0.0
    falsification_survival: float = 1.0
    contradiction_penalty: float = 0.0
    jury_score: float = 0.0
    composite_score: float = 0.0
    confidence: float = 0.5
    is_minority: bool = False

    def signature(self) -> str:
        from .rng import stable_sig
        return stable_sig(tuple(sorted(self.assignment.items())))


@dataclass
class Attack:
    attack_id: str
    attacker: str
    candidate_id: str
    constraint_id: str
    kind: str                            # counterexample | assumption | edge_case | metric_gaming
    succeeded: bool
    rationale: str


@dataclass
class FalsificationReport:
    candidate_id: str
    attacks: List[Attack] = field(default_factory=list)

    @property
    def attempted(self) -> int:
        return len(self.attacks)

    @property
    def successful(self) -> int:
        return sum(1 for a in self.attacks if a.succeeded)

    @property
    def survival(self) -> float:
        return 1.0 - (self.successful / self.attempted) if self.attempted else 1.0


@dataclass
class Contradiction:
    constraint_id: str
    claim_a: str
    claim_b: str
    kind: str                            # value_conflict | commitment_conflict
    detected_by: str


@dataclass
class JurorBallot:
    juror_id: str
    scores: Dict[str, float]             # candidate_id -> score
    top_choice: str
    reputation: float


@dataclass
class JuryVerdict:
    winner_id: Optional[str]
    ballots: List[JurorBallot] = field(default_factory=list)
    aggregate: Dict[str, float] = field(default_factory=dict)
    margin: float = 0.0
    agreement_kappa: float = 0.0
    blinded: bool = True


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------
@dataclass
class Contract:
    contract_id: str
    principal: str
    agent: str
    task_id: str
    depth: int
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    allowed_tools: Set[str] = field(default_factory=set)
    forbidden_scopes: Set[str] = field(default_factory=set)
    deliverable_keys: Set[str] = field(default_factory=set)
    token_budget: int = 8_000
    deadline_s: float = 30.0
    max_depth: int = 4


@dataclass
class ContractResult:
    contract_id: str
    ok: bool
    violations: List[str] = field(default_factory=list)
    tokens_used: int = 0
    elapsed_s: float = 0.0


# ---------------------------------------------------------------------------
# Checkpoints & events
# ---------------------------------------------------------------------------
@dataclass
class Checkpoint:
    checkpoint_id: str
    parent_id: Optional[str]
    iteration: int
    phase: Phase
    state_blob: str                      # JSON serialised orchestration state
    integrity_hash: str
    branch: str = "root"
    corrupted: bool = False


@dataclass
class LoopEvent:
    iteration: int
    phase: Phase
    universe: str
    detail: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class RoutingDecision:
    iteration: int
    task_id: str
    chosen: str
    ranked: List[Tuple[str, float]]
    oracle_choice: str
    oracle_utility: float
    chosen_utility: float
    predicted_reliability: float
    realized_success: Optional[bool] = None


@dataclass
class SovereigntyTransfer:
    iteration: int
    from_agent: Optional[str]
    to_agent: str
    competence_from: float
    competence_to: float


@dataclass
class TopologySnapshot:
    iteration: int
    n_nodes: int
    n_edges: int
    edges_added: int
    edges_removed: int
    avg_degree: float
    degree_entropy: float
    modularity: float
    avg_path_length: float


@dataclass
class RecoveryRecord:
    iteration: int
    failure_class: FailureClass
    detail: str
    rolled_back_to: Optional[str]
    attempts: int
    contained: bool
    escalated: bool
    recovered_at_iteration: Optional[int] = None


@dataclass
class RunTrace:
    """Everything the metrics engine needs. Append-only during a run."""
    mission: Optional[MissionSpec] = None
    events: List[LoopEvent] = field(default_factory=list)
    iterations: int = 0
    termination: Optional[Termination] = None
    final_candidate: Optional[Candidate] = None

    claims: List[Claim] = field(default_factory=list)
    candidates: List[Candidate] = field(default_factory=list)
    falsifications: List[FalsificationReport] = field(default_factory=list)
    contradictions: List[Contradiction] = field(default_factory=list)
    verdicts: List[JuryVerdict] = field(default_factory=list)

    agents_provisioned: List[AgentSpec] = field(default_factory=list)
    agents_used: Set[str] = field(default_factory=set)
    prune_decisions: List[Dict[str, Any]] = field(default_factory=list)
    routing: List[RoutingDecision] = field(default_factory=list)
    sovereignty: List[SovereigntyTransfer] = field(default_factory=list)
    topology: List[TopologySnapshot] = field(default_factory=list)

    contracts: List[Contract] = field(default_factory=list)
    contract_results: List[ContractResult] = field(default_factory=list)

    checkpoints: List[Checkpoint] = field(default_factory=list)
    recoveries: List[RecoveryRecord] = field(default_factory=list)
    guard_trips: List[Dict[str, Any]] = field(default_factory=list)
    escalations: List[Dict[str, Any]] = field(default_factory=list)

    blinding_leaks: int = 0
    blinding_checks: int = 0
    anchored_outputs: int = 0
    anchor_opportunities: int = 0

    tokens_used: int = 0
    tool_calls_used: int = 0
    wall_clock_s: float = 0.0
    budget_overruns: List[str] = field(default_factory=list)

    score_history: List[float] = field(default_factory=list)
    entropy_history: List[float] = field(default_factory=list)
    evoi_predicted: List[float] = field(default_factory=list)
    evoi_realized: List[float] = field(default_factory=list)
    minority_preserved: int = 0
    minority_survived_to_final: int = 0
    idempotent_hits: int = 0
    duplicates_prevented: int = 0
    isolation_purity: float = 1.0
    total_iterations: int = 0
    state_signatures: List[str] = field(default_factory=list)
