# Specification Quality Checklist: 実験B — 学習 MM collusion harness

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-10
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — 言語/ライブラリ/コード構造の指定なし。「tabular Q-learning・ε-greedy・memory」は実装詳細ではなく**研究対象そのもの**（Calvano 同型の被検体定義。どの学習器で collusion が創発するかが問いの一部）であり、001 の GM/Budish 指定と同格のドメイン要件として記載
- [x] Focused on user value and business needs — 研究者の value（二力対決の帰着、設計マップ、認定済み collusion）に焦点
- [x] Written for non-technical stakeholders — 研究設計を読む者向け。機構/指標は ontology.md の語彙で記述
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — 0 件（一次ソース＝research-design §3/§4・finding 0001・constitution が判断を事前確定済み）
- [x] Requirements are testable and unambiguous — 各 FR は機械判定（認定 gate、floor 単調性、決定論、gate 違反ゼロ）まで落ちる
- [x] Success criteria are measurable — markup±SE、分類（促進/抑制/無影響）、条件数、seed 数、違反ゼロ
- [x] Success criteria are technology-agnostic — 測度と判定のみ。ツール/言語への言及なし
- [x] All acceptance scenarios are defined — US1–US4 各 2–4 本、null 結論経路を含む
- [x] Edge cases are identified — 非収束、tie-breaking、退出張り付き、探索ノイズ誤検出、非対称均衡、機構整合
- [x] Scope is clearly bounded — Fixed Invariants（constitution-locked）＋ FR-013 ＋ Out of Scope
- [x] Dependencies and assumptions identified — 001 license 前提、① σ>0 並走、B1/④ は plan で数値確定、C3 在庫除外

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria — FR ↔ US/SC が対応（FR-007↔US1/SC-001、FR-003↔US2/SC-003、FR-009/010↔US3/SC-004/005、FR-011↔US4/SC-007）
- [x] User scenarios cover primary flows — 創発→認定（MVP）→設計効果→地図→外部アンカーの主線
- [x] Feature meets measurable outcomes defined in Success Criteria — SC-001〜008 で全 US を被覆
- [x] No implementation details leak into specification — 上記注記のとおり被検体定義のみ

## Notes

- 設計上の選択は spec 内で確定済み: committed-quote=baseline / revisable=ablation（finding 0001）、markup 分母=myopic-Nash（A1）、認定 gate（A3×C2）、null in outcome space（②）。
- plan フェーズへの持ち越し（spec の不確定ではなくフェーズ分担）: 収束判定の具体値、tie-breaking 規則、compute 予算の数値（B1）、外部アンカー銘柄（④）、第 2 学習アルゴリズムの選定。
- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan` — 現状 incomplete なし。
