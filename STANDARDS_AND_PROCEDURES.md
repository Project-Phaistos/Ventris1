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

## 7. Code and Implementation Standards

*(To be defined when implementation begins. For now, PRD design is the focus.)*

Preliminary notes:
- Pure Python with NumPy/scipy preferred (consistent with PhaiPhon4-5 stack)
- No PyTorch unless a specific pillar's algorithm requires gradient-based optimization
- Each pillar is an independent Python package/module with a clean API matching its interface contract
- Tests mirror go/no-go gates: every gate has a corresponding test
- All results are reproducible: fixed seeds, deterministic algorithms, versioned corpus

---

## 8. Working Process

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
