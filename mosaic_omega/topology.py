"""Dynamic communication topology and Dynamic Sovereignty.

Implements the governing state equation

    G_{t+1} = F(G_t, E_t, C_t, F_t, U_t)

where E_t is the evidence/event signal, C_t the competence vector, F_t the
failure signal and U_t the uncertainty signal.

Under Free-Energy Structural Control (see ``freeenergy.py``) ``F`` is no longer a
hand-tuned score: each edge target is the closed-form minimiser
``w* = clip(g/kappa, 0, 1)`` of the convex structural free energy ``J``, and the
learning-rate update is a provably convergent coordinate gradient step toward it.
``rewire`` also reports the free energy still recoverable next iteration, which
the loop consumes as a *derived* value-of-information estimate.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .config import MosaicConfig
from .freeenergy import FreeEnergyParams, StructuralFreeEnergy
from .types import AgentRuntime, SovereigntyTransfer, StageSpec, TopologySnapshot


# ---------------------------------------------------------------------------
class TopologyGraph:
    """Weighted, undirected communication graph + a directed handoff graph."""

    def __init__(self, config: MosaicConfig) -> None:
        self.config = config
        self.nodes: Set[str] = set()
        self.weights: Dict[Tuple[str, str], float] = {}     # undirected, key sorted
        self.handoffs: Dict[str, Set[str]] = {}             # directed delegation edges
        self.co_success: Dict[Tuple[str, str], float] = {}
        self.contamination: Dict[Tuple[str, str], float] = {}
        # The convex objective whose minimiser defines every edge target.
        self.fe = StructuralFreeEnergy(FreeEnergyParams(
            kappa=config.fe_kappa,
            w_complement=0.35,
            w_competence=0.30,
            w_evidence=0.20,
            w_uncertainty=0.15,
            w_failure=0.30,
            contamination_penalty=config.contamination_penalty,
            lambda_U=config.fe_lambda_U,
        ))
        # Free energy the *next* rewire can still shed; the loop reads this as
        # the derived value-of-information for the continue/stop decision.
        self.predicted_descent: float = 0.0

    # -- basic ops ----------------------------------------------------------
    @staticmethod
    def key(a: str, b: str) -> Tuple[str, str]:
        return (a, b) if a <= b else (b, a)

    def add_node(self, node: str) -> None:
        self.nodes.add(node)
        self.handoffs.setdefault(node, set())

    def remove_node(self, node: str) -> None:
        self.nodes.discard(node)
        self.handoffs.pop(node, None)
        for targets in self.handoffs.values():
            targets.discard(node)
        for k in [k for k in self.weights if node in k]:
            del self.weights[k]

    def neighbors(self, node: str) -> Set[str]:
        return {b if a == node else a for (a, b) in self.weights if node in (a, b)}

    def degree(self, node: str) -> int:
        return len(self.neighbors(node))

    def add_handoff(self, src: str, dst: str) -> None:
        self.handoffs.setdefault(src, set()).add(dst)
        self.handoffs.setdefault(dst, set())

    # -- cycle detection (circular handoff guard) ---------------------------
    def find_handoff_cycle(self) -> Optional[List[str]]:
        color: Dict[str, int] = {n: 0 for n in self.handoffs}
        parent: Dict[str, Optional[str]] = {n: None for n in self.handoffs}

        for start in sorted(self.handoffs):
            if color[start] != 0:
                continue
            stack: List[Tuple[str, Iterable[str]]] = [(start, iter(sorted(self.handoffs[start])))]
            color[start] = 1
            while stack:
                node, it = stack[-1]
                advanced = False
                for nxt in it:
                    if color.get(nxt, 0) == 0:
                        color[nxt] = 1
                        parent[nxt] = node
                        stack.append((nxt, iter(sorted(self.handoffs.get(nxt, ())))))
                        advanced = True
                        break
                    if color.get(nxt, 0) == 1:
                        cycle = [nxt]
                        cur: Optional[str] = node
                        while cur is not None and cur != nxt:
                            cycle.append(cur)
                            cur = parent[cur]
                        cycle.append(nxt)
                        return list(reversed(cycle))
                if not advanced:
                    color[node] = 2
                    stack.pop()
        return None

    def break_cycle(self, cycle: List[str]) -> Optional[Tuple[str, str]]:
        if len(cycle) < 2:
            return None
        src, dst = cycle[-2], cycle[-1]
        self.handoffs.get(src, set()).discard(dst)
        return (src, dst)

    # -- rewiring: G_{t+1} = F(G_t, E_t, C_t, F_t, U_t) ---------------------
    def rewire(
        self,
        iteration: int,
        capabilities: Dict[str, Set[str]],
        competence: Dict[str, float],
        failure: Dict[str, float],
        uncertainty: float,
        evidence: Dict[Tuple[str, str], float],
    ) -> TopologySnapshot:
        cfg = self.config
        lr = cfg.edge_learning_rate
        before = set(self.weights.keys())
        active = sorted(n for n in self.nodes if n in capabilities)

        # 1. update existing edges toward their affinity target
        for a in active:
            for b in active:
                if a >= b:
                    continue
                k = self.key(a, b)
                aff = self._affinity(a, b, capabilities, competence, failure,
                                     uncertainty, evidence)
                if k in self.weights:
                    self.weights[k] += lr * (aff - self.weights[k])

        # 2. grow: top-k complementary pairs not yet connected
        candidates: List[Tuple[float, Tuple[str, str]]] = []
        for a in active:
            for b in active:
                if a >= b:
                    continue
                k = self.key(a, b)
                if k in self.weights:
                    continue
                aff = self._affinity(a, b, capabilities, competence, failure,
                                     uncertainty, evidence)
                candidates.append((aff, k))
        candidates.sort(key=lambda t: (-t[0], t[1]))
        added = 0
        for aff, k in candidates:
            if added >= cfg.topology_add_top_k * max(1, len(active) // 4):
                break
            if aff <= cfg.edge_prune_threshold:
                break
            if self.degree(k[0]) >= cfg.max_degree or self.degree(k[1]) >= cfg.max_degree:
                continue
            self.weights[k] = aff
            added += 1

        # 3. prune weak edges, keeping every node minimally connected
        for k in sorted(list(self.weights.keys())):
            if self.weights[k] < cfg.edge_prune_threshold:
                a, b = k
                if self.degree(a) > 1 and self.degree(b) > 1:
                    del self.weights[k]

        # 4. enforce degree cap
        for node in active:
            nbrs = sorted(self.neighbors(node),
                          key=lambda m: self.weights[self.key(node, m)])
            while len(nbrs) > cfg.max_degree:
                drop = nbrs.pop(0)
                self.weights.pop(self.key(node, drop), None)

        # Derived value-of-information: free energy still recoverable by moving
        # every active pair to its optimum next iteration (EVOI = predicted J descent).
        descent = 0.0
        for i, a in enumerate(active):
            for b in active[i + 1:]:
                g = self._gain(a, b, capabilities, competence, failure,
                               uncertainty, evidence)
                w = self.weights.get(self.key(a, b), 0.0)
                descent += self.fe.edge_descent(w, g)
        self.predicted_descent = self.fe.predicted_descent([], uncertainty) + descent

        after = set(self.weights.keys())
        return TopologySnapshot(
            iteration=iteration,
            n_nodes=len(active),
            n_edges=len(after),
            edges_added=len(after - before),
            edges_removed=len(before - after),
            avg_degree=(2 * len(after) / len(active)) if active else 0.0,
            degree_entropy=self.degree_entropy(),
            modularity=self.modularity(),
            avg_path_length=self.avg_path_length(),
        )

    def _gain(
        self,
        a: str,
        b: str,
        capabilities: Dict[str, Set[str]],
        competence: Dict[str, float],
        failure: Dict[str, float],
        uncertainty: float,
        evidence: Dict[Tuple[str, str], float],
    ) -> float:
        """Expected epistemic gain ``g_ab`` of the edge (the ``-g w`` term of J)."""
        ca, cb = capabilities.get(a, set()), capabilities.get(b, set())
        union = ca | cb
        complement = len(union - (ca & cb)) / len(union) if union else 0.0
        comp = 0.5 * (competence.get(a, 0.5) + competence.get(b, 0.5))
        fail = 0.5 * (failure.get(a, 0.0) + failure.get(b, 0.0))
        ev = evidence.get(self.key(a, b), 0.0)
        contam = self.contamination.get(self.key(a, b), 0.0)
        return self.fe.edge_gain(complement, comp, ev, fail, uncertainty, contam)

    def _affinity(
        self,
        a: str,
        b: str,
        capabilities: Dict[str, Set[str]],
        competence: Dict[str, float],
        failure: Dict[str, float],
        uncertainty: float,
        evidence: Dict[Tuple[str, str], float],
    ) -> float:
        """Edge target = convex-optimal weight ``w* = clip(g/kappa, 0, 1)``."""
        g = self._gain(a, b, capabilities, competence, failure, uncertainty, evidence)
        return self.fe.optimal_weight(g)

    # -- structural metrics -------------------------------------------------
    def degree_entropy(self) -> float:
        if not self.nodes:
            return 0.0
        degs = [self.degree(n) for n in self.nodes]
        total = sum(degs)
        if total == 0:
            return 0.0
        h = 0.0
        for d in degs:
            if d:
                p = d / total
                h -= p * math.log(p, 2)
        return h

    def communities(self) -> Dict[str, int]:
        """Deterministic label propagation."""
        labels = {n: i for i, n in enumerate(sorted(self.nodes))}
        for _ in range(12):
            changed = False
            for n in sorted(self.nodes):
                nbrs = self.neighbors(n)
                if not nbrs:
                    continue
                tally: Dict[int, float] = {}
                for m in nbrs:
                    w = self.weights.get(self.key(n, m), 0.0)
                    tally[labels[m]] = tally.get(labels[m], 0.0) + w
                if not tally:
                    continue
                best = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
                if labels[n] != best:
                    labels[n] = best
                    changed = True
            if not changed:
                break
        return labels

    def modularity(self) -> float:
        m = sum(self.weights.values())
        if m <= 0:
            return 0.0
        labels = self.communities()
        strength: Dict[str, float] = {n: 0.0 for n in self.nodes}
        for (a, b), w in self.weights.items():
            strength[a] = strength.get(a, 0.0) + w
            strength[b] = strength.get(b, 0.0) + w
        q = 0.0
        for (a, b), w in self.weights.items():
            if labels.get(a) == labels.get(b):
                q += (w / m) - (strength[a] * strength[b]) / (2 * m * m)
        return q

    def avg_path_length(self) -> float:
        nodes = sorted(self.nodes)
        if len(nodes) < 2:
            return 0.0
        total, pairs = 0, 0
        for src in nodes:
            dist = {src: 0}
            q = deque([src])
            while q:
                cur = q.popleft()
                for nb in sorted(self.neighbors(cur)):
                    if nb not in dist:
                        dist[nb] = dist[cur] + 1
                        q.append(nb)
            for dst in nodes:
                if dst != src and dst in dist:
                    total += dist[dst]
                    pairs += 1
        return total / pairs if pairs else 0.0

    def edge_churn(self, prev: Set[Tuple[str, str]]) -> float:
        cur = set(self.weights.keys())
        union = prev | cur
        return len(union - (prev & cur)) / len(union) if union else 0.0


# ---------------------------------------------------------------------------
class SovereigntyController:
    """Transfers control to the most competent active agent.

    Hysteresis prevents leadership thrash (which would otherwise register as
    oscillation in the loop guards).
    """

    def __init__(self, config: MosaicConfig) -> None:
        self.config = config
        self.current: Optional[str] = None
        self.transfers: List[SovereigntyTransfer] = []

    def competence(self, rt: AgentRuntime, stage: StageSpec) -> float:
        w = self.config.sovereignty_weights
        need = set(stage.required_capabilities)
        match = len(rt.spec.capabilities & need) / len(need) if need else 0.0
        return (
            w["domain_match"] * match
            + w["reputation"] * rt.reputation
            + w["verification_pass"] * rt.verification_pass_rate
            - w["failure_penalty"] * rt.failure_rate
        )

    def evaluate(self, runtimes: Dict[str, AgentRuntime], stage: StageSpec,
                 iteration: int) -> Tuple[Optional[str], Dict[str, float]]:
        from .types import AgentRole
        eligible = {
            a: r for a, r in runtimes.items()
            if r.alive and r.spec.role in (AgentRole.SPECIALIST, AgentRole.MICRO)
        }
        scores = {a: self.competence(r, stage) for a, r in eligible.items()}
        if not scores:
            return self.current, scores
        best = max(sorted(scores), key=lambda a: scores[a])
        if self.current is None or self.current not in eligible:
            prev, prev_c = self.current, scores.get(self.current or "", 0.0)
            self.current = best
            self.transfers.append(
                SovereigntyTransfer(iteration, prev, best, prev_c, scores[best])
            )
        elif scores[best] > scores[self.current] * (1.0 + self.config.sovereignty_hysteresis):
            prev, prev_c = self.current, scores[self.current]
            self.current = best
            self.transfers.append(
                SovereigntyTransfer(iteration, prev, best, prev_c, scores[best])
            )
        return self.current, scores
