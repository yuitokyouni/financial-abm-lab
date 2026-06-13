"""
PoC v2: LLM-Decision Schelling Model with pluggable backends
=============================================================
Async-first design. Swap OllamaBackend ↔ VLLMBackend by changing one line.

Usage:
    # Ollama (local CPU):
    python run_v2.py --backend ollama --model gemma3:4b

    # vLLM (remote GPU):
    python run_v2.py --backend vllm --model google/gemma-3-4b-it \
                     --vllm-url http://gpu-server:8000

    # Mini test:
    python run_v2.py --grid 5 --agents 10 --steps 10
"""

import argparse
import asyncio
import json
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backends import OllamaBackend, VLLMBackend
from src.backends.base import LLMBackend, AgentContext


# ── Personas ────────────────────────────────────────────────

PERSONAS = {
    "traditionalist": {
        "label": "Traditionalist",
        "color": "#2ecc71",
        "profile": (
            "I value family bonds, local festivals, quiet mornings, "
            "home-cooked meals, temple visits, and stable community ties. "
            "I prefer a calm, orderly neighborhood where everyone knows each other."
        ),
    },
    "innovator": {
        "label": "Innovator",
        "color": "#e74c3c",
        "profile": (
            "I love hackathons, co-working spaces, avant-garde art, "
            "startup culture, late-night coding sessions, and global cuisine. "
            "I thrive in a fast-paced, ever-changing neighborhood full of new ideas."
        ),
    },
}


# ── Agent ───────────────────────────────────────────────────

@dataclass
class Agent:
    uid: int
    persona: str
    x: int = 0
    y: int = 0
    happy: bool = True


# ── Model ───────────────────────────────────────────────────

class LLMSchellingModel:
    def __init__(
        self,
        backend: LLMBackend,
        grid_w: int = 20,
        grid_h: int = 20,
        n_agents: int = 100,
        max_steps: int = 30,
        seed: int = 42,
        output_dir: str = "output_v2",
    ):
        self.backend = backend
        self.grid_w = grid_w
        self.grid_h = grid_h
        self.n_agents = n_agents
        self.max_steps = max_steps
        self.seed = seed
        self.output_dir = Path(output_dir)

        self.rng = random.Random(seed)
        self.agents: list[Agent] = []
        self.grid: dict[tuple[int, int], Agent | None] = {}
        self.history: list[dict] = []
        self.total_llm_calls = 0

        for x in range(grid_w):
            for y in range(grid_h):
                self.grid[(x, y)] = None

    def setup(self):
        half = self.n_agents // 2
        personas = ["traditionalist"] * half + ["innovator"] * (self.n_agents - half)
        self.rng.shuffle(personas)

        cells = [(x, y) for x in range(self.grid_w) for y in range(self.grid_h)]
        self.rng.shuffle(cells)

        for i, persona in enumerate(personas):
            a = Agent(uid=i, persona=persona, x=cells[i][0], y=cells[i][1])
            self.agents.append(a)
            self.grid[cells[i]] = a

        print(f"[Setup] {len(self.agents)} agents on {self.grid_w}x{self.grid_h} grid")
        print(f"  Traditionalists: {half}, Innovators: {self.n_agents - half}")
        print(f"  Backend: {type(self.backend).__name__}")
        self._record(0)

    def _neighbors(self, agent: Agent) -> list[Agent]:
        result = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx = (agent.x + dx) % self.grid_w
                ny = (agent.y + dy) % self.grid_h
                occ = self.grid.get((nx, ny))
                if occ is not None:
                    result.append(occ)
        return result

    def _to_context(self, agent: Agent) -> AgentContext:
        p = PERSONAS[agent.persona]
        return AgentContext(uid=agent.uid, persona_label=p["label"], profile=p["profile"])

    async def step(self, step_num: int) -> tuple[int, int]:
        t0 = time.time()

        # Build contexts for all agents
        agent_contexts = [self._to_context(a) for a in self.agents]
        neighbors_map: dict[int, list[AgentContext]] = {}
        for a in self.agents:
            nbrs = self._neighbors(a)
            neighbors_map[a.uid] = [self._to_context(n) for n in nbrs]

        # Async batch decision
        results = await self.backend.decide_batch(agent_contexts, neighbors_map)
        self.total_llm_calls += len(results)

        decisions = {r.uid: r.decision for r in results}

        # Move unhappy agents
        unhappy = [a for a in self.agents if decisions[a.uid] == "Move"]
        self.rng.shuffle(unhappy)

        empty = [(x, y) for (x, y), occ in self.grid.items() if occ is None]
        self.rng.shuffle(empty)

        moves = 0
        for a in unhappy:
            if not empty:
                break
            new_pos = empty.pop()
            old_pos = (a.x, a.y)
            self.grid[old_pos] = None
            a.x, a.y = new_pos
            self.grid[new_pos] = a
            empty.append(old_pos)
            moves += 1

        for a in self.agents:
            a.happy = (decisions[a.uid] == "Stay")

        elapsed = time.time() - t0
        seg = self._segregation_index()
        n_unhappy = len(unhappy)
        pct_happy = (len(self.agents) - n_unhappy) / len(self.agents) * 100

        # Decision summary (first 20 agents)
        dec_summary = " ".join(
            f"{a.uid}({'T' if a.persona == 'traditionalist' else 'I'})={decisions[a.uid][0]}"
            for a in self.agents[:20]
        )
        if len(self.agents) > 20:
            dec_summary += " ..."

        print(
            f"Step {step_num:3d} | Happy: {pct_happy:5.1f}% | "
            f"Moves: {moves:3d} | Seg: {seg:.3f} | "
            f"{elapsed:.1f}s | {dec_summary}"
        )

        self._record(step_num)
        return n_unhappy, moves

    async def run(self):
        print(f"\n{'='*60}")
        print("LLM-DECISION SCHELLING MODEL v2 (async)")
        print(f"{'='*60}\n")

        self.plot_grid(0)

        for s in range(1, self.max_steps + 1):
            n_unhappy, moves = await self.step(s)
            if s % 5 == 0 or s == 1:
                self.plot_grid(s)
            if moves == 0:
                print(f"\n*** Equilibrium at step {s} ***")
                self.plot_grid(s)
                break

        self.plot_grid(s, tag="final")
        self.plot_history()
        self.save_results()
        print(f"\nTotal LLM calls: {self.total_llm_calls}")

    # ── Metrics ─────────────────────────────────────────────

    def _segregation_index(self) -> float:
        ratios = []
        for a in self.agents:
            nbrs = self._neighbors(a)
            if nbrs:
                same = sum(1 for n in nbrs if n.persona == a.persona)
                ratios.append(same / len(nbrs))
        return float(np.mean(ratios)) if ratios else 0.0

    def _persona_seg(self, persona: str) -> float:
        ratios = []
        for a in self.agents:
            if a.persona != persona:
                continue
            nbrs = self._neighbors(a)
            if nbrs:
                same = sum(1 for n in nbrs if n.persona == a.persona)
                ratios.append(same / len(nbrs))
        return float(np.mean(ratios)) if ratios else 0.0

    def _record(self, step: int):
        seg = self._segregation_index()
        n_happy = sum(1 for a in self.agents if a.happy)
        self.history.append({
            "step": step,
            "happy_pct": n_happy / len(self.agents),
            "segregation": seg,
            "trad_seg": self._persona_seg("traditionalist"),
            "inno_seg": self._persona_seg("innovator"),
        })

    # ── Visualization ───────────────────────────────────────

    def plot_grid(self, step: int, tag: str | None = None):
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.set_xlim(-0.5, self.grid_w - 0.5)
        ax.set_ylim(-0.5, self.grid_h - 0.5)
        ax.set_aspect("equal")
        ax.set_facecolor("#f8f8f8")

        for x in range(self.grid_w + 1):
            ax.axvline(x - 0.5, color="#e0e0e0", lw=0.5)
        for y in range(self.grid_h + 1):
            ax.axhline(y - 0.5, color="#e0e0e0", lw=0.5)

        for a in self.agents:
            c = PERSONAS[a.persona]["color"]
            marker = "o" if a.happy else "X"
            ax.plot(a.x, a.y, marker, color=c, ms=10, mec="black", mew=0.3)

        seg = self._segregation_index()
        ax.set_title(f"Step {step}  |  Segregation: {seg:.3f}", fontsize=13)

        handles = [
            plt.Line2D([0], [0], marker="o", color="w",
                       markerfacecolor=p["color"], ms=10, label=p["label"])
            for p in PERSONAS.values()
        ]
        ax.legend(handles=handles, loc="upper right")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        name = tag or f"step_{step:03d}"
        fig.savefig(self.output_dir / f"grid_{name}.png", dpi=120)
        plt.close(fig)

    def plot_history(self):
        if not self.history:
            return
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
        steps = [h["step"] for h in self.history]

        ax1.plot(steps, [h["happy_pct"] * 100 for h in self.history], "b-o", ms=3)
        ax1.set_ylabel("Happy (%)")
        ax1.set_title("Agent Happiness")
        ax1.set_ylim(0, 105)
        ax1.grid(alpha=0.3)

        ax2.plot(steps, [h["segregation"] for h in self.history], "k-o", ms=3, label="Overall")
        ax2.plot(steps, [h["trad_seg"] for h in self.history], "-o",
                 color=PERSONAS["traditionalist"]["color"], ms=3, label="Traditionalist")
        ax2.plot(steps, [h["inno_seg"] for h in self.history], "-o",
                 color=PERSONAS["innovator"]["color"], ms=3, label="Innovator")
        ax2.set_xlabel("Step")
        ax2.set_ylabel("Same-Type Neighbor Ratio")
        ax2.set_title("Segregation Over Time")
        ax2.legend()
        ax2.set_ylim(0, 1.05)
        ax2.grid(alpha=0.3)

        plt.tight_layout()
        fig.savefig(self.output_dir / "history.png", dpi=120)
        plt.close(fig)

    def save_results(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "config": {
                "grid": f"{self.grid_w}x{self.grid_h}",
                "agents": self.n_agents,
                "backend": type(self.backend).__name__,
                "max_steps": self.max_steps,
                "seed": self.seed,
            },
            "agents": [
                {"id": a.uid, "persona": a.persona, "x": a.x, "y": a.y, "happy": a.happy}
                for a in self.agents
            ],
            "history": self.history,
            "total_llm_calls": self.total_llm_calls,
        }
        with open(self.output_dir / "results.json", "w") as f:
            json.dump(data, f, indent=2)
        print(f"[Save] {self.output_dir / 'results.json'}")


# ── CLI ─────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="LLM-Decision Schelling Model v2")
    p.add_argument("--backend", choices=["ollama", "vllm"], default="ollama")
    p.add_argument("--model", type=str, default=None,
                   help="Model name (default: gemma3:4b for ollama, google/gemma-3-4b-it for vllm)")
    p.add_argument("--vllm-url", type=str, default="http://localhost:8000")
    p.add_argument("--ollama-url", type=str, default="http://localhost:11434")
    p.add_argument("--grid", type=int, default=20, help="Grid size (square)")
    p.add_argument("--agents", type=int, default=100)
    p.add_argument("--steps", type=int, default=30)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--concurrent", type=int, default=8,
                   help="Max concurrent LLM requests")
    p.add_argument("--output", type=str, default=None)
    return p.parse_args()


def create_backend(args) -> LLMBackend:
    if args.backend == "vllm":
        model = args.model or "google/gemma-3-4b-it"
        print(f"[Backend] vLLM → {args.vllm_url} ({model})")
        return VLLMBackend(
            model=model,
            base_url=args.vllm_url,
            max_concurrent=args.concurrent,
        )
    else:
        model = args.model or "gemma3:4b"
        print(f"[Backend] Ollama → {args.ollama_url} ({model})")
        return OllamaBackend(
            model=model,
            base_url=args.ollama_url,
            max_concurrent=args.concurrent,
        )


async def main():
    args = parse_args()

    backend = create_backend(args)
    output = args.output or str(
        Path(__file__).parent / f"output_v2_{args.backend}_{args.grid}x{args.grid}"
    )

    model = LLMSchellingModel(
        backend=backend,
        grid_w=args.grid,
        grid_h=args.grid,
        n_agents=args.agents,
        max_steps=args.steps,
        seed=args.seed,
        output_dir=output,
    )
    model.setup()

    try:
        await model.run()
    finally:
        await backend.close()


if __name__ == "__main__":
    asyncio.run(main())
