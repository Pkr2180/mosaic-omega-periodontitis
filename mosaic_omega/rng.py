"""Deterministic randomness utilities.

Every stochastic decision in MOSAIC-Omega is derived from a stable hash of its
semantic coordinates (agent id, constraint id, iteration, ...) rather than from
a global mutable RNG. This makes any run bit-for-bit reproducible and makes
`deterministic replay fidelity` an actually measurable metric.
"""
from __future__ import annotations

import hashlib
import random
from typing import Any, Iterable


def stable_hash(*parts: Any) -> int:
    """Order-sensitive, process-independent 64-bit hash."""
    h = hashlib.blake2b(digest_size=8)
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x1f")
    return int.from_bytes(h.digest(), "big")


def stable_sig(*parts: Any) -> str:
    """Short hex signature, used for state/loop signatures."""
    return format(stable_hash(*parts), "016x")


def rng_for(*parts: Any) -> random.Random:
    """A seeded RNG bound to a semantic coordinate."""
    return random.Random(stable_hash(*parts))


def stable_shuffle(items: Iterable[Any], *seed_parts: Any) -> list:
    out = list(items)
    rng_for(*seed_parts).shuffle(out)
    return out
