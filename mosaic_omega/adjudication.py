"""Falsification, contradiction scanning, minority preservation, blinded jury."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .agents import BaseAgent, ContradictionAgent, FalsifierAgent, JurorAgent, MinorityPreservationAgent
from .config import MosaicConfig
from .governance import BlindingFilter, BlindingPolicy
from .rng import stable_shuffle, stable_sig
from .types import (
    Candidate,
    Claim,
    Contradiction,
    FalsificationReport,
    JurorBallot,
    JuryVerdict,
)


# ---------------------------------------------------------------------------
class FalsificationEngine:
    def __init__(self, config: MosaicConfig) -> None:
        self.config = config

    def run(self, candidate: Candidate, falsifiers: Sequence[FalsifierAgent],
            nonce: str) -> FalsificationReport:
        merged = FalsificationReport(candidate_id=candidate.candidate_id)
        for f in falsifiers:
            out = f.act({
                "candidate": candidate,
                "attacks": self.config.attacks_per_falsifier,
                "nonce": f"{nonce}:{f.agent_id}",
            })
            rep: FalsificationReport = out.payload["report"]
            merged.attacks.extend(rep.attacks)
        candidate.falsification_survival = merged.survival
        for atk in merged.attacks:
            if atk.succeeded:
                for claim in candidate.claims:
                    if claim.constraint_id == atk.constraint_id:
                        claim.falsified = True
        return merged


# ---------------------------------------------------------------------------
class ContradictionScanner:
    def run(self, agent: ContradictionAgent, claims: List[Claim],
            commitments: Dict[str, str]) -> List[Contradiction]:
        out = agent.act({"claims": claims, "commitments": commitments})
        return out.payload["contradictions"]

    @staticmethod
    def density(contradictions: Sequence[Contradiction], n_scanned: int) -> float:
        """Contradictions per scanned claim pair, clamped to [0,1]."""
        pairs = n_scanned * (n_scanned - 1) / 2
        return min(1.0, len(contradictions) / pairs) if pairs > 0 else 0.0


# ---------------------------------------------------------------------------
@dataclass
class ConsensusState:
    entropy: float
    majority_share: float
    clusters: Dict[str, List[str]]           # signature -> candidate ids
    majority_sig: Optional[str]
    minority_sig: Optional[str]
    premature: bool


class MinorityPreserver:
    """Prevents premature consensus.

    If candidate-space entropy collapses before evidence is sufficient, the
    top minority cluster is protected and handed to an advocate agent.
    """

    def __init__(self, config: MosaicConfig) -> None:
        self.config = config

    def analyse(self, candidates: Sequence[Candidate],
                evidence_sufficiency: float) -> ConsensusState:
        clusters: Dict[str, List[str]] = {}
        for c in candidates:
            clusters.setdefault(c.signature(), []).append(c.candidate_id)
        total = sum(len(v) for v in clusters.values())
        entropy = 0.0
        if total > 0 and len(clusters) > 1:
            for ids in clusters.values():
                p = len(ids) / total
                entropy -= p * math.log(p, 2)
            entropy /= math.log(len(clusters), 2)
        ordered = sorted(clusters.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        majority = ordered[0][0] if ordered else None
        minority = ordered[-1][0] if len(ordered) > 1 else None
        share = len(ordered[0][1]) / total if ordered and total else 0.0
        # Consensus is "premature" when the field has narrowed to a dominant
        # cluster while the evidence base is still thin, or when entropy has
        # collapsed outright. Either way a dissenting branch is protected.
        premature = (
            len(clusters) > 1
            and evidence_sufficiency < self.config.evidence_sufficiency_floor
            and (share >= self.config.consensus_share_ceiling
                 or entropy < self.config.minority_entropy_floor)
        )
        return ConsensusState(entropy, share, clusters, majority, minority, premature)

    def preserve(self, state: ConsensusState, candidates: Sequence[Candidate],
                 advocate: Optional[MinorityPreservationAgent]) -> Optional[Candidate]:
        if not state.premature or state.minority_sig is None:
            return None
        pool = [c for c in candidates if c.signature() == state.minority_sig]
        if not pool:
            return None
        champion = max(pool, key=lambda c: (c.verified_score, c.candidate_id))
        champion.is_minority = True
        if advocate is not None:
            advocate.act({"minority_candidate": champion})
        return champion


# ---------------------------------------------------------------------------
class BlindedJury:
    """Anonymises, shuffles and adjudicates competing candidates."""

    def __init__(self, config: MosaicConfig) -> None:
        self.config = config
        self.blinder = BlindingFilter(BlindingPolicy(level=config.blinding_level))

    def _blind(self, candidates: Sequence[Candidate], nonce: str
               ) -> Tuple[List[Dict[str, Any]], Dict[str, str], int, int]:
        shuffled = stable_shuffle(candidates, "jury", nonce)
        alias_to_id: Dict[str, str] = {}
        packets: List[Dict[str, Any]] = []
        leaks = checks = 0
        for i, c in enumerate(shuffled):
            alias = f"CAND-{i}"
            alias_to_id[alias] = c.candidate_id
            verified = [cl for cl in c.claims if cl.verified is not None]
            verified_ratio = (
                sum(1 for cl in verified if cl.verified) / len(verified)
                if verified else 0.0
            )
            mean_conf = (
                sum(cl.confidence for cl in c.claims) / len(c.claims)
                if c.claims else 0.5
            )
            raw = {
                "alias": alias,
                "verified_ratio": verified_ratio,
                "survival": c.falsification_survival,
                "mean_confidence": mean_conf,
                "contradiction_density": c.contradiction_penalty,
                # blinded surfaces:
                "peer_authors": list(c.authors),
                "author": c.authors[0] if c.authors else "",
                "peer_scores": [c.raw_score, c.jury_score],
                "universe_leaderboard": c.universe,
            }
            packet, report = self.blinder.apply(raw)
            checks += 1
            leaks += int(report.leaked)
            packet["alias"] = alias
            packets.append(packet)
        return packets, alias_to_id, leaks, checks

    def adjudicate(self, candidates: Sequence[Candidate],
                   jurors: Sequence[JurorAgent], nonce: str
                   ) -> Tuple[JuryVerdict, int, int]:
        if not candidates:
            return JuryVerdict(winner_id=None), 0, 0
        packets, alias_to_id, leaks, checks = self._blind(candidates, nonce)
        ballots: List[JurorBallot] = []
        for j in jurors:
            out = j.act({"blinded_candidates": packets, "nonce": nonce})
            ballots.append(out.payload["ballot"])

        weight_sum = sum(max(0.05, b.reputation) for b in ballots) or 1.0
        aggregate: Dict[str, float] = {}
        for packet in packets:
            alias = packet["alias"]
            agg = sum(max(0.05, b.reputation) * b.scores.get(alias, 0.0) for b in ballots)
            aggregate[alias_to_id[alias]] = agg / weight_sum

        ordered = sorted(aggregate.items(), key=lambda kv: (-kv[1], kv[0]))
        winner = ordered[0][0] if ordered else None
        margin = (ordered[0][1] - ordered[1][1]) if len(ordered) > 1 else 1.0
        kappa = self.fleiss_kappa([b.top_choice for b in ballots],
                                  [p["alias"] for p in packets])
        for c in candidates:
            c.jury_score = aggregate.get(c.candidate_id, 0.0)
        verdict = JuryVerdict(
            winner_id=winner,
            ballots=ballots,
            aggregate=aggregate,
            margin=margin,
            agreement_kappa=kappa,
            blinded=self.config.blinding_level != "none",
        )
        return verdict, leaks, checks

    @staticmethod
    def fleiss_kappa(votes: Sequence[str], categories: Sequence[str]) -> float:
        """Single-item Fleiss' kappa over top-choice votes.

        With one item, kappa reduces to (P_observed - P_expected)/(1 - P_expected)
        where P_observed is the pairwise agreement rate among raters.
        """
        n = len(votes)
        k = len(categories)
        if n < 2 or k < 2:
            return 0.0
        counts = {c: 0 for c in categories}
        for v in votes:
            if v in counts:
                counts[v] += 1
        p_obs = (sum(c * c for c in counts.values()) - n) / (n * (n - 1))
        p_exp = sum((c / n) ** 2 for c in counts.values())
        if p_exp >= 1.0:
            return 1.0
        return (p_obs - p_exp) / (1.0 - p_exp)
