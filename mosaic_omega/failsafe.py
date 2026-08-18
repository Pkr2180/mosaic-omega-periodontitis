"""Fail-safe loop engineering: budgets, checkpoints, guards, recovery."""
from __future__ import annotations

import json
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional, Sequence, Set, Tuple

from .config import MosaicConfig
from .rng import stable_sig
from .types import Checkpoint, FailureClass, Phase, RecoveryRecord


# ---------------------------------------------------------------------------
class BudgetExhausted(Exception):
    pass


class BudgetManager:
    def __init__(self, config: MosaicConfig) -> None:
        self.config = config
        self.tokens_used = 0
        self.tool_calls_used = 0
        self.started = time.perf_counter()
        self.overruns: List[str] = []

    def elapsed(self) -> float:
        return time.perf_counter() - self.started

    def consume(self, tokens: int = 0, tool_calls: int = 0) -> None:
        self.tokens_used += tokens
        self.tool_calls_used += tool_calls

    def fraction_left(self) -> float:
        f_tok = 1.0 - self.tokens_used / max(1, self.config.token_budget)
        f_tool = 1.0 - self.tool_calls_used / max(1, self.config.tool_call_budget)
        f_time = 1.0 - self.elapsed() / max(1e-9, self.config.wall_clock_budget_s)
        return max(0.0, min(f_tok, f_tool, f_time))

    def check(self) -> Optional[str]:
        if self.tokens_used >= self.config.token_budget:
            return "token_budget"
        if self.tool_calls_used >= self.config.tool_call_budget:
            return "tool_call_budget"
        if self.elapsed() >= self.config.wall_clock_budget_s:
            return "wall_clock_budget"
        return None

    def record_overrun(self, what: str) -> None:
        self.overruns.append(what)


# ---------------------------------------------------------------------------
class IdempotencyLedger:
    """Prevents duplicate side effects on replay/rollback."""

    def __init__(self) -> None:
        self.executed: Dict[str, Any] = {}
        self.hits = 0
        self.duplicates_prevented = 0

    @staticmethod
    def key(agent: str, tool: str, args: Any, checkpoint_id: Optional[str]) -> str:
        return stable_sig("action", agent, tool, json.dumps(args, sort_keys=True,
                                                            default=str), checkpoint_id)

    def run_once(self, key: str, fn: Callable[[], Any]) -> Any:
        if key in self.executed:
            self.hits += 1
            self.duplicates_prevented += 1
            return self.executed[key]
        result = fn()
        self.executed[key] = result
        return result


# ---------------------------------------------------------------------------
class CheckpointStore:
    """Content-addressed checkpoint chain with rollback to earliest corruption."""

    def __init__(self) -> None:
        self.chain: List[Checkpoint] = []
        self.by_id: Dict[str, Checkpoint] = {}

    @property
    def head(self) -> Optional[Checkpoint]:
        return self.chain[-1] if self.chain else None

    def commit(self, iteration: int, phase: Phase, state: Dict[str, Any],
               branch: str = "root") -> Checkpoint:
        blob = json.dumps(state, sort_keys=True, default=str)
        parent = self.head.checkpoint_id if self.head else None
        cp = Checkpoint(
            checkpoint_id=stable_sig("cp", branch, iteration, phase.value, blob, len(self.chain)),
            parent_id=parent,
            iteration=iteration,
            phase=phase,
            state_blob=blob,
            integrity_hash=stable_sig(blob),
            branch=branch,
        )
        self.chain.append(cp)
        self.by_id[cp.checkpoint_id] = cp
        return cp

    def verify_integrity(self, cp: Checkpoint) -> bool:
        return stable_sig(cp.state_blob) == cp.integrity_hash

    def find_earliest_corrupted(
        self, validator: Callable[[Dict[str, Any]], bool]
    ) -> Optional[Checkpoint]:
        """Binary search along the chain for the first checkpoint that fails
        the invariant (the chain is assumed monotone: once broken, stays broken)."""
        if not self.chain:
            return None
        lo, hi, found = 0, len(self.chain) - 1, None
        while lo <= hi:
            mid = (lo + hi) // 2
            cp = self.chain[mid]
            ok = self.verify_integrity(cp) and validator(json.loads(cp.state_blob))
            if ok:
                lo = mid + 1
            else:
                found = cp
                hi = mid - 1
        return found

    def rollback_to(self, checkpoint_id: str) -> Dict[str, Any]:
        cp = self.by_id.get(checkpoint_id)
        if cp is None:
            raise KeyError(f"unknown checkpoint {checkpoint_id}")
        idx = self.chain.index(cp)
        for dropped in self.chain[idx + 1:]:
            dropped.corrupted = True
        self.chain = self.chain[: idx + 1]
        return json.loads(cp.state_blob)

    def last_good_before(self, cp: Checkpoint) -> Optional[Checkpoint]:
        idx = self.chain.index(cp) if cp in self.chain else len(self.chain)
        return self.chain[idx - 1] if idx > 0 else None


# ---------------------------------------------------------------------------
@dataclass
class GuardTrip:
    guard: str
    iteration: int
    detail: str


class LoopGuards:
    """Duplicate-loop, oscillation, stagnation and deadlock detection."""

    def __init__(self, config: MosaicConfig) -> None:
        self.config = config
        self.signatures: List[str] = []
        self.signature_counts: Counter = Counter()
        self.scores: List[float] = []
        self.trips: List[GuardTrip] = []

    def observe(self, signature: str, score: float, iteration: int) -> None:
        self.signatures.append(signature)
        self.signature_counts[signature] += 1
        self.scores.append(score)

    # -- duplicate loop -----------------------------------------------------
    def duplicate_loop(self, iteration: int) -> Optional[GuardTrip]:
        if not self.signatures:
            return None
        sig = self.signatures[-1]
        if self.signature_counts[sig] >= self.config.duplicate_loop_k:
            trip = GuardTrip("duplicate_loop", iteration,
                             f"signature {sig} seen {self.signature_counts[sig]}x")
            self.trips.append(trip)
            return trip
        return None

    # -- oscillation --------------------------------------------------------
    def oscillation(self, iteration: int) -> Optional[GuardTrip]:
        w = self.signatures[-self.config.oscillation_window:]
        for period in range(self.config.oscillation_min_period,
                            self.config.oscillation_max_period + 1):
            need = period * (self.config.oscillation_min_repeats + 1)
            if len(w) < need:
                continue
            tail = w[-need:]
            block = tail[:period]
            if len(set(block)) < 2:
                continue
            if all(tail[i] == block[i % period] for i in range(need)):
                trip = GuardTrip("oscillation", iteration,
                                 f"period-{period} cycle over {need} steps")
                self.trips.append(trip)
                return trip
        return None

    # -- stagnation ---------------------------------------------------------
    def stagnation(self, iteration: int) -> Optional[GuardTrip]:
        w = self.config.stagnation_window
        if len(self.scores) < w + 1:
            return None
        recent = self.scores[-(w + 1):]
        gain = max(recent[1:]) - recent[0]
        if gain < self.config.stagnation_epsilon:
            trip = GuardTrip("stagnation", iteration,
                             f"gain {gain:.4f} < eps over {w} iterations")
            self.trips.append(trip)
            return trip
        return None

    # -- deadlock -----------------------------------------------------------
    def deadlock(self, iteration: int, blocked: Sequence[str],
                 active: Sequence[str]) -> Optional[GuardTrip]:
        if active and set(blocked) >= set(active):
            trip = GuardTrip("deadlock", iteration,
                             f"all {len(active)} active agents blocked")
            self.trips.append(trip)
            return trip
        return None


# ---------------------------------------------------------------------------
class RecoveryManager:
    """Contain -> rollback -> replay alternative branch -> escalate."""

    def __init__(self, config: MosaicConfig, store: CheckpointStore) -> None:
        self.config = config
        self.store = store
        self.records: List[RecoveryRecord] = []
        self.consecutive_failures = 0
        self.branch_counter = 0

    def new_branch(self) -> str:
        self.branch_counter += 1
        return f"branch-{self.branch_counter:02d}"

    def handle(
        self,
        iteration: int,
        failure_class: FailureClass,
        detail: str,
        validator: Callable[[Dict[str, Any]], bool],
        restore: Callable[[Dict[str, Any]], None],
    ) -> RecoveryRecord:
        self.consecutive_failures += 1
        attempts = self.consecutive_failures
        escalated = attempts > self.config.max_recovery_attempts
        rolled_to: Optional[str] = None
        contained = False

        if not escalated:
            corrupted = self.store.find_earliest_corrupted(validator)
            target = self.store.last_good_before(corrupted) if corrupted else self.store.head
            if target is not None:
                state = self.store.rollback_to(target.checkpoint_id)
                restore(state)
                rolled_to = target.checkpoint_id
                contained = True

        record = RecoveryRecord(
            iteration=iteration,
            failure_class=failure_class,
            detail=detail,
            rolled_back_to=rolled_to,
            attempts=attempts,
            contained=contained,
            escalated=escalated,
        )
        self.records.append(record)
        return record

    def mark_recovered(self, iteration: int) -> None:
        for rec in reversed(self.records):
            if rec.recovered_at_iteration is None:
                rec.recovered_at_iteration = iteration
                break
        self.consecutive_failures = 0
