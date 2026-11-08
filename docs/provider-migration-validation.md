# Groq migration validation — November 8, 2026

This document records the original migration run. The latest affected-suite
verification is **262 passed, 0 failed**, entirely offline; see
[coding argument validation follow-up](coding-argument-validation.md). The two
prompt-wording failures listed below have since been corrected as stale test
assertions. Other original full-suite results below are historical and were not
rerun as part of that focused offline cleanup.

Runtime: workspace `.venv\Scripts\python.exe`, Python 3.11.9. The execution sandbox could not access the installed interpreter; tests ran with elevated tool access. No live Groq request was made. The local `.env` was created only because it was absent, with blank credentials.

## Results

- Before implementation: **550 passed, 14 failed, 11 errors**.
- Complete suite after implementation: **594 passed, 13 failed, 11 errors**.
- Final affected set: **266 passed, 2 failed**; both failures existed before this change.
- **43 new tests passed**, covering mocked Groq requests and function conversion, cited findings/no-concern tools, allowlisted names, invalid/missing argument types, unknown citations, multiple/missing tool calls, invalid JSON, authentication/rate-limit/server/timeout failures, missing keys, missing policies, provider selection, configuration precedence, session clearing, rule preservation, failure logging, NPI short-circuit, UTF-8 loaders, incomplete UI rendering, and Streamlit interaction/startup.
- `git diff --check` passed. `.env` and `.streamlit/secrets.toml` are ignored. LICENSE and upstream notices were preserved. No push or deployment occurred.

Commands executed:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest tests/test_groq_provider.py tests/test_coverage_validation.py tests/test_coding_validation.py tests/test_orchestrator.py tests/test_secrets.py tests/test_session_api_key.py tests/test_run_logger.py tests/test_policy_repository.py tests/test_app_ai_disabled.py tests/test_cached_ai_demo.py tests/test_manual_claim_review.py tests/test_cms_data_control.py -q
```

## Pre-existing failures observed in the original migration run

- `test_audit.py::test_repository_with_no_db_path_arg_uses_default`: Windows prevents deleting the open default SQLite file during cleanup.
- `test_coverage_validation.py` and `test_coding_validation.py`, both `test_system_prompt_instructs_not_to_duplicate_rule_layer_findings`: literal phrase expectations disagree with existing prompts. These stale wording assertions were subsequently replaced with current prompt-contract checks; both now pass offline.
- `test_icd10.py`: three failures due to the absent real ICD-10 order file.
- `test_ncci_loader.py`: four failures due to absent real NCCI workbooks.
- `test_rule_engine.py::test_clean_claim_overall_risk_is_clean`: the absent real ICD-10 file changes the sample claim's result.
- `test_vector_store.py`: two failures and eleven fixture errors because optional ChromaDB is absent in the demo environment. The JSON fallback remains tested and usable.

The baseline disabled-header failure was resolved by showing the current provider's no-key/rule-only state and updating the assertion to match the requested terminology. No tests were skipped or weakened to conceal regressions. Existing Anthropic-specific tests now select Anthropic explicitly. Citation fixtures now provide a matching retrieved excerpt, and logging assertions expect a safe category instead of raw exception text.

## Changed files and purpose

- `agents/provider.py`: shared Groq HTTP adapter, tool-schema translation, strict response/argument validation, safe error categories, provider/model selection, and an unpack-compatible result with completion status.
- `agents/coverage_validation.py`, `agents/coding_validation.py`: shared adapter calls, explicit failure/no-policy status, no invented confidence/default findings, retrieved-source excerpts and headings.
- `agents/orchestrator.py`, `rules/models.py`: provider-aware gating, per-agent completion details, preserved available findings, incomplete-review escalation.
- `agents/secrets.py`: session/environment/root dotenv/Streamlit Secrets precedence and clearing both session key copies.
- `agents/run_logger.py`: UTF-8 logging, accurate failed-check status, sanitized unexpected errors.
- `app/main.py`: DenialGuard title, UTF-8 JSON loading, selected-provider password popup, configured/unverified labels, distinct review states, field/button help and Accept explanation.
- `.env.example`, `requirements.txt`, `requirements-demo.txt`, `README.md`: blank Groq configuration, direct httpx dependency, Windows setup and reviewer guidance. The user's existing untracked demo requirements were preserved and extended.
- `tests/test_groq_provider.py`: 43 new tests.
- Updated existing tests: `test_app_ai_disabled.py`, `test_cms_data_control.py`, `test_coding_validation.py`, `test_coverage_validation.py`, `test_manual_claim_review.py`, `test_orchestrator.py`, `test_run_logger.py`, `test_session_api_key.py`.
- `retrieval/policy_repository.py` and `.gitignore` required no edits: explicit UTF-8 and secret-file exclusions already existed.

The trained denial classifier and ambulance scenarios remain future work. Risk labels continue to come from deterministic synthesis.
