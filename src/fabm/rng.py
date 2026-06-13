import numpy as np

def make_rngs(master_seed: int) -> dict[str, np.random.Generator]:
    seed_seq = np.random.SeedSequence(master_seed)
    child_seeds = seed_seq.spawn(5)
    
    names = ["agents", "orders", "news", "simulation", "validation"]
    
    return{name: np.random.default_rng(seed)
           for name, seed in zip(names, child_seeds)
        }