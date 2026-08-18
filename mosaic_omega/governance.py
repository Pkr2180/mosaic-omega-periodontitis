"""Agentic Blinding and Contractual Handoffs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .rng import stable_sig
from .types import Contract, ContractResult


# ---------------------------------------------------------------------------
# Agentic Blinding
# ---------------------------------------------------------------------------
BLINDABLE_KEYS: Set[str] = {
    "peer_conclusions", "peer_confidences", "peer_scores", "peer_authors",
    "author", "author_reputation", "prior_verdicts", "universe_leaderboard",
    "current_best", "jury_history", "sovereign_opinion", "reputation_table",
}

PARTIAL_KEEP: Set[str] = {"peer_conclusions"}


@dataclass
class BlindingPolicy:
    level: str = "strict"                # strict | partial | none
    extra_blind: Set[str] = field(default_factory=set)
    allow: Set[str] = field(default_factory=set)

    def blinded_keys(self) -> Set[str]:
        if self.level == "none":
            return set()
        keys = set(BLINDABLE_KEYS) | set(self.extra_blind)
        if self.level == "partial":
            keys -= PARTIAL_KEEP
        return keys - set(self.allow)


@dataclass
class BlindingReport:
    redacted: List[str] = field(default_factory=list)
    leaks: List[str] = field(default_factory=list)

    @property
    def leaked(self) -> bool:
        return bool(self.leaks)


class BlindingFilter:
    """Removes anchoring/contamination surfaces from an agent's context and
    then audits the redacted context for residual fingerprints."""

    def __init__(self, policy: Optional[BlindingPolicy] = None) -> None:
        self.policy = policy or BlindingPolicy()

    def apply(self, context: Dict[str, Any]) -> Tuple[Dict[str, Any], BlindingReport]:
        blind = self.policy.blinded_keys()
        report = BlindingReport()
        fingerprints: Set[str] = set()

        def collect(value: Any) -> None:
            if isinstance(value, dict):
                for v in value.values():
                    collect(v)
            elif isinstance(value, (list, tuple, set)):
                for v in value:
                    collect(v)
            elif isinstance(value, str) and value:
                fingerprints.add(value)

        redacted: Dict[str, Any] = {}
        for k, v in context.items():
            if k in blind:
                report.redacted.append(k)
                collect(v)
            else:
                redacted[k] = v

        # audit: did a blinded string survive anywhere in the kept context?
        def scan(value: Any, path: str) -> None:
            if isinstance(value, dict):
                for kk, vv in value.items():
                    scan(vv, f"{path}.{kk}")
            elif isinstance(value, (list, tuple, set)):
                for i, vv in enumerate(value):
                    scan(vv, f"{path}[{i}]")
            elif isinstance(value, str):
                for fp in fingerprints:
                    if len(fp) >= 4 and fp in value:
                        report.leaks.append(f"{path}:{fp}")

        scan(redacted, "ctx")
        redacted["_blinding"] = {
            "level": self.policy.level,
            "redacted": sorted(report.redacted),
            "seal": stable_sig(sorted(report.redacted), self.policy.level),
        }
        return redacted, report


# ---------------------------------------------------------------------------
# Contractual Handoffs
# ---------------------------------------------------------------------------
class ContractLedger:
    """Issues, tracks and adjudicates constrained delegations."""

    def __init__(self, max_depth: int = 4) -> None:
        self.max_depth = max_depth
        self.open: Dict[str, Contract] = {}
        self.issued: List[Contract] = []
        self.results: List[ContractResult] = []

    def issue(
        self,
        principal: str,
        agent: str,
        task_id: str,
        depth: int,
        *,
        preconditions: Optional[List[str]] = None,
        postconditions: Optional[List[str]] = None,
        allowed_tools: Optional[Set[str]] = None,
        forbidden_scopes: Optional[Set[str]] = None,
        deliverable_keys: Optional[Set[str]] = None,
        token_budget: int = 8_000,
        deadline_s: float = 30.0,
    ) -> Contract:
        if depth > self.max_depth:
            raise RecursionError(
                f"bounded recursive delegation exceeded: depth={depth} > {self.max_depth}"
            )
        cid = stable_sig("contract", principal, agent, task_id, depth, len(self.issued))
        contract = Contract(
            contract_id=cid,
            principal=principal,
            agent=agent,
            task_id=task_id,
            depth=depth,
            preconditions=list(preconditions or []),
            postconditions=list(postconditions or ["deliverable_present", "within_scope"]),
            allowed_tools=set(allowed_tools or {"reason", "verify"}),
            forbidden_scopes=set(forbidden_scopes or set()),
            deliverable_keys=set(deliverable_keys or {"claims"}),
            token_budget=token_budget,
            deadline_s=deadline_s,
            max_depth=self.max_depth,
        )
        self.open[cid] = contract
        self.issued.append(contract)
        return contract

    def settle(
        self,
        contract: Contract,
        deliverable: Dict[str, Any],
        tokens_used: int,
        elapsed_s: float,
        tools_used: Optional[Set[str]] = None,
        touched_scopes: Optional[Set[str]] = None,
    ) -> ContractResult:
        violations: List[str] = []
        missing = contract.deliverable_keys - set(deliverable.keys())
        if missing:
            violations.append(f"missing_deliverable:{sorted(missing)}")
        if tokens_used > contract.token_budget:
            violations.append(f"token_overrun:{tokens_used}>{contract.token_budget}")
        if elapsed_s > contract.deadline_s:
            violations.append(f"deadline_exceeded:{elapsed_s:.2f}>{contract.deadline_s}")
        illegal = set(tools_used or set()) - contract.allowed_tools
        if illegal:
            violations.append(f"illegal_tools:{sorted(illegal)}")
        out_of_scope = set(touched_scopes or set()) & contract.forbidden_scopes
        if out_of_scope:
            violations.append(f"scope_violation:{sorted(out_of_scope)}")

        result = ContractResult(
            contract_id=contract.contract_id,
            ok=not violations,
            violations=violations,
            tokens_used=tokens_used,
            elapsed_s=elapsed_s,
        )
        self.open.pop(contract.contract_id, None)
        self.results.append(result)
        return result

    @property
    def compliance_rate(self) -> float:
        if not self.results:
            return 1.0
        return sum(1 for r in self.results if r.ok) / len(self.results)
