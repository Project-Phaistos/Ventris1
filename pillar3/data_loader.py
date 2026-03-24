"""Data loader for Pillar 3 (Distributional Grammar).

Loads Pillar 1 output, Pillar 2 output, and the raw SigLA corpus,
providing typed dataclasses for downstream grammar induction modules.

PRD Section 3: Inputs
- Pillar 1: grid assignments, vowel inventory, phonotactics
- Pillar 2: segmented lexicon, paradigm table, morphological word classes, affix inventory
- Raw corpus: inscriptions with words, signs, and positional context
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Pillar 1 typed structures
# ---------------------------------------------------------------------------

@dataclass
class GridAssignment:
    """A sign's position in the C-V grid (Pillar 1)."""
    sign_id: str
    consonant_class: int
    vowel_class: int
    confidence: float = 0.0
    evidence_count: int = 0


@dataclass
class PhonotacticBigram:
    """A favored or forbidden bigram from Pillar 1 phonotactic analysis."""
    sign_i: str
    sign_j: str
    bigram_type: str  # "favored" or "forbidden"
    observed: int = 0
    expected: float = 0.0
    std_residual: float = 0.0
    p_value_corrected: float = 1.0


@dataclass
class Pillar1Data:
    """Pillar 1 output relevant to Pillar 3.

    PRD Section 3.2: grid assignments inform distributional similarity
    between grid-row-mates; favored bigrams define fixed collocations.
    """
    grid_assignments: List[GridAssignment]
    consonant_count: int
    vowel_count: int
    vowel_sign_ids: List[str]
    favored_bigrams: List[PhonotacticBigram]
    forbidden_bigrams: List[PhonotacticBigram]

    # Prebuilt lookups
    sign_to_grid: Dict[str, GridAssignment] = field(default_factory=dict)
    favored_bigram_set: set = field(default_factory=set)

    # Provenance
    pillar1_hash: str = ""


# ---------------------------------------------------------------------------
# Pillar 2 typed structures
# ---------------------------------------------------------------------------

@dataclass
class SegmentedWord:
    """A word from the Pillar 2 segmented lexicon."""
    word_sign_ids: List[str]
    stem: List[str]
    suffixes: List[List[str]]
    prefixes: List[List[str]]
    segmentation_confidence: float
    frequency: int
    inscription_types: List[str]
    method: str


@dataclass
class AffixEntry:
    """A suffix or prefix from the Pillar 2 affix inventory."""
    signs: List[str]
    frequency: int
    n_distinct_stems: int
    productivity: float
    classification: str  # "inflectional", "derivational", "ambiguous"
    paradigm_classes: List[int]


@dataclass
class ParadigmSlot:
    """A slot within a paradigm class."""
    slot_id: int
    ending_signs: List[str]
    frequency: int
    label: str


@dataclass
class ParadigmStemExample:
    """An example stem within a paradigm class."""
    stem: List[str]
    attested_slots: List[int]
    attested_forms: List[Dict[str, Any]]


@dataclass
class ParadigmClass:
    """A paradigm class from the Pillar 2 paradigm table."""
    class_id: int
    n_members: int
    slots: List[ParadigmSlot]
    example_stems: List[ParadigmStemExample]
    completeness: float


@dataclass
class MorphologicalWordClass:
    """A morphological word class from Pillar 2 (declining/uninflected/unknown)."""
    class_id: int
    label: str  # "declining", "uninflected", "unknown"
    description: str
    n_stems: int
    paradigm_classes: List[int]


@dataclass
class Pillar2Data:
    """Pillar 2 output for Pillar 3 consumption.

    PRD Section 3.1: stems, suffixes, paradigm classes, and word-class
    hints are the primary inputs for distributional grammar induction.
    """
    segmented_lexicon: List[SegmentedWord]
    affix_inventory_suffixes: List[AffixEntry]
    affix_inventory_prefixes: List[AffixEntry]
    paradigm_classes: List[ParadigmClass]
    n_paradigm_classes: int
    morphological_word_classes: List[MorphologicalWordClass]

    # Prebuilt lookups (populated by loader)
    stem_to_word_class: Dict[Tuple[str, ...], str] = field(default_factory=dict)
    stem_to_paradigm_class: Dict[Tuple[str, ...], int] = field(default_factory=dict)
    stem_to_suffixes: Dict[Tuple[str, ...], List[Tuple[str, ...]]] = field(
        default_factory=dict
    )
    word_ids_to_stem: Dict[Tuple[str, ...], Tuple[str, ...]] = field(
        default_factory=dict
    )

    # Provenance
    pillar2_hash: str = ""


# ---------------------------------------------------------------------------
# Corpus structures
# ---------------------------------------------------------------------------

@dataclass
class CorpusWord:
    """A word occurrence within an inscription, with positional context.

    PRD Section 3.3 / 5.1: positional features (relative_position,
    is_initial, is_final, is_pre_numeral) are extracted per-word for
    distributional profile construction.
    """
    word_sign_ids: List[str]
    transliteration: str
    inscription_id: str
    inscription_type: str
    position_in_inscription: int
    total_words_in_inscription: int
    has_numeral_after: bool
    has_damage: bool = False

    @property
    def relative_position(self) -> float:
        """Position as a fraction: 0.0 = first, 1.0 = last."""
        if self.total_words_in_inscription <= 1:
            return 0.5
        return self.position_in_inscription / (self.total_words_in_inscription - 1)

    @property
    def is_initial(self) -> bool:
        return self.position_in_inscription == 0

    @property
    def is_final(self) -> bool:
        return self.position_in_inscription == self.total_words_in_inscription - 1


@dataclass
class CorpusInscription:
    """A single inscription from the SigLA corpus."""
    inscription_id: str
    inscription_type: str
    site: str
    words: List[CorpusWord]
    sign_count: int = 0
    word_count: int = 0


# ---------------------------------------------------------------------------
# Combined input
# ---------------------------------------------------------------------------

@dataclass
class GrammarInputData:
    """All inputs combined for Pillar 3 grammar induction.

    Provides Pillar 1, Pillar 2, and raw corpus data together with
    provenance hashes for reproducibility.
    """
    pillar1: Pillar1Data
    pillar2: Pillar2Data
    inscriptions: List[CorpusInscription]
    corpus_hash: str = ""


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

# Signs that are logograms representing commodities/ideograms (heuristic:
# codes starting with A3xx-A7xx or containing VAS/VIR/GRA/OLE/VIN/OLIV/
# FIC/SUS/OVIS/CAP/BOS/TELA).
_IDEOGRAM_PREFIXES = ("A3", "A4", "A5", "A6", "A7")
_IDEOGRAM_SUBSTRINGS = (
    "VAS", "VIR", "GRA", "OLE", "VIN", "OLIV", "FIC", "SUS",
    "OVIS", "CAP", "BOS", "TELA", "N800",
)


def _is_ideogram_or_numeral(ab_code: str) -> bool:
    """Heuristic: does this ab_code represent an ideogram or numeral?

    In the SigLA corpus, numerals and commodity ideograms appear as
    logograms with specific code patterns.  Pillar 3 uses this to
    detect ``is_pre_numeral`` for distributional profiles.
    """
    code = ab_code.strip().rstrip("?")
    if code.startswith("N"):
        return True  # Numeral codes
    for prefix in _IDEOGRAM_PREFIXES:
        if code.startswith(prefix):
            return True
    for sub in _IDEOGRAM_SUBSTRINGS:
        if sub in code:
            return True
    return False


def _parse_ab_codes(ab_codes_str: str) -> List[str]:
    """Parse a hyphen-separated ab_codes string into a list of sign IDs.

    Handles damage markers like ``[?]`` and uncertain readings like ``AB27?``.
    """
    if not ab_codes_str:
        return []
    parts = ab_codes_str.split("-")
    return [p.strip() for p in parts if p.strip()]


def load_pillar1(path: str | Path) -> Pillar1Data:
    """Load Pillar 1 output JSON into typed dataclasses.

    Args:
        path: Path to ``results/pillar1_output.json``.

    Returns:
        Pillar1Data with grid assignments, vowel inventory, phonotactics,
        and prebuilt lookup dictionaries.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If required top-level keys are missing.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Pillar 1 output not found: {path}")

    raw_bytes = path.read_bytes()
    pillar1_hash = hashlib.sha256(raw_bytes).hexdigest()

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for key in ("grid", "vowel_inventory", "phonotactics"):
        if key not in data:
            raise ValueError(f"Pillar 1 output missing required key: {key}")

    # Grid assignments
    grid_data = data["grid"]
    grid_assignments = [
        GridAssignment(
            sign_id=a["sign_id"],
            consonant_class=a["consonant_class"],
            vowel_class=a["vowel_class"],
            confidence=a.get("confidence", 0.0),
            evidence_count=a.get("evidence_count", 0),
        )
        for a in grid_data.get("assignments", [])
    ]
    consonant_count = grid_data.get("consonant_count", 0)
    vowel_count = grid_data.get("vowel_count", 0)

    # Vowel inventory
    vowel_data = data["vowel_inventory"]
    vowel_sign_ids = [
        s["sign_id"] for s in vowel_data.get("signs", [])
    ]

    # Phonotactics
    phon_data = data["phonotactics"]
    favored_bigrams = [
        PhonotacticBigram(
            sign_i=b["sign_i"],
            sign_j=b["sign_j"],
            bigram_type="favored",
            observed=b.get("observed", 0),
            expected=b.get("expected", 0.0),
            std_residual=b.get("std_residual", 0.0),
            p_value_corrected=b.get("p_value_corrected", 1.0),
        )
        for b in phon_data.get("favored_bigrams", [])
    ]
    forbidden_bigrams = [
        PhonotacticBigram(
            sign_i=b["sign_i"],
            sign_j=b["sign_j"],
            bigram_type="forbidden",
            observed=b.get("observed", 0),
            expected=b.get("expected", 0.0),
            std_residual=b.get("std_residual", 0.0),
            p_value_corrected=b.get("p_value_corrected", 1.0),
        )
        for b in phon_data.get("forbidden_bigrams", [])
    ]

    sign_to_grid = {a.sign_id: a for a in grid_assignments}
    favored_set = {(b.sign_i, b.sign_j) for b in favored_bigrams}

    return Pillar1Data(
        grid_assignments=grid_assignments,
        consonant_count=consonant_count,
        vowel_count=vowel_count,
        vowel_sign_ids=vowel_sign_ids,
        favored_bigrams=favored_bigrams,
        forbidden_bigrams=forbidden_bigrams,
        sign_to_grid=sign_to_grid,
        favored_bigram_set=favored_set,
        pillar1_hash=pillar1_hash,
    )


def load_pillar2(path: str | Path) -> Pillar2Data:
    """Load Pillar 2 output JSON into typed dataclasses.

    Args:
        path: Path to ``results/pillar2_output.json``.

    Returns:
        Pillar2Data with segmented lexicon, affix inventory, paradigm table,
        morphological word classes, and prebuilt lookups.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If required top-level keys are missing.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Pillar 2 output not found: {path}")

    raw_bytes = path.read_bytes()
    pillar2_hash = hashlib.sha256(raw_bytes).hexdigest()

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for key in ("segmented_lexicon", "affix_inventory", "paradigm_table",
                "morphological_word_classes"):
        if key not in data:
            raise ValueError(f"Pillar 2 output missing required key: {key}")

    # Segmented lexicon
    segmented_lexicon: List[SegmentedWord] = []
    for w in data["segmented_lexicon"]:
        seg = w["segmentation"]
        segmented_lexicon.append(SegmentedWord(
            word_sign_ids=w["word_sign_ids"],
            stem=seg["stem"],
            suffixes=seg.get("suffixes", []),
            prefixes=seg.get("prefixes", []),
            segmentation_confidence=seg.get("segmentation_confidence", 0.0),
            frequency=w["frequency"],
            inscription_types=w.get("inscription_types", []),
            method=w.get("method", ""),
        ))

    # Affix inventory
    affix_data = data["affix_inventory"]
    suffixes = [
        AffixEntry(
            signs=a["signs"],
            frequency=a["frequency"],
            n_distinct_stems=a["n_distinct_stems"],
            productivity=a.get("productivity", 0.0),
            classification=a.get("classification", "ambiguous"),
            paradigm_classes=a.get("paradigm_classes", []),
        )
        for a in affix_data.get("suffixes", [])
    ]
    prefixes = [
        AffixEntry(
            signs=a["signs"],
            frequency=a["frequency"],
            n_distinct_stems=a["n_distinct_stems"],
            productivity=a.get("productivity", 0.0),
            classification=a.get("classification", "ambiguous"),
            paradigm_classes=a.get("paradigm_classes", []),
        )
        for a in affix_data.get("prefixes", [])
    ]

    # Paradigm table
    pt_data = data["paradigm_table"]
    paradigm_classes: List[ParadigmClass] = []
    for p in pt_data.get("paradigms", []):
        slots = [
            ParadigmSlot(
                slot_id=s["slot_id"],
                ending_signs=s["ending_signs"],
                frequency=s["frequency"],
                label=s.get("label", ""),
            )
            for s in p.get("slots", [])
        ]
        example_stems = [
            ParadigmStemExample(
                stem=e["stem"],
                attested_slots=e["attested_slots"],
                attested_forms=e.get("attested_forms", []),
            )
            for e in p.get("example_stems", [])
        ]
        paradigm_classes.append(ParadigmClass(
            class_id=p["class_id"],
            n_members=p["n_members"],
            slots=slots,
            example_stems=example_stems,
            completeness=p.get("completeness", 0.0),
        ))

    # Morphological word classes
    morph_classes = [
        MorphologicalWordClass(
            class_id=c["class_id"],
            label=c["label"],
            description=c.get("description", ""),
            n_stems=c["n_stems"],
            paradigm_classes=c.get("paradigm_classes", []),
        )
        for c in data["morphological_word_classes"]
    ]

    # --- Build lookups ---
    # Map stem tuple -> paradigm class ID (from paradigm examples)
    stem_to_paradigm: Dict[Tuple[str, ...], int] = {}
    for pc in paradigm_classes:
        for ex in pc.example_stems:
            stem_key = tuple(ex.stem)
            stem_to_paradigm[stem_key] = pc.class_id

    # Map stem tuple -> word class label and suffix list
    stem_to_word_class: Dict[Tuple[str, ...], str] = {}
    stem_to_suffixes: Dict[Tuple[str, ...], List[Tuple[str, ...]]] = {}
    word_ids_to_stem: Dict[Tuple[str, ...], Tuple[str, ...]] = {}

    for w in segmented_lexicon:
        stem_key = tuple(w.stem)
        word_key = tuple(w.word_sign_ids)
        word_ids_to_stem[word_key] = stem_key

        # Accumulate suffixes for this stem
        if stem_key not in stem_to_suffixes:
            stem_to_suffixes[stem_key] = []
        for suf in w.suffixes:
            suf_key = tuple(suf)
            if suf_key not in stem_to_suffixes[stem_key]:
                stem_to_suffixes[stem_key].append(suf_key)

    # Assign word class labels based on morphological classes + paradigm membership
    # Build set of paradigm class IDs for each morph class
    morph_label_by_paradigm: Dict[int, str] = {}
    for mc in morph_classes:
        for pc_id in mc.paradigm_classes:
            morph_label_by_paradigm[pc_id] = mc.label

    for stem_key, pc_id in stem_to_paradigm.items():
        label = morph_label_by_paradigm.get(pc_id, "unknown")
        stem_to_word_class[stem_key] = label

    # Stems not in any paradigm
    all_stems = {tuple(w.stem) for w in segmented_lexicon}
    for stem_key in all_stems:
        if stem_key not in stem_to_word_class:
            # Check if stem has suffixes -> unknown, else uninflected
            if stem_to_suffixes.get(stem_key):
                stem_to_word_class[stem_key] = "unknown"
            else:
                stem_to_word_class[stem_key] = "uninflected"

    return Pillar2Data(
        segmented_lexicon=segmented_lexicon,
        affix_inventory_suffixes=suffixes,
        affix_inventory_prefixes=prefixes,
        paradigm_classes=paradigm_classes,
        n_paradigm_classes=pt_data.get("n_paradigm_classes", len(paradigm_classes)),
        morphological_word_classes=morph_classes,
        stem_to_word_class=stem_to_word_class,
        stem_to_paradigm_class=stem_to_paradigm,
        stem_to_suffixes=stem_to_suffixes,
        word_ids_to_stem=word_ids_to_stem,
        pillar2_hash=pillar2_hash,
    )


def load_corpus(
    path: str | Path,
    pillar2: Optional[Pillar2Data] = None,
) -> List[CorpusInscription]:
    """Load the SigLA corpus JSON into typed dataclasses.

    Each word in each inscription is converted to a ``CorpusWord`` with
    positional context (position_in_inscription, total_words_in_inscription,
    has_numeral_after).

    The ``word_sign_ids`` are extracted from the ``ab_codes`` field in the
    corpus, splitting on hyphens and filtering out damage markers.

    Args:
        path: Path to ``data/sigla_full_corpus.json``.
        pillar2: Optional Pillar 2 data for enrichment (unused currently,
            reserved for future stem lookup during loading).

    Returns:
        List of CorpusInscription, each containing CorpusWord entries.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the corpus format is unexpected.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Corpus file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        raw_inscriptions = data.get("inscriptions", [])
    elif isinstance(data, list):
        raw_inscriptions = data
    else:
        raise ValueError(f"Unexpected corpus format: {type(data)}")

    inscriptions: List[CorpusInscription] = []

    for raw_insc in raw_inscriptions:
        insc_id = raw_insc.get("id", "")
        insc_type = raw_insc.get("type", "")
        site = raw_insc.get("site", "")
        sign_count = raw_insc.get("sign_count", 0)
        raw_words = raw_insc.get("words", [])
        word_count = len(raw_words)

        if word_count == 0:
            continue

        # First pass: parse ab_codes for all words (needed for
        # has_numeral_after lookahead), filtering empty/damage-only entries.
        parsed_words: List[Tuple[List[str], str, bool, int]] = []
        for i, rw in enumerate(raw_words):
            ab_codes_str = rw.get("ab_codes", "")
            word_sign_ids = _parse_ab_codes(ab_codes_str)
            transliteration = rw.get("transliteration", "")
            has_damage = rw.get("has_damage", False) or rw.get(
                "has_damage_marker", False
            )

            # Skip empty words (empty ab_codes) and damage-only words
            # where all signs are [?] markers.
            real_signs = [
                s for s in word_sign_ids
                if s not in ("[?]", "?") and not s.startswith("[")
            ]
            if not real_signs:
                continue

            parsed_words.append((word_sign_ids, transliteration, has_damage, i))

        # Recount after filtering
        effective_word_count = len(parsed_words)
        if effective_word_count == 0:
            continue

        corpus_words: List[CorpusWord] = []

        for pos, (word_sign_ids, transliteration, has_damage, orig_idx) in enumerate(parsed_words):
            # Check if the next valid word is a numeral/ideogram.
            has_numeral_after = False
            if pos + 1 < effective_word_count:
                next_ids = parsed_words[pos + 1][0]
                real_next = [
                    c for c in next_ids
                    if c not in ("[?]", "?") and not c.startswith("[")
                ]
                if real_next and all(
                    _is_ideogram_or_numeral(c) for c in real_next
                ):
                    has_numeral_after = True

            corpus_words.append(CorpusWord(
                word_sign_ids=word_sign_ids,
                transliteration=transliteration,
                inscription_id=insc_id,
                inscription_type=insc_type,
                position_in_inscription=pos,
                total_words_in_inscription=effective_word_count,
                has_numeral_after=has_numeral_after,
                has_damage=has_damage,
            ))

        inscriptions.append(CorpusInscription(
            inscription_id=insc_id,
            inscription_type=insc_type,
            site=site,
            words=corpus_words,
            sign_count=sign_count,
            word_count=word_count,
        ))

    return inscriptions


def load_all(
    pillar1_path: str | Path = "results/pillar1_output.json",
    pillar2_path: str | Path = "results/pillar2_output.json",
    corpus_path: str | Path = "data/sigla_full_corpus.json",
) -> GrammarInputData:
    """Load all inputs for Pillar 3 grammar induction.

    Convenience function that loads Pillar 1, Pillar 2, and the corpus
    in one call.

    Args:
        pillar1_path: Path to Pillar 1 output JSON.
        pillar2_path: Path to Pillar 2 output JSON.
        corpus_path: Path to SigLA corpus JSON.

    Returns:
        GrammarInputData combining all inputs with provenance hashes.
    """
    p1 = load_pillar1(pillar1_path)
    p2 = load_pillar2(pillar2_path)
    inscriptions = load_corpus(corpus_path, pillar2=p2)

    # Compute corpus hash for provenance
    corpus_path = Path(corpus_path)
    corpus_hash = hashlib.sha256(corpus_path.read_bytes()).hexdigest()

    return GrammarInputData(
        pillar1=p1,
        pillar2=p2,
        inscriptions=inscriptions,
        corpus_hash=corpus_hash,
    )
