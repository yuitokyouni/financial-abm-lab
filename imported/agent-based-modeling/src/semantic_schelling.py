"""
Semantic Schelling Model - LLM-Based Agent-Based Modeling Prototype

Core concept:
- Agents express lifestyle preferences as rich natural language text
- Similarity is computed via sentence embeddings (cosine similarity)
- Agents move if average similarity with neighbors falls below threshold
- Emergent: cultural/lifestyle-based urban segregation (gentrification)

This replaces the classic Schelling model's binary (type A/B) with
continuous, multi-dimensional semantic similarity.
"""

import json
import random
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from dataclasses import dataclass, field
from pathlib import Path

# ---------- Configuration ----------

@dataclass
class Config:
    grid_width: int = 20
    grid_height: int = 20
    num_agents: int = 200  # ~50% occupancy on 20x20
    similarity_threshold: float = 0.3  # min avg cosine similarity to be happy
    max_steps: int = 50
    seed: int = 42
    use_llm: bool = True  # If False, use predefined persona texts
    llm_model: str = "gemma3:4b"
    embedding_model: str = "all-MiniLM-L6-v2"
    output_dir: str = "output"


# ---------- Persona Definitions ----------

PERSONAS = [
    {
        "id": "artist",
        "label": "Artist / Creative",
        "color": "#e74c3c",
        "seed_prompt": "You are a bohemian artist who loves vintage galleries, street art, independent coffee shops, poetry readings, and DIY culture. Describe your ideal neighborhood lifestyle in 2-3 sentences."
    },
    {
        "id": "tech",
        "label": "Tech Professional",
        "color": "#3498db",
        "seed_prompt": "You are a tech startup worker who loves co-working spaces, craft beer breweries, smart home gadgets, hackathons, and cycling to work. Describe your ideal neighborhood lifestyle in 2-3 sentences."
    },
    {
        "id": "traditional",
        "label": "Traditional Family",
        "color": "#2ecc71",
        "seed_prompt": "You are a parent in a traditional family who values safe parks for children, good local schools, quiet streets, community festivals, and family-run restaurants. Describe your ideal neighborhood lifestyle in 2-3 sentences."
    },
    {
        "id": "student",
        "label": "Student",
        "color": "#f39c12",
        "seed_prompt": "You are a university student who loves cheap eats, late-night study cafes, live music venues, thrift stores, and spontaneous house parties. Describe your ideal neighborhood lifestyle in 2-3 sentences."
    },
    {
        "id": "retiree",
        "label": "Retiree",
        "color": "#9b59b6",
        "seed_prompt": "You are a retiree who enjoys morning walks in botanical gardens, traditional tea houses, local history clubs, bird watching, and quiet evenings reading. Describe your ideal neighborhood lifestyle in 2-3 sentences."
    },
]

# Fallback texts when LLM is not available
FALLBACK_TEXTS = {
    "artist": [
        "I dream of living surrounded by murals and street art, where every corner has a hidden gallery. My mornings start with pour-over coffee at an independent cafe, and evenings are spent at open mic nights or pottery workshops.",
        "Nothing beats a neighborhood with converted warehouse studios, community art projects, and weekly flea markets. I love cycling past colorful graffiti to reach my favorite vinyl record shop.",
        "I want a place where creativity bleeds into everyday life — neighbors who paint, sculpt, and play music. Farmers markets on weekends, zine fairs, and rooftop film screenings make me feel alive.",
    ],
    "tech": [
        "My ideal neighborhood has fast fiber internet, co-working spaces on every block, and craft coffee shops with good WiFi. I bike to work and unwind at a microbrewery discussing the latest open-source projects.",
        "I thrive in innovation districts with startup incubators, maker spaces, and smart city infrastructure. Electric scooters, app-based everything, and a vibrant meetup culture define my lifestyle.",
        "Give me a neighborhood where I can grab matcha from an automated kiosk, code at a minimalist co-working space, and join a weekend hackathon. Efficiency and connectivity are my priorities.",
    ],
    "traditional": [
        "I want a safe, quiet neighborhood with good schools, green parks, and friendly neighbors who wave hello. Weekend barbecues, community sports leagues, and family movie nights at the local theater are what matter most.",
        "My ideal area has tree-lined streets where kids can ride bikes safely, a reliable local pediatrician, and family-owned bakeries. Sunday mornings mean church and brunch at the diner everyone knows.",
        "A neighborhood with block parties, parent-teacher associations, and a well-maintained playground is perfect. I value routine, stability, and knowing the shopkeepers by name.",
    ],
    "student": [
        "I need affordable ramen shops, a 24-hour library nearby, and bars with cheap drink specials. The vibe should be chaotic and creative — house parties, pickup basketball, and spontaneous road trips.",
        "My perfect area is walkable to campus with lots of thrift stores, taco trucks, and underground music venues. I thrive in a messy, energetic environment where everyone is figuring things out.",
        "Late-night pizza, study groups at noisy cafes, and weekend festivals in the park — that's my scene. I want a place that's diverse, affordable, and never boring.",
    ],
    "retiree": [
        "I cherish quiet mornings walking through the botanical garden, followed by tea and a good book at the local library. Bridge club on Tuesdays and bird watching on Saturdays give my week a pleasant rhythm.",
        "My ideal neighborhood has gentle walking paths along a river, a traditional tea house, and a community center hosting lectures on local history. Peace and routine are my greatest luxuries.",
        "I prefer a serene area with well-kept gardens, a friendly post office, and a weekly farmers market. Evenings are for classical music on the radio and writing letters to old friends.",
    ],
}


# ---------- LLM Client ----------

class LLMClient:
    """Wrapper for Ollama LLM calls with fallback."""

    def __init__(self, config: Config):
        self.config = config
        self._ollama = None
        if config.use_llm:
            try:
                import ollama
                # Test connection
                ollama.list()
                self._ollama = ollama
                print("[LLM] Connected to Ollama successfully.")
            except Exception as e:
                print(f"[LLM] Ollama not available ({e}). Using fallback texts.")
                self._ollama = None

    def generate_lifestyle_text(self, persona: dict, index: int) -> str:
        """Generate a lifestyle preference text for an agent."""
        if self._ollama:
            try:
                response = self._ollama.chat(
                    model=self.config.llm_model,
                    messages=[
                        {"role": "system", "content": "You are writing a short, vivid description of your ideal neighborhood lifestyle. Be specific and personal. Reply in 2-3 sentences only."},
                        {"role": "user", "content": persona["seed_prompt"]},
                    ],
                    options={"temperature": 0.9, "seed": self.config.seed + index},
                )
                return response["message"]["content"].strip()
            except Exception as e:
                print(f"[LLM] Generation failed ({e}), using fallback.")

        # Fallback: use predefined texts with slight variation
        texts = FALLBACK_TEXTS[persona["id"]]
        return texts[index % len(texts)]


# ---------- Embedding Engine ----------

class EmbeddingEngine:
    """Compute sentence embeddings and cosine similarities."""

    def __init__(self, config: Config):
        self.config = config
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.config.embedding_model)
                print(f"[Embedding] Loaded model: {self.config.embedding_model}")
            except ImportError:
                print("[Embedding] sentence-transformers not installed. Using TF-IDF fallback.")
                self._model = "tfidf"

    def encode(self, texts: list[str]) -> np.ndarray:
        """Encode texts to embeddings. Returns (N, D) array."""
        self._load_model()
        if self._model == "tfidf":
            return self._tfidf_encode(texts)
        return self._model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

    def _tfidf_encode(self, texts: list[str]) -> np.ndarray:
        """Fallback: TF-IDF based embeddings."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        vectorizer = TfidfVectorizer(max_features=300)
        matrix = vectorizer.fit_transform(texts).toarray()
        # Normalize
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return matrix / norms


# ---------- Agent ----------

@dataclass
class Agent:
    agent_id: int
    persona_id: str
    persona_label: str
    color: str
    lifestyle_text: str
    embedding: np.ndarray = field(default_factory=lambda: np.array([]))
    x: int = 0
    y: int = 0
    happy: bool = True


# ---------- Semantic Schelling Model ----------

class SemanticSchellingModel:
    """
    Grid-based Schelling model where similarity is computed
    via cosine similarity of lifestyle text embeddings.
    """

    def __init__(self, config: Config):
        self.config = config
        self.rng = random.Random(config.seed)
        self.np_rng = np.random.default_rng(config.seed)
        self.agents: list[Agent] = []
        self.grid: dict[tuple[int, int], Agent | None] = {}
        self.history: list[dict] = []
        self.similarity_matrix: np.ndarray = np.array([])

        # Initialize grid as empty
        for x in range(config.grid_width):
            for y in range(config.grid_height):
                self.grid[(x, y)] = None

    def setup(self):
        """Initialize agents with personas, generate texts, compute embeddings."""
        print("=" * 60)
        print("SEMANTIC SCHELLING MODEL - Setup")
        print("=" * 60)

        llm = LLMClient(self.config)
        embedding_engine = EmbeddingEngine(self.config)

        # 1. Create agents with assigned personas
        print(f"\n[Setup] Creating {self.config.num_agents} agents...")
        agents_per_persona = self.config.num_agents // len(PERSONAS)
        remainder = self.config.num_agents % len(PERSONAS)

        agent_id = 0
        for i, persona in enumerate(PERSONAS):
            count = agents_per_persona + (1 if i < remainder else 0)
            for j in range(count):
                text = llm.generate_lifestyle_text(persona, index=agent_id)
                agent = Agent(
                    agent_id=agent_id,
                    persona_id=persona["id"],
                    persona_label=persona["label"],
                    color=persona["color"],
                    lifestyle_text=text,
                )
                self.agents.append(agent)
                agent_id += 1

        # 2. Compute embeddings
        print(f"\n[Setup] Computing embeddings for {len(self.agents)} agents...")
        texts = [a.lifestyle_text for a in self.agents]
        embeddings = embedding_engine.encode(texts)
        for i, agent in enumerate(self.agents):
            agent.embedding = embeddings[i]

        # 3. Compute pairwise similarity matrix
        print("[Setup] Computing similarity matrix...")
        self.similarity_matrix = embeddings @ embeddings.T  # cosine sim (already normalized)

        # 4. Place agents randomly on grid
        print("[Setup] Placing agents on grid...")
        all_cells = [(x, y) for x in range(self.config.grid_width)
                     for y in range(self.config.grid_height)]
        self.rng.shuffle(all_cells)
        for i, agent in enumerate(self.agents):
            x, y = all_cells[i]
            agent.x, agent.y = x, y
            self.grid[(x, y)] = agent

        self._record_state(step=0)
        print(f"[Setup] Done. Grid: {self.config.grid_width}x{self.config.grid_height}, "
              f"Agents: {len(self.agents)}, Threshold: {self.config.similarity_threshold}")
        self._print_sample_texts()

    def _print_sample_texts(self):
        """Print sample lifestyle texts for each persona."""
        print("\n--- Sample Lifestyle Texts ---")
        seen = set()
        for agent in self.agents:
            if agent.persona_id not in seen:
                seen.add(agent.persona_id)
                print(f"\n[{agent.persona_label}] (Agent #{agent.agent_id})")
                print(f"  \"{agent.lifestyle_text[:150]}...\"")
        print("-" * 40)

    def get_neighbors(self, agent: Agent) -> list[Agent]:
        """Get agents in Moore neighborhood (8 surrounding cells)."""
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx = (agent.x + dx) % self.config.grid_width
                ny = (agent.y + dy) % self.config.grid_height
                neighbor = self.grid.get((nx, ny))
                if neighbor is not None:
                    neighbors.append(neighbor)
        return neighbors

    def compute_happiness(self, agent: Agent) -> tuple[bool, float]:
        """Compute if agent is happy based on semantic similarity with neighbors."""
        neighbors = self.get_neighbors(agent)
        if not neighbors:
            return True, 1.0  # No neighbors = happy

        similarities = [self.similarity_matrix[agent.agent_id][n.agent_id] for n in neighbors]
        avg_sim = np.mean(similarities)
        happy = avg_sim >= self.config.similarity_threshold
        return happy, avg_sim

    def step(self):
        """Execute one simulation step."""
        # 1. Compute happiness for all agents
        unhappy_agents = []
        for agent in self.agents:
            happy, avg_sim = self.compute_happiness(agent)
            agent.happy = happy
            if not happy:
                unhappy_agents.append(agent)

        # 2. Shuffle unhappy agents and try to move them
        self.rng.shuffle(unhappy_agents)
        moves = 0

        # Find empty cells
        empty_cells = [(x, y) for (x, y), occupant in self.grid.items() if occupant is None]

        for agent in unhappy_agents:
            if not empty_cells:
                break

            # Try random empty cells, pick the best one
            candidates = self.rng.sample(empty_cells, min(10, len(empty_cells)))
            best_cell = None
            best_sim = -1

            for cx, cy in candidates:
                # Temporarily compute similarity at candidate location
                temp_neighbors = []
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx == 0 and dy == 0:
                            continue
                        nx = (cx + dx) % self.config.grid_width
                        ny = (cy + dy) % self.config.grid_height
                        n = self.grid.get((nx, ny))
                        if n is not None:
                            temp_neighbors.append(n)

                if temp_neighbors:
                    avg_sim = np.mean([self.similarity_matrix[agent.agent_id][n.agent_id]
                                       for n in temp_neighbors])
                else:
                    avg_sim = 0.5  # Neutral if no neighbors

                if avg_sim > best_sim:
                    best_sim = avg_sim
                    best_cell = (cx, cy)

            if best_cell and best_sim > -1:
                # Move agent
                old_pos = (agent.x, agent.y)
                self.grid[old_pos] = None
                agent.x, agent.y = best_cell
                self.grid[best_cell] = agent
                empty_cells.remove(best_cell)
                empty_cells.append(old_pos)
                moves += 1

        return len(unhappy_agents), moves

    def run(self):
        """Run the simulation."""
        print(f"\n{'=' * 60}")
        print("SIMULATION START")
        print(f"{'=' * 60}\n")

        for step in range(1, self.config.max_steps + 1):
            unhappy, moves = self.step()
            self._record_state(step)
            pct_happy = (len(self.agents) - unhappy) / len(self.agents) * 100
            print(f"Step {step:3d} | Unhappy: {unhappy:3d} ({100-pct_happy:.1f}%) | Moves: {moves:3d}")

            if unhappy == 0:
                print(f"\n*** All agents happy at step {step}! ***")
                break

        print(f"\n{'=' * 60}")
        print("SIMULATION COMPLETE")
        print(f"{'=' * 60}")

    def _record_state(self, step: int):
        """Record state for analysis."""
        unhappy_count = sum(1 for a in self.agents if not a.happy)
        # Compute average similarity per persona
        persona_sims = {}
        for persona in PERSONAS:
            agents_of_type = [a for a in self.agents if a.persona_id == persona["id"]]
            sims = []
            for a in agents_of_type:
                neighbors = self.get_neighbors(a)
                same_type_neighbors = [n for n in neighbors if n.persona_id == a.persona_id]
                if neighbors:
                    sims.append(len(same_type_neighbors) / len(neighbors))
            persona_sims[persona["id"]] = np.mean(sims) if sims else 0

        self.history.append({
            "step": step,
            "unhappy": unhappy_count,
            "happy_pct": (len(self.agents) - unhappy_count) / len(self.agents),
            "persona_segregation": persona_sims,
        })

    # ---------- Visualization ----------

    def plot_grid(self, step: int | None = None, save: bool = True):
        """Plot the current grid state."""
        fig, ax = plt.subplots(1, 1, figsize=(10, 10))
        ax.set_xlim(-0.5, self.config.grid_width - 0.5)
        ax.set_ylim(-0.5, self.config.grid_height - 0.5)
        ax.set_aspect("equal")
        ax.set_title(f"Semantic Schelling Model - Step {step or 'Final'}", fontsize=14)
        ax.set_facecolor("#f5f5f5")

        # Draw grid lines
        for x in range(self.config.grid_width + 1):
            ax.axvline(x - 0.5, color="#ddd", linewidth=0.5)
        for y in range(self.config.grid_height + 1):
            ax.axhline(y - 0.5, color="#ddd", linewidth=0.5)

        # Draw agents
        for agent in self.agents:
            marker = "o" if agent.happy else "x"
            ax.plot(agent.x, agent.y, marker, color=agent.color,
                    markersize=12 if agent.happy else 8, markeredgecolor="black",
                    markeredgewidth=0.5)

        # Legend
        handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=p["color"],
                              markersize=10, label=p["label"]) for p in PERSONAS]
        ax.legend(handles=handles, loc="upper right", fontsize=9)

        plt.tight_layout()
        if save:
            out_dir = Path(self.config.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = f"grid_step_{step or 'final'}.png"
            fig.savefig(out_dir / filename, dpi=150)
            print(f"[Plot] Saved: {out_dir / filename}")
        plt.close(fig)

    def plot_history(self, save: bool = True):
        """Plot simulation metrics over time."""
        if not self.history:
            return

        fig, axes = plt.subplots(2, 1, figsize=(12, 8))

        steps = [h["step"] for h in self.history]

        # Plot 1: Happiness over time
        happy_pcts = [h["happy_pct"] * 100 for h in self.history]
        axes[0].plot(steps, happy_pcts, "b-o", markersize=3)
        axes[0].set_ylabel("Happy Agents (%)")
        axes[0].set_title("Agent Happiness Over Time")
        axes[0].set_ylim(0, 105)
        axes[0].grid(True, alpha=0.3)

        # Plot 2: Segregation by persona
        for persona in PERSONAS:
            seg_values = [h["persona_segregation"].get(persona["id"], 0) * 100
                         for h in self.history]
            axes[1].plot(steps, seg_values, "-o", color=persona["color"],
                        label=persona["label"], markersize=3)
        axes[1].set_xlabel("Step")
        axes[1].set_ylabel("Same-Type Neighbor Ratio (%)")
        axes[1].set_title("Segregation by Persona Type")
        axes[1].legend(fontsize=8)
        axes[1].set_ylim(0, 105)
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()
        if save:
            out_dir = Path(self.config.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            fig.savefig(out_dir / "history.png", dpi=150)
            print(f"[Plot] Saved: {out_dir / 'history.png'}")
        plt.close(fig)

    def plot_similarity_heatmap(self, save: bool = True):
        """Plot pairwise similarity matrix sorted by persona."""
        # Sort agents by persona
        sorted_agents = sorted(self.agents, key=lambda a: a.persona_id)
        indices = [a.agent_id for a in sorted_agents]
        sorted_matrix = self.similarity_matrix[np.ix_(indices, indices)]

        fig, ax = plt.subplots(1, 1, figsize=(10, 8))
        im = ax.imshow(sorted_matrix, cmap="RdYlBu_r", vmin=0, vmax=1)
        plt.colorbar(im, ax=ax, label="Cosine Similarity")
        ax.set_title("Agent Pairwise Similarity (sorted by persona)")

        # Draw persona boundaries
        counts = []
        for persona in sorted(set(a.persona_id for a in self.agents)):
            counts.append(sum(1 for a in sorted_agents if a.persona_id == persona))
        cumsum = np.cumsum(counts)
        for c in cumsum[:-1]:
            ax.axhline(c - 0.5, color="black", linewidth=1)
            ax.axvline(c - 0.5, color="black", linewidth=1)

        plt.tight_layout()
        if save:
            out_dir = Path(self.config.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            fig.savefig(out_dir / "similarity_heatmap.png", dpi=150)
            print(f"[Plot] Saved: {out_dir / 'similarity_heatmap.png'}")
        plt.close(fig)

    def save_results(self):
        """Save agent data and history to JSON."""
        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        agent_data = []
        for a in self.agents:
            agent_data.append({
                "id": a.agent_id,
                "persona": a.persona_id,
                "text": a.lifestyle_text,
                "x": a.x,
                "y": a.y,
                "happy": bool(a.happy),
            })

        with open(out_dir / "agents.json", "w") as f:
            json.dump(agent_data, f, indent=2, ensure_ascii=False)

        with open(out_dir / "history.json", "w") as f:
            json.dump(self.history, f, indent=2)

        print(f"[Save] Results saved to {out_dir}/")


# ---------- Main ----------

def main():
    config = Config(
        grid_width=10,
        grid_height=10,
        num_agents=64,
        similarity_threshold=0.3,
        max_steps=50,
        seed=42,
        use_llm=True,
        llm_model="gemma3:1b",
        output_dir="/home/yuito/ai-lab/agent-based-modeling/output",
    )

    model = SemanticSchellingModel(config)

    # Setup: generate texts, compute embeddings, place agents
    model.setup()

    # Visualize initial state
    model.plot_grid(step=0)
    model.plot_similarity_heatmap()

    # Run simulation
    model.run()

    # Visualize final state
    model.plot_grid(step=model.history[-1]["step"])
    model.plot_history()

    # Save results
    model.save_results()


if __name__ == "__main__":
    main()
