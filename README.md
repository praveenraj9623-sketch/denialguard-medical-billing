# DenialGuard

A portfolio / demo project: agentic pre-submission claim review that catches denial risks before a claim leaves the building. A deterministic rule layer (NCCI, MUE, NPI, code validity) and two citation-grounded LLM agents — Coverage Validation (medical necessity) and Coding Validation (diagnosis specificity, coding defensibility, payer scrutiny risk) — feed a single Unified Review that synthesizes a denial risk score. Every AI finding is backed by a cited LCD/NCD source. Humans make every final call.


The separate **Ambulance prediction** tab uses a fitted scikit-learn model trained
on simulated ambulance claims. It works entirely offline, is clearly labelled
**Trained on synthetic data**, and is separate from rule risk and Groq findings.
Its metrics measure agreement with invented outcomes, not real payer accuracy.

A Documentation Review Agent remains part of the product vision and roadmap but is currently deferred (not implemented, not required for this MVP) — see `docs/Roadmap.md` Phase 6.

Built on free public data: NPPES NPI Registry, CMS Coverage API (NCDs/LCDs), NCCI PTP and MUE files, the real CMS ICD-10-CM order file. HCPCS Level II is recognized via a small curated common-code set, not a full reference-file loader (see `docs/Technical_Debt_Register.md` TD-06). **Synthetic data only — no PHI, no real claims.**

> **Not for clinical or billing use.** This is a synthetic-data prototype demonstrating an architecture pattern, not production healthcare software. It is not HIPAA certified and has not been validated against real claims, real payer adjudication, or real patient data. Do not use it to make actual coverage, coding, or billing decisions.

## Product Screenshots

![Denial Prevention Copilot reference architecture](docs/assets/denial-copilot-architecture-overview.png)

Reference architecture and product overview

![Live Denial Prevention Copilot app snapshot](docs/assets/denial-copilot-live-app-snapshot.png)

Live Denial Prevention Copilot app snapshot

## Current Public Release

**V1.0 MVP**

Denial Prevention Copilot has reached MVP status and is publicly released.

The MVP includes:

- Deterministic claim validation
- NPI validation
- NCCI bundling checks
- MUE validation
- ICD-10 validation
- HCPCS validation
- Modifier validation
- Coverage Validation Agent
- Coding Validation Agent
- Citation grounding
- Supporting Policies Reviewed
- Risk scoring
- Human review workflow
- Audit trail
- Manual claim review
- Streamlit Cloud deployment hardening
- Self-healing audit database initialization
- Graceful ChromaDB fallback behavior
- Live CMS rule-layer support using maintainer-managed GitHub Release Assets
- Session-scoped Anthropic API key entry via the UI (no `.env` required for end users)
- Expanded automated test coverage (564+ passing tests)

Engineering release history continues internally through v1.11.x releases, which represent deployment, reliability, testing, and operational hardening improvements beyond the original MVP scope. The public V1.0 MVP designation corresponds to engineering releases v1.8a (UI polish and first-time UX), v1.8b (citation transparency / Supporting Policies Reviewed), v1.9.x (Streamlit Cloud deployment readiness, audit-schema self-healing, ChromaDB graceful fallback, and manual-claim AI execution parity), v1.11-live-cms (optional Live CMS rule-layer data via GitHub Release Assets), v1.11.1 (CMS/Chroma policy retrieval enhancement deferred — tracked as TD-28), and v1.11.2 (session-scoped Anthropic API key via the UI gear icon). The in-app "Getting Started" → "What Changed" notes show only the public-facing V1.0 MVP summary; full engineering version history — v1.0 through v1.11.2 — is preserved in `docs/Roadmap.md`. Historical upstream test and model results below predate the Groq migration. The current default is Groq `openai/gpt-oss-20b` (override with `GROQ_MODEL`). See `docs/Technical_Debt_Register.md` for the full TD-24 calibration history and the Haiku/Sonnet/Opus model comparison behind that choice.

## Demonstrated Capabilities

- Deterministic claim validation
- NCCI bundling detection
- MUE validation
- ICD-10 validation
- Coverage policy review
- Coding validation
- Human-in-the-loop review workflow
- Audit trail and governance
- Explainable findings with citations
- Live CMS reference datasets (current implementation)

## Screenshots

| | |
|---|---|
| ![Header and landing state](docs/screenshots/01_header_and_landing.png) | ![Findings with source badges](docs/screenshots/03_findings_with_source_badges.png) |
| Header bar (AI status, data-source status, Getting Started) with the demo-scenario landing state | Findings with severity + source badges (Rule Engine / Coverage Agent / Coding Agent) |
| ![Supporting Policies Reviewed](docs/screenshots/04_supporting_policies_reviewed.png) | ![Getting Started dialog](docs/screenshots/05_getting_started_dialog.png) |
| "Supporting Policies Reviewed" — every policy an AI agent considered, not just the one it cited (TD-22) | The Getting Started onboarding dialog |

## Local setup (Windows, Python 3.11)

```powershell
Set-Location C:\AI-Projects\denialguard-medical-billing
py -3.11 -m venv .venv  # only when creating a new environment
.\.venv\Scripts\python.exe -m pip install -r requirements-demo.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m streamlit run app/main.py --server.port 8502
```

Stop the running server with Ctrl+C before restarting. The demo requirements omit
optional ChromaDB. Coverage and coding retrieval keep the curated UTF-8 JSON
policy fallback when ChromaDB is unavailable or the vector index is empty.
`requirements.txt` includes ChromaDB for optional vector retrieval.

## AI features and review states

Groq is the default live provider. Edit the root `.env` locally:

```dotenv
LLM_PROVIDER=groq
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
```

Fill in `GROQ_API_KEY` yourself, or use **Groq API Key → Enable AI** in the app
for a session-only key. The password field and saved session override are both
removed by **Clear Key**. Clearing an override restores any owner-configured key;
it does not delete environment variables or files.

Resolution order for nonblank values: session override (API keys only), OS
environment, repository-root `.env`, Streamlit Secrets, then defaults. A session
key for one provider never enables the other provider. `.env` is read explicitly
as UTF-8 without populating OS variables; environment settings win. Configuration
changes in files require a restart. Streamlit may itself expose top-level secrets
as environment variables, in which case those values occupy the environment tier.
Never commit credentials: `.env` and `.streamlit/secrets.toml` are Git-ignored.

Streamlit Secrets uses top-level TOML:

```toml
LLM_PROVIDER = "groq"
GROQ_API_KEY = "paste-your-key-locally"
GROQ_MODEL = "openai/gpt-oss-20b"
```

For optional legacy Anthropic support, set `LLM_PROVIDER=anthropic`,
`ANTHROPIC_API_KEY`, and optionally `ANTHROPIC_MODEL` (default `claude-sonnet-4-6`).
An Anthropic key is never required for Groq. Configured keys are **unverified**
until a requested review completes; loading the page makes no LLM request.

- **Rule-only review:** deterministic checks ran; AI checks did not run. Missing
  keys prevent LLM requests. Invalid NPI short-circuits all subsequent checks.
- **Pre-generated demonstration results:** separately labelled, read-only cached
  examples for selected synthetic claims; never presented as a live review.
- **Live Groq review:** coverage and coding requests both completed with valid
  allowed tool calls. A valid no-concern tool is required to report no concerns.
- **AI review failed or incomplete:** provider/API/response errors or missing
  retrieval context prevented completion. Available rule and AI findings remain
  visible, escalation is required, and no overall successful clean review is shown.

The shared adapter uses Groq's [chat-completions API](https://console.groq.com/docs/api-reference)
and [local tool format](https://console.groq.com/docs/tool-use/local-tool-calling),
checked on November 8, 2026: `tool_choice="required"`,
`parallel_tool_calls=false`, `max_completion_tokens=4096`. Tool responses are
validated as data against an allowlist; no model-selected function is executed.
Citations must reference retrieved documents, displayed excerpts come from
retrieved text, and confidence must be supplied as a finite number in [0, 1].
Run logs contain safe error categories rather than raw provider exceptions.

**Reviewer guide:** CPT/HCPCS codes describe services, ICD-10 codes describe
diagnoses, modifiers add service details, units count billed services, NPI
identifies the provider, and payer names the insurer. Full Review adds configured
AI policy checks to rules; Rule-only skips AI. **Accept means agreeing with a
finding, not approving a claim.** Human decisions are saved as append-only audit
records. The risk label is a deterministic synthesis, not a trained classifier.
A separate **Ambulance prediction** tab now runs a genuine saved logistic-regression
classifier trained on synthetic ambulance data; it does not change that rule risk label.
See [the model card](docs/ambulance-model-card.md) for the simulator, isolation checks and measured results.

## UI overview (v1.8a/v1.8b)

The app has no sidebar — the reviewer name field and two status pills live in a header bar at the top of the page:

- **AI status:** provider-specific key configuration (unverified), with a session key popover; completed review state is shown with each result.
- **Data Source Status pill** — defaults to "⚪ Data: Not Refreshed" on every fresh page load; nothing is checked or downloaded automatically, so startup stays fast regardless of CMS reference data size. Click the pill to open a popover with a "🔍 Check CMS Data Availability" button — only then does it call `rules/data_source_status.py` and resolve to "🟢 Data: Live CMS" / "🟡 Data: Synthetic fallback" / "🟡 Data: Mixed" (see TD-27 in `docs/Technical_Debt_Register.md`). The result is cached for the rest of the browser session — it won't re-check itself. A "🔄 Refresh Data Status" button appears once checked, useful after updating secrets, deploying new CMS assets, or testing in a different environment.
- **❔ Getting Started** — an onboarding dialog covering how the system works, AI/demo-mode states, the confidence legend, limitations, and full version history.

Claim entry is a single "Claim Details" flow: pick "Pick a demo scenario" or "Enter manually" — there's no separate Sample Claim/Manual Claim Entry tab split.

AI-sourced finding cards include a **"Supporting Policies Reviewed"** section listing other LCD/NCD policies the agent retrieved and considered but didn't cite as the basis for the finding (TD-22) — separate from the primary citation, so it's never read as additional evidence.

The audit database initializes automatically on first app load — no manual setup step is required, and the schema is re-applied (idempotently) on every connection, so it self-repairs if the underlying file is ever recreated empty mid-session. The audit trail is demo-local: on hosted deployments such as Streamlit Cloud, audit history may reset when the app restarts, redeploys, or sleeps — acceptable here since the app uses synthetic demo data only.

## Live CMS Data (optional, Phase 11)

The real NCCI/MUE/ICD-10 reference files (~266MB combined) are gitignored and never committed (see TD-27 in `docs/Technical_Debt_Register.md`) — a fresh clone or hosted deployment normally runs on the small curated synthetic fallback tables instead. Phase 11 adds an **optional** way for a hosted deployment to use the real datasets anyway: if the repo maintainer configures GitHub Release Asset URLs as environment variables (or Streamlit Cloud secrets), the app downloads them once per process into a temp-directory cache and uses them exactly as if they'd been placed locally.

```bash
CMS_NCCI_F1_URL=https://github.com/<org>/<repo>/releases/download/<tag>/ccipra-v322r0-f1.xlsx
CMS_NCCI_F2_URL=...
CMS_NCCI_F3_URL=...
CMS_NCCI_F4_URL=...
CMS_MUE_URL=https://github.com/<org>/<repo>/releases/download/<tag>/MCR_MUE_PractitionerServices_Eff_07-01-2026.xlsx
CMS_ICD10_URL=https://github.com/<org>/<repo>/releases/download/<tag>/icd10cm_order_2026.txt
```

All six are optional and independent — set none, some, or all. Checking is **on demand**, not automatic: nothing in this list is touched until you click "Check CMS Data Availability" in the Data pill's popover, so startup time is unaffected by whether any of these are configured. Behavior once checked:

- **None configured**: no download is attempted, nothing changes from today's behavior — local files if present, synthetic fallback otherwise.
- **Some/all configured, download succeeds**: the file is cached under `tempfile.gettempdir()/denial_copilot_cms_cache/` and used exactly like a local file — the Data pill resolves to "🟢 Live CMS" (or "🟡 Mixed" if only some datasets downloaded), and its popover notes "📥 Downloaded from a configured GitHub Release Asset."
- **Configured but the download fails** (network error, timeout, bad URL): the failure is caught and logged, nothing crashes, and the app falls back to the local file or synthetic table exactly as if nothing had been configured — the popover notes the attempt and its error instead of silently hiding it.
- **Caching is per-process and per-session**: once checked, a download is attempted at most once per running process (mirroring the existing audit-DB and ChromaDB self-healing patterns), and the resolved status is cached in your browser session so the app doesn't re-check itself. Click "🔄 Refresh Data Status" in the same popover after updating secrets, deploying new CMS assets, or testing in a different environment — that re-attempts the check (and any configured download) from scratch.

Asset URLs must point at actual tagged GitHub Release assets (`.../releases/download/<tag>/<file>`), not ephemeral `github.com/user-attachments/...` comment-attachment links, which aren't guaranteed to remain stable. No URL is hardcoded anywhere in the codebase — the feature is entirely opt-in via configuration, and no secret/credential is required (these are public file URLs, not API keys).

This sprint covers only the rule-layer datasets (NCCI, MUE, ICD-10) and the Data Source Status pill. Coverage/Coding policy retrieval (Chroma vs. JSON fallback) is unchanged and out of scope here — see `docs/Roadmap.md` for that as a separate future phase.

## Test

```bash
pytest tests/
```

## Evaluate

A golden-set evaluation harness measures finding precision/recall/F1 against a labelled set of synthetic claims:

```bash
python -m evaluation.run_evaluation          # offline — no Anthropic calls, rule layer measured for real
python -m evaluation.run_evaluation --live    # real Coverage/Coding Agent calls (default: Groq openai/gpt-oss-20b, override with GROQ_MODEL)
```

Saves `latest_report.md`, `latest_results.json`, and `latest_summary.json` to `evaluation/`. Current live benchmark (15-claim golden set, Phase 3B prompt calibration):

| Category | Precision | Recall | F1 |
|---|---|---|---|
| Overall | 0.92 | 0.85 | 0.88 |
| Rule Engine | 1.00 | 1.00 | 1.00 |
| Coverage Agent | 1.00 | 0.50 | 0.67 |
| Coding Agent | 0.60 | 0.60 | 0.60 |

See `docs/Roadmap.md` Phase 8 and `docs/Technical_Debt_Register.md` TD-09/TD-24 for full results, the Haiku/Sonnet/Opus model comparison behind the default-model choice, and known gaps (15-claim set is still too small to be statistically significant; TD-24 remains partially resolved).

## Architecture Overview

Full product spec: `docs/PRD_Agentic_Claims_Review_and_Denial_Prevention_Copilot.pdf`.

```
Claim intake (app/) → orchestrator.py
  → rules/ (NPI, code validity, NCCI PTP, MUE)   ← synchronous, short-circuits on hard failure
  → agents/ (coverage, coding) sequentially       ← LLM-backed, skipped entirely with no API key
  → denial_prevention.py (synthesis, risk score)  ← deterministic over structured Finding objects
  → db/audit.py (immutable write)
  → app/ (findings panel, human decision)
```

**Rule Layer** (`rules/`) — always runs first, no LLM call:
- `rules/npi.py` — live NPPES NPI Registry lookup, Luhn check-digit validation; a HIGH invalid-NPI finding short-circuits everything downstream
- `rules/ncci.py` — NCCI PTP procedure-bundling edits, loaded from real CMS quarterly files (small synthetic fallback if the files aren't present locally — see `rules/data_source_status.py` for a programmatic real-data-vs-fallback check, TD-27)
- `rules/mue.py` — MUE unit limits, MAI-aware severity
- `rules/code_validity.py` — diagnosis-to-procedure conflict and modifier rules (25, 76/77 repeat-procedure, 50 bilateral)
- `rules/icd10.py` / `rules/icd10_loader.py` — ICD-10-CM code validity and unspecified-diagnosis detection against the real CMS order file
- `rules/hcpcs.py` — HCPCS Level II format recognition against a small curated common-code set (not a full reference-file loader — see `docs/Technical_Debt_Register.md` TD-06)

**AI Layer** (`agents/`) — only runs if the selected provider has a key:
- `agents/coverage_validation.py` — RAG over LCD/NCD chunks → LLM reasoning → cited medical-necessity findings
- `agents/coding_validation.py` — LLM coding-defensibility review (diagnosis specificity, payer scrutiny risk)
- `agents/documentation_review.py` — deferred, not implemented (see `docs/Roadmap.md` Phase 6)
- `agents/run_logger.py` — structured local logging (timestamp, claim_id, agent, finding_count, success, latency_ms) for each check the orchestrator dispatches

**Orchestration:**
- `agents/orchestrator.py` — Python controller, not an agent loop: runs the rule layer, gates the two agents on both the NPI short-circuit and key presence, then passes everything to synthesis. Agents never call each other or spawn sub-agents.
- `agents/denial_prevention.py` — deterministic synthesis of all findings into a `RiskAssessment` — no LLM call here.
- `db/audit_repository.py` — append-only audit log (INSERT only, no UPDATE/DELETE) for every human Accept/Override decision.

**Evaluation:**
- `evaluation/` — a golden-set harness that runs the same orchestrator end-to-end against labelled synthetic claims and reports precision/recall/F1 per finding category, in both offline (no API calls) and live modes.

Citation grounding is the load-bearing constraint throughout: an AI finding with no retrieved source is suppressed, never displayed.


## Synthetic ambulance classifier: train, evaluate and demo

Python 3.11 on CPU is supported. From PowerShell:

```powershell
Set-Location C:\AI-Projects\denialguard-medical-billing
.\.venv\Scripts\python.exe -m pip install -r requirements-demo.txt
.\.venv\Scripts\python.exe -m ambulance_ml.train --seed 20261109 --families 3000 --output-dir artifacts/ambulance
.\.venv\Scripts\python.exe -m ambulance_ml.evaluate --artifact-dir artifacts/ambulance
.\.venv\Scripts\python.exe -m streamlit run app/main.py --server.port 8502
```

Stop an existing server with Ctrl+C before launching. Training creates the
fixed-seed dataset and saves both pipelines; evaluation reloads them without
fitting. Existing saved artifacts are included, so training is only needed to
reproduce them or intentionally change the experiment. Streamlit loads a cached
saved model and **never retrains during interactions**. No API key or external
service is used for training/inference. Optional Groq review stays in Claim Review.

Open **Ambulance prediction**, choose a scenario, edit the claim/documentation
inputs, then click **Predict simulated denial**. Compare the complete-documentation
and documentation-gap examples. Inspect held-out metrics, counts, confusion
matrices and limitations below the form. Inputs are validated; outcomes are
simulated and do not approve claims or create human audit decisions.

Dataset: **6,000 simulated rows / 3,000 scenario families**. Related variants and
exact duplicates stay together: training 3,600 rows (1,800 families), validation
1,200 (600), test 1,200 (600). The 12 pre-submission features cover transport and
dispatch categories, loaded distance, documentation delay and eight documentation
flags. IDs, target labels, denial reasons, adjudication/payment outcomes, rule
scores and AI findings cannot enter the feature matrix. Preprocessing is fitted
on training only; thresholds maximize validation F1 on a fixed grid.

Measured held-out **synthetic** test results (denial is the positive class):

| Model | Threshold | Denial precision | Denial recall | Denial F1 | Average precision |
|---|---:|---:|---:|---:|---:|
| DummyClassifier (prior) | 0.36 | 0.3675 | 1.0000 | 0.5375 | 0.3675 |
| LogisticRegression | 0.32 | 0.5952 | 0.7937 | 0.6803 | 0.7015 |

The tuned dummy predicts all test rows as denial. Average precision is the
non-interpolated weighted precision-recall summary, not trapezoidal PR-AUC.
The test set has **441 simulated denials / 759 simulated non-denials**. These
numbers reflect the documented simulator only, not real-world prediction accuracy.

The [model card](docs/ambulance-model-card.md) documents every feature, the
stochastic label formula, assumptions, partitions, packages, validation procedure,
artifact checksums, exact confusion matrices and limitations. Machine-readable
metrics, schema, seed and versions are saved in
[metadata.json](artifacts/ambulance/metadata.json); the frozen-model evaluation is
[evaluation.json](artifacts/ambulance/evaluation.json).

**Unsupported checks:** existing generic rules are not comprehensive ambulance
validation. The model does not validate payer-specific coverage/authorization,
ambulance HCPCS/modifiers, clinical necessity, covered destinations, actual mileage,
PCS applicability/timing or signature exceptions. Documentation flags are
self-reported. Probabilities are not calibrated to real claims. Never use this
prototype for clinical or billing decisions. Load only trusted local joblib files.

## Contributions and attribution

This project builds on [jigger-shah/denial-prevention-copilot](https://github.com/jigger-shah/denial-prevention-copilot).
Upstream notices and [LICENSE](LICENSE) are preserved. DenialGuard additions include
provider-neutral Groq integration, safer validation diagnostics, Windows UTF-8
loading, reviewer help, and this synthetic ambulance ML phase (generator,
leakage-isolated training/evaluation, saved artifacts, separate UI and tests).

For contributions, keep synthetic data/assumptions explicit, keep identifiers and
outcomes out of predictors, reserve untouched evaluation data, preserve citation
checks and append-only human audit decisions, and add offline regression tests.
Do not commit API keys, PHI or untrusted model artifacts. Avoid tuning against
published held-out metrics; use a new untouched test sample for future experiments.
