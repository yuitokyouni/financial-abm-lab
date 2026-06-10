# Architecture (auto-generated)

## Packages
```mermaid
classDiagram
  class microstructure {
  }
  class agents {
  }
  class anchors {
  }
  class benchmarks {
  }
  class book {
  }
  class config {
  }
  class engine {
  }
  class env {
  }
  class learnconfig {
  }
  class metrics {
  }
  class qlearn {
  }
  class verdict {
  }
  microstructure --> config
  microstructure --> engine
  agents --> book
  benchmarks --> anchors
  benchmarks --> learnconfig
  engine --> config
  engine --> metrics
  env --> learnconfig
  learnconfig --> anchors
  qlearn --> env
  qlearn --> learnconfig
  verdict --> env
  verdict --> learnconfig
  verdict --> qlearn
```

## Classes
```mermaid
classDiagram
  class CellMeasurement {
    converged : bool
    exited : bool
    extraction_rate : float
    floors : dict[str, float]
    markup : float
    mm_pnl : float
    realized_spread : float
    seed : int
  }
  class CollusionVerdict {
    certified : bool
    converged_all : bool
    ir_pass_frac : float
    markup_mean : float
    markup_se : float
    markup_significant : bool
    n_seeds : int
  }
  class FixedPolicy {
    table
    act(state: int, t: int) int
    frozen() 'FixedPolicy'
    greedy(state: int) int
    update(s, a, r, s_next, a_next)* None
  }
  class IRResult {
    baseline_profile : tuple[int, ...]
    deviation_action : int
    deviation_profitable : bool
    profiles : list
    punish_lag : int | None
    punished : bool
    restored : bool
  }
  class LearnConfig {
    action_grid : tuple[float, ...]
    algo : Literal['qlearning', 'sarsa', 'zi', 'fixed']
    alpha : float
    batch_interval : int
    dt : float
    eps_beta : float
    fee : float
    gamma : float
    grid_hi_mult : float
    grid_lo_mult : float
    h_star_cont : float
    initial_price : float
    ir_horizon : int
    ir_pre : int
    ir_punish_lag : int
    ir_restore_tail : int
    jump_size : float
    lambda_jump : float
    lr : float
    markup_floor : float
    measure_periods : int
    mechanism : Literal['continuous', 'batch']
    memory : int
    n_actions : int
    n_mm : int
    n_states : int
    noise_rate : float
    noise_reserve : float
    period_steps : int
    q_init : float
    seed : int
    sigma : float
    stable_window : int
    staleness : Literal['committed', 'revisable']
    t_max : int
    tie_rule : Literal['split', 'rotate']
    replace() 'LearnConfig'
  }
  class MarketEnv {
    cfg
    grid
    m
    v
    step(actions: tuple[int, ...]) tuple[np.ndarray, dict]
  }
  class MarketMaker {
    m : float
    learn(v: float) None
    quote(h: float) tuple[float, float]
  }
  class Metrics {
    effective_spread : float
    extraction : float
    fees : float
    informed_impact : float
    mm_exits : bool
    mm_net_pnl : float
    mm_trading_pnl : float
    n_arb : int
    n_noise : int
    n_trades : int
    noise_pnl : float
    participation_margin : float
    price_impact : float
  }
  class Order {
    agent_id : str
    price : float
    side
    size : float
    t : int
  }
  class QLearner {
    update(s: int, a: int, r: float, s_next: int, a_next: int) None
  }
  class RunResult {
    config
    extraction_rate : float
    metrics
    runtime_sec : float
  }
  class SARSA {
    update(s: int, a: int, r: float, s_next: int, a_next: int) None
  }
  class Side {
    name
  }
  class SimConfig {
    alpha : float
    batch_interval : int
    dt : float
    fee : float
    half_spread : float
    horizon : float
    initial_price : float
    jump_size : float
    lambda_jump : float
    mechanism : Literal['continuous', 'batch']
    n_periods : int
    noise_rate : float
    opp_cost : float
    se_mult : float
    seed : int
    sigma : float
  }
  class TrainResult {
    converged : bool
    periods_run : int
    policies : list
    policy_stable_at : int | None
  }
  class ZIPolicy {
    n_actions
    stream
    act(state: int, t: int) int
    frozen() 'ZIPolicy'
    greedy(state: int) int
    update(s, a, r, s_next, a_next)* None
  }
  class _Tabular {
    beta
    gamma
    lr
    n_actions
    q : ndarray
    stream
    act(state: int, t: int) int
    frozen() 'FixedPolicy'
    greedy(state: int) int
  }
  QLearner --|> _Tabular
  SARSA --|> _Tabular
  Order --> Side : side
  RunResult --> SimConfig : config
  RunResult --> Metrics : metrics
  LearnConfig --o MarketEnv : cfg
```
