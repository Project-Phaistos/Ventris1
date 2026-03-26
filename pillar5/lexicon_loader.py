"""Pillar 5 Step 2 (partial): Load candidate language lexicons.

Loads IPA lexicons from ancient-scripts-datasets TSV files.
Each lexicon entry has: word, IPA transcription, and optionally a gloss
(English meaning via Concept_ID field).

TSV format (from ancient-scripts-datasets):
    Word  IPA  SCA  Source  Concept_ID  Cognate_Set_ID

Semantic scoring in Step 3 requires glosses. Languages without glosses
can still participate in phonological matching but with semantic_compatibility=null.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class LexiconEntry:
    """A single entry in a candidate language lexicon."""

    word: str
    ipa: str
    gloss: Optional[str]  # English meaning (from Concept_ID), None if unavailable
    source: str  # Data source (e.g., "northeuralex", "wikipron")


@dataclass
class CandidateLexicon:
    """A candidate language's full lexicon with metadata."""

    language_code: str  # ISO 639-3 code (e.g., "grc", "akk")
    language_name: str
    family: str
    plausibility: str  # HIGH / MEDIUM / LOW-MED / LOW / UNKNOWN / REFERENCE
    entries: List[LexiconEntry] = field(default_factory=list)

    @property
    def n_entries(self) -> int:
        return len(self.entries)

    @property
    def n_with_glosses(self) -> int:
        return sum(1 for e in self.entries if e.gloss is not None)

    @property
    def gloss_coverage(self) -> float:
        if self.n_entries == 0:
            return 0.0
        return self.n_with_glosses / self.n_entries

    @property
    def has_glosses(self) -> bool:
        """True if enough entries have glosses for semantic scoring."""
        return self.gloss_coverage >= 0.01  # At least 1% coverage


# Candidate languages from PRD Section 3.5 (geographically and temporally
# plausible for Bronze Age Crete)
CANDIDATE_LANGUAGES = {
    # --- Original lexicon-based candidates ---
    "grc": {"name": "Ancient Greek", "family": "Hellenic IE", "plausibility": "LOW-MED"},
    "akk": {"name": "Akkadian", "family": "Semitic", "plausibility": "MEDIUM"},
    "heb": {"name": "Hebrew", "family": "Semitic", "plausibility": "MEDIUM"},
    "arb": {"name": "Arabic", "family": "Semitic", "plausibility": "LOW"},
    "arc": {"name": "Aramaic", "family": "Semitic", "plausibility": "LOW-MED"},
    "lat": {"name": "Latin", "family": "Italic IE", "plausibility": "LOW"},
    "san": {"name": "Sanskrit", "family": "Indo-Aryan IE", "plausibility": "LOW"},
    "ell": {"name": "Modern Greek", "family": "Hellenic IE", "plausibility": "LOW"},
    "hun": {"name": "Hungarian", "family": "Uralic", "plausibility": "LOW"},
    "fin": {"name": "Finnish", "family": "Uralic", "plausibility": "LOW"},
    "tur": {"name": "Turkish", "family": "Turkic", "plausibility": "LOW"},
    "kat": {"name": "Georgian", "family": "Kartvelian", "plausibility": "LOW"},
    "eus": {"name": "Basque", "family": "Isolate", "plausibility": "LOW"},
    "got": {"name": "Gothic", "family": "Germanic IE", "plausibility": "LOW"},
    "cop": {"name": "Coptic", "family": "Afro-Asiatic", "plausibility": "LOW-MED"},
    # --- PP fleet languages (from Phonetic Prior production run) ---
    "hit": {"name": "Hittite", "family": "Anatolian IE", "plausibility": "MEDIUM"},
    "elx": {"name": "Elamite", "family": "Isolate", "plausibility": "MEDIUM"},
    "uga": {"name": "Ugaritic", "family": "Semitic", "plausibility": "MEDIUM"},
    "phn": {"name": "Phoenician", "family": "Semitic", "plausibility": "MEDIUM"},
    "peo": {"name": "Old Persian", "family": "Iranian IE", "plausibility": "LOW-MED"},
    "xlc": {"name": "Lycian", "family": "Anatolian IE", "plausibility": "HIGH"},
    "xld": {"name": "Lydian", "family": "Anatolian IE", "plausibility": "HIGH"},
    "xpg": {"name": "Phrygian", "family": "Paleo-Balkan IE", "plausibility": "MEDIUM"},
    "xrr": {"name": "Eteocretan", "family": "Pre-Greek", "plausibility": "HIGH"},
    "ave": {"name": "Avestan", "family": "Iranian IE", "plausibility": "LOW"},
    "sem-pro": {"name": "Proto-Semitic", "family": "Afro-Asiatic", "plausibility": "MEDIUM"},
    "ine-pro": {"name": "Proto-IE", "family": "Indo-European", "plausibility": "LOW-MED"},
    "dra-pro": {"name": "Proto-Dravidian", "family": "Dravidian", "plausibility": "LOW"},
    "ccs-pro": {"name": "Proto-Caucasian", "family": "Caucasian", "plausibility": "LOW"},
    "cms": {"name": "Messapic", "family": "Pre-Greek", "plausibility": "MEDIUM"},
    "xcr": {"name": "Carian", "family": "Anatolian IE", "plausibility": "MEDIUM"},
    "xle": {"name": "Lepontic", "family": "Celtic IE", "plausibility": "LOW"},
    "xur": {"name": "Urartian", "family": "Hurro-Urartian", "plausibility": "MEDIUM"},
}


def _parse_gloss(concept_id: str) -> Optional[str]:
    """Convert a Concept_ID field to a human-readable gloss.

    The Concept_ID field uses formats like:
    - "FATHER" -> "father"
    - "EARTH (SOIL)" -> "earth (soil)"
    - "-" -> None (no gloss available)
    - "" -> None
    """
    if not concept_id or concept_id.strip() == "-":
        return None
    return concept_id.strip().lower()


def load_lexicon(
    tsv_path: str | Path,
    language_code: str,
    max_entries: int = 0,
) -> CandidateLexicon:
    """Load a single candidate language lexicon from a TSV file.

    Args:
        tsv_path: Path to the TSV file (Word, IPA, SCA, Source, Concept_ID, Cognate_Set_ID)
        language_code: ISO 639-3 code for this language
        max_entries: Maximum entries to load (0 = no limit)

    Returns:
        CandidateLexicon with all parsed entries.
    """
    path = Path(tsv_path)
    if not path.exists():
        raise FileNotFoundError(f"Lexicon file not found: {path}")

    lang_meta = CANDIDATE_LANGUAGES.get(language_code, {})

    entries: List[LexiconEntry] = []
    seen_ipa: set = set()  # Deduplicate by IPA

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            word = row.get("Word", "").strip()
            ipa = row.get("IPA", "").strip()
            source = row.get("Source", "").strip()
            concept_id = row.get("Concept_ID", "").strip()

            if not word or not ipa:
                continue

            # Deduplicate by IPA to avoid inflated match counts
            if ipa in seen_ipa:
                continue
            seen_ipa.add(ipa)

            gloss = _parse_gloss(concept_id)

            entries.append(LexiconEntry(
                word=word,
                ipa=ipa,
                gloss=gloss,
                source=source,
            ))

            if max_entries > 0 and len(entries) >= max_entries:
                break

    return CandidateLexicon(
        language_code=language_code,
        language_name=lang_meta.get("name", language_code),
        family=lang_meta.get("family", "Unknown"),
        plausibility=lang_meta.get("plausibility", "UNKNOWN"),
        entries=entries,
    )


def load_all_lexicons(
    lexicon_dir: str | Path,
    language_codes: Optional[Sequence[str]] = None,
    max_entries_per_language: int = 0,
) -> Dict[str, CandidateLexicon]:
    """Load lexicons for all candidate languages.

    Args:
        lexicon_dir: Directory containing {lang_code}.tsv files
        language_codes: Which languages to load (default: all in CANDIDATE_LANGUAGES)
        max_entries_per_language: Max entries per language (0 = no limit)

    Returns:
        Dict mapping language code to CandidateLexicon.
    """
    lexicon_dir = Path(lexicon_dir)
    if language_codes is None:
        language_codes = list(CANDIDATE_LANGUAGES.keys())

    lexicons: Dict[str, CandidateLexicon] = {}
    for code in language_codes:
        tsv_path = lexicon_dir / f"{code}.tsv"
        if not tsv_path.exists():
            continue
        lexicons[code] = load_lexicon(
            tsv_path, code, max_entries=max_entries_per_language
        )

    return lexicons


def audit_gloss_availability(
    lexicons: Dict[str, CandidateLexicon],
) -> List[Dict[str, Any]]:
    """Audit gloss availability across all loaded lexicons.

    Returns a list of dicts with coverage info per language,
    sorted by coverage descending.
    """
    audit = []
    for code, lex in lexicons.items():
        audit.append({
            "language_code": code,
            "language_name": lex.language_name,
            "family": lex.family,
            "n_entries": lex.n_entries,
            "n_with_glosses": lex.n_with_glosses,
            "gloss_coverage": round(lex.gloss_coverage, 4),
            "usable_for_semantic": lex.has_glosses,
        })
    audit.sort(key=lambda x: -x["gloss_coverage"])
    return audit
