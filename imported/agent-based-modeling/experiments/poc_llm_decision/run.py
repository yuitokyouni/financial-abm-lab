"""
PoC: LLM-Decision Semantic Schelling Model
===========================================
20x20 grid, ~100 agents, 2 persona types.
LLM (Ollama gemma3:4b) decides Stay/Move by reading neighbor profiles.
Goal: verify if macro segregation emerges from LLM judgment alone.
"""

import random
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import ollama
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ── Config ──────────────────────────────────────────────────

@dataclass
class Config:
    grid_w: int = 20
    grid_h: int = 20
    n_agents: int = 100
    max_steps: int = 30
    seed: int = 42
    model: str = "gemma3:4b"
    output_dir: str = "output"


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
    profile: str
    x: int = 0
    y: int = 0
    happy: bool = True


# ── LLM Decision ───────────────────────────────────────────

DECISION_PROMPT = """\
You are {persona_label}.
Your profile: {profile}

Your current neighbors:
{neighbor_block}

Based on how well you fit in with these neighbors, should you Stay or Move?
Answer with a single word: Stay or Move."""


def ask_llm(model: str, agent: Agent, neighbors: list[Agent]) -> str:
    """Ask LLM whether to Stay or Move. Returns 'Stay' or 'Move'."""
    if not neighbors:
        return "Stay"

    neighbor_lines = []
    for i, n in enumerate(neighbors, 1):
        label = PERSONAS[n.persona]["label"]
        neighbor_lines.append(f"  {i}. [{label}] {n.profile}")
    neighbor_block = "\n".join(neighbor_lines)

    prompt = DECISION_PROMPT.format(
        persona_label=PERSONAS[agent.persona]["label"],
        profile=agent.profile,
        neighbor_block=neighbor_block,
    )

    try:
        resp = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3, "num_predict": 10},
        )
        answer = resp["message"]["content"].strip().split()[0].lower()
        if "stay" in answer:
            return "Stay"
        elif "move" in answer:
            return "Move"
        else:
            # Ambiguous → default Stay
            return "Stay"
    except Exception as e:
        print(f"  [LLM error] agent {agent.uid}: {e}")
        return "Stay"


# ── Model ──────────────────────────────────────────────────

class LLMSchellingModel:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.agents: list[Agent] = []
        self.grid: dict[tuple[int, int], Agent | None] = {}
        self.history: list[dict] = []
        self.llm_call_count = 0

        for x in range(cfg.grid_w):
            for y in range(cfg.grid_h):
                self.grid[(x, y)] = None

    def setup(self):
        """Create agents (50/50 split) and place randomly."""
        half = self.cfg.n_agents // 2
        personas = ["traditionalist"] * half + ["innovator"] * (self.cfg.n_agents - half)
        self.rng.shuffle(personas)

        cells = [(x, y) for x in range(self.cfg.grid_w) for y in range(self.cfg.grid_h)]
        self.rng.shuffle(cells)

        for i, persona in enumerate(personas):
            a = Agent(
                uid=i,
                persona=persona,
                profile=PERSONAS[persona]["profile"],
                x=cells[i][0],
                y=cells[i][1],
            )
            self.agents.append(a)
            self.grid[cells[i]] = a

        print(f"[Setup] {len(self.agents)} agents on {self.cfg.grid_w}x{self.cfg.grid_h} grid")
        print(f"  Traditionalists: {half}, Innovators: {self.cfg.n_agents - half}")
        self._record(0)

    def neighbors(self, agent: Agent) -> list[Agent]:
        """Moore neighborhood (8 cells, toroidal)."""
        result = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx = (agent.x + dx) % self.cfg.grid_w
                ny = (agent.y + dy) % self.cfg.grid_h
                occ = self.grid.get((nx, ny))
                if occ is not None:
                    result.append(occ)
        return result

    def step(self, step_num: int):
        """One simulation step: ask LLM for each agent, move unhappy ones."""
        t0 = time.time()
        decisions: list[tuple[Agent, str]] = []

        # Phase 1: collect decisions
        for agent in self.agents:
            nbrs = self.neighbors(agent)
            decision = ask_llm(self.cfg.model, agent, nbrs)
            decisions.append((agent, decision))
            self.llm_call_count += 1

        # Phase 2: move agents that chose Move
        unhappy = [(a, d) for a, d in decisions if d == "Move"]
        self.rng.shuffle(unhappy)

        empty = [(x, y) for (x, y), occ in self.grid.items() if occ is None]
        self.rng.shuffle(empty)

        moves = 0
        for agent, _ in unhappy:
            if not empty:
                break
            new_pos = empty.pop()
            old_pos = (agent.x, agent.y)
            self.grid[old_pos] = None
            agent.x, agent.y = new_pos
            self.grid[new_pos] = agent
            empty.append(old_pos)
            moves += 1
            agent.happy = False

        for agent, decision in decisions:
            agent.happy = (decision == "Stay")

        elapsed = time.time() - t0
        n_unhappy = len(unhappy)
        pct_happy = (len(self.agents) - n_unhappy) / len(self.agents) * 100
        seg = self._segregation_index()

        print(
            f"Step {step_num:3d} | Happy: {pct_happy:5.1f}% | "
            f"Moves: {moves:3d} | Segregation: {seg:.3f} | "
            f"LLM calls: {len(self.agents)} | {elapsed:.1f}s"
        )

        self._record(step_num)
        return n_unhappy, moves

    def run(self):
        """Run full simulation."""
        print(f"\n{'='*60}")
        print("LLM-DECISION SCHELLING MODEL")
        print(f"{'='*60}\n")

        self.plot_grid(0)

        for s in range(1, self.cfg.max_steps + 1):
            n_unhappy, moves = self.step(s)
            if s % 5 == 0 or s == 1:
                self.plot_grid(s)
            if moves == 0:
                print(f"\n*** Equilibrium at step {s} (no moves) ***")
                self.plot_grid(s)
                break

        self.plot_grid(s, tag="final")
        self.plot_history()
        self.save_results()
        print(f"\nTotal LLM calls: {self.llm_call_count}")

    # ── Metrics ─────────────────────────────────────────────

    def _segregation_index(self) -> float:
        """Fraction of same-type neighbors (averaged over all agents)."""
        ratios = []
        for a in self.agents:
            nbrs = self.neighbors(a)
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

    def _persona_seg(self, persona: str) -> float:
        ratios = []
        for a in self.agents:
            if a.persona != persona:
                continue
            nbrs = self.neighbors(a)
            if nbrs:
                same = sum(1 for n in nbrs if n.persona == a.persona)
                ratios.append(same / len(nbrs))
        return float(np.mean(ratios)) if ratios else 0.0

    # ── Visualization ───────────────────────────────────────

    def plot_grid(self, step: int, tag: str | None = None):
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.set_xlim(-0.5, self.cfg.grid_w - 0.5)
        ax.set_ylim(-0.5, self.cfg.grid_h - 0.5)
        ax.set_aspect("equal")
        ax.set_facecolor("#f8f8f8")

        for x in range(self.cfg.grid_w + 1):
            ax.axvline(x - 0.5, color="#e0e0e0", lw=0.5)
        for y in range(self.cfg.grid_h + 1):
            ax.axhline(y - 0.5, color="#e0e0e0", lw=0.5)

        for a in self.agents:
            c = PERSONAS[a.persona]["color"]
            marker = "o" if a.happy else "X"
            ax.plot(a.x, a.y, marker, color=c, ms=10, mec="black", mew=0.3)

        seg = self._segregation_index()
        ax.set_title(f"Step {step}  |  Segregation Index: {seg:.3f}", fontsize=13)

        handles = [
            plt.Line2D([0], [0], marker="o", color="w",
                       markerfacecolor=p["color"], ms=10, label=p["label"])
            for p in PERSONAS.values()
        ]
        ax.legend(handles=handles, loc="upper right")

        out = Path(self.cfg.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        name = tag or f"step_{step:03d}"
        fig.savefig(out / f"grid_{name}.png", dpi=120)
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
        out = Path(self.cfg.output_dir)
        fig.savefig(out / "history.png", dpi=120)
        plt.close(fig)

    def save_results(self):
        out = Path(self.cfg.output_dir)
        out.mkdir(parents=True, exist_ok=True)

        data = {
            "config": {
                "grid": f"{self.cfg.grid_w}x{self.cfg.grid_h}",
                "agents": self.cfg.n_agents,
                "model": self.cfg.model,
                "max_steps": self.cfg.max_steps,
                "seed": self.cfg.seed,
            },
            "agents": [
                {"id": a.uid, "persona": a.persona, "x": a.x, "y": a.y, "happy": a.happy}
                for a in self.agents
            ],
            "history": self.history,
            "total_llm_calls": self.llm_call_count,
        }
        with open(out / "results.json", "w") as f:
            json.dump(data, f, indent=2)
        print(f"[Save] {out / 'results.json'}")


# ── Main ───────────────────────────────────────────────────

if __name__ == "__main__":
    cfg = Config(
        grid_w=20,
        grid_h=20,
        n_agents=100,
        max_steps=30,
        seed=42,
        model="gemma3:4b",
        output_dir="/home/yuito/ai-lab/agent-based-modeling/experiments/poc_llm_decision/output",
    )

    model = LLMSchellingModel(cfg)
    model.setup()
    model.run()
