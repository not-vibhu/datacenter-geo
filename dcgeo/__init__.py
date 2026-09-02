"""dcgeo — deterministic measurement and scoring core for datacenter-geo.

Design rule: this package never calls an LLM and never makes a judgment.
Adapters measure; the scoring engine arithmetics. All judgment lives in the
agent layer (.claude/agents/) and is recorded as Claims, not Measurements.
"""

__version__ = "0.1.0"
