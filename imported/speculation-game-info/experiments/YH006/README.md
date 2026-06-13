# YH006: Speculation Game on LOB (PAMS)

Katahira-Chen 2019 Speculation Game (SG) decision rule を PAMS 0.2.2
(Hirano-Izumi 2023) の tick-scale LOB 環境に移植する。YH005_1 Phase 1 の 5
figure を LOB 世界で再現し、どの機構が LOB 微視構造下で保存され、どれが
壊れるかを切り分ける。

詳細仕様: [`SPEC.md`](SPEC.md)

## Conditions — 2×2 (world × wealth), N=100 固定

|  | uniform init | Pareto α=1.5 init |
|---|---|---|
| **aggregate-demand** | **C0u** (N=100) | **C0p** (N=100) |
| **LOB (PAMS)** | **C2** (N=100) | **C3** (N=100, 主実験) |

LOB 側には更に流動性 null として **C1** (FCN baseline, SG なし) を併走。

Reference (2×2 には含めない、N scaling 補遺):
- 旧 C0: N=1000 aggregate-demand uniform (YH005_1 output, 有限サイズ効果の基準)

## Layout

- `SPEC.md` — 実装仕様書 (PAMS API 詳細含む)
- `speculation_agent.py` — SG decision rule を `pams.agents.Agent` subclass 化
- `history_broadcast.py` — 全 SG agent で共有する cognitive history μ(t)
- `configs/` — C1/C2/C3 の config dict 生成関数
- `yh006_to_yh005_adapter.py` — PAMS 結果を YH005 互換 dict に変換
- `calibrate_c_ticks.py` — C1 から C_ticks=3×median|Δmid| を較正
- `run_experiment.py` — C1/C2/C3 の主実行エントリ (LOB 側)
- `aggregate_sim.py` — aggregate-demand SG simulator (YH005 simulate の
  YH006 local fork、`wealth_mode` ∈ {uniform, pareto} 対応。uniform は
  YH005 simulate と同 seed で bit-一致)
- `run_aggregate_c0.py` — N=100 の C0u / C0p を生成 (2×2 aggregate 側)
- `compare_figure.py` — 5 figure × 4 condition (2×2) の比較図生成
- `load_c0.py` — C0u / C0p / 旧 C0 (N=1000 reference) の metrics loader
- `smoke_test.py` — 縮小版 C3 で agent wiring sanity
- `tests/` — parity / roundtrip invariants / wealth conservation
- `outputs/` — 実験成果物 (git 管理外)

## 再現手順

```bash
cd experiments/
# 1) C_ticks calibration (C1 を走らせて median|Δmid|×3 を算出)
.venv/bin/python -u YH006/calibrate_c_ticks.py
# outputs/C_ticks_calibration.json が出来る

# 2) C1/C2/C3 を順次実行 (LOB 側)
.venv/bin/python -u YH006/run_experiment.py \
    --num-fcn 30 --num-sg 100 \
    --warmup 200 --main 1500 \
    --max-normal-orders 500
# outputs/C{1,2,3}_result.pkl

# 2b) C0u / C0p を N=100 で生成 (aggregate-demand 側)
.venv/bin/python -u YH006/run_aggregate_c0.py
# outputs/c0u_metrics.json, outputs/c0p_metrics.json + 5×2 figure

# 3) 比較図 (2×2 + 5 列 + N scaling 補遺) + metrics JSON
.venv/bin/python -u YH006/compare_figure.py
# outputs/yh006_comparison_2x2.png, yh006_comparison_5col.png,
# outputs/yh006_appendix_N_scaling.png, yh006_metrics.json

# 4) 検証
.venv/bin/python -u YH006/tests/test_aggregate_parity.py
.venv/bin/python -u YH006/tests/test_parity.py
.venv/bin/python -u YH006/tests/test_roundtrip_invariants.py
.venv/bin/python -u YH006/tests/test_wealth_conservation.py
```

## Phase 1 実行結果 (seed=777)

### 2×2 結果 (world × wealth, N=100 統一)

LOB 側: 30 FCN + 100 SG × (warmup 200, main 1500), c_ticks ≈ 28.0 tick。
aggregate 側: 100 SG × T=50000 (`run_aggregate_c0.py`, runtime 各 ~30 s)。

| metric | **C0u** agg×uni | **C0p** agg×Par | **C2** LOB×uni | **C3** LOB×Par | C1 null |
|---|---:|---:|---:|---:|---:|
| num_round_trips | 1,041,712 | 1,049,903 | 879 | 1,080 | 0 |
| median horizon | 2.0 | 2.0 | 2.0 | 2.0 | — |
| mean horizon | 3.30 | 3.27 | 3.26 | 3.37 | — |
| max horizon | 151 | 125 | 36 | 33 | — |
| α_hill (wealth p90) | 3.910 | 4.068 | 1.98 | 1.91 | — |
| median wealth | 26.5 | 27.0 | 49 | 32 | — |
| corr(\|ΔG\|, horizon) | 0.353 | 0.347 | 0.61 | 0.33 | — |
| active_hold | 0.234 | 0.232 | 0.324 | 0.327 | 0 |
| passive_hold | 0.246 | 0.244 | 0.353 | 0.330 | 0 |
| idle | 0.104 | 0.104 | 0.004 | 0.005 | — |
| num_substitutions | 10,708 | 10,744 | — | — | — |

α_hill の tail サンプル数 n_tail=10 (xmin=p90 規約)、点推定の誤差は大きい。
有意性は Phase 2 で 100 trial bootstrap CI を取るまで保留 (本節の差は方向性の指標として読む)。

#### (i) 純効果 — wealth 軸 (uniform → Pareto、同 world)

| metric | aggregate: C0p − C0u | LOB: C3 − C2 |
|---|---:|---:|
| num_round_trips | +8,191 (+0.8 %) | +201 (+23 %) |
| α_hill | +0.16 | −0.07 |
| corr(\|ΔG\|, h) | **−0.006** | **−0.28** |
| passive_hold | −0.002 | −0.023 |
| median_wealth | +0.5 | −17 |

aggregate 世界では初期 wealth 分布は metric をほぼ動かさない (差はいずれも < 5 %)。
SG の `substitute` による turnover が初期条件を洗い流し、定常分布が走り勝つため。
LOB 世界では同じ Pareto 初期化が corr を約半減 (0.61 → 0.33)、median_wealth を 1/3 圧縮。
LOB の方が初期 wealth が持続する → dynamic-wealth turnover が弱い、と読める。

#### (ii) 純効果 — world 軸 (aggregate → LOB、同 wealth)

| metric | uniform: C2 − C0u | Pareto: C3 − C0p |
|---|---:|---:|
| num_round_trips | −1,040,833 (÷ 1183) | −1,048,823 (÷ 972) |
| α_hill | **−1.93** | **−2.16** |
| corr(\|ΔG\|, h) | +0.26 | −0.02 |
| passive_hold | +0.107 | +0.086 |
| active_hold | +0.090 | +0.095 |

World 効果は wealth 効果に対し 1 桁以上大きい。
特に num_round_trips の 10³ 倍減と α_hill の −2 は LOB friction の基本 signature。
passive/active_hold が +0.09 ほど共に増えるのは「SG が約定できず holding に追い込まれる」LOB 固有挙動。

#### (iii) 交互作用 = (LOB Pareto 効果) − (aggregate Pareto 効果)

| metric | (C3 − C2) − (C0p − C0u) | 判定 |
|---|---:|---|
| α_hill | −0.23 | tail 推定誤差 (n_tail=10) と同程度、判断保留 |
| corr(\|ΔG\|, h) | **−0.27** | **明瞭な交互作用**: aggregate で robust、LOB で破壊 |
| passive_hold | −0.021 | 小 |
| active_hold | +0.005 | ゼロ付近 |

最も鮮明なのは corr(\|ΔG\|, horizon) の交互作用 −0.27。
**「funnel 構造」(YH005_1 Phase 1 の主結果) は aggregate 世界では Pareto 初期化に対し
robust (0.353 → 0.347)、LOB 世界では Pareto 初期化で大きく劣化する (0.61 → 0.33)。**
つまり LOB は dynamic-wealth layer の自己組織化を弱め、初期 wealth heterogeneity を
funnel 形成の妨げに変換している。Phase 2 で bootstrap CI を取るまで定量的有意性は
保留するが、方向性は再現可能 (seed 固定で reproducible)。

### N scaling 補遺 (本論 2×2 から分離)

旧 C0 (N=1000, aggregate, uniform, YH005_1 output) と本 C0u (N=100, 同左) を比較すると:

| metric | 旧 C0 (N=1000) | C0u (N=100) | Δ |
|---|---:|---:|---:|
| α_hill (p90) | 2.54 | 3.910 | +1.37 (N 縮小で tail 推定精度が落ちる) |
| corr(\|ΔG\|, h) | 0.42 | 0.353 | −0.07 |
| passive_hold | 0.251 | 0.246 | **−0.005 (N 不変)** |
| active_hold | 0.237 | 0.234 | **−0.003 (N 不変)** |
| median_wealth | 31 | 26.5 | −4.5 |

**hold ratio は N 不変** (N 1000→100 で差 < 0.01)、よって pre-2×2 で報告した
「passive_hold が LOB で 0.25 → 0.33 に増える」は依然として正当。
一方 **α_hill の LOB 低下は N=1000→100 の confound で過大評価されていた**:
旧表 2.54 → 1.98 = −0.56 → 真の LOB 効果 (N=100 同士) は 3.91 → 1.98 = **−1.93** で約 3.4 倍。
**N を揃えなければ α 比較は意味がない、という finding 自体が論文材料**。

<details>
<summary>pre-2×2 の旧表 (N=1000 C0 と N=100 C2/C3 の混成、上記 2×2 に置き換え済)</summary>

| metric | C0 ref (N=1000) | C1 | C2 (N=100) | C3 (N=100) |
|---|---:|---:|---:|---:|
| num_round_trips | 10,419,681 | 0 | 879 | 1,080 |
| α_hill (p90) | 2.54 | — | 1.98 | 1.91 |
| corr(\|ΔG\|, h) | 0.42 | — | 0.61 | 0.33 |
| passive_hold | 0.251 | 0 | 0.353 | 0.330 |

</details>

### Limitations

- **N=100 ⇒ σ 大**: 単一 trial、特に Hill α は xmin=p90 規約で n_tail=10、
  点推定の標準誤差は ~α/√n ≈ 1.2 程度。本節の数値差はあくまで方向性。
  **bootstrap CI と 100 trial ensemble 平均は Phase 2 で取る**。
- **N の confound 解消**: 2×2 を全て N=100 で揃えたので、旧 N=1000 C0 vs
  N=100 C2/C3 で抱えていた「N 効果と LOB 効果の分離不能」問題は除去済。
- **substitute dynamics の収束時間**: dynamic-wealth layer の自己組織化は
  T 依存だが N にも依存しうる (N=100 では substitute イベントの空間混合が
  N=1000 より粗い)。本節の corr / α_hill の N 不変性は T=50000 での観察値で、
  T 短化や別 N で再現するかは Phase 2 で確認。
- **LOB artifact (Phase 1 既知)**:
  - zero-fill open 率 ≈ 30 % (流動性不足で不一致)。LIMIT_ORDER (mid±10 %, ttl=3)
    で置換し book O(N²) 経路は回避済。
  - `lob_mtm` (PAMS cash + asset × price) は ±数千ドルに分散。これは SG sizing
    q=⌊w/B⌋ が cost basis を LOB 単位で負にする artifact、`sg_wealth` (cognitive)
    とは分離して追跡。
- **MMFCNAgent の order_volume=30**: pams 0.2.2 の `FCNAgent.submit_orders_by_market`
  が order_volume=1 ハードコードしている問題への structural workaround。
  「外部流動性条件」として spec 化しているが、本値が結果に与える sensitivity は
  Phase 2 で scan 要 (現状は 1 点のみ)。

**実行時間** (Apple Silicon, single thread):
C0u 30 s + C0p 31 s + C1 56 s + C2 13 s + C3 15 s ≈ 2.4 分 (c_ticks 較正別途 55 s)。
Smoke test 0.5 s。全 test < 30 s (parity 9 件含む)。

## 検証 (全 pass)

- `test_parity.py`: seed 固定で bit 一致 (LOB 側、PAMS runner)
- `test_aggregate_parity.py`: aggregate_sim uniform モード × 4 seeds で
  YH005 simulate と bit-一致 / Pareto モード × 2 seeds で determinism /
  uniform vs Pareto × 3 seeds で divergence (計 9 件、`pytest -v` で 19 s)
- `test_roundtrip_invariants.py`: open_t < close_t, entry_action ∈ {±1},
  entry_quantity ≥ 1, delta_G ↔ cognitive_prices 再構成一致
- `test_wealth_conservation.py`: sg_wealth ≥ 0 かつ有界

## 参照

- YH005: `../YH005/` — aggregate-demand baseline 実装の原典 (`aggregate_sim.py`
  は YH005 simulate の YH006-local fork、uniform モードで bit-parity)
- YH005_1: `../YH005_1/outputs/phase1_metrics.json` — N=1000 reference row の source
- 共通 analysis: `../../analysis/` — stylized facts 計算群 (tail_exponent 等)
- PAMS: https://github.com/masanorihirano/pams
- Katahira & Chen 2019: https://arxiv.org/abs/1909.03185
