# Pillar Weakness Audit — 2026-03-27

Honest assessment of methodological weaknesses across all 5 pillars, ranked dodgiest to most solid.

## Pillar 5 — Multi-Source Vocabulary Resolution (CRITICAL issues)

### Issue 1: Min-max normalization destroys absolute quality signal
**Severity:** CRITICAL — invalidates strata percentages

The pipeline normalizes per-character PP scores to [0,1] across languages for each substring using min-max normalization. This means the "best" language ALWAYS gets score 1.0, even if every language is a terrible match. Consequences:
- 0% substrate is an artifact — every substring has a "winner" by definition
- The Lydian 40% means "Lydian is relatively less bad" — not "Lydian is actually a good match"
- No way to distinguish real cognates from noise

**Fix needed:** Absolute quality threshold from a null distribution. Run the same PP fleet data through a synthetic random language (or known isolate) and establish what "no signal" looks like.

### Issue 2: Proto-Dravidian at 11% is a methodological red flag
**Severity:** HIGH — suggests scoring produces false positives

No plausible mechanism for Bronze Age Crete to have Dravidian contact vocabulary. If the methodology produces Dravidian at 11%, it likely produces garbage for other languages too. Per Standards Section 14.1, this should have triggered a redesign.

### Issue 3: Progressive scan overlap inflates strata counts
**Severity:** MEDIUM — misleading statistics

The 1,177 "substring hypotheses" include massive overlap (a-sa-sa, a-sa-sa-ra, a-sa-sa-ra-me all counted as separate entries from the same text position). Strata percentages are inflated by this redundancy.

### Issue 4: Semantic scoring at 9.7% coverage
**Severity:** MEDIUM — most matches lack semantic validation

PP substrings cross word boundaries, so they rarely overlap with P4 anchors. Combined scoring can't distinguish phonological coincidence from real cognates without semantic constraints.

### Issue 5: Ad hoc combined scoring formula
**Severity:** MEDIUM — validated only via Gate 1 (not yet run)

The formula `combined = phon * 0.5 + semantic * w_prov` is acknowledged as ad hoc in the PRD. The specific weights have no empirical basis.

---

## Pillar 1 — Phonological Engine (known weakness, honestly flagged)

### Issue 1: V=1 is too conservative
**Severity:** HIGH — cascades through P2 and P3

Bonferroni correction is too stringent for this corpus size. Only AB08 passes, but bootstrap CI=[1,4] and decades of scholarship say 3-5 vowels exist. BH-FDR would likely find 3-4.

**Fix:** Relax to BH-FDR or override to V=4 with explicit CONSENSUS_ASSUMED tag.

### Issue 2: Sparse grid (69/170 signs assigned)
**Severity:** MEDIUM — 60% of signs have no grid position

Most signs lack enough distributional evidence for confident assignment.

### Strength: Consonant ARI=0.615
This is genuinely solid independent validation and doesn't depend on vowel count.

---

## Pillar 3 — Distributional Grammar (weak but honest)

### Issue 1: 1 dominant cluster + 6 singletons
**Severity:** MEDIUM — word class induction failed

Silhouette=0.712 is misleading (dominated by one large cluster). The system found "content words" vs "everything else" — not noun/verb/adjective distinctions.

### Issue 2: Word order inconclusive
**Severity:** LOW — expected for administrative lists, but means P3 doesn't contribute much

### Strength: Functional word identification
ku-ro, si, ki-ro identification is independently validated and genuinely useful.

---

## Pillar 2 — Morphological Decomposition (mostly solid)

### Issue 1: Possible over-segmentation (106 suffixes from 787 words)
**Severity:** LOW — suffix-strip method may be too aggressive

Some "suffixes" may be coincidental sign sequences. But the Latin known-answer test passes (recovers 3 declension classes), validating the core methodology.

---

## Pillar 4 — Semantic Anchoring (most conservative, least dodgy)

### Issue 1: Heavy consensus dependence
**Severity:** LOW-MEDIUM — 34 high-confidence anchors, 106 low-confidence

Place names and ideogram IDs depend on scholarly consensus (Evans 1909, Bennett 1950). But these are properly tagged with CONSENSUS_ASSUMED/CONSENSUS_DEPENDENT provenance.

### Strength: Zero-bias design
No deity, ritual, or verb labels. Purely frequency-based classifications. The most methodologically sound pillar.

---

## Priority fix order

1. **Pillar 5 scoring methodology** — null baseline + absolute thresholds (CRITICAL)
2. **Pillar 1 V=1** — relax to BH-FDR (HIGH, cascading effects)
3. **Pillar 5 progressive scan deduplication** — collapse overlapping substrings (MEDIUM)
4. **Pillar 3 word class induction** — use morphological features as primary signal (MEDIUM)
5. **Pillar 5 semantic coverage** — extract more glossed lexicons (MEDIUM, in progress)
