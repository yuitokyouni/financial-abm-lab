# YH006: Speculation Game on LOB — 実装仕様書 (PAMS API 詳細版)

## 0. 前提と position

Yuito は金融 ABM 論文の連番実装シリーズ YH001-YH005 を完了し、
現在 YH005_1 (Phase 1 済) と YH006 を並走させている。

- **YH005_1** (`experiments/YH005_1/`): Katahira & Chen 2019 arXiv:1909.03185
  の「3 層機構」(cognitive world / round-trip 制約 / dynamic wealth)
  を **aggregate-demand 世界で** 数値可視化する。5 figure が確定済。
- **YH006** (本仕様書の対象): YH005_1 Phase 1 の 5 figure を **LOB 世界
  (PAMS)** で再現し、どの機構が LOB 微視構造下で保存され、どれが壊れるか
  を切り分ける。

入試本番 2026/08、YH006 Lite 完成目標は 2026/06 末。
Full scope は YH006 Phase 2 以降 (入試後) に送る。

## 1. ゴール

YH005_1 Phase 1 の 5 figure を、LOB 版 3 条件で再現:

| Figure | YH005_1 対応 | Katahira 2019 論文2 |
|---|---|---|
| Fig A: Wealth の Pareto 分布 (Hill α) | results_wealth_pareto.png | Fig 4 |
| Fig B: Round-trip horizon 分布 (冪) | results_horizon_distribution.png | Fig 8 |
| Fig C: \|ΔG\| vs horizon 漏斗 (相関) | results_deltaG_vs_horizon.png | Fig 7 |
| Fig D: hold ratio (active/passive) | results_hold_ratio.png | Fig 10 |
| Fig E: large-order burst vs r(t) 同期 | results_order_size_time_series.png | Fig 2 |

4 条件比較:

| ID | 世界 | SG agents | wealth 分布 | 備考 |
|---|---|---|---|---|
| **C0** | aggregate-demand | N=1000 | Pareto (dynamic) | YH005_1 の既存 output を流用、再実行しない |
| **C1** | LOB (PAMS) | なし | — | FCN baseline のみ |
| **C2** | LOB (PAMS) | N=500 | 一様 | wealth heterogeneity 無し ablation |
| **C3** | LOB (PAMS) | N=500 | Pareto α=1.5 | **主実験** |

出力: 5 figure × 4 条件 = 20 panel 比較図 + 各 condition metrics JSON。

## 2. Scope

### 含む (YH006 Lite)
- PAMS 0.2.2 上で動く `SpeculationAgent(pams.agents.Agent)` 実装
- Pareto wealth 初期化 (agent 内で `self.prng.paretovariate(alpha)`)
- round-trip closing (成行 close)
- 5 figure 測定 (YH005_1 analysis を adapter 経由で流用)
- C1 / C2 / C3 を seed=777 で実行 → 20 panel 比較図
- parity テスト (同一 seed → 再現)
- C0 を比較図に並べるための YH005_1 output loader

### 含まない (Phase 2 以降)
- 100 trial 平均、parameter scan、指値 close、async wake-up
- Kyle's λ 等 LOB microstructure metrics
- 論文1 Fig 11/12/13
- MGDC、Self-organized SG

## 3. 科学的仕様

### 3.1 SG decision rule (YH005 からの継承)
YH005/YH005_1 で実装・検証済:
- M-digit quinary history H(t), base-5 (h ∈ {-2..+2}, digit = h+2)
- S 個の戦略テーブル ∈ {-1, 0, +1}, 形状 (S, 5^M)
- argmax G strategy 選択、tie-break は現 active 優先 → argmax 集合 uniform
- virtual round-trip: j ≠ j* の戦略で独立に open/close 追跡
- real round-trip: open で entry_price 固定、close で ΔG を G に加算
- bankruptcy: wealth < B で substitute (新 strategies + 新 wealth = ⌊B + U[0,100)⌋)

### 3.2 LOB への翻訳 (YH006 固有決定)

**(a) 認知世界**
- mid-price Δ を quantize: `h(t) = quantize(Δmid_t, C_ticks)` ∈ {-2..+2}
- `C_ticks = 3 × median(|Δmid|)` を C1 warm-up run で較正
- History H(t) は global quantity、全 SG agents で共有
  (PAMS Market の price_history を参照、各 agent は読み取り専用)
- Cognitive price `P(t) = Σ h(s)` を SpeculationAgent 内部で accumulate
- ΔG 計算は cognitive price ベース、mid-price は順序情報としてのみ使用

**(b) 連続時間翻訳**
- SG の離散 t = PAMS の tick-step
- PAMS の SequentialRunner が wake_interval=1 で全 SG agent を順次呼ぶ
- 全 SG agent が同じ step で同じ history を見る (YH005_1 の global history 仮定保存)

**(c) round-trip 成立**
- **成行のみ** (Phase 1): `kind=MARKET_ORDER` で open / close 両方
- partial fill: `min(entry_quantity, available_on_opposite_side)` で切る、
  partial 発生率を metrics に記録
- entry_quantity は open 時に `⌊wealth / B⌋` で固定、close で同量送る

**(d) wealth 意味論**
- `self.cash_amount` (PAMS 標準 attr) を SG の cash として扱う
- `self.asset_volumes[market_id]` を position として使う (sign = ±1, 値 = q_i)
- `wealth = cash_amount + asset_volumes * mid_price` (評価額)
- substitute 時: cash_amount を `int(B + prng.random() * 100)` に reset

**(e) C_ticks 較正手順**
1. C1 (SG なし) を 1 run, 5000 step 実行
2. mid-price の 1-step diff を取り median(|Δmid|) 計算
3. `C_ticks = 3 × median` で fix
4. `outputs/C_ticks_calibration.json` に記録、C2/C3 はこの値を読む

## 4. PAMS API 具体仕様 (実装時の直接参照)

### 4.1 継承元クラスと必須メソッド
```python
from pams.agents import Agent                       # base class
from pams.order import Order, Cancel, LIMIT_ORDER, MARKET_ORDER
from pams.market import Market
from pams.logs.base import Logger
```

`Agent` (pams/agents/base.py) の override 対象:
- `__init__(agent_id, prng, simulator, name, logger=None)` (line 32)
- `setup(settings, accessible_markets_ids, *args, **kwargs)` (line 73)
- `submit_orders(markets) -> List[Union[Order, Cancel]]` (line 213)

参考実装: `FCNAgent` (pams/agents/fcn_agent.py)
- `__init__` (line 46): `super().__init__(...)` を呼び instance attr 初期化
- `setup` (line 68): settings dict から値を読み、必要なら draw
- `submit_orders` (line 113): markets をループして submit_orders_by_market を呼ぶ委譲パターン
- `submit_orders_by_market(market)` (line 124): 1 市場分の決定ロジック

### 4.2 Runner と Logger
```python
from pams.runners import SequentialRunner
from pams.logs.market_step_loggers import MarketStepSaver

saver = MarketStepSaver()
runner = SequentialRunner(
    settings=config,
    prng=random.Random(777),
    logger=saver,
)
runner.main()

# 実行後に取り出す
for log in saver.market_step_logs:
    # log は dict:
    #   "market_time", "market_price", その他
    pass
```

### 4.3 Session 2-phase 構造 (CI2002 から流用)
```python
config = {
    "simulation": {
        "markets": ["Market"],
        "agents": ["FCNAgents", "SGAgents"],
        "sessions": [
            {   # warm-up
                "sessionName": 0,
                "iterationSteps": 500,
                "withOrderPlacement": True,
                "withOrderExecution": False,   # マッチング止めて板を暖める
                "withPrint": True,
                "hiFrequencySubmitRate": 1.0,
            },
            {   # main
                "sessionName": 1,
                "iterationSteps": 5000,
                "withOrderPlacement": True,
                "withOrderExecution": True,
                "withPrint": True,
            },
        ],
    },
    "Market": { "class": "Market", "tickSize": 0.01, "marketPrice": 100.0 },
    "FCNAgents": { ... },   # CI2002 と同形式、C1 の baseline として流用
    "SGAgents": {            # YH006 新規
        "class": "SpeculationAgent",
        "numAgents": 500,
        "markets": ["Market"],
        "cashAmount": 9,
        "assetVolume": 0,
        # SG 固有 (SpeculationAgent.setup が読む)
        "M": 5,
        "S": 2,
        "B": 9,
        "wealthMode": "pareto",      # "uniform" | "pareto"
        "paretoAlpha": 1.5,
        "paretoXmin": 9,
        "cTicks": 0.03,              # C1 較正後に埋める
    },
}
```

### 4.4 mid-price の取り出し
```python
market_price_dict = dict(sorted(map(
    lambda x: (x["market_time"], x["market_price"]),
    filter(lambda x: x["market_time"] >= 500, saver.market_step_logs)
)))
mid_prices = list(market_price_dict.values())
```
(`>= 500` は warm-up を捨てる閾値、session 0 の iterationSteps に合わせる)

### 4.5 Pareto wealth は agent 内で draw
```python
class SpeculationAgent(Agent):
    def setup(self, settings, accessible_markets_ids, *args, **kwargs):
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        mode = settings.get("wealthMode", "uniform")
        if mode == "pareto":
            alpha = settings.get("paretoAlpha", 1.5)
            xmin = settings.get("paretoXmin", 9)
            w = int(xmin * self.prng.paretovariate(alpha))
            self.cash_amount = w     # PAMS 標準 attr を上書き
        elif mode == "uniform":
            B = settings.get("B", 9)
            self.cash_amount = int(B + self.prng.random() * 100)
```

`self.prng` は Agent base が保持する `random.Random` instance (コンストラクタ
`prng` 引数から来る)。seed 固定で reproducible。PAMS に pareto 組み込みは無い
(`pams/utils/json_random.py` 確認済)。

## 5. 実装フェーズ

### Phase 0: 準備 (0.5 日)
- [x] PAMS sanity: CI2002.ipynb 完走、mid-price 取得 API 確認済
- [x] Agent / FCNAgent ソース読解、メソッド行番号特定済
- [x] Pareto の PAMS 対応状況確認 (組み込み無しで確定)

### Phase 1: SpeculationAgent 単体 (2-3 日)
- [ ] `speculation_agent.py`:
      Agent subclass 実装
      - __init__: instance attr (strategies, G, active_idx, position,
        entry_price_cognitive, entry_action, entry_quantity,
        virtual_position, virtual_entry_price, virtual_entry_action,
        P_cognitive, mu) 初期化
      - setup: config から読む + Pareto draw + strategies 初期化
      - submit_orders_by_market: decision → Order 生成
- [ ] `history_broadcast.py`:
      global history μ(t) を Market.price_history から都度計算する utility
      (class にせず function で書く、SpeculationAgent から直接呼ぶ)
- [ ] `configs/C1.py`, `C2.py`, `C3.py`: 各 3 条件の config dict 生成関数
- [ ] Smoke test: C3 を seed=777, iterationSteps=500 で回して例外なく完走

### Phase 2: 分析 adapter (1 日)
- [ ] `yh006_to_yh005_adapter.py`:
      PAMS 実行結果を YH005/simulate.py の返り dict 互換形式に変換
      - `prices`: mid-price time series (ndarray)
      - `log_returns`: np.diff(np.log(prices))
      - `round_trips`: SpeculationAgent が内部記録した round-trip events
        を dict of arrays に整形
      - `wealth_snapshots`: 特定 step での全 SG agent cash_amount + holding
      - `num_orders_by_size`: bucket 定義は YH005_1 同様 (Phase 1 は 50/100 閾値)
- [ ] 分析は repo 共通 `analysis/` から import:
      - `analysis.tail_exponent` (Hill α)
      - `analysis.volatility_clustering` (|r| ACF)
      - `analysis.stylized_facts` (CCDF, moments)
      新規に analysis 関数を書かない

### Phase 3: 実験と比較図 (1-2 日)
- [ ] `calibrate_c_ticks.py`: C1 を 5000 step 走らせて median|Δmid|×3 を出力
- [ ] `run_experiment.py`:
      C1 → (C_ticks 較正) → C2 → C3 を seed=777 で順次実行
      各 run の adapter 経由 dict を pickle 保存
- [ ] `load_C0.py`: YH005_1/outputs/phase1_metrics.json 読み込み
- [ ] `compare_figure.py`:
      5 figure × 4 条件 = 5×4 grid 比較図生成
      `outputs/yh006_comparison_5x4.png`
- [ ] `outputs/yh006_metrics.json`: C0-C3 全 metrics 集約

### Phase 4: parity / invariant テスト (0.5 日)
- [ ] `tests/test_parity.py`: seed=777, 42 で同一 seed の 2 連続実行が
      bit-一致 (mid_prices と round_trips 両方)
- [ ] `tests/test_roundtrip_invariants.py`:
      - open_filled_t < close_filled_t
      - entry_action ∈ {-1, +1}
      - entry_quantity_sent ≥ 1
      - close_quantity_sent == entry_quantity_sent
- [ ] `tests/test_wealth_conservation.py`:
      substitute 以外で全 agent cash 合計 + asset × mid が保存に近い
      (LOB には MM や value agent との資金やり取りがあるので厳密保存でない、
       SG agent 群内部では保存、という弱い不変量を確認)

## 6. ディレクトリ構成

```
experiments/YH006/
├── SPEC.md                       # 本ファイル
├── README.md                     # 実行手順 + 結果サマリ
├── speculation_agent.py          # Agent subclass
├── history_broadcast.py          # global history utility
├── yh006_to_yh005_adapter.py     # 分析層互換
├── calibrate_c_ticks.py
├── run_experiment.py             # メインエントリ
├── load_C0.py                    # YH005_1 output loader
├── compare_figure.py             # 比較図生成
├── configs/
│   ├── C1.py
│   ├── C2.py
│   └── C3.py
├── notebooks/
│   ├── CI2002.ipynb              # PAMS 参考 (凍結)
│   ├── 00_pams_sanity.ipynb
│   └── 01_exploration.ipynb
├── outputs/                      # git 管理外
│   ├── C_ticks_calibration.json
│   ├── C1_result.pkl
│   ├── C2_result.pkl
│   ├── C3_result.pkl
│   ├── yh006_metrics.json
│   └── yh006_comparison_5x4.png
└── tests/
    ├── test_parity.py
    ├── test_roundtrip_invariants.py
    └── test_wealth_conservation.py
```

## 7. 成功基準

### Must-pass
1. C1/C2/C3 が seed=777 で完走 (エラー無し、各 run < 30 min)
2. 5×4 = 20 panel 比較図が出力
3. parity テスト全通過 (同一 seed → bit-一致)
4. invariant テスト全通過

### Nice-to-have
5. C3 の Fig D で passive_hold > 0.15 (C0 = 0.251 の半分以上)
6. C3 の Fig B で round-trip median が 2-10 step
7. C2 vs C3 で Fig A (Pareto α) に明確な差

(5-7 は科学的 finding の判定用、結果がどう転んでも論文 material)

## 8. 参照ファイル

### YH005 (凍結、読み取り専用)
- `experiments/YH005/model.py`: Agent / run_reference 設計の原典
- `experiments/YH005/simulate.py`: 返り dict schema の原典

### YH005_1 (output を参照、touch 禁止)
- `experiments/YH005_1/phase1_mechanism_figures.py`: 5 figure 定義
- `experiments/YH005_1/outputs/phase1_metrics.json`: **C0 値の source**
- `experiments/YH005_1/results_*.png`: 比較図に embed

### 共通 analysis (repo 直下)
- `analysis/stylized_facts.py`
- `analysis/tail_exponent.py`
- `analysis/volatility_clustering.py`

### PAMS (外部参照、read-only)
- `~/Documents/GitHub/pams_reference/pams/agents/base.py`
- `~/Documents/GitHub/pams_reference/pams/agents/fcn_agent.py`
- `~/Documents/GitHub/pams_reference/pams/order.py`
- `~/Documents/GitHub/pams_reference/pams/market.py`

## 9. 制約と禁則

1. **YH005 / YH005_1 / repo 共通 analysis/ を touch しない**
2. **独自の stylized facts 関数を新規に書かない** (repo analysis/ から import)
3. **PAMS core に patch をあてない** (subclass + config のみ)
4. **LLM agent 要素禁止** (YH006 は rule-based のみ)
5. **ABIDES を使わない** (2025/6 archive、PAMS で完結)
6. **新規 Python パッケージの追加禁止** (pams/numpy/pandas/matplotlib/scipy のみ)
