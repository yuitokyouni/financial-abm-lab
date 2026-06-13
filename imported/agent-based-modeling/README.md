# AI Lab - LLM-Based Agent-Based Modeling

LLMを用いたエージェントベースモデリング研究プロジェクト。

## Core Concept

```
複雑な言語情報 → LLMが解釈 → 単純な行動(buy/sell等) → エージェント群の相互作用 → マクロ現象の創発
```

## Tech Stack

| Phase | LLM | Framework |
|-------|-----|-----------|
| Prototype | Ollama + Gemma 3 4B | Mesa / YuLan-OneSim |
| Mid-scale | Ollama + Gemma 2 27B | YuLan-OneSim |
| Large-scale | vLLM + Gemma 2 27B | YuLan-OneSim |

## Research Themes (10 themes, prioritized)

### Tier 1: First Prototypes
| # | Theme | Feasibility | Novelty |
|---|-------|-------------|---------|
| 6 | Semantic Schelling Model (Gentrification) | ★★★★★ | ★★★★☆ |
| 3 | Bank Run via Linguistic Contagion | ★★★★★ | ★★★★☆ |
| 9 | DAO Ideological Split & Hard Fork | ★★★★★ | ★★★☆☆ |

### Tier 2: After Foundation Established
| # | Theme | Feasibility | Novelty |
|---|-------|-------------|---------|
| 4 | Central Bank Statement Interpretation | ★★★★☆ | ★★★★☆ |
| 7 | Meme Stock Cult Formation | ★★★★☆ | ★★★★☆ |
| 1 | Inflation Narrative Propagation | ★★★★☆ | ★★★★★ |

### Tier 3: Advanced Challenges
| # | Theme | Feasibility | Novelty |
|---|-------|-------------|---------|
| 8 | Supply Chain "Giri & Ninjo" Collapse | ★★★☆☆ | ★★★★★ |
| 10 | Toxic Culture Epidemic in Organizations | ★★★☆☆ | ★★★★★ |
| 5 | Emergence of Money from Barter | ★★★☆☆ | ★★★★★ |
| 2 | Regulator-Bank Semantic Co-evolution | ★★★☆☆ | ★★★★☆ |

## Key Frameworks & Tools

- **YuLan-OneSim** (RUC, 2025) - 10万エージェント対応、vLLM/Ollama互換
- **TradingAgents** (TauricResearch, 2024) - Ollama対応済み金融取引ABM
- **Concordia** (DeepMind) - LLM-ABM、記憶管理
- **Mesa** (Python) - 汎用ABM、シェリングモデル標準実装あり
- **MTOS** (Zuo et al., 2025) - エコーチェンバー・分極化シミュレーション

## Directory Structure

```
agent-based-modeling/
├── README.md
├── research/
│   ├── 00_tech_stack.md         # Ollama, Gemma, vLLM setup
│   ├── 01_inflation_narrative.md
│   ├── 02_regulatory_coevolution.md
│   ├── 03_bank_run.md
│   ├── 04_central_bank_interpretation.md
│   ├── 05_emergence_of_money.md
│   ├── 06_semantic_schelling.md
│   ├── 07_meme_stock_cult.md
│   ├── 08_supply_chain_giri.md
│   ├── 09_dao_hard_fork.md
│   └── 10_toxic_culture.md
└── src/                         # (future) implementation
```
