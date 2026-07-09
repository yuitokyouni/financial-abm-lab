<!--
  YH009 / CONTRIBUTION statement — 新規性の明文化と、以後の設計判断の参照点。
  凍結spec(MEASUREMENT_SPEC.md / BENCHMARK_SPEC.md)の定義は一切変更・再解釈しない。
  参照した方法論ノート: imported/PROV-ABM-atlas/docs/{prov_abm_design_notes, program_claims_v1,
    working_paper_identification_obstacle_v0}.md, CLAUDE.md。
  Simudyne監査のノート: リポジトリ内に該当ファイルなし(→ §未参照)。Simudyne記述は公開資料に限定。
-->

# YH009 Contribution Statement v1（2026-07-09）

研究ID **YH009** = 政策保有株処分の**吸収・ルーティングABM**(経験的イベントスタディ + ABM)。
本書は新規性を明文化し、**以後の全設計判断の参照点**にする。凍結spec を上位に置き、本書はそれと矛盾しない範囲でのみ主張する。

---

## 1. Contribution claim（1文）

> **本研究は、政策保有株処分の執行コストを、(a) 執行ベニュー(ルート)の選択を所与とせず最適化の結果として内生化し、(b) `disclosure_time` で day0 を規定した独自イベントテープ上の route別 `s1/s2/s3` 分布を経験的標的とし、(c) stylized-fact 適合ではなくルート選択という(準)介入への分布応答として捉える点で、既存の単一ベニュー価格形成モデル・最適執行・イベントスタディ誘導形のいずれとも異なる枠組みを与える。**

過大主張はしない(「世界初」等の形容は用いない)。足すのは上記 (a)(b)(c) の3点であり、それ以外(生成機構の同定、汎用性)は主張しない。

---

## 2. 差分表（研究対象 / 経験的標的データ / 識別戦略 × 比較対象）

各セル: 「相手が扱う範囲」→ 「**差**: YH009 との違い」。YH009 側の核は claim の (a)(b)(c)(変更禁止)。

| 次元 ＼ 比較対象 | Simudyne① LOB微細構造 | Simudyne② fire-sale/カスケード | 学術 fire-sale（GLT / Cont–Wagalath） | 最適執行（Almgren–Chriss） | ブロック・売出しディスカウント実証 |
|---|---|---|---|---|---|
| **研究対象** | lit 板の内生的価格形成・インパクト(単一/少数銘柄)。**差**: YH009は**立会外を含むルート選択を内生化**し、板を避ける執行を対象にする。 | バランスシート連鎖・追証起点の投げ売り伝播(機関間)。**差**: 起点は追証でなく**政策保有削減の意思決定**、対象は単一発行体の吸収。 | 保有共通性による fire-sale スピルオーバー/内生リスク(ネットワーク)。**差**: 横断スピルオーバーでなく**1イベントのルート選択と吸収**。 | 所与の板で執行スケジュールを最適化(インパクト対リスク)。**差**: スケジュールでなく**ルート(ベニュー)選択自体**を内生化。 | ブロック/売出しの価格反応(誘導形)。**差**: 反応の平均でなく**選択に条件付けたコスト分布の形**。 |
| **経験的標的データ** | stylized facts / ミリ秒板系列。**差**: `disclosure_time` で day0 を規定したテープ上の **route別 s1/s2/s3 分布**。 | BS/レバレッジ/資金調達パス(ストレスシナリオ)。**差**: 実イベントの route別実損分布(同左)。 | 保有・価格の横断/時系列(exposure)。**差**: 同左。 | 執行タイムスタンプ / VWAP。**差**: 執行だけでなく**発表(親)〜執行(子)を分けた**テープ。 | 公表イベント×株価反応(CAR)。**差**: CAR(= s1 側)に加え **s2/s3 と route・参加率で条件付けた分布**。 |
| **識別戦略** | SF 適合 / 系列マッチ。**差**: SF 適合でなく**ルート選択という(準)介入への分布応答**(PROV-ABM の立場と接続)。 | カスケード再現(閾値/伝播の当てはめ)。**差**: 介入応答による識別(同左)。 | 誘導形回帰 / エクスポージャ係数。**差**: 同左。 | 最適化解のモデル整合。**差**: 同左。 | 平均処理効果(誘導形イベントスタディ)。**差**: 平均でなく**分布の応答形** + ルート選択の内生化。 |

**方法論的接続(PROV-ABM)**: 「介入応答は stylized facts では分けられない機構を分ける」という Intervention Atlas / PROV-ABM の load-bearing 前提(`imported/PROV-ABM-atlas/CLAUDE.md`、`docs/working_paper_identification_obstacle_v0.md`)を、YH009 は**識別哲学として**借りる。ただし PROV-ABM の scope は「合成データ上で ground truth 既知のモデル間識別まで。実データからの機構同定は主張しない」(`program_claims_v1.md §0`)。YH009 は実データなので、この立場を**ルート選択を(準)介入とみなす拡張**として継承し、識別対象は生成機構でなく**条件付き分布の応答形**に留める(§4 と §末尾で明示)。

---

## 3. 退化経路（Degradation paths）— 不変条件

以下3つが揃うと本研究は既存の下位互換に退化する。設計判断のたびに照合する**不変条件**。

- **D1 — ルート選択の内生化を落とし単一ベニューに簡略化する**
  - 許容(一時): 初期プロトタイプで単一 route(例: `secondary_offering`)に絞って配管を通す。
  - 不可(恒久): ルート選択を外生固定したまま「コスト分布を説明した」と主張すること(差分表**研究対象**行の全列を毀損、C1/C4 の下位互換へ退化)。
- **D2 — イベントテープの N 不足を理由に汎用 stylized facts 適合へ回帰する**
  - 許容(一時): N ゲート未達の間、配管検証のため SF 的整合チェックを**補助的に**使う(主張には使わない)。
  - 不可(恒久): measurable legs の N を満たさぬまま SF 適合を**識別の主軸**に据えること(Simudyne① / PRISM の死因の再演、**識別戦略**行を毀損)。
- **D3 — 介入応答による検証を後回しにする**
  - 許容(一時): 初期は分布の**記述**(参照分布・route別 s3)を先に出し、応答検証を次段に置く。
  - 不可(恒久): 応答検証を実装せずに「識別した」と結論すること(誘導形イベントスタディ C5 と区別がつかなくなる)。

---

## 4. 正直性の但し書き

- **s2 の解釈限界**: 日次データで観測できるのは**価格ドリフトのみ**。先回り・ヘッジ・需要退避・インデックス調整の**メカニズム帰属は識別できない**。標的は「**参加率の関数としての分布の形**」であって、s2 に単一機構を割り当てない。これは PROV-ABM の「実データからの機構同定は非主張」(`program_claims_v1.md §0`)と整合する。
- **N ゲート未達の間は経験的主張をしない**: `measurable execution legs >= 30、かつ主要route 2系統以上で各 10 leg 以上`(`BENCHMARK_SPEC.md` §N ゲート)。未達の間は記述・配管のみ。
- **s3 の route 間単純比較は禁止**(spec 凍結、`MEASUREMENT_SPEC.md`)。route 間比較は `IS_adj` で行う。本書の主張(特に (c) の「分布の応答」)はこれと矛盾しない ── 応答は route を**条件**として扱い、s3 単体を route 横断で比較しない。
- **(要人間判断)** PROV-ABM の介入応答識別は synthetic・GT 既知のモデル対で確立された。YH009 は実データで、ルート選択を(準)介入とみなす**拡張**である。「識別」の語は**条件付き分布の応答形**に限定し、生成機構の同定には及ばない。この拡張の妥当性は末尾「spec 整合性の確認」に人間判断項として回す。

---

## 5. 運用チェックリスト（CLAUDE.md / HANDOFF.md 転記用）

```
【YH009 設計判断の3問】設計を変えるたびに問う:
 1. この変更は差分表(研究対象/標的データ/識別戦略)のどの行を毀損するか?
 2. 退化経路 D1(単一ベニュー化)/D2(SF回帰)/D3(応答検証後回し)のどれかに近づくか?
 3. 凍結spec(s1/s2/s3・IS_adj・Nゲート・s3のroute間比較禁止)と矛盾しないか?
 → いずれか YES なら「一時簡略化」と明示するか、設計を戻す。恒久化は不可。
```

---

## 参考文献（実在確認済み。書誌が不確かなものは [要確認]）

- Perold, A. F. (1988). "The Implementation Shortfall: Paper versus Reality." *Journal of Portfolio Management* 14(3). — 実装ショートフォールの起点。
- Almgren, R. & Chriss, N. (2000/2001). "Optimal Execution of Portfolio Transactions." *Journal of Risk* 3(2). — 最適執行(C4)。
- Almgren, R., Thum, C., Hauptmann, E. & Li, H. (2005). "Direct Estimation of Equity Market Impact." *Risk*. — 平方根インパクト則。
- Kraus, A. & Stoll, H. R. (1972). "Price Impacts of Block Trading on the New York Stock Exchange." *Journal of Finance* 27(3). — ブロック取引の価格インパクト(C5)。
- Scholes, M. (1972). "The Market for Securities: Substitution versus Price Pressure…" *Journal of Business* 45(2). — 価格圧力仮説(C5)。
- Mikkelson, W. H. & Partch, M. M. (1985). "Stock Price Effects and Costs of Secondary Distributions." *Journal of Financial Economics* 14(2). — 売出し(secondary distribution)の価格効果(C5)。
- Corwin, S. A. (2003). "The Determinants of Underpricing for Seasoned Equity Offerings." *Journal of Finance* 58(5). — SEO ディスカウント(C5)。
- Greenwood, R., Landier, A. & Thesmar, D. (2015). "Vulnerable Banks." *Journal of Financial Economics* 115(3). — fire-sale スピルオーバー(C3)。
- Cont, R. & Wagalath, L. (2016). "Fire Sales Forensics: Measuring Endogenous Risk." *Mathematical Finance* 26(4). — 内生リスク(C3)。
- Fagiolo, G., Moneta, A. & Windrum, P. (2007). "A Critical Guide to Empirical Validation of Agent-Based Models in Economics." *Computational Economics* 30(3). — ABM 検証方法論(PROV-ABM が接続)。
- 日本の持ち合い/政策保有株の解消に関する実証研究 — **[要確認]**(具体的な書誌を実装前に固定する。推測で引かない)。
- Simudyne(公開資料のみ): [Market Simulation Research](https://www.simudyne.com/resources/simudyne-research-on-market-simulation/)、[Agent-based Liquidity Risk Modelling](https://www.simudyne.com/resources/agent-based-liquidity-risk-modelling-for-financial-markets/)、[HKEX 事例](https://www.simudyne.com/resources/hkex/)。**商用製品の内部仕様は推測で書かない。**

---

## 未参照（該当ファイルなし）

- **Simudyne 監査のノート**: リポジトリ内に専用の監査ノートは**存在しない**。`imported/PROV-ABM-atlas/docs/prov_abm_design_notes.md §20` に「昇格させるのは Simudyne / Macrocosm 等でも構わない」という**一箇所の言及**があるのみ。よって Simudyne に関する本書の記述は§参考文献の**公開資料と本セッションの Web 調査に限定**し、内部仕様の推測はしない。

---

## spec 整合性の確認 / spec 矛盾の疑い（人間の判断に回す）

凍結 spec の定義(`s1/s2/s3`・`IS_raw/IS_adj`・N ゲート・`measurable_flag`・route 別定義・s3 route 間比較禁止)は**一切変更・再解釈していない**。現時点で**明確な矛盾は検出していない**。ただし人間判断が要る論点を2つ挙げる:

1. **層の区別(矛盾ではないが誤読注意)**: 凍結 spec は**測定層**で route を**所与**として route別に実損を測る。本 claim (a) は**説明層**で route 選択を**内生化**する。両者は矛盾せず、測定層の route別 s1/s2/s3 分布が説明層(ルート内生化 ABM)の**キャリブレーション標的**になる、という補完関係。設計時にこの層を混同しないこと。
2. **「識別」の語の射程(要確認)**: PROV-ABM の介入応答識別は synthetic・GT 既知で確立。YH009 は実データへの拡張であり、claim (c) の「識別」は**条件付き分布の応答形**に限る(生成機構の同定には及ばない)。この語法を承認するか、より弱い語(「特徴づけ」等)に置換するかは人間判断。
