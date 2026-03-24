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

### 7.1 The Iron Law

```
┌─────────────────────────────────────────────────────────┐
│  DATA MAY ONLY ENTER THE PROJECT THROUGH CODE THAT       │
│  DOWNLOADS IT FROM AN EXTERNAL SOURCE.                   │
│                                                          │
│  NO EXCEPTIONS. NO "JUST THIS ONCE." NO "IT'S FASTER."  │
└─────────────────────────────────────────────────────────┘
```

This means:
- **YES**: Write a script with `urllib`, `requests`, `curl`, API calls that fetches and parses
- **YES**: Parse HTML/JSON/XML/CSV from downloaded content
- **YES**: Apply deterministic transformations (transliteration, normalization) with cited rules
- **NO**: Write data rows directly into files from memory
- **NO**: Hardcode word lists "from WebFetch results" without reproducible fetch code
- **NO**: "I know this word means X" → write it into the dataset
- **NO**: Fill in missing fields with plausible guesses
- **NO**: Pad entries to reach a target count — target counts are aspirational, never quotas

If a data field cannot be extracted from the source, it must be left empty or marked as unknown. NEVER fill in plausible values.

### 7.2 Dual-agent adversarial extraction pipeline

Data extraction uses a **dual-agent architecture** with adversarial integrity enforcement:

```
┌─────────────────────────────────────────────────────────┐
│                   EACH EXTRACTION STEP                    │
│                                                          │
│  Team A (Extractor) ──→ Step Output ──→ Team B (Auditor) │
│                                         │                │
│                              PASS → Next Step            │
│                              FAIL → Block + Log          │
└─────────────────────────────────────────────────────────┘
```

**Team A (Extraction Agent)** writes and runs extraction code. Team A NEVER writes data directly.

**Team B (Adversarial Auditor)** runs AFTER each step with VETO power. Team A and Team B MUST be separate agents with separate context. The auditor exists because extraction without verification is worthless.

### 7.3 The 7 modular extraction steps

Each step gets its own audit. Steps 2-4 can be combined into a single script, but the auditor must check all aspects.

| Step | Team A does | Team B checks |
|------|-------------|---------------|
| **1. Source Discovery** | Identifies URLs, APIs, databases | URLs are real (HTTP 200), source is authoritative, license permits extraction |
| **2. Data Download** | Writes code that downloads raw content | Code contains actual HTTP requests, raw content saved to intermediate file |
| **3. Parsing** | Parses downloaded content into structured records | Parsed entries appear in raw source; no entries present that DON'T appear in source |
| **4. Transformation** | Applies deterministic transforms (transliteration→IPA, normalization) | Every transformation rule cites a published academic reference; sample 10 manual checks match |
| **5. Output Writing** | Writes final structured data file | Schema matches spec, no silent empty fields, entry count is non-round and plausible |
| **6. Integration** | Updates metadata, manifests, indexes | Metadata counts match actual file counts, existing entries unchanged |
| **7. Cross-Validation** | — | Random sample 20 entries, trace EACH back through: output → transform → parse → download → source URL. Every entry must have complete provenance chain |

### 7.4 Red flags — STOP immediately

| Red Flag | What It Means |
|----------|---------------|
| No `urllib`/`requests`/`curl` in extraction code | Agent is authoring data, not extracting |
| Entry count is exactly round (100, 200, 500) | Likely padded to hit a target |
| >90% of entries have empty required fields | Extraction didn't actually get the data |
| Script contains `f.write("word\tipa\t...")` with literal data | Direct data authoring violation |
| Agent says "I know this word means..." | LLM knowledge substituted for source data |
| Transformation output == input for >80% of entries WITHOUT a cited reference explaining why | Transformation wasn't applied |
| Agent proposes to "manually compile" a word list | Data authoring, not extraction |
| Intermediate files not saved | Audit trail destroyed |
| Download step has no error handling | Silent failures will produce garbage |
| Agent says "I'll add the fetch code later" | No. Code first, data second. Always. |

### 7.5 The cached-fetch pattern (acceptable compromise)

Many sources require interactive browsing (CAPTCHAs, JavaScript, session cookies) that automated scripts can't handle. The **cached-fetch pattern** is acceptable:

1. Use WebFetch or manual browsing to access the source
2. Save the raw source content to an intermediate file (e.g., `raw/{source}_{iso}_{date}.html`)
3. Write a parsing script that reads from the intermediate file
4. The auditor verifies the intermediate file against the live source (spot-check 5 entries)

This is acceptable because the intermediate file IS a verifiable artifact. A hardcoded Python list is not.

### 7.6 Rationalization table

Every excuse has already been tried. None are acceptable.

| Excuse | Reality |
|--------|---------|
| "I fetched it with WebFetch so it's extracted" | WebFetch in conversation ≠ reproducible extraction code. Write a script. |
| "The data is well-known, I don't need to fetch it" | Your knowledge is not a source. Fetch it. |
| "It's faster to hardcode the list" | Speed doesn't matter. Provenance does. |
| "The source is down, I'll use my knowledge" | Log the failure. Return empty. Never substitute. |
| "I'm just filling in obvious glosses" | "Obvious" to an LLM is still hallucination. Extract or leave empty. |
| "The transliteration is trivial, I don't need a reference" | Cite the reference anyway. No exceptions. |
| "This is a small dataset, adversarial checking is overkill" | Small datasets are MORE vulnerable to hallucination. Check harder. |
| "I already verified this mentally" | Mental verification by an LLM is not verification. Run the auditor. |

### 7.7 Source registry

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

### 7.8 Corpus versioning

The Linear A corpus is the foundation of the entire project. It must be versioned and checksummed:

- A single canonical corpus file (or directory) with a SHA-256 hash recorded in `data/CORPUS_MANIFEST.json`.
- Any modification to the corpus (adding inscriptions, correcting readings, updating sign values) creates a new version with a new hash and a changelog entry.
- Every experiment log (Section 9) records which corpus version was used.
- The held-out set (Knossos ivory scepter) is stored in a separate file, never co-mingled with the training corpus, and its hash is independently tracked.

### 7.9 Candidate language data

For each candidate language used in Pillar 5 (and earlier for validation):

- IPA transcriptions must come from published dictionaries or peer-reviewed databases, never from automated IPA converters unless the converter's error rate is documented and acceptable.
- The source's coverage (% of reconstructed vocabulary included) must be documented.
- Known romanization/IPA inconsistencies across sources must be flagged.
- Every transformation rule (romanization → IPA, normalization) must cite a published academic reference. No "common knowledge" or "standard" mappings without citation.

### 7.10 Auditor report format

Each extraction audit step produces a structured report:

```markdown
# Extraction Audit: {Step Name} — {Dataset/Source} ({identifier})

## Step: {1-7}
## Agent Action: {what Team A did}
## Audit Checks:
- [ ] Check 1: {description} → PASS/FAIL
- [ ] Check 2: {description} → PASS/FAIL
...

## Evidence:
{specific entries examined, URLs verified, code inspected}

## Verdict: PASS / WARN / FAIL
## Blocking: {YES if FAIL — pipeline stops here}
```

**WARN accumulation rule:** 3+ WARNs on one dataset = effective FAIL. WARNs are not soft passes — they are tracked problems that compound.

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

## 11. Paper/Reference Implementation Fidelity

When implementing algorithms from published papers, a specific class of bugs arises from misreading or misimplementing the paper's equations. PhaiPhon had at least 6 of these, and each one was silent — the code ran, produced numbers, and looked plausible.

### 11.1 Parameter audit table (mandatory)

For every paper-derived algorithm, create a **parameter audit table** before writing any code. This table maps every parameter in the paper to its code location, default value, and verification status.

```markdown
| Paper param | Paper value | Paper reference | Code variable | Code default | Match? | Verified by |
|-------------|-------------|-----------------|---------------|-------------|--------|-------------|
| T           | 0.2         | Appendix A.3    | config.temperature | 0.2    | YES    | unit test   |
| α           | 3.5         | Appendix A.3    | config.alpha       | 3.5    | YES    | unit test   |
| emb_dim     | 700         | Section 3.1     | config.embedding_dim | ???   | ???    | ???         |
```

PhaiPhon lesson: The reproduction had `embedding_dim=64` instead of 700, `dropout=0.0` instead of 0.5, 36/61 IPA features, `.mean()` instead of `.sum()` for Omega_loss, and wrong sign on the coverage penalty. Each was a one-value error that silently degraded results. The audit table catches these BEFORE the first run.

### 11.2 Equation-to-code traceability

Every equation from a paper must have a comment in the code citing the exact equation number. The comment must include the equation itself (in ASCII math or a simplified form) so a reviewer can verify the implementation matches without having the paper open.

```python
# Eq. 10: S = Σ Q(X) - λ_cov · Ω_cov - λ_loss · Ω_loss
# Note: we MAXIMIZE S, so loss = -S
objective = quality - lambda_cov * omega_cov - lambda_loss * omega_loss
```

### 11.3 Unit tests at the FUNCTION level, not just pipeline level

PhaiPhon's mean-vs-sum bug (`mean*sqrt(n_eff/n)` vs `return total_log_bf`) was a single-line error in one function. End-to-end tests didn't catch it because the pipeline still produced plausible rankings — just wrong ones. The function-level unit test with a known answer would have caught it instantly.

**Rule:** Every function that implements a mathematical formula gets a unit test with a hand-computed expected value. Not "does it run without error" — "does it produce the RIGHT number for this specific input?"

---

## 12. Configuration and Reproducibility Standards

### 12.1 All hyperparameters in config files

No hyperparameters hardcoded in source code. Every tunable value lives in a YAML config file. The config file is committed with every experiment result.

```
configs/
├── pillar1_default.yaml
├── pillar1_sensitivity_sweep.yaml
└── pillar2_default.yaml
```

PhaiPhon lesson: Hardcoded defaults that diverged from paper values were not caught because reviewers looked at the config file (which didn't include them) rather than the source code (which had wrong defaults baked in).

### 12.2 Config-to-result binding

Every result artifact must include or reference the exact config that produced it. The config is either:
- Embedded in the result file's header/metadata, OR
- Referenced by SHA-256 hash in the result file, with the config committed alongside

**No "I think I used the default config" situations.** If the config isn't recorded, the result is unreproducible and should be treated as suspect.

### 12.3 Determinism requirements

- All random operations use explicit seeds recorded in the config.
- Running the same code + same config + same data = identical output, byte-for-byte.
- If an algorithm is inherently non-deterministic (e.g., MCMC), the seed, chain length, and convergence diagnostics are recorded.
- **No implicit randomness**: `random.seed()` without an argument, unseeded `numpy.random`, or `torch.manual_seed()` called in some runs but not others.

### 12.4 Environment pinning

The Python environment is pinned with exact versions:
- `requirements.txt` with `==` pins (not `>=`)
- Or `pyproject.toml` with locked dependencies
- The environment file is committed with results

PhaiPhon lesson: "Library/runtime differences from the original 2021 environment" was cited as a possible cause for reproduction mismatches. Don't leave this to chance.

---

## 13. Regression Prevention

### 13.1 Every bug fix includes a regression test

When a bug is found and fixed, the fix commit MUST include a test that:
- Would have FAILED before the fix
- PASSES after the fix
- Is named descriptively (e.g., `test_omega_loss_uses_sum_not_mean`)

This test lives in the test suite permanently. It can never be deleted without a decision log entry explaining why.

### 13.2 Test suite runs before every commit

No code is committed without the test suite passing. If a test fails, the commit is blocked until:
- The test is fixed, OR
- The test is explicitly marked as `@pytest.mark.skip(reason="...")` with a linked issue

### 13.3 Regression test naming convention

Regression tests are named after the bug they prevent, not the feature they test:

```python
# BAD: test_aggregation()
# GOOD: test_log_bf_aggregation_uses_sum_not_mean()

# BAD: test_coverage()
# GOOD: test_coverage_penalty_is_max_rcov_minus_cov_not_soft_reward()

# BAD: test_features()
# GOOD: test_ipa_features_uses_all_61_dimensions_not_36()
```

### 13.4 Deep correctness testing (mandatory for every module)

Surface-level regression tests ("does it run without error") are necessary but NOT sufficient. PhaiPhon's mean-vs-sum bug, coverage penalty sign error, and IPA feature dimension error all produced code that ran, returned plausible numbers, and passed basic smoke tests — while being fundamentally wrong.

Every module must have three tiers of tests. All three are mandatory. A module missing any tier is not shippable.

#### Tier 1: Formula-level mathematical correctness tests

Every function that implements a mathematical formula gets a test with a **hand-computed expected value**. Not "does it return a float" — "does it return THIS specific float for THIS specific input?"

```python
# TIER 1 example: verify the binomial test computation
def test_binomial_enrichment_hand_computed():
    """AB08 with 83 initial out of 90 total, global rate 0.339.
    Hand-computed: P(X >= 83 | Bin(90, 0.339)) = scipy.stats.binom.sf(82, 90, 0.339)
    Expected: < 1e-20 (astronomically significant)."""
    p = binom.sf(82, 90, 0.339)
    assert p < 1e-20

def test_enrichment_score_formula():
    """E = (k/n) / p0 = (83/90) / 0.339 = 2.720."""
    E = (83 / 90) / 0.339
    assert abs(E - 2.720) < 0.01
```

**Minimum coverage:** Every equation cited in the code (from PRD or paper) must have at least one Tier 1 test. Count the equations → count the tests. If there are 8 equations, there must be ≥ 8 Tier 1 tests.

#### Tier 2: Known-language end-to-end tests (real data, known answers)

Run the module on a **real corpus from a known language** where the correct answer is independently established by decades of scholarship. This is not synthetic data — it is real attested text from a deciphered language.

**Requirements:**
- At least ONE known-language corpus must be maintained in the test suite for each module.
- The corpus must be a real historical script/language (Linear B, Cuneiform, Latin, etc.) — not a modern language, not generated data.
- Expected results must be cited from published scholarship (e.g., "Linear B has 5 vowels — Ventris & Chadwick 1956").
- The test must verify specific quantitative outputs against the known answer, not just "did it produce something."

**Examples per pillar:**

| Module | Known-language test corpus | Expected result | Source |
|--------|--------------------------|-----------------|--------|
| Vowel identifier | Linear B sign frequency data | V = 5 (a, e, i, o, u) | Ventris & Chadwick 1956 |
| Alternation detector | Linear B inflected forms | Recovers known consonant alternations (e.g., -to/-ta/-te series) | Chadwick 1958 |
| Grid constructor | Linear B corpus | Grid matches published syllabary grid (ARI > 0.5) | Bennett 1951 |
| Morphological decomp | Latin corpus | Recovers 5 declension classes | Any Latin grammar |
| Distributional grammar | Latin or Greek corpus | Identifies nouns vs. verbs with >70% accuracy | Any reference grammar |
| Multi-source vocab | English (known mixed etymology) | Identifies Latin/French/Germanic strata | OED |

**Failure of a known-language test is a CRITICAL gate.** If the module can't get the right answer on a deciphered language, it will not get the right answer on an undeciphered one.

#### Tier 3: Random/null data tests (anti-hallucination)

Run the module on data where there is **no signal**, and verify it finds **no signal**. This catches methods that detect patterns in noise.

Three mandatory variants:

1. **Random permutation null:** Take the real Linear A corpus and randomly permute sign assignments within each word (destroying positional/inflectional structure but preserving word-length distribution and sign frequencies). The module should produce NO significant results (no vowels, no alternation pairs, no grid structure, ARI ≈ 0).

2. **Uniform random corpus:** Generate a synthetic corpus where signs are drawn uniformly at random (destroying both structure AND frequency distribution). The module should produce NO significant results AND should flag "insufficient structure" or similar.

3. **Known-negative control:** Run on a real corpus that is known to lack the structure being tested. For a CV syllabary detector: run on an alphabetic script (Hebrew, Arabic). It should NOT detect CV syllabary structure. For inflectional paradigms: run on an isolating language (Mandarin). It should NOT find rich inflection.

**If any Tier 3 test produces a false positive (significant result from null data), the module has a methodological flaw. This is a CRITICAL failure — do not attempt to fix by adjusting thresholds. Redesign the method.**

### 13.5 Test tier summary and enforcement

```
┌──────────┬─────────────────────────────────┬──────────┬───────────┐
│ Tier     │ What it tests                   │ Minimum  │ Severity  │
├──────────┼─────────────────────────────────┼──────────┼───────────┤
│ Tier 1   │ Formula-level math correctness  │ 1 per    │ CRITICAL  │
│          │ (hand-computed expected values)  │ equation │           │
├──────────┼─────────────────────────────────┼──────────┼───────────┤
│ Tier 2   │ Known-language end-to-end       │ 1 per    │ CRITICAL  │
│          │ (real data, published answers)   │ module   │           │
├──────────┼─────────────────────────────────┼──────────┼───────────┤
│ Tier 3   │ Null/random data               │ 3 per    │ CRITICAL  │
│          │ (must find no signal in noise)   │ module   │           │
└──────────┴─────────────────────────────────┴──────────┴───────────┘
```

A module is not shippable unless ALL three tiers pass. A failure in any tier blocks the module — no exceptions, no "we'll add it later."

---

## 14. Statistical Rigor Standards

### 14.1 Every ranking must be checked for confounds

When any module produces a ranking (of signs, paradigms, candidate languages, etc.), the FIRST analysis is:

1. Compute Spearman correlation between the ranking and every known confound variable (inventory size, corpus frequency, word length, etc.)
2. If |rho| > 0.5 for any confound, the ranking is suspect. Report the confound correlation alongside the ranking.
3. If the confound explains more variance than the intended signal, redesign the module.

PhaiPhon lesson: Rankings correlated rho=0.667 with inventory size. This was discovered only in post-mortem. It should have been the first thing checked.

### 14.2 Every filter must report its selectivity

When a statistical test, threshold, or filter is applied:

- Report what fraction of inputs pass (acceptance rate)
- If acceptance rate > 90%: the filter is a rubber stamp — it's not doing its job
- If acceptance rate < 10%: the filter is too aggressive — either the threshold is wrong or the data doesn't contain the signal

PhaiPhon lesson: FDR accepted 558/559 pairs (99.8%) for 17/20 languages. This rubber-stamping was the root cause of meaningless rankings but wasn't flagged until the post-run diagnostic.

### 14.3 Confidence intervals, not just point estimates

Every reported metric includes a confidence interval or credible interval. Methods:
- Bootstrap CI (percentile method) for non-parametric quantities
- Profile likelihood CI for model parameters
- Posterior credible interval for Bayesian quantities

A result reported as "P@10 = 0.86" is incomplete. Report "P@10 = 0.86, 95% CI [0.79, 0.91]".

### 14.4 Effect sizes, not just significance

Statistical significance (p < 0.05) is not enough. Report effect sizes:
- For comparisons: Cohen's d or rank-biserial correlation
- For rankings: Kendall's tau or Spearman's rho between predicted and expected
- For classifications: precision, recall, F1 — not just accuracy

A "significant" result with a tiny effect size is a real but useless signal.

### 14.5 Multiple comparisons correction

When testing multiple hypotheses (e.g., "is each of 20 languages related to Linear A?"), apply correction:
- Benjamini-Hochberg FDR for exploratory analyses
- Bonferroni for confirmatory analyses
- Report BOTH corrected and uncorrected p-values

But also check that the correction actually filters (see 14.2 — FDR that accepts everything is not correction).

---

## 15. Consensus Dependency Layer

Every finding, label, and output in the system inherits assumptions from either (a) internal statistical analysis of the corpus or (b) external scholarly consensus. These are fundamentally different kinds of evidence. Scholarly consensus can be wrong — Ventris himself overturned the consensus that Linear B was not Greek. The dependency layer makes these assumptions explicit so that downstream consumers (especially Pillar 5) know which evidence to trust most.

### 15.1 Evidence provenance tags (mandatory on all outputs)

Every finding in every pillar output must carry an `evidence_provenance` tag:

| Tag | Meaning | Trust level | Example |
|-----|---------|-------------|---------|
| `INDEPENDENT` | Derived entirely from internal statistical analysis of the corpus. No external scholarly claim required. | HIGHEST | "AB08 is enriched in initial position (p=4.2e-10)" |
| `INDEPENDENT_VALIDATED` | Derived independently, then checked against scholarly consensus and found to agree. The finding stands on its own even if the consensus turns out to be wrong. | HIGH | "Consonant ARI=0.615 vs LB — independent clustering agrees with LB, but does not depend on LB" |
| `CONSENSUS_CONFIRMED` | Based on scholarly consensus that is universally accepted AND independently confirmable from the data. | MEDIUM-HIGH | "ku-ro = total marker — Bennett 1950, independently confirmed as final-position structural marker by Pillar 3" |
| `CONSENSUS_ASSUMED` | Based on scholarly consensus that cannot be independently verified from the corpus alone. If the consensus is wrong, this finding falls. | MEDIUM | "A704 = 10 (numeral value) — Bennett 1950, not independently verifiable" |
| `CONSENSUS_DEPENDENT` | Inherits a consensus assumption from an upstream pillar. The finding itself may be statistically valid, but its interpretation depends on the inherited assumption. | LOWER | "Sign-group X is in COMMODITY:FIG semantic field — depends on AB30/FIC ideogram identification (Evans 1909, pictographic)" |
| `SPECULATIVE` | Not supported by consensus OR independent evidence. Should never appear in the system — if it does, it's a bug. | REJECT | Should not exist in any output |

### 15.2 How to tag findings

In output JSON, every finding that carries a semantic claim, label, or interpretation must include:

```json
{
  "finding": "AB08 is a pure vowel sign",
  "evidence_provenance": "INDEPENDENT",
  "evidence_chain": [
    "Positional frequency analysis: initial enrichment E=2.72, p=4.2e-10 (Bonferroni-corrected)",
    "Medial depletion confirmed (p<0.001)",
    "No external knowledge used"
  ],
  "consensus_dependencies": []
}
```

vs.

```json
{
  "finding": "Sign-group ka-pa is associated with COMMODITY:FIG",
  "evidence_provenance": "CONSENSUS_DEPENDENT",
  "evidence_chain": [
    "Co-occurs with AB30/FIC ideogram 4 times (Fisher p=0.003)",
    "Exclusivity=0.80 (appears predominantly with FIG ideogram)"
  ],
  "consensus_dependencies": [
    {
      "assumption": "AB30/FIC represents figs",
      "source": "Evans 1909, Bennett 1950 — pictographic identification",
      "independently_testable": false,
      "what_breaks_if_wrong": "Semantic field label is wrong, but co-occurrence pattern is still real"
    }
  ]
}
```

### 15.3 The consensus dependency registry

All consensus assumptions used anywhere in the system are registered in a single file: `docs/CONSENSUS_DEPENDENCIES.md`. This file lists every external scholarly claim the system relies on, who made it, how widely accepted it is, whether it's independently testable, and what breaks if it's wrong.

Format:

```markdown
### CD-001: Sign type classification (syllabogram vs logogram)
**Source:** GORILA catalogue (Godart & Olivier 1976-1985)
**Acceptance:** Universal — no serious challenge in the literature
**Independently testable:** Partially — sign count heuristic (V(1+C)=N) provides a consistency check
**Used by:** Pillar 1 (all analysis filters to syllabograms only)
**What breaks if wrong:** All of Pillar 1 operates on the wrong sign set. Cascades through P2, P3.
**Mitigation:** Run Pillar 1 on ALL signs (not just classified syllabograms) as a sensitivity analysis. If results are qualitatively similar, the classification is not load-bearing.
```

### 15.4 Downstream trust hierarchy for Pillar 5

When Pillar 5 uses findings from Pillars 1-4, it must weight them by evidence provenance:

1. **INDEPENDENT findings get full weight.** These are pure data — they're true regardless of what language Linear A is or what scholars have claimed.

2. **INDEPENDENT_VALIDATED findings get full weight** but with the validation noted as a bonus, not a requirement.

3. **CONSENSUS_CONFIRMED findings get 80% weight.** The independent confirmation is strong, but the consensus label (e.g., "total") adds an interpretive layer that could be wrong.

4. **CONSENSUS_ASSUMED findings get 50% weight.** These are only as good as the consensus they depend on. Pillar 5 should treat them as priors, not certainties.

5. **CONSENSUS_DEPENDENT findings get 30% weight.** These inherit assumptions that cannot be independently verified. Useful as soft constraints, not hard ones.

These weights are used when combining evidence in Pillar 5's multi-source vocabulary resolution. A word anchored to COMMODITY:FIG (CONSENSUS_DEPENDENT, weight 0.3) provides weaker constraint than a word identified as a final-position structural marker (INDEPENDENT, weight 1.0).

### 15.5 Current system audit

As of Pillar 4 completion:

| Pillar | INDEPENDENT | INDEPENDENT_VALIDATED | CONSENSUS_CONFIRMED | CONSENSUS_ASSUMED | CONSENSUS_DEPENDENT |
|--------|-------------|----------------------|---------------------|-------------------|---------------------|
| 1 | 5 findings | 1 (ARI vs LB) | 0 | 3 (sign types, CV assumption, AB codes) | 2 (LB comparison, damage marking) |
| 2 | 4 findings | 0 | 0 | 1 (sign-group segmentation) | 2 (inherits P1 sign types, P1 phonotactics) |
| 3 | 5 findings | 0 | 1 (ku-ro as structural marker) | 1 (inscription type labels) | 1 (inherits P2 morphology) |
| 4 | 3 findings | 0 | 1 (ku-ro = total) | 3 (numeral values, ideogram IDs, place names) | 1 (semantic field labels) |
| **Total** | **17** | **1** | **2** | **8** | **6** |

**Independence ratio: 17/34 = 50% of findings are purely independent.** The other 50% inherit scholarly consensus at various levels.

### 15.6 Periodic consensus audit

After every 5th experiment or at each pillar completion, re-evaluate:
- Has any consensus assumption been challenged in recent scholarship?
- Can any CONSENSUS_ASSUMED finding be upgraded to CONSENSUS_CONFIRMED by adding an independent test?
- Can any CONSENSUS_DEPENDENT finding be made more independent by removing the dependency?

The goal is to MAXIMIZE the independence ratio over time. Every consensus dependency is a liability.

---

## 16. Multi-Agent Workspace Hygiene

### 15.1 File ownership boundaries

When multiple agents or workstreams operate on the same repo:
- Each agent/workstream owns specific directories. Ownership is declared in a `CODEOWNERS`-style comment at the top of the repo or in this document.
- **No touching files owned by another workstream** without explicit coordination.
- If two workstreams need to modify the same file, one of them is mis-scoped.

PhaiPhon lesson: Two parallel Claude instances shared the repo. One owned `PhaiPhon/`, the other owned `repro_decipher_phonetic_prior/`. The boundary was documented in memory but should have been in the repo itself.

### 15.2 Resource profiling before renting compute

Before renting cloud compute (Lambda, Vast.ai, etc.):
- Profile the workload locally to determine whether it's CPU-bound or GPU-bound
- Estimate wall-clock time and cost for the target instance type
- If the workload is CPU-bound, rent CPU instances (not GPU instances at 10x the cost)

PhaiPhon lesson: Lambda A100 GPU ran at 0% GPU utilization because the DP alignment bottleneck was entirely CPU-bound. ~$69.50 spent before discovering local Windows CPU was actually faster (14x with vectorized DP).

### 15.3 Cost tracking

Maintain a running cost log for any paid compute:

```markdown
| Date | Platform | Instance type | Duration | Cost | Task | Was GPU used? |
|------|----------|--------------|----------|------|------|---------------|
```

Before any cloud run, estimate cost and compare to remaining budget. If estimated cost > 50% of remaining budget, get explicit approval.

---

## 16. Code and Implementation Standards

Preliminary notes (to be fully expanded when implementation begins):
- Pure Python with NumPy/scipy preferred (consistent with PhaiPhon4-5 stack)
- No PyTorch unless a specific pillar's algorithm requires gradient-based optimization
- Each pillar is an independent Python package/module with a clean API matching its interface contract
- Tests mirror go/no-go gates: every gate has a corresponding test
- All results are reproducible: fixed seeds, deterministic algorithms, versioned corpus
- No dead code: if code is removed, it's removed — no commenting out, no `_unused` variables, no "keeping for reference"
- Functions do one thing: if a function has an `if mode == ...` branch that changes its behavior, split it into separate functions
- Error handling is loud: `raise`, don't `print` and continue. Silent failures are how bugs compound across pillars

---

## 17. Session Handoff Protocol

Claude sessions are ephemeral — context is lost between conversations. PhaiPhon relied on memory files and session briefs, which was fragile (memory could be stale, session briefs could be incomplete, new sessions sometimes repeated work or contradicted previous decisions). Ventris1 formalizes the handoff.

### 17.1 What a new session must read (in order)

When a new Claude session starts work on Ventris1, it MUST read these files before doing anything:

```
1. README.md                           — ground truth (high-level approach, axioms)
2. STANDARDS_AND_PROCEDURES.md         — how we work (this file)
3. docs/decisions/DECISION_LOG.md      — what has changed since README was written
4. docs/RUN_LOG.md (last 3 entries)    — what happened most recently
5. The PRD for the pillar being worked on — current design spec
6. The relevant test suite               — what's passing/failing
```

The session must NOT proceed with substantive work until it has confirmed it understands:
- Which pillar is currently active
- What the current status is (PRD phase? Implementation? Testing?)
- What the last session accomplished
- What the next step is

### 17.2 What every session must leave behind

Before a session ends (or when a significant milestone is reached), it must:

1. **Commit and push all work** — uncommitted work doesn't exist. If the session is interrupted, at minimum a WIP commit captures the state.
2. **Update RUN_LOG.md** — log what was done, what results were obtained, and what the next step is.
3. **Update the decision log** — if any design decisions were made during the session.
4. **Do NOT rely on Claude memory as the primary handoff mechanism.** Memory is supplementary. The repo itself must contain everything the next session needs. Memory is for user preferences, project context, and cross-project patterns — not for tracking the current state of Ventris1 work.

### 17.3 Session brief (in-repo, not in memory)

Each pillar directory contains a `SESSION_BRIEF.md` that is updated at the end of every session:

```markdown
# Session Brief: Pillar N — [Name]

**Last updated:** YYYY-MM-DD
**Last session by:** [human/agent name]

## Current status
[One sentence: where are we?]

## What was done last session
[Bullet list: 3-5 items max]

## What to do next
[Bullet list: 3-5 items max, in priority order]

## Blockers
[Anything that prevents progress, or "None"]

## Key files modified
[List of files changed in last session]
```

### 17.4 Detecting stale state

A new session must verify that the repo state matches expectations before acting:
- Run the test suite. If tests that should pass are failing, investigate before proceeding.
- Check `git log` against the RUN_LOG. If commits exist that aren't logged, something was done without documentation.
- Check that interface contracts are still met (upstream output files exist and match expected schema).

---

## 18. Kill Criteria — When to Stop Iterating

PhaiPhon went through 6 versions (3.0 → 3.2 → 3.4 → 3.4.5 → 3.5.0 → 3.5.1) before concluding the fundamental approach had structural issues that no amount of patching could fix. Each version addressed a symptom while leaving the root cause intact. This consumed weeks of effort and compute budget.

**Iteration is not progress if each iteration fixes a symptom but not the cause.**

### 18.1 Pre-defined kill criteria (set BEFORE starting)

Every pillar PRD must include a **kill criteria** section that defines, in advance, the conditions under which the approach should be abandoned rather than iterated:

```markdown
## Kill Criteria

This approach should be ABANDONED (not iterated) if any of:

1. [Specific falsifiable condition — e.g., "known-answer test on Greek fails
   to recover >3 of 5 vowels after 3 implementation attempts"]
2. [Specific falsifiable condition — e.g., "confound correlation |rho| > 0.6
   persists after 2 correction attempts"]
3. [Resource limit — e.g., "more than N person-hours spent without passing
   the go/no-go gate"]
```

These are set during PRD design, not after a failure. They cannot be retroactively loosened without a decision log entry.

### 18.2 The three-strike rule

If a module fails its go/no-go gate:

- **Strike 1**: Diagnose root cause. Fix. Re-run. Log the fix.
- **Strike 2**: Different root cause? Fix. Re-run. If same root cause as strike 1, the fix from strike 1 didn't work — escalate to approach review.
- **Strike 3**: The approach is structurally flawed. Do NOT attempt a fourth fix. Instead:
  1. Write a post-mortem (what was tried, why it failed, what the root causes were)
  2. File a decision log entry (DEC-NNN) documenting the abandonment
  3. Propose an alternative approach in a new PRD revision
  4. The post-mortem and all failed experiments remain in the log permanently

### 18.3 Symptom-chasing detection

Warning signs that you're chasing symptoms rather than fixing root causes:

| Warning sign | What it means |
|-------------|---------------|
| Each fix introduces a new failure in a different metric | The fixes are shifting the problem, not solving it |
| The fix is a special case / hardcoded threshold | You're overfitting to the test, not fixing the algorithm |
| The same module has been modified >3 times without passing its gate | The design is wrong, not just the implementation |
| You're adding complexity (more parameters, more stages) to fix something that should be simple | The approach doesn't fit the problem |
| Post-run diagnostics keep finding NEW confounds | The signal-to-noise ratio is too low for this method |
| Results improve on the known-answer test but degrade on new data | You're overfitting to the validation set |

When 2+ of these are present simultaneously, invoke the three-strike rule regardless of which strike you're on.

### 18.4 Sunk cost protocol

When deciding whether to abandon an approach:

- **Do NOT consider** time already spent, code already written, or compute already consumed. These are sunk costs. They are irrelevant to whether the approach will work going forward.
- **DO consider** only: (a) Is there a plausible fix that addresses the root cause (not a symptom)? (b) Has a similar fix already been tried and failed? (c) Is there an alternative approach that avoids the structural issue entirely?
- **The hardest part is admitting an approach is wrong.** PhaiPhon 3.x iterated for weeks partly because each version showed "partial improvement" — Hattic moved from #1 to #3, Greek moved up, IsolateControl stayed last. These incremental movements felt like progress but were noise around a broken signal. Improvement in noise is not signal.

---

## 19. Working Process

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
- [ ] Are kill criteria defined before starting?
- [ ] Is the session brief up to date?
