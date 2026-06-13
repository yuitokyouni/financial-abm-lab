"""
Mini PoC: LLM-Decision Schelling (10 agents, 5x5 grid, 10 steps)
================================================================
Quick test to verify LLM segregation behavior before scaling up.
Expected runtime: ~10 agents * 10 steps * ~5s/call = ~8 min
"""

import random
import json
import time
from pathlib import Path

import ollama
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


PERSONAS = {
    "traditionalist": {
        "label": "Traditionalist",
        "color": "#2ecc71",
        "profile": (
            "I value family bonds, local festivals, quiet mornings, "
            "home-cooked meals, temple visits, and stable community ties."
        ),
    },
    "innovator": {
        "label": "Innovator",
        "color": "#e74c3c",
        "profile": (
            "I love hackathons, co-working spaces, avant-garde art, "
            "startup culture, late-night coding, and global cuisine."
        ),
    },
}

PROMPT_TEMPLATE = """\
You are {label}. Your values: {profile}

Your neighbors are:
{neighbors}

Do you feel you belong here? Reply ONLY "Stay" or "Move"."""


def llm_decide(model: str, agent: dict, neighbors: list[dict]) -> str:
    if not neighbors:
        return "Stay"

    nbr_text = "\n".join(
        f"- {PERSONAS[n['persona']]['label']}: {PERSONAS[n['persona']]['profile']}"
        for n in neighbors
    )
    prompt = PROMPT_TEMPLATE.format(
        label=PERSONAS[agent["persona"]]["label"],
        profile=PERSONAS[agent["persona"]]["profile"],
        neighbors=nbr_text,
    )

    resp = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.2, "num_predict": 5},
    )
    ans = resp["message"]["content"].strip().lower()
    return "Move" if "move" in ans else "Stay"


def get_neighbors(agent, agents, grid_w, grid_h):
    result = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx = (agent["x"] + dx) % grid_w
            ny = (agent["y"] + dy) % grid_h
            for a in agents:
                if a["x"] == nx and a["y"] == ny and a["uid"] != agent["uid"]:
                    result.append(a)
    return result


def segregation_index(agents, grid_w, grid_h):
    ratios = []
    for a in agents:
        nbrs = get_neighbors(a, agents, grid_w, grid_h)
        if nbrs:
            same = sum(1 for n in nbrs if n["persona"] == a["persona"])
            ratios.append(same / len(nbrs))
    return float(np.mean(ratios)) if ratios else 0.0


def plot_grid(agents, grid_w, grid_h, step, seg, out_dir):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_xlim(-0.5, grid_w - 0.5)
    ax.set_ylim(-0.5, grid_h - 0.5)
    ax.set_aspect("equal")
    ax.set_facecolor("#f8f8f8")

    for x in range(grid_w + 1):
        ax.axvline(x - 0.5, color="#e0e0e0", lw=0.5)
    for y in range(grid_h + 1):
        ax.axhline(y - 0.5, color="#e0e0e0", lw=0.5)

    for a in agents:
        c = PERSONAS[a["persona"]]["color"]
        m = "o" if a.get("happy", True) else "X"
        ax.plot(a["x"], a["y"], m, color=c, ms=14, mec="black", mew=0.5)

    ax.set_title(f"Step {step}  |  Seg: {seg:.3f}", fontsize=13)

    handles = [
        plt.Line2D([0], [0], marker="o", color="w",
                   markerfacecolor=p["color"], ms=10, label=p["label"])
        for p in PERSONAS.values()
    ]
    ax.legend(handles=handles, loc="upper right")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"grid_step_{step:02d}.png", dpi=120)
    plt.close(fig)


def main():
    GRID_W, GRID_H = 5, 5
    N_AGENTS = 10
    MAX_STEPS = 10
    MODEL = "gemma3:4b"
    SEED = 42
    OUT = "/home/yuito/ai-lab/agent-based-modeling/experiments/poc_llm_decision/output_mini"

    rng = random.Random(SEED)

    # Create agents
    personas = ["traditionalist"] * (N_AGENTS // 2) + ["innovator"] * (N_AGENTS - N_AGENTS // 2)
    rng.shuffle(personas)

    cells = [(x, y) for x in range(GRID_W) for y in range(GRID_H)]
    rng.shuffle(cells)

    agents = []
    for i, p in enumerate(personas):
        agents.append({"uid": i, "persona": p, "x": cells[i][0], "y": cells[i][1], "happy": True})

    history = []

    seg = segregation_index(agents, GRID_W, GRID_H)
    print(f"{'='*50}")
    print(f"MINI PoC: {N_AGENTS} agents, {GRID_W}x{GRID_H} grid")
    print(f"{'='*50}")
    print(f"Step  0 | Segregation: {seg:.3f}")
    history.append({"step": 0, "seg": seg, "moves": 0})
    plot_grid(agents, GRID_W, GRID_H, 0, seg, OUT)

    total_calls = 0

    for step in range(1, MAX_STEPS + 1):
        t0 = time.time()

        # Collect LLM decisions
        decisions = {}
        for a in agents:
            nbrs = get_neighbors(a, agents, GRID_W, GRID_H)
            d = llm_decide(MODEL, a, nbrs)
            decisions[a["uid"]] = d
            a["happy"] = (d == "Stay")
            total_calls += 1

        # Move unhappy agents to random empty cells
        movers = [a for a in agents if decisions[a["uid"]] == "Move"]
        rng.shuffle(movers)

        occupied = {(a["x"], a["y"]) for a in agents}
        empty = [(x, y) for x in range(GRID_W) for y in range(GRID_H) if (x, y) not in occupied]
        rng.shuffle(empty)

        moves = 0
        for a in movers:
            if not empty:
                break
            new_pos = empty.pop()
            old_pos = (a["x"], a["y"])
            a["x"], a["y"] = new_pos
            empty.append(old_pos)
            moves += 1

        seg = segregation_index(agents, GRID_W, GRID_H)
        elapsed = time.time() - t0

        # Log LLM decisions for transparency
        dec_summary = " ".join(
            f"{a['uid']}({'T' if a['persona']=='traditionalist' else 'I'})={decisions[a['uid']][0]}"
            for a in agents
        )
        print(
            f"Step {step:2d} | Seg: {seg:.3f} | Moves: {moves} | "
            f"{elapsed:.1f}s | {dec_summary}"
        )
        history.append({"step": step, "seg": seg, "moves": moves})
        plot_grid(agents, GRID_W, GRID_H, step, seg, OUT)

        if moves == 0:
            print(f"\n*** Equilibrium at step {step} ***")
            break

    # Plot history
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot([h["step"] for h in history], [h["seg"] for h in history], "ko-")
    ax.set_xlabel("Step")
    ax.set_ylabel("Segregation Index")
    ax.set_title("Segregation Over Time (Mini PoC)")
    ax.set_ylim(0, 1.05)
    ax.grid(alpha=0.3)
    Path(OUT).mkdir(exist_ok=True)
    fig.savefig(Path(OUT) / "history.png", dpi=120)
    plt.close(fig)

    # Save
    with open(Path(OUT) / "results.json", "w") as f:
        json.dump({"history": history, "total_llm_calls": total_calls,
                    "agents_final": agents}, f, indent=2)
    print(f"\nTotal LLM calls: {total_calls}")
    print(f"Results saved to {OUT}/")


if __name__ == "__main__":
    main()
