# OSF registration form answers — density spoke (paste-ready)

## Open-Ended Registration: Summary（実際に使用したテンプレ）

> This registration freezes the interpretation rules for the "density spoke" experiment (Experiment B, portability audit of Calvano-type algorithmic collusion to sparse-reward market making) before any spoke results exist. The complete pre-registered rules — design (18 cells: 3 event-density × learning-rate points × 6 market-design conditions, 5 seeds each), mechanical certification criteria, headline-cell selection rule, degradation rules for the negative outcome, and disclosure of all data existing at registration time — are specified in the attached `prereg-density-spoke.md`, frozen at public git commit `3cad65f` (repository: github.com/yuitokyouni/ABM-Microstructure). The attached file is canonical; no spoke data have been generated. Certification will be the mechanical application of the analysis code at the pinned commit, with no post-hoc criterion adjustment.

---

以下は "OSF Preregistration" 詳細テンプレ用の全欄英文（未使用だが将来の P1 paper-grade
登録の雛形として保持）。

対応する凍結文書: `prereg-density-spoke.md`（git commit `3cad65f`）。本ファイルは OSF の
"OSF Preregistration" テンプレ各欄に貼る英文の記録（single source of truth）。
登録後、registration URL を `prereg-density-spoke.md` 冒頭に逆記入する。

---

## Study Information

**Title**
Certifiable algorithmic-collusion regimes in sparse-reward market making: the density-spoke experiment (portability audit of Calvano-type collusion, Experiment B).

**Research Questions**
Calvano et al. (2020, AER) showed Q-learning agents learn supra-competitive pricing in a Bertrand setting with dense, deterministic per-period rewards. Market making has sparse, high-variance rewards (fills are rare; sniping rarer). RQ: Does a certifiable (behavior-level) collusion regime exist for tabular Q-learning market makers in a realistic sparse-reward microstructure — and if so, where in event-density × learning-rate space?

**Hypotheses**
H1 (already observed in disclosed pilot data, baseline density): at baseline event density (per-period fill probability p≈0.01), neither policy-level (Calvano) nor behavior-level (greedy limit-cycle) convergence is reached within t_max = 2×10⁶ periods; certification is impossible there.
H2 (open): at elevated event density and reduced learning rate (ν=30, lr=0.02), the payoff-gap-to-Q-noise ratio (≈2.7 by pre-registered SNR arithmetic) makes limit-cycle convergence physically possible; whether cells certify is the open question. Both outcomes ("regime exists at specified cells" / "no certifiable regime within the tabular budget") are interpretable under the pre-specified degradation rules (Section: Analysis Plan).

## Design Plan

**Study type** — Simulation study (agent-based model of market microstructure). No human participants, no observational data.

**Blinding** — Not applicable (deterministic simulation).

**Study design**
18 cells = 3 (noise_rate ν, learning rate lr) points {(10, 0.02), (30, 0.02), (30, 0.15)} × 6 market-design conditions {continuous, batch interval 5, batch interval 20} × {committed quotes, revisable quotes}. All other parameters fixed at the pre-registered center cell (jump intensity λ=5, jump size J=1, fee=0, memory=1, n=2 market makers, tabular Q-learning). Horizon t_max = 2×10⁶ learning periods per run. The executable definition is `microstructure.designmap.density_spoke` at the pinned git commit; code is the canonical specification.

## Sampling Plan

**Existing data**
Registration prior to creation of the data analyzed here. Disclosed existing data (none of which are density-spoke results): (i) a 2-seed pilot at baseline density (all non-converged); (ii) a memory=0 sanity run at comparable dense settings (6/6 seeds converged; different state space, not part of this experiment); (iii) a 72-cell coarse map entirely at baseline density ν=1, disjoint from the spoke's ν∈{10,30}. The public git history (commit 3cad65f) freezes these rules prior to this registration.

**Data collection procedures**
Deterministic simulation: master seed spawns independent substreams (price, arrival, exploration); identical (config, seed) reproduces bit-identical trajectories. Runs execute under a pre-fixed compute-budget ledger that mechanically refuses over-budget runs.

**Sample size & rationale**
5 seeds per cell × 18 cells (≈1.8×10⁸ learning periods). The compute budget is pre-fixed (dense tier ≤ 1×10⁹ periods) to foreclose incremental expansion of the design space ("run a bit more" forbidden by ledger). Certification requires statistical significance of supra-Nash markup across the 5 seeds; all results reported as mean ± SE with n.

## Variables

**Manipulated**: noise arrival rate ν (event density); learning rate lr; matching mechanism (continuous vs batch, interval N); quote staleness regime (committed vs revisable — an ablation of the arbitrageur-predation channel).

**Measured**: markup of realized spread over the myopic-Nash (Glosten-Milgrom break-even) benchmark; extraction rate; convergence label under criterion v2 (greedy limit-cycle: deterministic policy probe every 10⁴ periods, 10 consecutive identical signatures); certification verdict (convergence + supra-Nash markup significance + impulse-response gate: deviation-punishment response); exit fraction (participation margin).

## Analysis Plan

**Inference criteria**
1. Cell certification is the mechanical application of `microstructure.verdict.certify` at the pinned commit; no manual re-judgment, no post-hoc criterion adjustment.
2. "A certifiable regime exists" ⟺ at least 1 of the 18 cells is certified.
3. Headline-cell selection rule (fixed to prevent cherry-picking): among certified cells, minimum ν (sparsest, closest to reality); ties broken by committed over revisable, then smaller batch interval.
4. Secondary (only if certification occurs): batch modulation attribution Δ_total / Δ_GP / Δ_pred via seed-paired differences with a ±2SE classification (promote / suppress / null).
5. Reporting: all metrics as seed-wise mean ± SE with n=5; no single-run numbers in the main text.

**Degradation rules (negative outcome)**
If zero cells certify, claim (ii) of the audit holds in its negative branch: no certifiable collusion regime exists within the tabular budget (t_max=2×10⁶, tabular Q/SARSA). The robustness tier is then re-allocated to verifying that non-convergence replicates across algorithms and hyperparameters — direct evidence for the audit claim.

**lr-contrast interpretation (fixed ex ante)**
(30, 0.02) certifies but (30, 0.15) does not → the sparse-reward obstacle is predominantly statistical (insufficient averaging). Both certify → density itself dominates. (10, 0.02) locates the regime boundary. Scope limit stated ex ante: this spoke cannot fully separate the statistical channel from the economic (Green-Porter imperfect-monitoring) channel, because reward density and monitoring-signal density co-move; no separation claim will be made.

**Data exclusion / missing data**
No exclusions; all 18 cells reported. Worker crashes are handled by deterministic rerun (bit-identical) with audited budget reconciliation.

## Other

Canonical detailed rules (Japanese) are in the attached `prereg-density-spoke.md`, frozen at public git commit `3cad65f` prior to this registration. Program context: this experiment is the primary result of P2 (portability audit) in a three-paper program (P1 mechanism-discrimination benchmark / P2 this audit / P3 LLM-ABM audit).
