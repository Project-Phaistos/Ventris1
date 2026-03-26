#!/usr/bin/env python3
"""
extract_glosses.py -- Download and parse glossary data from three academic sources.

Sources:
  1. eDiAna Lydian   (CC BY-SA 4.0)  ~453 entries
  2. IDS Elamite     (CC BY 4.0)     ~340 entries
  3. eCUT/ORACC Urartian (CC0)       ~147 entries

DATA MAY ONLY ENTER THE DATASET THROUGH CODE THAT DOWNLOADS IT FROM AN
EXTERNAL SOURCE.  This script fetches raw data, saves it for audit, then
parses and writes cleaned TSV files.

Usage:
    python -m pillar5.scripts.extract_glosses
    python pillar5/scripts/extract_glosses.py
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PILLAR5_DIR = SCRIPT_DIR.parent
DATA_DIR = PILLAR5_DIR / "data"
RAW_DIR = DATA_DIR / "raw"

# Ensure output directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

UA = "Ventris1-Academic-Research/1.0 (Linear A decipherment project)"
TIMESTAMP = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove HTML/XML tags from a string (e.g. eDiAna inline styling)."""
    return _HTML_TAG_RE.sub("", text)


def _tsv_header(source_name: str, source_url: str, license_: str) -> str:
    """Return a comment header block for a TSV file."""
    lines = [
        f"# Source: {source_name}",
        f"# URL: {source_url}",
        f"# License: {license_}",
        f"# Downloaded: {TIMESTAMP}",
        f"# Script: pillar5/scripts/extract_glosses.py",
        "",
    ]
    return "\n".join(lines)


def _write_tsv(
    path: Path,
    rows: list[dict],
    header_comment: str,
) -> None:
    """Write rows (list of dicts with word/translation/source/source_url) to TSV."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(header_comment)
        fh.write("word\ttranslation\tsource\tsource_url\n")
        for row in rows:
            w = _strip_html(row["word"]).replace("\t", " ").replace("\n", " ").strip()
            t = _strip_html(row["translation"]).replace("\t", " ").replace("\n", " ").strip()
            s = row["source"].replace("\t", " ")
            u = row["source_url"].replace("\t", " ")
            fh.write(f"{w}\t{t}\t{s}\t{u}\n")


# ===================================================================
# Source 1: eDiAna Lydian
# ===================================================================
def extract_ediana_lydian() -> int:
    """POST to eDiAna API, save raw JSON, parse glosses, write TSV."""
    print("\n=== Source 1: eDiAna Lydian ===")

    url = "https://www.ediana.gwi.uni-muenchen.de/includes/api.php"
    body = "headword_spec=&headword_sub=Lydian&headword_search=true"
    raw_path = RAW_DIR / "ediana_lydian_raw.json"
    out_path = DATA_DIR / "ediana_lydian_glosses.tsv"

    # --- Download ---
    print(f"  POST {url}")
    req = Request(
        url,
        data=body.encode("utf-8"),
        headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as resp:
            raw_bytes = resp.read()
    except (HTTPError, URLError) as exc:
        print(f"  FAILED to download eDiAna Lydian: {exc}")
        raise

    # Save raw
    raw_path.write_bytes(raw_bytes)
    print(f"  Raw saved: {raw_path} ({len(raw_bytes):,} bytes)")

    # --- Parse ---
    data = json.loads(raw_bytes)

    # The API may return a list directly or wrap it in a dict
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        # Try common wrapper keys
        for key in ("results", "data", "entries", "headwords"):
            if key in data:
                entries = data[key]
                break
        else:
            # If the dict itself looks like it maps IDs to entries, flatten
            if all(isinstance(v, dict) for v in data.values()):
                entries = list(data.values())
            else:
                print(f"  ERROR: Unexpected JSON structure. Top-level keys: {list(data.keys())[:20]}")
                raise ValueError("Cannot find entry list in eDiAna response")
    else:
        raise ValueError(f"Unexpected JSON type: {type(data)}")

    print(f"  Entries in raw response: {len(entries)}")

    rows: list[dict] = []
    skipped = 0
    for entry in entries:
        # Extract word form -- try several possible field names
        word = None
        for field in ("L_lemma_full", "lemma_full", "lemma", "headword", "hw"):
            if field in entry and entry[field]:
                word = str(entry[field]).strip()
                break

        # Extract translation
        trans = None
        for field in ("L_trans", "trans", "translation", "meaning", "gloss"):
            if field in entry and entry[field]:
                trans = str(entry[field]).strip()
                break

        if not word:
            skipped += 1
            continue

        rows.append({
            "word": word,
            "translation": trans or "",
            "source": "eDiAna",
            "source_url": "https://www.ediana.gwi.uni-muenchen.de/",
        })

    # --- Write ---
    header = _tsv_header(
        "eDiAna Digital Philological-Etymological Dictionary of the Minor Ancient Anatolian Corpus Languages (Lydian)",
        "https://www.ediana.gwi.uni-muenchen.de/",
        "CC BY-SA 4.0",
    )
    _write_tsv(out_path, rows, header)
    print(f"  Extracted: {len(rows)} glosses (skipped {skipped} entries without word form)")
    print(f"  Output: {out_path}")
    return len(rows)


# ===================================================================
# Source 2: IDS Elamite
# ===================================================================
def extract_ids_elamite() -> int:
    """GET IDS contribution 216 (Elamite), save raw, parse, write TSV."""
    print("\n=== Source 2: IDS Elamite ===")

    url = "https://ids.clld.org/contributions/216.tab"
    raw_path = RAW_DIR / "ids_elamite_raw.tsv"
    out_path = DATA_DIR / "ids_elamite_glosses.tsv"

    # --- Download ---
    print(f"  GET {url}")
    req = Request(url, headers={"User-Agent": UA})
    try:
        with urlopen(req, timeout=60) as resp:
            raw_bytes = resp.read()
    except (HTTPError, URLError) as exc:
        print(f"  FAILED to download IDS Elamite: {exc}")
        raise

    raw_path.write_bytes(raw_bytes)
    print(f"  Raw saved: {raw_path} ({len(raw_bytes):,} bytes)")

    # --- Parse ---
    text = raw_bytes.decode("utf-8")
    lines = text.strip().split("\n")
    if not lines:
        raise ValueError("Empty response from IDS")

    # Parse header
    header_line = lines[0]
    cols = header_line.split("\t")
    col_idx = {c.strip(): i for i, c in enumerate(cols)}
    print(f"  Columns: {cols}")

    # Find the right columns -- try several plausible names
    word_col = None
    for name in ("Elamite_Phonemic", "Form", "Value", "Transcription", "Word"):
        if name in col_idx:
            word_col = col_idx[name]
            print(f"  Word column: '{name}' (index {word_col})")
            break

    meaning_col = None
    for name in ("meaning", "Meaning", "Parameter", "Gloss", "English"):
        if name in col_idx:
            meaning_col = col_idx[name]
            print(f"  Meaning column: '{name}' (index {meaning_col})")
            break

    if word_col is None:
        # Fallback: scan all columns for one that looks like word forms
        print(f"  WARNING: Could not identify word column. Available: {cols}")
        print("  Attempting heuristic column detection...")
        # Print first data row for diagnosis
        if len(lines) > 1:
            print(f"  First data row: {lines[1]}")
        raise ValueError("Cannot identify word column in IDS data")

    if meaning_col is None:
        print(f"  WARNING: Could not identify meaning column. Available: {cols}")
        raise ValueError("Cannot identify meaning column in IDS data")

    rows: list[dict] = []
    skipped = 0
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split("\t")
        word = fields[word_col].strip() if word_col < len(fields) else ""
        meaning = fields[meaning_col].strip() if meaning_col < len(fields) else ""

        if not word or word == "-" or word == "":
            skipped += 1
            continue

        rows.append({
            "word": word,
            "translation": meaning,
            "source": "IDS (Intercontinental Dictionary Series)",
            "source_url": "https://ids.clld.org/contributions/216",
        })

    # --- Write ---
    header = _tsv_header(
        "IDS — Intercontinental Dictionary Series, Elamite (contribution 216)",
        "https://ids.clld.org/contributions/216",
        "CC BY 4.0",
    )
    _write_tsv(out_path, rows, header)
    print(f"  Extracted: {len(rows)} glosses (skipped {skipped} entries without word form)")
    print(f"  Output: {out_path}")
    return len(rows)


# ===================================================================
# Source 3: eCUT / ORACC Urartian
# ===================================================================
def extract_ecut_urartian() -> int:
    """GET eCUT zip from ORACC, extract Urartian glossary JSON, parse, write TSV."""
    print("\n=== Source 3: eCUT/ORACC Urartian ===")

    url = "https://build-oracc.museum.upenn.edu/json/ecut.zip"
    raw_path = RAW_DIR / "ecut_urartian_raw.zip"
    out_path = DATA_DIR / "ecut_urartian_glosses.tsv"

    # --- Download ---
    print(f"  GET {url}")
    req = Request(url, headers={"User-Agent": UA})
    try:
        with urlopen(req, timeout=120) as resp:
            raw_bytes = resp.read()
    except (HTTPError, URLError) as exc:
        print(f"  FAILED to download eCUT zip: {exc}")
        raise

    raw_path.write_bytes(raw_bytes)
    print(f"  Raw saved: {raw_path} ({len(raw_bytes):,} bytes)")

    # --- Extract and find glossary ---
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw_bytes))
    except zipfile.BadZipFile as exc:
        print(f"  ERROR: Downloaded file is not a valid zip: {exc}")
        raise

    all_files = zf.namelist()
    print(f"  Files in zip: {len(all_files)}")

    # Find Urartian glossary: gloss-xur-*.json  (xur = Urartian ISO 639-3)
    gloss_files = [f for f in all_files if "gloss" in f.lower() and f.endswith(".json")]
    xur_files = [f for f in gloss_files if "xur" in f.lower()]

    if xur_files:
        # Prefer the base glossary (gloss-xur.json) over period-specific subsets
        # (gloss-xur-946.json, gloss-xur-944.json, etc.)
        base_xur = [f for f in xur_files if f.endswith("gloss-xur.json")]
        gloss_file = base_xur[0] if base_xur else xur_files[0]
    elif gloss_files:
        print(f"  WARNING: No xur glossary found. Available glossary files: {gloss_files}")
        # Try the first glossary file
        gloss_file = gloss_files[0]
    else:
        # List some files for diagnosis
        json_files = [f for f in all_files if f.endswith(".json")][:20]
        print(f"  ERROR: No glossary JSON found. JSON files: {json_files}")
        print(f"  All files (first 30): {all_files[:30]}")
        raise FileNotFoundError("No glossary JSON in eCUT zip")

    print(f"  Using glossary file: {gloss_file}")
    gloss_bytes = zf.read(gloss_file)
    gloss_data = json.loads(gloss_bytes)

    # --- Parse ---
    # ORACC glossary JSON structure: { "entries": { "ID": { "cf": ..., "gw": ... } } }
    # or it may be nested under "instances" or "members"
    rows: list[dict] = []

    def _extract_from_entries(obj: dict | list, depth: int = 0) -> None:
        """Recursively find entries with cf/gw fields."""
        if depth > 10:
            return
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    _extract_from_entries(item, depth + 1)
            return
        if not isinstance(obj, dict):
            return

        # Check if this dict itself is an entry
        cf = obj.get("cf", "")
        gw = obj.get("gw", "")
        if cf and gw:
            rows.append({
                "word": str(cf).strip(),
                "translation": str(gw).strip(),
                "source": "eCUT/ORACC",
                "source_url": "https://oracc.museum.upenn.edu/ecut/",
            })

        # Recurse into sub-dicts and lists
        for key, val in obj.items():
            if isinstance(val, (dict, list)):
                _extract_from_entries(val, depth + 1)

    _extract_from_entries(gloss_data)

    # Deduplicate by (word, translation)
    seen = set()
    unique_rows: list[dict] = []
    for row in rows:
        key = (row["word"], row["translation"])
        if key not in seen:
            seen.add(key)
            unique_rows.append(row)

    # --- Write ---
    header = _tsv_header(
        "eCUT — electronic Corpus of Urartian Texts (ORACC), Urartian glossary",
        "https://oracc.museum.upenn.edu/ecut/",
        "CC0 1.0 (Public Domain)",
    )
    _write_tsv(out_path, unique_rows, header)
    print(f"  Extracted: {len(unique_rows)} unique glosses (from {len(rows)} raw entries)")
    print(f"  Output: {out_path}")
    return len(unique_rows)


# ===================================================================
# Main
# ===================================================================
def main() -> None:
    print("=" * 60)
    print("Ventris1 Pillar 5 — Gloss Extraction")
    print(f"Timestamp: {TIMESTAMP}")
    print("=" * 60)

    results: dict[str, int | str] = {}

    # Source 1
    try:
        results["eDiAna Lydian"] = extract_ediana_lydian()
    except Exception as exc:
        results["eDiAna Lydian"] = f"FAILED: {exc}"
        print(f"\n  *** eDiAna Lydian extraction FAILED: {exc}")

    # Source 2
    try:
        results["IDS Elamite"] = extract_ids_elamite()
    except Exception as exc:
        results["IDS Elamite"] = f"FAILED: {exc}"
        print(f"\n  *** IDS Elamite extraction FAILED: {exc}")

    # Source 3
    try:
        results["eCUT Urartian"] = extract_ecut_urartian()
    except Exception as exc:
        results["eCUT Urartian"] = f"FAILED: {exc}"
        print(f"\n  *** eCUT Urartian extraction FAILED: {exc}")

    # --- Summary ---
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total = 0
    failures = 0
    for source, count in results.items():
        if isinstance(count, int):
            print(f"  {source}: {count} entries")
            total += count
        else:
            print(f"  {source}: {count}")
            failures += 1

    print(f"\n  Total extracted: {total} entries")
    if failures:
        print(f"  FAILURES: {failures}")
        sys.exit(1)
    else:
        print("  All sources succeeded.")


if __name__ == "__main__":
    main()
