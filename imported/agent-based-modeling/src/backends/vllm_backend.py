"""
VLLMBackend - Async parallel inference via vLLM's OpenAI-compatible API.

vLLM provides continuous batching, meaning it dynamically groups
incoming requests for GPU-efficient inference. This is significantly
faster than Ollama when running on a GPU server.

Usage:
    # Start vLLM server (on a GPU machine):
    python -m vllm.entrypoints.openai.api_server \
        --model google/gemma-3-4b-it --port 8000

    # Or via Docker:
    docker run --gpus all -p 8000:8000 \
        vllm/vllm-openai --model google/gemma-3-4b-it

    # Then point this backend to it:
    backend = VLLMBackend(
        model="google/gemma-3-4b-it",
        base_url="http://<gpu-server>:8000",
    )
"""

import asyncio

import httpx

from .base import LLMBackend, AgentContext, DecisionResult


class VLLMBackend(LLMBackend):
    def __init__(
        self,
        model: str = "google/gemma-3-4b-it",
        base_url: str = "http://localhost:8000",
        temperature: float = 0.2,
        max_tokens: int = 10,
        max_concurrent: int = 64,
        timeout: float = 30.0,
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
        if not neighbors:
            return DecisionResult(uid=agent.uid, decision="Stay", raw_response="(no neighbors)")

        prompt = self.build_prompt(agent, neighbors)
        client = await self._get_client()

        async with self.semaphore:
            try:
                # vLLM exposes OpenAI-compatible /v1/chat/completions
                resp = await client.post(
                    "/v1/chat/completions",
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                    },
                )
                resp.raise_for_status()
                raw = resp.json()["choices"][0]["message"]["content"]
                decision = self.parse_decision(raw)
                return DecisionResult(uid=agent.uid, decision=decision, raw_response=raw)
            except Exception as e:
                print(f"  [vLLM] agent {agent.uid} error: {e}")
                return DecisionResult(uid=agent.uid, decision="Stay", raw_response=f"ERROR: {e}")

    async def decide_batch(
        self,
        agents: list[AgentContext],
        neighbors_map: dict[int, list[AgentContext]],
    ) -> list[DecisionResult]:
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
