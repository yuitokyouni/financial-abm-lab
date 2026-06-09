### Building the Foundation for Financial ABM Research

financial-abm-lab/
  README.md
  pyproject.toml
  .gitignore
  configs/
    experiment_example.yaml
  data/
    raw/
    processed/
    external/
  notebooks/
    00_sanity_check.ipynb
  src/
    fabm/
      __init__.py
      config.py
      rng.py
      logging.py
      data/
      stats/
      microstructure/
      abm/
      validation/
  experiments/
    runs/
  reports/
  tests/
    test_rng.py
    test_config.py

## Rules
# All experiments have to be driven from config
experiment_name: "stylized_facts_baseline"
seed: 42

data:
  symbol: "TOPIX"
  start: "2010-01-01"
  end: "2025-12-31"

simulation:
  n_agents: 100
  n_steps: 10000

metrics:
  - mean_return
  - volatility
  - kurtosis
  - tail_index
  - abs_return_acf

# Conduct an experiment with multi seeds
master_seed = 42

agent_seed
order_seed
news_seed
simulation_seed
validation_seed

# The results have to be preseaved in tables, not in graphs only.
run_id
timestamp
git_commit
config_path
seed
parameters
metrics
artifact_paths
notes