# Claim-review reference data

This directory supports the inherited deterministic rule and policy-review components. It is separate from the [synthetic ambulance ML dataset](../../artifacts/ambulance).

| Reference | Purpose | Implementation |
|---|---|---|
| NCCI PTP | Procedure-code combinations | `rules/ncci_loader.py` and `rules/ncci.py` |
| MUE | Reported units | `rules/mue_loader.py` and `rules/mue.py` |
| ICD-10-CM | Diagnosis reference | `rules/icd10_loader.py` and `rules/icd10.py` |
| LCD/NCD policy context | Coverage/coding agent context | `retrieval/` and the agent retrieval functions |

Large reference assets are not included in a normal clone. Optional maintainer-configured release assets and local files can populate rule references; curated fallback data can otherwise be used. Inspect the UI's data-source status and each policy finding's provenance. Rule-reference availability is not proof that a populated ChromaDB policy index exists.

Consult the actual loaders for supported file names/formats rather than assuming CSV. HCPCS Level II recognition is a limited curated set, not a comprehensive file-backed catalogue. Preserve applicable source terms and code-set notices; do not assume every third-party code description is unrestricted simply because it is referenced by CMS.

Use no real patient information. See the [project README](../../README.md), [model card](../../docs/ambulance-model-card.md) and [technical-debt notes](../../docs/Technical_Debt_Register.md) for scope and limitations.
