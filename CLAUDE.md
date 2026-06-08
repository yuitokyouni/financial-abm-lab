# CLAUDE.md — 真・PRISM toy + PROV-ABM/Atlas framework

このファイルは Claude Code に対するプロジェクト全体の orientation。新しい conversation でも毎回読まれる前提で書く。

---

## プロジェクトの一文目的

**Intervention Atlas / PROV-ABM(`docs/prov_abm_design_notes.md` 参照)の load-bearing な経験的前提——「介入応答は stylized facts では分けられない機構を分ける」——を、controlled toy experiment で検証する。**

検証のための toy 実装が、同時に将来構築する PROV-ABM(provenance/再現性 framework)と Intervention Atlas(機構弁別ベンチ)の **最初の dogfood** として走る。

最終的な deliverable は framework(検証ツール)だが、**本 repo の v0 では toy 実験の完遂を最優先する**。framework は toy が必要とする分だけ最小で育てる。

---

## 戦略フレーム(コードを書く前に読め)

二アーティファクト構成で adoption physics が**別**(`prov_abm_design_notes.md §1.3` 参照):

- **Intervention Atlas**(楔/wedge): 機構弁別ベンチ。bottom-up、low-friction、maximally open。
- **PROV-ABM**(土台/foundation): provenance/再現性 spec。top-down、trust-required、heavyweight。

**両者を誤って coupling すると両方死ぬ**(設計ノート §1.3)。本 repo では両者をパッケージとして分離し、toy はその両方の最初のユーザーとして動く。

検証する経験的前提(`prov_abm_design_notes.md §2.5`): 介入応答が SF より機構を弁別できるか。これが **collapse するなら Atlas の楔に edge は無い**。本 toy はこの命題を決着させる。

---

## スコープ規律(これを守れ)

| 領域 | v0 で実装する | v0 で touch しない |
|------|----------|---------------|
| Toy experiment | 完全実装。`docs/experimental_design_v0.2.md` を pre-registered spec として扱う | 判定基準の post-hoc 修正 |
| PROV-ABM | L2 capture(`ctx.*` API、reported reach、最低限の seed/config/output 記録) | L3+ AST whitelist、taint、validator strict 拒否ロジック、may\\must gap 計算、Lean 形式化 |
| Atlas | Battery/Mechanism/Response の抽象 protocol scaffold(空 class、type hint のみ) | 実際の battery 実装、leaderboard infrastructure、scoring 機構、Type2 survival test |

**Type1 (auditability/hygiene、GT-free) のみ。Type2 (SME 許容境界、参照を裏口から要求) は明示的にスコープ外**(設計ノート §2.2)。

**反パターン**: framework を綺麗に作り込んで toy がそれに合わせる順序。**禁止**。逆方向だけ採る: toy のニーズに合わせて framework が最小限育つ。toy が動かない framework は無価値。

---

## アーキテクチャ

```
real-prism/
├── CLAUDE.md                  # 本書
├── README.md
├── LICENSE                    # MIT
├── pyproject.toml             # uv で管理、Python 3.11+
├── .github/workflows/         # CI(pytest + ruff + mypy)
├── .pre-commit-config.yaml
├── docs/
│   ├── experimental_design_v0.2.md   # pre-registered spec(§2/§14 post-hoc 変更禁止)
│   └── prov_abm_design_notes.md      # PROV-ABM/Atlas 設計ノート
├── provabm/                   # framework パッケージ
│   ├── __init__.py
│   ├── ctx.py                 # ctx.observe / read_own_state / random / submit_order
│   ├── capture.py             # capture level L0-L2(L3+ は protocol stub のみ)
│   ├── reach.py               # reported reach のみ実装。may/must/exact は Enum + raise NotImplementedError
│   ├── validator.py           # claim↔reach の最小強制(reported からの invariance/counterfactual claim を reject する)
│   └── provenance.py          # seed/config/output digest、Hydra 連携、prov.json 出力
├── atlas/                     # ベンチマーク format scaffold
│   ├── __init__.py
│   ├── protocols.py           # Battery, Mechanism, Response 抽象 protocol
│   └── README.md              # 「format scaffold のみ、実装は将来」と明記
├── toy/                       # 真・PRISM toy 実験本体
│   ├── __init__.py
│   ├── market.py              # 単一資産市場、excess demand 価格更新、Numba 最適化
│   ├── agents/
│   │   ├── base.py            # Agent 抽象、ctx 強制
│   │   ├── trend.py           # Model T (trend-following)
│   │   └── herd.py            # Model H (herding)
│   ├── observation.py         # 観測ベクトル構築 + B2 masking schemes (a-d)
│   ├── sf_battery.py          # SF1-SF6 測定
│   ├── calibration.py         # SF-等価 grid search / BO(留保 1/2 解決後に full 実装)
│   ├── classifiers.py         # SF classifier (LR + 1D-CNN)、IR classifier (XGBoost)
│   ├── intervention.py        # B2 介入 4 scheme 実装
│   └── analysis.py            # response curve、susceptibility 特徴抽出
├── experiments/
│   ├── conf/                  # Hydra config
│   │   ├── config.yaml
│   │   ├── market/default.yaml
│   │   ├── agents/{T,H}.yaml
│   │   ├── intervention/{a,b,c,d}.yaml
│   │   └── classifier/{sf_lr,sf_cnn,ir_xgb}.yaml
│   ├── Snakefile              # 全 sweep の DAG
│   └── runners/
├── tests/
│   ├── unit/
│   ├── property/              # Hypothesis、ctx 不変条件 / reach 性質
│   └── integration/           # toy end-to-end smoke
└── scripts/
    └── reproduce.sh           # 公開時の bit-reproduction エントリ
```

---

## 技術選択

- **Python 3.11+** 主言語
- **uv** package manager(決定的 resolve、`uv.lock` を commit)
- **Numba** for `toy/market.py` hot loop(1 run 0.5 秒目標)
- **Hydra** config composition
- **Snakemake** workflow DAG
- **PyTorch** 1D-CNN discriminator
- **XGBoost** IR classifier
- **arch** GARCH 推定、**statsmodels** for ACF
- **Hypothesis** property tests(特に reach/validator)
- **pytest**, **ruff**, **mypy --strict**, **black**
- **pre-commit** で全 lint を gate

---

## Provenance 要件(L2 minimum)

各 simulation run は以下を必ず吐く:

```json
{
  "uuid": "uuid7-string",
  "git_commit": "abc123...",
  "config_hash": "sha256-of-resolved-config",
  "config_yaml": "<resolved Hydra config>",
  "seed": {"numpy": ..., "python": ..., "torch": ...},
  "env": {"python_version": "...", "pip_freeze_sha256": "..."},
  "started_at_utc": "2026-06-05T...",
  "completed_at_utc": "...",
  "output_sha256": "...",
  "ctx_log_path": "relative/path/to/ctx_log.parquet",
  "reach_claim": "reported"
}
```

`reach_claim` field は将来 `may`/`must`/`exact` に拡張可能な Enum にしておく。v0 では `reported` のみ受け付け、それ以外を `validator.py` は reject する。

`ctx` 経由でない RNG (素の `np.random`、`random.random()` 等) の使用を整合性 lint で警告する(L2 でも honest 性確保のため。AST whitelist は L3 まで持ち越し)。

---

## 命名規約

- すべての simulation run に **UUID v7** を付与(時刻順 sort 可能)
- 出力ファイル: `{config_hash[:12]}_{seed}_{uuid7}.parquet`
- Provenance metadata: `{output_basename}.prov.json`
- branch 戦略: `main` + feature branch、`main` は常に green CI
- commit message: Conventional Commits

---

## 事前登録(pre-registered)制約

`docs/experimental_design_v0.2.md` の **§2(仮説と判定基準)と §14(decision tree)は post-hoc 変更禁止**。

実装中に「この基準は厳しすぎる/緩すぎる」「サンプルサイズを減らせば速い」と気づいても、勝手に動かすな。**Issue を立てて Yuito の判断を仰げ。** これが pre-registration の核心で、ここを緩めると本 repo の価値が消える。

---

## 留保 1/2(解決済み・v0.2)

`docs/experimental_design_v0.2.md` で留保 1/2 を default で解決済み(2026-06-08 Yuito confirm)。

- **留保 1 → 相互等価性 anchor**: Model T を固定点 T* に置き、Model H を SF1-4 距離最小化で calibrate。実データ(S&P500)参照は外す(spec §5.2)。
- **留保 2 → SF1-4 を calibration target、SF5/6 を post-equivalence 独立検証量**(spec §4 末尾・§5.1・§6.1。SF classifier 入力は SF1-4 の 4 次元)。

これで `toy/sf_battery.py`(SF1-6 測定、spec §4)と `toy/calibration.py`(Stage 1-3、spec §5.2)の本体実装が unblock された。

**ただし留保の substance(T* の具体固定値、Model H 探索空間、SF5/6 verification の妥当性)は別途議論予定で未確定。** spec §4-§6 に「v0.2 暫定」として inline マーク済み。変更が生じたら **v0.3 として versioned に切り直す**(post-hoc サイレント編集は禁止)。実装は v0.2 の確定部分に沿って進め、暫定部分に依存する箇所は議論確定を待つ。

---

## 反パターン(踏むな)

1. **Rigor trap**: framework の「綺麗な部分」(validator の formal semantics、reach の完全実装、Lean 形式化、may\\must gap 計算)に時間を吸われる癖。設計ノート §1.4 が警告している通り、本 repo では toy が動くことが至上、framework は toy が要求する分だけ。
2. **Framework-first 順序**: 「先に framework を綺麗に作ってから toy を載せる」禁止。toy と framework は並列で最小実装を出す。toy が動いてから framework を refactor。
3. **設計と実装の同時走り**: 留保が残ったまま該当箇所の実装に入らない。判断確定後に実装する。
4. **PROV-ABM/Atlas を本気で完成させようとする**: 本 repo は dogfood seed であって framework 完成形ではない。L2 で足りる、Atlas は protocol のみ。
5. **「ついでに」拡張**: 「Atlas の leaderboard 試しに作ってみよう」「validator も書いちゃおう」禁止。スコープ規律表を厳守。
6. **テスト後回し**: 各モジュールに対応する test を最初から書く。特に `ctx` API の不変条件は property test で固める。
7. **Type2 survival test の混入**: SME 許容境界 / SME 期待値との比較 / 「現実から離れすぎてないか」のチェックは v0 では一切やらない(設計ノート §2.2 参照)。Type1(hygiene、reachability、reproducibility)のみ。

---

## マイルストーン

| Week | Deliverable | gate |
|------|-------------|------|
| 1 | repo skeleton、provabm L2 minimum、market core、Model T/H stub、CI green | smoke test pass |
| 2 | SF battery 実装、calibration scaffold(留保解決後に本体実装) | SF1-SF6 が単体で動く |
| 3 | SF classifier(LR + 1D-CNN)、等価性検証、null layer 1 (T1 vs T1 異 seed) | null layer 1 が 50% を返す |
| 4 | 介入 4 scheme + observation masking 実装 | 各 scheme で θ sweep が回る |
| 5 | response curve sweep + susceptibility 特徴抽出 | susceptibility data が parquet で出る |
| 6 | IR classifier、null layer 2(T1 vs T2)、主結果集計 | decision tree §14 が機械評価できる |
| 7-8 | robustness check、解釈、writeup draft | reviewable draft |

---

## 進行ルール

- Issue/PR ベースで進める。直 `main` push 禁止。
- Yuito の確認が必要な判断ポイントは GitHub Issue を立てて待つ。勝手に進めない。
- 留保が残ってる領域の関数は `raise NotImplementedError("awaiting v0.2: 留保 N decision")` で明示。
- 各 PR の description には「(a) 実装スコープ、(b) 設計 spec のどこに対応するか、(c) 残った TODO」を書く。
- design 仕様と実装が乖離したら spec を更新する(逆ではない)。spec が ground truth。

---

## 参考文献

- `docs/experimental_design_v0.2.md` — pre-registered 実験設計
- `docs/prov_abm_design_notes.md` — PROV-ABM / Atlas 戦略・設計ノート
- 学術文献は `docs/experimental_design_v0.2.md` の Appendix C