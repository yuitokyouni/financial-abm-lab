"""
LLMBackend - Abstract base class for LLM inference backends.

All backends implement the same interface so the simulation code
doesn't care whether it's talking to Ollama, vLLM, or a remote API.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AgentContext:
    """What the backend needs to know about an agent to build a prompt."""
    uid: int
    persona_label: str
    profile: str


@dataclass
class DecisionResult:
    """LLM decision for a single agent."""
    uid: int
    decision: str  # "Stay" or "Move"
    raw_response: str = ""


class LLMBackend(ABC):
    """Abstract base class for LLM inference backends."""

    @abstractmethod
    async def decide_batch(
        self,
        agents: list[AgentContext],
        neighbors_map: dict[int, list[AgentContext]],
    ) -> list[DecisionResult]:
        """
        Ask the LLM for Stay/Move decisions for a batch of agents.

        Args:
            agents: List of agents that need decisions.
            neighbors_map: uid -> list of neighbor AgentContexts.

        Returns:
            List of DecisionResult, one per agent.
        """
        ...

    @abstractmethod
    async def close(self):
        """Clean up resources (HTTP clients, etc.)."""
        ...

    def build_prompt(self, agent: AgentContext, neighbors: list[AgentContext]) -> str:
        """Build the Stay/Move prompt. Shared across backends."""
        if not neighbors:
            return ""

        nbr_lines = "\n".join(
            f"  {i}. [{n.persona_label}] {n.profile}"
            for i, n in enumerate(neighbors, 1)
        )
        return (
            f"You are {agent.persona_label}.\n"
            f"Your values: {agent.profile}\n\n"
            f"Your current neighbors:\n{nbr_lines}\n\n"
            f"Based on how well you fit in with these neighbors, "
            f"should you Stay or Move?\n"
            f"Answer with a single word: Stay or Move."
        )

    @staticmethod
    def parse_decision(text: str) -> str:
        """Parse LLM output into 'Stay' or 'Move'."""
        lower = text.strip().lower()
        if "move" in lower:
            return "Move"
        return "Stay"
