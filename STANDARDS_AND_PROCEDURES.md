# Ventris1 — Standards and Procedures

**Last updated:** 2026-03-23

---

## 1. Document Hierarchy

This project uses a strict document hierarchy to keep design work grounded and traceable:

```
README.md  (ground truth — high-level approach)
    │
    ├── STANDARDS_AND_PROCEDURES.md  (this file — how we work)
    │
    ├── docs/prd/
    │   ├── PRD_PILLAR_1_PHONOLOGY.md
    │   ├── PRD_PILLAR_2_MORPHOLOGY.md
    │   ├── PRD_PILLAR_3_GRAMMAR.md
    │   ├── PRD_PILLAR_4_SEMANTICS.md
    │   ├── PRD_PILLAR_5_VOCAB_RESOLUTION.md
    │   └── PRD_ORCHESTRATOR.md          (cross-pillar integration)
    │
    └── docs/decisions/
        └── DECISION_LOG.md              (design decisions with rationale)
```

### README.md is the ground truth

The `README.md` contains the high-level restructured approach — the five pillars, their dependency chain, resolved design decisions, and the fundamental axiom (Linear A as chimaera language, no single-cognate assumption). Every PRD, every design decision, and every implementation must trace back to this document.

**Rules:**
- No PRD may contradict the README. If a PRD needs to deviate, the README must be amended FIRST with explicit rationale, not the other way around.
- The README is updated only by deliberate decision, never as a side effect of implementation.
- When reviewing any PRD or code, the first check is: "Does this align with the high-level approach?"

---

## 2. PRD Design Process

PRDs are written **one pillar at a time**, following the dependency chain. We do not write PRDs for downstream pillars until their dependencies are designed, because upstream outputs constrain downstream inputs.

### Ordering

```
Phase 1:  PRD_PILLAR_1_PHONOLOGY        (no dependencies — design first)
Phase 2:  PRD_PILLAR_2_MORPHOLOGY        (depends on Pillar 1 outputs)
          PRD_PILLAR_4_SEMANTICS          (independent — can design in parallel with Pillar 2)
Phase 3:  PRD_PILLAR_3_GRAMMAR           (depends on Pillar 2 outputs)
Phase 4:  PRD_PILLAR_5_VOCAB_RESOLUTION  (depends on all above)
Phase 5:  PRD_ORCHESTRATOR               (cross-pillar integration, data flow, pipeline)
```

### Writing a PRD: step-by-step

Each PRD goes through a deliberate multi-step process. Do NOT skip steps.

**Step 1 — Ideation (conversational)**
- Re-read the relevant section of README.md to ground the discussion.
- Brainstorm approaches, algorithms, data structures. Explore tradeoffs.
- Identify what is known vs. what needs research.
- No document is written yet — this is purely conversational.

**Step 2 — Structural outline**
- Define the pillar's inputs, outputs, and interface contracts.
- Inputs must match the declared outputs of upstream pillars (or raw corpus if no upstream).
- Outputs must be specified concretely enough that downstream pillars can design against them.
- List the major components/modules and their responsibilities.
- Identify risks, unknowns, and go/no-go gates.

**Step 3 — Draft PRD**
- Write the full PRD following the template (Section 3 below).
- Push to `docs/prd/` in the repo.
- Review against README.md for alignment.

**Step 4 — Review and amend**
- Walk through the PRD critically. Does every component trace to the high-level approach?
- Are the interface contracts precise enough for implementation?
- Are the go/no-go gates falsifiable?
- Amend as needed. Each amendment is a separate commit with rationale.

**Step 5 — Lock**
- Mark the PRD status as "Locked" once we're satisfied.
- A locked PRD can still be amended, but only through the decision log (Section 5).
- Implementation may begin on a locked PRD.

---

## 3. PRD Template

Every pillar PRD follows this structure:

```markdown
# PRD: Pillar N — [Name]

**Status:** Draft | Under Review | Locked
**Depends on:** [list of upstream pillars and their specific outputs]
**Feeds into:** [list of downstream pillars and what they consume]
**Date:** YYYY-MM-DD
**Authors:** [names]

---

## 1. Objective
What this pillar does and why, traced to the README.

## 2. Non-goals
What this pillar explicitly does NOT do. Include cognate-matching
unless this is Pillar 5.

## 3. Inputs
Concrete specification of input data — format, source, schema.
For Pillar 1: the raw Linear A corpus.
For Pillars 2+: outputs of upstream pillars (reference their output spec).

## 4. Outputs (interface contract)
Concrete specification of what this pillar produces.
Format, schema, and what downstream consumers can rely on.
This section is the most critical — it defines the contract between pillars.

## 5. Approach
The algorithms, methods, and architecture. Include reasoning for
key choices. Reference academic literature where applicable.

## 6. Components
Module-level breakdown with responsibilities.

## 7. Go/No-Go Gates
Falsifiable tests that must pass before the pillar's output is trusted.
Each gate specifies: what is tested, expected result, and what happens
on failure (revise approach vs. accept limitation).

## 8. Risks and Mitigations
Known risks with concrete mitigation strategies.

## 9. Corpus Budget
How much of the ~7,400-token corpus this pillar consumes or relies on.
Flag if multiple pillars compete for the same data splits.

## 10. Relationship to PhaiPhon (legacy)
What, if anything, can be reused from PhaiPhon1-5. What must be
discarded. Explicit about what changed and why.
```

---

## 4. Interface Contracts Between Pillars

The dependency chain means each pillar's outputs are another pillar's inputs. These contracts must be explicit and stable. A change to a contract requires updating both the producing and consuming PRDs.

### Expected contract chain

**Pillar 1 → Pillar 2:**
- C-V grid (sign-to-{consonant class, vowel class} mapping with confidence scores)
- Phonotactic constraint set (legal/illegal sign sequences, syllable boundary rules)
- Vowel inventory (which signs are pure vowels, how many vowel classes)
- Consonant inventory (how many consonant classes, which signs are in each)
- LB agreement score (measured divergence from Linear B phonetic values)

**Pillar 2 → Pillar 3:**
- Stem-affix segmented lexicon (each attested sign-group decomposed into stem + affixes)
- Inflectional paradigm table (paradigm classes, case/number/gender slots, endings)
- Morphological word-class hints (stems that decline vs. stems that conjugate vs. uninflected)

**Pillar 4 → Pillar 5:**
- Anchor vocabulary (sign-groups with constrained meanings from ideogram/numeral context)
- Semantic field constraints (for each anchored word: set of plausible semantic categories)
- Formula atlas (libation formula variants mapped, fixed vs. variable elements identified)
- Place name phonetic anchors (confirmed phonetic values from known place names)

**Pillars 1+2+3+4 → Pillar 5:**
- All of the above, plus the grammar sketch from Pillar 3 (word order, agreement patterns, word classes)
- Pillar 5 uses all of this to constrain cognate search: only search for words that (a) have a known phonological form, (b) fit the morphological structure, (c) belong to a known word class, and (d) match a constrained semantic field

---

## 5. Decision Log

Design decisions that deviate from, refine, or extend the README are recorded in `docs/decisions/DECISION_LOG.md`. Each entry:

```markdown
### DEC-NNN: [Short title]
**Date:** YYYY-MM-DD
**Context:** Why this decision was needed.
**Decision:** What was decided.
**Rationale:** Why this choice over alternatives.
**Impact:** Which PRDs or components are affected.
```

---

## 6. Axioms (non-negotiable)

These are restated from the README and must be checked at every review:

1. **No single-cognate assumption.** Linear A is a chimaera language with multiple influences. Architecture must allow mixed provenance at every level.

2. **Structure before content.** Internal structural analysis (phonology, morphology, grammar) comes before any external language comparison.

3. **Cognates are tools, not goals.** Cross-language matching serves vocabulary resolution only. It is never framed as proving a genetic relationship.

4. **Independent phonological discovery.** The phonological engine discovers the sound system from distributional evidence. Linear B values are soft validation only, applied post-hoc.

5. **Falsifiable gates.** Every pillar has go/no-go gates with concrete pass/fail criteria. No pillar's output is trusted without passing its gates.

6. **Held-out validation.** The Knossos ivory scepter (119 signs) is reserved as a held-out test set. It is never used during development or training — only for final validation.

---

## 7. Data Extraction and Ingestion Standards

All data in this project traces back to the Linear A corpus and candidate language corpora. These standards ensure the data pipeline is auditable, reproducible, and free from contamination.

### 7.1 Cardinal rule: no fabricated data

Data must NEVER be manually written, AI-generated, or hallucinated. Every data point must be traceable to a published, peer-reviewed, or institutionally curated source via a scripted pipeline. If a value cannot be sourced, it is marked as missing — never filled in.

### 7.2 Source registry

Every external data source used by any pillar must be registered in `data/SOURCES.md` with:

| Field | Description |
|-------|-------------|
| **Name** | Human-readable name (e.g., "SigLA corpus", "GORILA sign list") |
| **URL** | Permanent link to source repository or publication |
| **Version/Date** | Specific version, commit hash, or access date |
| **License** | License type and any usage restrictions |
| **Maintainer** | Institution or individual responsible |
| **Peer review** | Publication status, citation count, or academic standing |
| **Known limitations** | Any documented biases, gaps, or quality issues |
| **Cross-references** | Other sources that can verify this one |

### 7.3 Ingestion pipeline requirements

Every ingestion script must:

1. **Read from a declared source** — the script's input must point to a registered source, not a local file of unknown provenance.
2. **Be deterministic** — same source version → same output, always. No random sampling during ingestion.
3. **Produce a provenance record** — a machine-readable JSON sidecar file recording: source URL, source version/hash, ingestion timestamp, script path, script git hash, row counts, any filtering applied.
4. **Validate on ingest** — schema validation (expected columns, types, non-null constraints), row count sanity checks, and at least 3 spot-checked entries verified against the original source.
5. **Never modify source data silently** — if the pipeline normalizes, filters, or transforms data, each transformation must be logged in the provenance record with rationale.

### 7.4 Corpus versioning

The Linear A corpus is the foundation of the entire project. It must be versioned and checksummed:

- A single canonical corpus file (or directory) with a SHA-256 hash recorded in `data/CORPUS_MANIFEST.json`.
- Any modification to the corpus (adding inscriptions, correcting readings, updating sign values) creates a new version with a new hash and a changelog entry.
- Every experiment log (Section 9) records which corpus version was used.
- The held-out set (Knossos ivory scepter) is stored in a separate file, never co-mingled with the training corpus, and its hash is independently tracked.

### 7.5 Candidate language data

For each candidate language used in Pillar 5 (and earlier for validation):

- IPA transcriptions must come from published dictionaries or peer-reviewed databases, never from automated IPA converters unless the converter's error rate is documented and acceptable.
- The source's coverage (% of reconstructed vocabulary included) must be documented.
- Known romanization/IPA inconsistencies across sources must be flagged.

---

## 8. Adversarial Agent Audit System

Every module that gets built must survive adversarial review before its outputs are trusted. This is not optional quality assurance — it is a structural part of the pipeline.

### 8.1 Purpose

PhaiPhon taught us that subtle bugs compound silently. FDR rubber-stamping 558/559 pairs (PhaiPhon 3.4.5), mass leakage in JSD computation (PhaiPhon4 v5), mean-vs-sum aggregation errors (PhaiPhon 3.4.5), and inventory-size confounds driving rankings instead of linguistics (PhaiPhon 3.5.1) — these were all cases where the module appeared to work, produced plausible-looking outputs, and passed basic tests, but was fundamentally broken in ways that only adversarial scrutiny uncovered.

The adversarial audit system exists to catch exactly these failures.

### 8.2 Audit structure

For each module (not just each pillar — each significant component within a pillar), an adversarial audit is triggered after the module passes its own go/no-go gates. The audit is performed by a separate agent/review process with an explicitly adversarial mandate.

**The auditor's job is to BREAK the module, not validate it.**

### 8.3 Audit checklist

Every audit must attempt ALL of the following:

#### A. Known-answer tests
- Feed the module inputs where the correct output is independently known.
- Example (Pillar 1): Run the phonological engine on Linear B data (where we know the answer is Greek phonology). Does it recover the right vowel count? The right consonant groupings?
- Example (Pillar 2): Run morphological decomposition on a well-understood inflected language (Latin, Greek). Does it recover known declension classes?
- **If no known-answer test exists for a module, that is a design flaw. Fix the design.**

#### B. Null/degenerate input tests
- What happens with an empty corpus? A corpus of one word? A corpus of random signs?
- The module must either fail gracefully with a clear error or produce explicitly flagged "insufficient data" output. It must NEVER produce confident-looking garbage.

#### C. Invariance tests
- Does the output change when it shouldn't?
- Permuting the order of inscriptions should not change results (order invariance).
- Duplicating the corpus should not change results (scale invariance for normalized metrics).
- Adding a small amount of noise should not dramatically change results (stability).

#### D. Confound analysis
- Is the output driven by the signal we care about, or by a confound?
- PhaiPhon lesson: rankings were driven by phoneme inventory size, not linguistic affinity. The auditor must check for equivalent confounds in every module.
- For each output, ask: "What ELSE could explain this result besides the intended signal?" Test that alternative explanation.

#### E. Sensitivity analysis
- Vary key hyperparameters across a reasonable range. Does the output remain qualitatively stable, or does it flip?
- If the output is fragile (changes qualitatively with small parameter changes), the module is not trustworthy and needs redesign.

#### F. Edge case / boundary tests
- Test at the extremes of every input dimension: shortest inscriptions, longest inscriptions, rarest signs, most common signs, signs that appear only once (hapax legomena).
- Hapax handling is critical in a 7,400-token corpus — many signs may appear only 1-3 times.

#### G. Cross-validation against independent methods
- Where possible, compare the module's output against a completely different algorithmic approach to the same question.
- If two independent methods agree, confidence is high. If they disagree, investigate why before trusting either.

### 8.4 Audit output

Each audit produces a short report filed in `docs/audits/`:

```markdown
# Audit: [Module Name]

**Date:** YYYY-MM-DD
**Auditor:** [name/agent]
**Module version:** [git hash]
**Verdict:** PASS | CONDITIONAL PASS | FAIL

## Known-answer tests
[results]

## Null/degenerate tests
[results]

## Invariance tests
[results]

## Confound analysis
[results]

## Sensitivity analysis
[results]

## Edge cases
[results]

## Cross-validation
[results]

## Issues found
[list with severity: CRITICAL / HIGH / MEDIUM / LOW]

## Recommendation
[pass / fix issues and re-audit / redesign module]
```

### 8.5 Audit gates

- A module with any CRITICAL issue does not ship. Period.
- A module with HIGH issues may ship only if the issues are documented in the module's limitations section and downstream consumers are aware.
- The audit report is linked from the module's go/no-go gate results.

---

## 9. Experiment and Run Logging Standards

Every experiment, run, module test, or diagnostic produces a log entry. These are not optional developer notes — they are the scientific record of the project.

### 9.1 Log location and structure

```
docs/
├── RUN_LOG.md                    # Master log (reverse chronological)
├── experiments/
│   ├── EXP-001_description.md    # Individual experiment reports
│   ├── EXP-002_description.md
│   └── ...
└── audits/
    ├── AUDIT_pillar1_phonotactics.md
    └── ...
```

### 9.2 RUN_LOG.md format

The master log is reverse chronological (newest first). Each entry follows this format:

```markdown
## YYYY-MM-DD — [Short descriptive title]

**Type:** Experiment | Module Test | Diagnostic | Production Run | Audit
**Pillar:** 1 | 2 | 3 | 4 | 5 | Cross-pillar
**Module:** [specific module name]
**Commit:** [git hash]
**Corpus version:** [SHA-256 hash from CORPUS_MANIFEST.json]
**Duration:** [wall clock time]
**Platform:** [e.g., Windows 11 local, Vast.ai 16-vCPU, Lambda A100]

### Objective
What was this run trying to determine or validate?

### Configuration
Key parameters, config file path, any deviations from defaults.
```yaml
parameter: value
parameter: value
```

### Results
Concrete numbers. Tables preferred over prose. Include:
- Primary metric(s) with values
- Comparison to baseline or previous run (with delta)
- Statistical significance where applicable (confidence intervals, p-values)

### Interpretation
What do the results mean? One paragraph maximum.
- Was the objective met?
- Any surprises or anomalies?
- Does this change the plan?

### Artifacts
Links to output files, figures, saved models.

### Next steps
What follows from this result? Be specific.
```

### 9.3 Individual experiment reports (EXP-NNN)

For experiments that are too detailed for a RUN_LOG entry (multi-day runs, complex diagnostics, parameter sweeps), write a full report in `docs/experiments/`. The RUN_LOG entry should link to it.

Full experiment reports follow this template:

```markdown
# EXP-NNN: [Title]

**Date:** YYYY-MM-DD
**Authors:** [names]
**Pillar:** N
**Status:** Planned | Running | Complete | Failed | Superseded

## 1. Hypothesis
What specific claim is being tested? Phrased as a falsifiable statement.

## 2. Method
Step-by-step procedure. Detailed enough that someone else could reproduce it.
Include: code entry points, config files, environment setup.

## 3. Data
Which corpus version. Which subset. Any filtering or preprocessing.
Provenance record reference.

## 4. Results
Tables, figures, raw numbers. Primary and secondary metrics.

## 5. Analysis
Statistical analysis. Confound checks. Comparison to known-answer baselines.

## 6. Conclusion
Was the hypothesis supported, refuted, or inconclusive?
If inconclusive, what additional evidence would resolve it?

## 7. Failures and surprises
What went wrong? What was unexpected?
This section is MANDATORY even if everything went well — write "None" explicitly.
Lessons learned from PhaiPhon: failures that aren't documented get repeated.

## 8. Impact on plan
Does this result change any PRD, interface contract, or approach?
If yes, file a decision log entry (DEC-NNN) and link it here.
```

### 9.4 What gets logged

**Always log:**
- Any run that produces results used in a decision (even negative results)
- Any parameter sweep or sensitivity analysis
- Any diagnostic run (pre-run GO/NO-GO, post-run analysis)
- Any adversarial audit
- Any run that fails unexpectedly (with root cause analysis)

**Don't log:**
- Interactive debugging sessions (unless they reveal a bug worth documenting)
- Repeated identical runs for timing purposes (log once with note "N=5, mean=X, std=Y")

### 9.5 Commit discipline for runs

- Every completed run is committed with its log entry in the same commit (or immediately after).
- Result artifacts (output files, figures) are committed alongside the log.
- Commit message references the experiment: `"EXP-003: Pillar 1 vowel count sensitivity analysis"`.
- Results are pushed to GitHub. Unpushed results don't exist.

---

## 10. Lessons from PhaiPhon: Rigorous Experimentation Practices

These are hard-won lessons from the PhaiPhon1-5 development cycle. They are codified here so they are never re-learned.

### 10.1 Pre-run diagnostics (GO/NO-GO gates)

Before any production run, execute a pre-run diagnostic that verifies:

- **Known-answer sanity**: Run the pipeline on a case where you know the answer. If it gets the known answer wrong, do not proceed. (PhaiPhon lesson: the known-answer tests on Linear B/Greek caught bugs that production runs on Linear A would have missed.)
- **Numerical sanity**: Check for NaN, Inf, degenerate distributions, zero gradients, collapsed outputs. These should be automated tests that run in <1 minute.
- **Scale sanity**: Run on a tiny subset first (smoke test). If the smoke test output is qualitatively wrong, the full run will be too — but 100x more expensive.

### 10.2 Post-run diagnostics

After any production run, before interpreting results:

- **Confound check**: Is the primary result explained by a confound? (PhaiPhon 3.4.5: inventory size drove rankings. PhaiPhon 3.5.1: vocab size drove rankings.) For every result, identify the top 3 potential confounds and test whether they explain the signal.
- **Selectivity check**: Did the pipeline actually discriminate, or did it accept/reject everything? (PhaiPhon 3.4.5: FDR accepted 558/559 pairs = no discrimination = rubber stamp.) If a filter accepts >90% or <10%, it's not filtering — investigate why.
- **Stability check**: How sensitive is the result to random seed, parameter perturbation, or data subsetting? If changing the seed flips the ranking, the result is noise.

### 10.3 Root cause analysis for failures

When a run produces unexpected results:

1. **Do not patch and re-run.** Diagnose the root cause first. (PhaiPhon lesson: 5 successive versions tried to fix symptoms of what turned out to be a single architectural issue — the phonetic prior model doesn't discriminate between languages when the FDR null is too permissive.)
2. **Spawn parallel diagnostic agents** if the failure is complex. Independent agents analyzing the same failure from different angles catches things that a single linear investigation misses. (PhaiPhon 3.4.5 post-run diagnostic used 5 parallel agents and identified the root cause.)
3. **Write the root cause into the log** with enough detail that someone reading it in 6 months can understand what went wrong and why the fix works.

### 10.4 Baseline and control requirements

Every experiment must include:

- **A positive control**: An input where you expect a strong signal. If the positive control fails, your pipeline is broken.
- **A negative control**: An input where you expect NO signal. If the negative control produces a signal, your pipeline is detecting noise. (PhaiPhon lesson: IsolateControl was the negative control — a synthetic unrelated language. It correctly ranked last in most runs, validating the pipeline's ability to reject non-signal.)
- **A baseline comparison**: What does the simplest possible approach give you? If your sophisticated model doesn't beat random chance or a trivial heuristic, it's not working.

### 10.5 Avoiding silent bias accumulation

Biases compound across pillar boundaries. A small systematic error in Pillar 1 (e.g., miscounting vowels by 1) propagates into Pillar 2 (wrong syllable boundaries → wrong morpheme segmentation) and cascades into Pillar 3 (wrong word classes) and Pillar 5 (wrong cognate matches). To catch this:

- **End-to-end smoke tests**: Run the entire pipeline (all pillars) on a known-answer language. If the end-to-end result degrades relative to individual pillar accuracy, there's a compounding error at an interface boundary.
- **Interface contract validation tests**: At every pillar boundary, verify that the upstream output meets the downstream's expectations — not just schema-level (correct types, correct shapes) but semantically (the C-V grid from Pillar 1 actually captures consonant/vowel distinctions, not just random clusters).
- **Periodic bias audits**: After every 3rd experiment, step back and ask: "Are we drifting toward confirming a preconception?" Specifically check for single-cognate assumption creep — the tendency to interpret mixed results as evidence for one dominant language rather than multiple sources.

### 10.6 Reporting negative results

Negative results (this approach didn't work, this hypothesis was refuted) are EQUALLY important as positive results. They must be:

- Logged with the same rigor as positive results
- Kept in the experiment log permanently (never deleted or hidden)
- Analyzed for WHY the approach failed, not just that it failed
- Used to constrain future approaches (if X didn't work because of Y, future approaches must account for Y)

PhaiPhon lesson: PhaiPhon 3.5.0 (z-score cross-language null) failed completely — accepted 0 pairs for all 20 languages. This negative result was more informative than many positive results, because it revealed that best-of-500 subsampling compresses score distributions below the z-score detection threshold. This directly informed the design of 3.5.1's rank-based approach.

---

## 11. Code and Implementation Standards

*(To be fully defined when implementation begins. For now, PRD design is the focus.)*

Preliminary notes:
- Pure Python with NumPy/scipy preferred (consistent with PhaiPhon4-5 stack)
- No PyTorch unless a specific pillar's algorithm requires gradient-based optimization
- Each pillar is an independent Python package/module with a clean API matching its interface contract
- Tests mirror go/no-go gates: every gate has a corresponding test
- All results are reproducible: fixed seeds, deterministic algorithms, versioned corpus

---

## 12. Working Process

### Current phase: PRD design
We are in the PRD design phase. No code is being written. The process is:

1. Start with Pillar 1 (no dependencies).
2. Ideate conversationally (Step 1).
3. Define outputs/interfaces (Step 2) — these constrain everything downstream.
4. Draft the PRD (Step 3).
5. Review against README.md (Step 4).
6. Lock (Step 5).
7. Move to the next pillar in dependency order.

### Ground truth check
At each step, verify:
- [ ] Does this align with README.md?
- [ ] Does the input match the upstream pillar's declared output?
- [ ] Does the output provide what downstream pillars need?
- [ ] Are the go/no-go gates falsifiable?
- [ ] Is there any implicit single-cognate assumption?
- [ ] Does the approach work with ~7,400 tokens?
