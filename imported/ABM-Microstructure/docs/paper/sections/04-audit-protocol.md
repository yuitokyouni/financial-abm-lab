# §4 The audit protocol — draft v1 (2026-06-12)

<!-- 本文化第1弾。出典: finding 0002（単位監査・gate）、prereg 3本、verdict.py、
     0002a/b。TODO マークは数値・引用の pin 待ち。 -->

## 4 The audit protocol

The substantive question of this paper—whether Calvano-type collusion survives
transplantation into a realistic market-making environment—is one on which both
prior expectations and policy stakes run high. Our methodological premise is that
such a question should be settled the way a referee settles a disputed call: by a
procedure fixed before the play, applied mechanically, and auditable after the
fact. This section specifies that procedure. It has four components: a
pre-registration chain that freezes interpretation before data exist (§4.1), a
certification gate whose verdict is a mechanical function of simulation output
(§4.2), a measurement layer whose units survive an adversarial audit (§4.3), and
a compute-governance layer that makes the budget, the provenance, and even our
own failures inspectable (§4.4). None of these components is individually novel;
their joint, pre-committed application to an algorithmic-collusion question is,
to our knowledge, new, and we regard it as a primary contribution alongside the
substantive findings.

### 4.1 Pre-registration chain

Every confirmatory experiment in this paper follows the same chain:
**(i) freeze → (ii) register → (iii) generate → (iv) judge mechanically.**

*Freeze.* The interpretation rules for an experiment—cell definitions, judgment
criteria, the rule selecting a headline cell among multiple positives, and,
critically, *degradation rules* specifying how the claim shrinks under each
negative outcome—are written into a versioned document in the public repository
before any result of that experiment exists. The repository's commit history
provides an internal timestamp; the executable definitions (grid builders,
certification function) are pinned by commit hash, so "the criteria" denotes a
specific function, not a description of one.

*Register.* The frozen document is then registered on the Open Science Framework
with a public timestamp (registration: osf.io/63pj2), prior to data generation.
For follow-on experiments within the same campaign (the calibrated-venue cells
and the robustness tier), the freeze documents are committed as addenda to the
registered design; each records, at freeze time, an explicit disclosure of all
data in existence.

*Generate.* Runs are launched only after the freeze. Where a clarification to a
frozen document became necessary while a run was in flight (twice in this
campaign), it was committed *before reading any result*, and the unread status is
itself documented; we return to one such clarification—the convergence-clause
probability arithmetic—in §5.2, because it materially disciplined how the
outcome must be interpreted.

*Judge.* Certification is the mechanical application of the pinned function to
the output. No human re-judgment occurs, and no criterion is adjusted after
contact with data. Where a result fell outside the enumerated branches of the
frozen interpretation (one case: the direction of the learning-rate contrast,
§5.2), the additional interpretation is reported and labeled as post hoc; the
pre-registered judgment itself is never displaced.

Two consequences of this chain recur throughout the paper. First, negative and
"demoted" outcomes are reported in the pre-specified wording, which prevents the
quiet migration of a weakened claim into a strong one. Second,
criterion-shopping is structurally unavailable: the convergence criterion used in
our headline judgment (v2 below) was itself adopted *before* the dense-regime
experiments, and the document trail shows that the baseline-density
non-convergence label was retained even though a laxer criterion would have
"produced" convergence.

### 4.2 The certification gate

A cell—a configuration of mechanism, staleness regime, environment, and learner,
run over multiple seeds—is *certified* as collusive only if it passes three
jointly necessary components, evaluated by a single pinned function:

1. **Convergence (criterion v2, behavior-level).** Calvano et al.'s policy-level
   criterion—the argmax table stable over a long window—is structurally
   unreachable in our environment (§5.1); a criterion that can never fire cannot
   gate anything. Criterion v2 instead probes the *greedy limit cycle*: every
   10^4 periods, learning is paused, the deterministic greedy trajectory is
   recorded, and convergence is declared after ten consecutive identical cycle
   signatures. The probe reads the Q-table without writing; learning
   trajectories are bit-identical with and without it. Off-path noise in the
   Q-table—the reason the policy-level criterion fails—does not enter.
2. **Supra-competitive markup (pooled).** The pooled mean markup over seeds must
   exceed the competitive benchmark by a margin: mean − 2·SE > 0.05, i.e. five
   percent above the own-condition Nash level (§4.3 for units).
3. **Impulse response (deviation–punishment).** Collusion is distinguished from
   mere supra-competitive drift by Calvano-style intervention: force a one-period
   best-response deviation, and require (a) detectable punishment, (b)
   non-profitability of the deviation against the counterfactual same-flow path,
   and (c) restoration of the pre-deviation profile. A cell passes if at least
   80% of seeds pass.

The gate's own discriminative power is verified independently of the simulator:
synthetic grim-trigger policies (which must PASS) and fixed wide-quoting
policies (which must FAIL) are pushed through the gate in the test suite. This
mirrors, at the certification layer, the anchor-battery discipline of the
underlying market simulator (§3): the instrument is validated against cases with
known answers before it is pointed at the unknown.

The components have deliberately different aggregation structure—pooled mean for
markup, a pass-fraction for impulse response, unanimity for convergence—and the
unanimity clause matters: under per-seed convergence probability p, an n-seed
pool survives with probability p^n. We pre-registered this arithmetic, and its
interpretive asymmetry (failure of the strict pool is *not* evidence of regime
absence), before reading the n = 20 robustness results; §5.2 reports the
outcome in exactly those terms.

### 4.3 Measurement: the markup, its units, and an adversarial audit

All headline quantities in this paper are markups:

> markup = (realized − nash) / nash,

where *realized* is the mean per-period winning half-spread over a measurement
window run at zero exploration with learning frozen, and *nash* is the myopic
(one-shot stage-game) Nash spread of the *same condition*—same mechanism, same
staleness regime, same calibration. Three properties, established by an explicit
unit audit and recorded with the data, govern interpretation:

*Quote-based, not fill-based.* The realized spread averages the posted winning
quote per period regardless of execution. The markup therefore does not scale
mechanically with event density; a sparse market is not "low markup" by
construction. (This excludes one of the three readings a skeptical reader might
entertain when comparing tables across density regimes.)

*Condition-specific denominators.* The competitive benchmark is an economic
object that moves with the environment. Under committed quotes it is the
Glosten–Milgrom break-even against arbitrageur adverse selection, and it falls
as uninformed flow thickens (0.664 at baseline density; 0.165 at the dense
regime; 0.137 at the empirically calibrated point). Under revisable quotes—the
ablation that severs sniping—adverse selection vanishes and the Bertrand
undercutting fixed point is the bottom of the action grid (0.0238 dense; 0.0625
calibrated). The order-of-magnitude differences in markup across tables are
therefore *denominator economics*, not unit inconsistency: the measured quantity
is the same dimensionless excess everywhere, and the certification floor (five
percent above own-condition Nash) means the same thing in every cell. Within a
staleness regime the denominator is mechanism-invariant (machine-verified across
both batch grids, N ∈ {1,5,20} dense and N ∈ {1,10,100} calibrated), so the
channel-attribution differences of §5.4 share denominators by construction.

*What cross-condition comparisons do and do not say.* A markup comparison across
staleness regimes compares each world's excess over *its own* competitive level,
not absolute spreads. At the calibrated point the absolute realized half-spreads
of the committed and revisable worlds overlap; what separates completely is the
markup (§5.3). We report both, because the distinction carries the paper's
monitoring implication (§6): the raw spread distribution is not the collusion-
relevant observable—the benchmark-relative one is—and computing the benchmark
requires a model of the staleness and adverse-selection structure. Two further
caveats are recorded once and inherited by every table: the revisable
denominator inherits the resolution of the discrete action grid, so revisable
markup *magnitudes* are not grid-invariant (the qualitative statement—dwelling
above the own-condition floor—is); and ceiling levels are grid-determined under
inelastic noise flow [TODO: cross-ref D-B11 limitation], so markup levels are
interpreted only through certification and within-grid comparisons.

We emphasize how this audit originated: a consistency check *failed*. Inverting
the headline markup (62.05) through the committed denominator implied a realized
spread of 10.4 on a grid bounded at 2.0—an impossibility that forced the
denominator structure into the open and produced, on re-derivation, an exact
reconciliation (realized = 1.50, interior to the grid). We record the failed
check alongside the reconciliation, for two reasons. First, an audit trail
documents procedures performed, not verdicts reached; this one is re-executable
against the archived artifacts, which—not the presence of failures—is what makes
it inspectable. Second, a check that cannot fail certifies nothing by passing;
the recorded failure documents that ours could.

### 4.4 Compute governance: budgets, an append-only ledger, and incidents

*Budget.* The campaign's compute is capped ex ante at 10^9 learning periods per
tier (coarse map, dense refinement, robustness), enforced mechanically: a run
whose planned periods would exceed its tier cap is refused at submission, and
the refusal is itself recorded. This forecloses the incremental "one more run"
expansion of the design space. Final consumption: 739.2M / 410.4M / 191.0M
periods (coarse / dense / robustness), the dense figure stated as a conservative
upper bound [TODO: cross-ref Appendix C].

*Determinism.* A master seed spawns independent substreams (price, arrivals,
exploration) independently of configuration; identical (configuration, seed)
reproduces bit-identical trajectories. This is load-bearing in three ways: it
makes re-running lost work a *recomputation* rather than additional sampling
(so crash recovery cannot become criterion-shopping); it makes paired
cross-condition comparisons exact common-random-number designs (§5.3); and it
made forensic reconstruction of the ledger possible after the incident below.

*Ledger as append-only journal.* Budget events (charge, refund, audited
reconciliation, audit notes) are recorded in an append-only journal, one event
per line; the spent totals are a fold of the journal, and the human-readable
snapshot is a cache verified against it. Result rows are keyed by a full
configuration hash rather than a display identifier, so perturbation axes that
do not appear in a cell's name cannot silently collide.

*Incidents.* Both governance properties above were forced by failures we
detected in our own pipeline mid-campaign, and we report them as exhibits rather
than bury them (Appendix C): (0002a) a result-identity key that could not
distinguish robustness variants, detected while the affected run was in flight—
the run was stopped and its partial results *discarded unread*, the schema
repaired and regression-tested, the spent budget refunded under an audited
reconciliation entry, and the experiment relaunched as a deterministic
recomputation; (0002b) a snapshot-overwrite ledger that lost concurrent updates,
detected because an audit note vanished—repaired by the journal redesign, with
the spent totals reconstructed deterministically from artifacts and, separately,
a bounding argument recorded showing that no budget-gate decision could have
flipped under any magnitude of the lost updates. The general lessons—identity
keys must be total over the perturbation space, and a ledger is an append-only
log, not an overwritable snapshot—are, we suggest, portable to any simulation
campaign that wants its claims audited. Both incidents were caught by the
protocol's own consistency checks; the complete records, including the
discarded-unread partial results and the ledger reconstruction worksheets,
accompany the paper.

<!-- TODO(pin): OSF URL 表記の最終形 / D-B11・Appendix C の cross-ref 番号 /
     文献引用(Calvano et al. 2020, Glosten-Milgrom 1985, Green-Porter 1984,
     Budish et al. 2015)の bib key / 数値の最終照合(739.2/410.4/191.0) -->
