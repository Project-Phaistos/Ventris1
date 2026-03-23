# Data

## SigLA Full Corpus

The primary corpus file `sigla_full_corpus.json` (2.1MB) is too large for git.

**Source:** Project-Phaistos/ancient-scripts-datasets on GitHub
**Version:** 2.0.0 (2026-02-28)

To download:
```bash
gh api repos/Nacryos/Project-Phaistos/git/blobs/$(gh api repos/Nacryos/Project-Phaistos/contents/ancient-scripts-datasets/data/linear_a/sigla_full_corpus.json --jq '.sha') --jq '.content' | base64 -d > data/sigla_full_corpus.json
```

**Expected SHA-256:** Verify with `sha256sum data/sigla_full_corpus.json` and compare against the hash in the Pillar 1 output metadata.

## sign_to_ipa.json

Linear B phonetic value mappings. 34 entries. Used only for post-hoc LB validation (Step 6), never as input to discovery algorithms.
