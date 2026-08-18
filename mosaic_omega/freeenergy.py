"""Free-Energy Structural Control (FESC) -- the algorithmic core.

MOSAIC-Omega's earlier drafts drove three separate decisions -- how densely to
wire the agent graph, how much another iteration is worth, and when to stop --
from three unrelated heuristics. FESC replaces them with a *single convex
variational objective* that the loop provably descends. The topology update, the
value-of-information estimate and the stop rule all fall out of the same
functional, so they can no longer disagree with one another.

The structural free energy
--------------------------

At iteration ``t`` the system holds a weighted collaboration graph ``G`` with
edge weights ``w_ab in [0, 1]`` (the bandwidth agent ``a`` and ``b`` are allowed
to influence each other) and a residual belief-uncertainty ``U`` -- the mean
binary entropy of the per-constraint "is the committed value correct" beliefs.
Define

    J(G) = sum_{a<b} [ (kappa/2) * w_ab^2  -  g_ab * w_ab ]  +  lambda_U * U

where ``g_ab`` is the *expected epistemic gain* of the edge: how much a unit of
collaboration bandwidth between ``a`` and ``b`` is expected to reduce belief
uncertainty. It rises with capability complementarity, joint competence and
accumulated co-success evidence, is amplified by how much uncertainty is still
on the table, and is discounted by each agent's failure rate and by
cross-universe contamination:

    g_ab = w_comp*complement + w_competence*competence + w_evidence*evidence
           + w_uncertainty*U  -  w_failure*failure  -  contam_penalty*contam

The ``(kappa/2) w^2`` term is a wiring/complexity cost with diminishing returns.

Why this is an algorithm, not a score
--------------------------------------

1. **Closed-form optimum.** ``J`` is a positive-definite quadratic in every
   ``w_ab`` (second derivative ``kappa > 0``), hence convex and separable across
   edges. Setting ``dJ/dw_ab = kappa*w_ab - g_ab = 0`` gives the unique optimal
   weight

       w*_ab = clip(g_ab / kappa, 0, 1).

   Rewiring is a gradient step ``w <- w - eta * (kappa*w - g)`` toward ``w*`` and,
   because each per-edge problem is 1-D convex, it converges monotonically. (With
   ``kappa = 1`` the step reduces exactly to the legacy affinity update, so the
   reframing is behaviour-preserving; ``kappa`` now *means* something.)

2. **A termination guarantee, not a step counter.** Every accepted structural
   move strictly decreases ``J`` and ``J`` is bounded below by
   ``-sum_{a<b} g_ab^2 / (2 kappa)``. A monotonically decreasing sequence bounded
   below converges, so the loop must reach a point where no move sheds more than
   ``epsilon`` of free energy -- that fixed point *is* the stop condition.

3. **A derived value of information.** The worth of another iteration is the free
   energy still recoverable from moving each weight to its optimum, which for a
   quadratic has the closed form

       EVOI_t = sum_{a<b} (g_ab - kappa*w_ab)^2 / (2*kappa)  +  lambda_U * U.

   This is a *predicted descent* with the same units as ``J`` -- unlike the old
   momentum estimate, its calibration against realised improvement is meaningful.

Everything here is pure-stdlib and side-effect free, so it stays bit-for-bit
deterministic and independently testable.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FreeEnergyParams:
    """Coefficients of the structural free-energy functional ``J``."""

    kappa: float = 1.0                 # wiring/complexity cost; also sets w* scale
    w_complement: float = 0.35         # capability complementarity
    w_competence: float = 0.30         # joint competence
    w_evidence: float = 0.20           # accumulated co-success evidence
    w_uncertainty: float = 0.15        # amplify collaboration while U is high
    w_failure: float = 0.30            # discount for unreliable agents
    contamination_penalty: float = 0.45  # cross-universe leakage discount
    lambda_U: float = 0.15             # price of residual belief uncertainty


class StructuralFreeEnergy:
    """The FESC objective and the moves that descend it.

    All methods are pure functions of their arguments; the object only carries
    the coefficient block, so a single instance can score any edge in any graph.
    """

    def __init__(self, params: FreeEnergyParams | None = None) -> None:
        self.p = params or FreeEnergyParams()

    # -- the epistemic gain of an edge -------------------------------------
    def edge_gain(
        self,
        complement: float,
        competence: float,
        evidence: float,
        failure: float,
        uncertainty: float,
        contamination: float,
    ) -> float:
        p = self.p
        return (
            p.w_complement * complement
            + p.w_competence * competence
            + p.w_evidence * evidence
            + p.w_uncertainty * uncertainty
            - p.w_failure * failure
            - p.contamination_penalty * contamination
        )

    # -- the convex-optimal weight for that gain ---------------------------
    def optimal_weight(self, gain: float) -> float:
        """``w* = clip(g / kappa, 0, 1)`` -- the unique minimiser of ``J`` in w."""
        return max(0.0, min(1.0, gain / self.p.kappa if self.p.kappa else gain))

    # -- free energy stored in / recoverable from one edge -----------------
    def edge_energy(self, weight: float, gain: float) -> float:
        """``J_edge(w) = (kappa/2) w^2 - g w``."""
        return 0.5 * self.p.kappa * weight * weight - gain * weight

    def edge_descent(self, weight: float, gain: float) -> float:
        """Free energy still sheddable by moving ``w`` to ``w*``.

        For the convex quadratic this is ``(kappa*w - g)^2 / (2 kappa) >= 0``.
        Zero exactly when the edge already sits at its optimum.
        """
        kappa = self.p.kappa or 1.0
        grad = kappa * weight - gain
        return (grad * grad) / (2.0 * kappa)

    # -- the value of another iteration ------------------------------------
    def predicted_descent(self, edge_terms, uncertainty: float) -> float:
        """EVOI as marginal free energy: sum of per-edge descent + the U price.

        ``edge_terms`` is an iterable of ``(weight, gain)`` pairs for the edges
        the next rewire may act on.
        """
        structural = sum(self.edge_descent(w, g) for w, g in edge_terms)
        return structural + self.p.lambda_U * uncertainty
