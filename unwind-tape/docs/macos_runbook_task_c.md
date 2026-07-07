# Task C — macOS terminal runbook

Task B と同じスタイル。あなたの Mac で以下をコピペで実行してください。

---

## 前提

- macOS + Homebrew Python 3.11+
- J-Quants Light プラン契約済み (API キーまたは refresh token 発行済み)
- このリポの branch `claude/unwind-tape-data-foundation-0txm6z` を pull 済み

## 0. 依存を入れる

Task B で入れた `requests`, `openpyxl`, `PyYAML` に加えて `numpy`, `pandas`, `pytest` を追加:

```bash
cd path/to/financial-abm-lab
pip3 install --user numpy pandas pytest
```

## 1. 認証情報を環境変数に

J-Quants は 4 通りの認証パスに対応 (fetcher が自動判定、優先順位は上から):

```bash
# V2 (2025-12-22 以降の新規登録者はこれのみ発行される。ダッシュボードに
# 単一の「API キー」という文字列が1個だけ表示されているタイプ):
export JQUANTS_API_KEY="ここに値"

# 以下は V1 のみ (旧登録者向け):
# 推奨: refresh_token (ダッシュボードから発行、有効期間は約 1 週間)
# export JQUANTS_REFRESH_TOKEN="eyJ..."

# もしくは mail + password でログインさせる方式:
# export JQUANTS_MAIL="you@example.com"
# export JQUANTS_PASSWORD="xxxxx"

# もしくは id_token を直接 (最短 6 時間有効):
# export JQUANTS_ID_TOKEN="eyJ..."
```

**V2 API キー使用時の注意**: base_url は既定で V1 パス (`https://api.jquants.com/v1`) のままです。V2 キーで 404 が出た場合は `--base-url https://api.jquants.com/v2` を試してください:

```bash
python3 unwind-tape/scripts/jquants_fetch.py --base-url https://api.jquants.com/v2
```

シェルを閉じても残したいなら `~/.zshrc` などに `export` を書いておく。

## 2. 単体テストで engine の math を先に確認

price data を取る前に、CAR 計算ロジックが正しいことを合成データで検証:

```bash
python3 -m pytest unwind-tape/tests/test_car_engine.py -v
```

23 件全通過すればロジックは OK。

## 3. J-Quants から price data を取る

11 銘柄 × 4 年分 + TOPIX + trading_calendar + fins_statements + listed_info を fetch:

```bash
python3 unwind-tape/scripts/jquants_fetch.py
```

デフォルト:
- `--from-date 2022-07-01` (estimation window [-140,-21] backstop)
- `--to-date <today JST>`
- `--codes 6902 6201 7259 7267 8154 3950 4246 7974 4063 4062 2871`
- rate limit: 1.1 秒/コール (Light 60/min の余裕マージン)

初回は 15-20 分程度。冪等 (再実行で新規分だけ append)。

一部だけ再取得したいとき:
```bash
python3 unwind-tape/scripts/jquants_fetch.py --codes 7267        # Honda だけ
python3 unwind-tape/scripts/jquants_fetch.py --skip fins_statements listed_info
```

## 4. CAR engine を回す

```bash
python3 unwind-tape/scripts/car_engine.py
```

出力:
- `unwind-tape/data/parsed/tape/legs_computed.csv` — ADV20/60, market_cap 等
- `unwind-tape/data/parsed/tape/legs_car.csv` — 8 CAR 列
- `unwind-tape/data/parsed/tape/car_report.md` — サマリ + G004(Honda)/G008(Nintendo) 詳細

## 5. G004 / G008 の CAR を手計算と突合

`car_report.md` の下部に G004/G008 の詳細が出ています。この数字を手計算 (Excel + J-Quants 生 CSV) と突き合わせて一致することを確認。

不一致なら `unwind-tape/PREREG.md` の day 0 規則・estimation window を確認し、必要なら `unwind-tape/configs/car.yaml` を調整して再実行。

## 6. モデル切替

TOPIX 差分 (`topix_adjusted`) と market model (`market_model`) の両方が実装済み。config で切替:

```bash
# vim/nano で config を編集
vim unwind-tape/configs/car.yaml
# model.primary を 'topix_adjusted' → 'market_model' に変更、または逆

python3 unwind-tape/scripts/car_engine.py    # 再実行
```

**本採用の仕様は `unwind-tape/PREREG.md` に確定させてから運用してください。**

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| `authentication failed` | refresh_token 期限切れ | ダッシュボードで再発行、`export JQUANTS_REFRESH_TOKEN=...` |
| `HTTP 401` 途中で発生 | id_token が中で失効 | fetcher は自動で refresh するはず。再実行 |
| `HTTP 429` | rate limit 抵触 | fetcher は指数バックオフ retry。何度も出るなら `RATE_LIMIT_SLEEP_SEC` を 2.0 に上げる |
| TOPIX が空 | Free プランに落ちてる / V2 endpoint 名称違い | ダッシュボードでプラン確認、fetcher の topix path を `/indices/bars/daily/topix` に切替 |
| `market_cap` が NaN | /fins/statements の shares field が FY-end のみ | 想定内。R2 リスク。FY 末値 forward-fill で対応済み |
| ADV20 が NaN | estimation 前日の営業日データ不足 | `--from-date` を早めにして再 fetch |

---

## fetcher と engine の分離設計 (なぜこう分けたか)

- **fetcher (`jquants_fetch.py`)**: HTTP + jsonl 出力のみ。API 依存はここに閉じる。
- **engine (`car_engine.py`)**: jsonl を読んで CAR 計算。API 未接続でも CSV/jsonl があれば動く。
- **tests (`test_car_engine.py`)**: engine を合成データで検証。API 未接続で走る。

これにより:
- Light プラン期間中に全期間バックフィル → 解約 → 以後は engine だけ手元で回せる
- price data のスナップショットを保存しておけば再現性が担保される (raw jsonl + sha256)
