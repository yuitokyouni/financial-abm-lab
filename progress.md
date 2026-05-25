# Current Progress — Scientific Validation Mode

## Summary

Measurement infrastructure repaired. **0 scientifically conclusive cells** —
all 6 JPX 2014 CI95 intervals cross zero, making sign matching statistically
indeterminate. Prior claims of SG/FW discriminating power (5/6 sign matches)
are withdrawn: p=0.109 (not significant at α=0.05), tick_size was inverted,
and path-averaging destroyed the measured quantities.

## Session 2026-05-26: Measurement Infrastructure Repair

### Committed changes:
1. **docs/AUDIT_REPORT.md** — Critical audit identifying 5 FATAL, 3 SERIOUS, 4 MODERATE issues
2. **FATAL-2 fix:** `per_path_facts=True` default in `run_cell()` and `run_tensor()` —
   prevents CLT from destroying fat_tails/kurtosis when averaging across paths
3. **FATAL-4 fix:** Tick size intervention now ratio-based (`baseline × tick_to/tick_from`)
   across all 5 adapters — JPX 2014 was applying 10x INCREASE instead of 10x DECREASE
4. **FATAL-5 fix:** `score_sign()` returns INCONCLUSIVE when empirical CI95 crosses zero;
   `binomial_sign_pvalue()` added for formal testing
5. **FINAL_REPORT.md updated** — prior discriminating power claims retracted, honest
   assessment of 0 conclusive cells

### Tests: 306 unit tests pass. Integration tests running.

### Current blockers:
- All 6 JPX 2014 ground truth CI95 intervals cross zero → 0 conclusive cells
- Need narrower CI95 (more stocks, longer windows, or higher-freq data)
- 4 ABMs structurally near-identical (FATAL-3 from audit, not yet addressed)

### Next steps:
- Verify integration tests pass with new defaults
- Consider multi-seed stability analysis
- FATAL-3 (ABM structural differentiation) is the largest remaining issue
  but requires significant model rewriting

## 科学的妥当性の自己評価

**科学的前進あり — ただし否定的方向。** 今回のセッションは「結果が科学的に有効だったか」ではなく
「計測器が壊れていた」ことを発見・修正した。これは地味だが本質的な前進:
1. 壊れた計測器で出した結果を主張するより、計測器を修正して「まだ結論が出せない」と
   正直に報告する方が科学的に価値がある
2. 0 conclusive cells は失敗ではなく、正直な現状認識
3. 修正方針（CI95を狭める、seed安定性テスト）が明確になった
