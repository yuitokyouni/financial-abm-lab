"""
OllamaBackend - Async parallel inference via Ollama HTTP API.

Uses httpx.AsyncClient to send concurrent requests.
Ollama queues them internally, but with OLLAMA_NUM_PARALLEL > 1
multiple requests can share the KV cache for real speedup.

Usage:
    export OLLAMA_NUM_PARALLEL=4  # set before starting ollama
"""

import asyncio

import httpx

from .base import LLMBackend, AgentContext, DecisionResult


class OllamaBackend(LLMBackend):
    def __init__(
        self,
        model: str = "gemma3:4b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.2,
        max_tokens: int = 10,
        max_concurrent: int = 8,
        timeout: float = 120.0,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def _ask_one(
        self, agent: AgentContext, neighbors: list[AgentContext]
    ) -> DecisionResult:
        """Send a single LLM request with concurrency control."""
        if not neighbors:
            return DecisionResult(uid=agent.uid, decision="Stay", raw_response="(no neighbors)")

        prompt = self.build_prompt(agent, neighbors)
        client = await self._get_client()

        async with self.semaphore:
            try:
                resp = await client.post(
                    "/api/chat",
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "options": {
                            "temperature": self.temperature,
                            "num_predict": self.max_tokens,
                        },
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                raw = resp.json()["message"]["content"]
                decision = self.parse_decision(raw)
                return DecisionResult(uid=agent.uid, decision=decision, raw_response=raw)
            except Exception as e:
                print(f"  [Ollama] agent {agent.uid} error: {type(e).__name__}: {e}")
                return DecisionResult(uid=agent.uid, decision="Stay", raw_response=f"ERROR: {e}")

    async def decide_batch(
        self,
        agents: list[AgentContext],
        neighbors_map: dict[int, list[AgentContext]],
    ) -> list[DecisionResult]:
        """Send all agent decisions concurrently."""
        tasks = [
            self._ask_one(agent, neighbors_map.get(agent.uid, []))
            for agent in agents
        ]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
