# YH011 — 値動きから AI トレーダー比率は推定できるか

Nakagawa, Hirano, Minami & Mizuta (2024, [arXiv:2409.12516]) の
「AI トレーダーを含む multi-agent 市場モデル → GARCH のミクロ的基礎付け」を
**逆向き**に使い、収益率から AI トレーダー比率 $p_2$ を推定できるかを検証する研究ライン。
BTC を対象データとする。

きっかけは X 上のやり取り(2026-08-21):

* [@blog_uki] — 論文は「AI Trader が増えたら値動きがどうなるか」であって、
  「値動きから AI Trader の割合を推定する」のは逆方向。追加の仮定が要る。
* [@_mhirano] — 「GARCH の推定が綺麗にできるなら AI Trader の割合の推定はできた気がする。
  ただ、問題は GARCH の推定が精度高くできないのがボトルネックで
  そっち向きの実証を諦めた記憶がある」

本ラインは (1) そのボトルネックの正体を測り、(2) GARCH を経由しない推定に置き換え、
(3) BTC に当てる前に**モデルがデータに届いているか**を検定する。

## 構成

```
specs/YH011_identification.md   同定可能性の解析(何が原理的に取れないか)
docs/YH011_findings.md          結果と結論                     ← 読むならここ
scripts/
  nh_model.py                   厳密な再帰の実装 + Theorem 4.1 の係数 + 定常性境界
  summaries.py                  sieve の stylized-fact battery + |r| 系形状統計量
  inference.py                  局所線形回帰調整つき ABC / Theorem 4.1 の閉形式反転
  fetch_btc.py                  Coinbase Exchange から BTC-USD ローソク足を取得
  btc_data.py                   テープのギャップを跨がない窓の切り出し
  run_identifiability.py        step 1: p2 は要約統計量に効いているか(最小検出差)
  run_estimators.py             step 2: 4 ルートの推定量を既知の真値で採点
  run_model_adequacy.py         step 3: BTC はモデルの到達可能集合の中にあるか
  run_memory_check.py           step 3b: 届かない理由 — ボラティリティ記憶
  run_btc.py                    step 4: ゲートを通った窓だけに推定を出す
results/                        各 step の JSON + ログ
data/                           BTC-USD 1h (Coinbase, 2016-01-01 以降)
```

## 再現

```
uv venv .venv && uv pip install --python .venv/bin/python numpy scipy arch
uv pip install --python .venv/bin/python -e /path/to/sieve

cd experiments/YH011/scripts
python nh_model.py                     # 論文 Table 1 の再現チェック
python fetch_btc.py --granularity 3600 --start 2016-01-01 --out ../data/btc_usd_1h.csv
python run_identifiability.py --n-paths 400
python run_estimators.py --n-bank 20000 --n-test 1500 --lengths 2000
python run_model_adequacy.py --n-draws 15000 --window 2000
python run_memory_check.py
python run_btc.py                      # step 3 のゲートを内蔵
```

## sieve の役割

sieve は「スコアを出さない」設計なので、ここでは**推定器ではなくゲートと計量**として使う:

* prespecified な stylized-fact metric 群を要約統計量として使う。全 metric が
  `scale_invariant=True` と宣言されており、これはモデルのスケール同変性
  (`specs/YH011_identification.md` §2a)が要求する条件そのもの。
* `known_blind_spots` が数値と一緒に運ばれる。たとえば `acf_abs_1` には
  「GARCH(1,1) で再現される。これが通っても機構については何も言えない」とある。
  AI 比率という**機構パラメータ**を推定しようとしている以上、必要な警告。
* 事前登録された固定セットなので、結果を見てから統計量を足せない。

sieve 側の変更は不要。本ラインは sieve を import する satellite。
