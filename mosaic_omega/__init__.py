"""MOSAIC-Omega: a self-reconfiguring agentic architecture with fail-safe
loop engineering.

Quick start
-----------
    from mosaic_omega import MosaicOmega, MosaicConfig, SyntheticConstraintProblem

    problem = SyntheticConstraintProblem()
    result = MosaicOmega(MosaicConfig()).solve(problem)
    print(result.summary())
    print(MetricsEngine(result.trace, problem).report())
"""
from .adjudication import BlindedJury, ContradictionScanner, FalsificationEngine, MinorityPreserver
from .agents import (
    BaseAgent, ContradictionAgent, FalsifierAgent, JurorAgent, MetaAgent,
    MicroAgent, MinorityPreservationAgent, SpecialistAgent, VerifierAgent, WatchdogAgent,
    build_agent,
)
from .config import MosaicConfig
from .failsafe import (
    BudgetManager, CheckpointStore, IdempotencyLedger, LoopGuards, RecoveryManager,
)
from .freeenergy import FreeEnergyParams, StructuralFreeEnergy
from .governance import BlindingFilter, BlindingPolicy, ContractLedger
from .kernel import AgentPruner, DynamicAgentProvisioner, MissionKernel
from .llm import AnthropicBackend, LLMBackend, NullBackend
from .loop import FailSafeLoop, LoopOutcome
from .memory import MemoryFabric
from .metrics import MetricsEngine
from .orchestrator import MosaicOmega, RunResult
from .problem import Problem, SyntheticConstraintProblem
from .routing import ReputationRouter
from .topology import SovereigntyController, TopologyGraph
from .types import (
    AgentRole, AgentRuntime, AgentSpec, Candidate, Claim, MissionSpec, Phase,
    RiskLevel, RunTrace, StageSpec, Termination,
)
from .universes import UniverseManager, UniverseState

__version__ = "1.0.0"
__all__ = [
    "MosaicOmega", "MosaicConfig", "RunResult", "MetricsEngine",
    "Problem", "SyntheticConstraintProblem", "MissionKernel",
    "DynamicAgentProvisioner", "AgentPruner", "TopologyGraph",
    "SovereigntyController", "ReputationRouter", "UniverseManager",
    "UniverseState", "BlindingFilter", "BlindingPolicy", "ContractLedger",
    "FalsificationEngine", "ContradictionScanner", "MinorityPreserver",
    "BlindedJury", "MemoryFabric", "FailSafeLoop", "LoopOutcome",
    "StructuralFreeEnergy", "FreeEnergyParams",
    "CheckpointStore", "LoopGuards", "RecoveryManager", "BudgetManager",
    "IdempotencyLedger", "BaseAgent", "SpecialistAgent", "MicroAgent",
    "VerifierAgent", "FalsifierAgent", "ContradictionAgent",
    "MinorityPreservationAgent", "JurorAgent", "WatchdogAgent", "MetaAgent",
    "build_agent", "AnthropicBackend", "NullBackend", "LLMBackend",
    "AgentRole", "AgentSpec", "AgentRuntime", "Candidate", "Claim",
    "MissionSpec", "StageSpec", "Phase", "RiskLevel", "Termination", "RunTrace",
    "__version__",
]
