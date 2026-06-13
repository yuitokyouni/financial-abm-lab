# CLAUDE.md — ABM-Microstructure / 標準事実のみ
<!-- このリポの「動かない事実」だけ。手順は skill、強制は hook、隔離は subagent。lint規則・コードスニペットは書かない。 -->

## What this is
市場微細構造の ABM。主成果物 = **Calvano 型アルゴ共謀の現実的 microstructure への移植可能性監査**（P2。目標文と主従は `docs/research-design.md` §9）。従 = 「連続マッチング vs batch auction」の latency-fairness × collusion-resistance 設計マップ。実験A（速度ベース抽出）は検証アンカー、実験B（学習 collusion）が本体。設計一次ソースは `docs/research-design.md`。研究プログラム全体（P1/P2/P3、claim-first ループ）= `../PROV-ABM-atlas/docs/program_claims_v1.md`。

## Stack / entrypoints
- 言語/環境: Python 3.13、依存は `uv`（`pip` も可）。numpy + pytest。ABM フレームワーク不使用。Node なし。
- 計画パッケージ: `src/microstructure`（M1 plan で確定、コードは未実装）。エントリ `microstructure.run(SimConfig) -> RunResult`。
- 構造図の対象: `ABM_PKG=src/microstructure`。
<!-- 実装が入ったら主要モジュールを file:line で指す。スニペットは貼らない。 -->

## Conventions
- spec → plan → tasks → implement の順（`/speckit-*`、ハイフン）。spec に無いものを勝手に作らない。
- 図は LLM に描かせず `scripts/generate_diagrams.sh` で決定論的に抽出する。
<!-- このリポ固有の規約だけ追記。一般論は書かない。 -->

## Where the truth lives
- spec: `specs/` および `.specify/memory/constitution.md`（Spec Kit 導入後）
- 用語: `ontology.md`
- 構造図: `docs/architecture.md`（commit ごとに自動再生成）
- 決定: `docs/adr/`
- 人間向け運用マニュアル: `obsidian_ABM_microstructure/00 claude engineering playbook.md.md`

## M1 Fixed Invariants（実験A harness — 実装で絶対に落とすな）
<!-- agent に実装を委ねる場合、spec を読まなくてもここで invariants が伝播するように手で焼いてある。 -->
- 市場オブジェクト = **CLOB/quoting-MM**、baseline **inventory-free**。pool 無し → **LVR は A で使わない**（算出不能）。
- competitive spread = arbitrageur 逆選択への **GM break-even**（monopoly spread にしない＝knot 違反）。逆選択源は **arbitrageur**（noise ではない）。
- **gate（原則I）**: anchor battery 合格まで実験B に進まない。許容は **tight な統計 consistency ＋ dt→0 収束**で、「緩い方」は使わない。
- anchor battery = **GM + Kyle λ + Budish + uniform-price clearing 単体テスト**（4層、sim と独立実装）。
- US3 は competitive で PnL ゼロ → **participation margin**（`f·noise量 − sniping − c`）で退出判定。
- arbitrageur = **1体**（monopolist sniper＝gross 抽出極限）。競争散逸は A scope 外。
- 詳細は `specs/001-exp-a-clob-harness/`（spec/plan/research/data-model/contracts）。

<!-- SPECKIT START -->
現在アクティブな feature: 実験B 学習 MM collusion harness。plan = `specs/002-exp-b-collusion-harness/plan.md`
（spec.md / research.md / data-model.md / contracts/learning-interface.md / quickstart.md。tasks は未生成 → `/speckit-tasks`）。
実験A（001、検証済・license 成立）: `specs/001-exp-a-clob-harness/`。
technologies・project structure・コマンドはここを読む。
<!-- SPECKIT END -->
