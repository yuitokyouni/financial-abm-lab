<!--
  unwind-tape / MEASUREMENT_SPEC — realized cost / shortfall 分解の測定系仕様
  本文(下記 v0.2)はユーザ確定の一次仕様。実装(scripts/shortfall_engine.py)は
  この spec と突合して整合を検証する。以後の変更は本ファイルに追記する。
-->

# MEASUREMENT_SPEC v0.2 — 測定系を2系統に分離(レビュー3点を反映)

## 系統A: 情報効果イベントスタディ(親レベル、既実装のまま変更なし)
- 対称窓 CAR[-1,+1], [0,+1] 等。day-1のリーク・先回りを含めて測る系統。
- 系統Bの分解には流用しない(価格の起点がP_refと1日ずれるため)。

## 系統B: shortfall分解(measurableな子legレベル、新規実装)
- P_ref = 親day0の前営業日終値(調整後)。IS_raw = ln(P_ref) - ln(P_exec)。正=コスト。
- 恒等分解(構成上厳密に成立): IS_raw = s1 + s2 + s3
  s1 = ln(P_ref) - ln(close[day0+a])        # 発表インパクト(前方窓。a=1既定、configで事前登録)
  s2 = ln(close[day0+a]) - ln(P_exec_ref)   # ドリフト(先回り売り・需給の居場所)
  s3 = ln(P_exec_ref) - ln(P_exec)          # 執行ギャップ(生の契約量)
- route別定義:
  - secondary_offering: P_exec_ref=条件決定日終値、P_exec=売出価格。s3=ディスカウント(生)
  - offauction_distribution: P_exec_ref=前日終値、P_exec=分売価格。s3=開示ディスカウント(生)
  - toSTNeT_3(応募): P_exec=約定値=前日終値 → s3≡0(構成上)。
    補助指標 aux_protection = ln(P_exec / open[trade_date])(正=市場より有利に執行。
    理想はVWAP比だが日次データではopenを代理に使う)、fill_ratio = 約定株数/上限株数を併記。
    exec_refがday0+aより前に来る即日型はstage分解せずIS_raw(≒0)+補助指標のみ(degenerate扱い)
  - open_market_sale / share_forward: measurable_flag=FALSE。親側(系統A)のみ。近似値の創作禁止
- 日付順序ガード: P_ref < day0+a <= exec_ref が崩れる行はstage分解をスキップしフラグを立てる

## TOPIX調整(系統B)
- totalレベルで一回: IS_adj = IS_raw - [ln(TOPIX@P_ref日) - ln(TOPIX@P_exec_ref日)]
- s3は同一時点の契約ギャップで市場時間を跨がないため生のまま
  (s1,s2を窓別調整しても合計は同値。実装はtotal減算を採用)
- 用途: IS_raw=セラーの実損(実務向け)、IS_adj=イベント間比較・回帰用。両方保存。
- route間比較はIS_adjで行う。s3単体の横比較は禁止(v0.1から変更なし)

## 新規列(legs側)
stage1_cost / stage2_cost / stage3_cost / IS_raw / IS_adj / aux_protection / fill_ratio / measurable_flag

## Nゲート(残差分析・Task D着手条件)
- 「30イベント」ではなく measurable execution legs >= 30、かつ主要route2系統以上で各10 leg以上
- Task A捕捉の無帰属プリント(超大口・分売)はtapeの行にしない。
  route別exec_gapの無条件分布(参照ベンチマーク)として別テーブルで活用する
- 依存(変更なし): G001-G007のdisclosure_time転記が全計算のday0を規定する。最優先

---

## 実装ノート(Claude, 2026-07-08 — 実装時の必須逸脱1点)

**価格基準は「調整後」ではなく「生(unadjusted)」を採用した。理由は正確性上の必然:**
系統Bは契約上の生価格(売出価格・分売価格・ToSTNeT約定値)を P_exec に使う。一方
J-Quants の調整後終値(`AdjC`)は将来の分割を遡及反映するため、イベント後に分割が
あった銘柄では `ln(AdjC_ref) − ln(生の売出価格)` に累積調整係数 `ln(f)` の定数バイアスが
乗る(例: Honda 7267 は 2023-10 に 1:3 分割済み → f=1/3、offering が 2024-07 で
分割後のため、調整後終値と生の売出価格を混ぜると s3 が約 −ln(3)≈−1.10 ずれ、
ディスカウントが壊滅的に誤る)。

系統Bの [P_ref → P_exec] 区間は offering で数営業日・ToSTNeT で当日と短く、**単一
イベント区間内に分割は入らない**ため、生終値(`C`)で通せば契約価格と整合し恒等分解も
閉じる。よって系統B全体を**生終値ベース**で実装した。系統A(長い CAR 窓・推定窓が
分割を跨ぎ得る)は従来どおり調整後(`AdjC`)のままで変更なし。

この逸脱は spec の「(調整後)」表記に対する訂正。次版で spec 本文を「生終値」に
改めるか、調整後を使うなら売出価格側も累積調整係数で補正する処理を足すか、要判断。
