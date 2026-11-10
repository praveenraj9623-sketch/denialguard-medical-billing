# DenialGuard - Claim Review and Synthetic Denial Prediction

[Live demo](https://praveen-denialguard.streamlit.app/) · [Source](https://github.com/praveenraj9623-sketch/denialguard-medical-billing) · [Model card](docs/ambulance-model-card.md)

A Python/Streamlit portfolio prototype for investigating possible claim issues before submission. It contains **two separate systems**: rules plus optional LLM policy review, and a trained classifier on simulated ambulance data.

## User value and scope

Help billing reviewers inspect potential issues and supporting evidence. The intended benefit is more focused human review; actual denial reduction, staff-time savings and revenue gains have not been measured. Use synthetic data only. This is not validated clinical or payer-adjudication software.

| Workflow | Input | Output |
|---|---|---|
| Claim Review | Structured claim codes, diagnoses and payer details | Rule findings, optional cited AI findings, review status and human audit decisions |
| Ambulance prediction | Twelve pre-submission transport/documentation features | Saved-model simulated score and class |

A rule severity, an LLM's reported confidence and the classifier's score are different values. Neither workflow approves or denies a real claim, and the classifier does not create audit decisions automatically.

## Claim Review pipeline and agents

1. Validate claim input and run the existing deterministic rules first.
2. A high invalid-NPI finding can stop subsequent checks. Rule-only mode skips LLM review.
3. For eligible full reviews, run **Coverage Validation**, then **Coding Validation**, sequentially.
4. Validate the structured findings and citation identifiers; combine completed work with explicit completion status.
5. Let a human accept or override a finding and save the audit decision. Accept means agreement with a finding, not claim approval.

**Coverage Validation** reviews possible coverage/medical-necessity concerns against supplied policy context. **Coding Validation** reviews policy-based coding defensibility; it does not replace the deterministic NCCI/MUE rule layer. The controller in `agents/orchestrator.py` is custom Python, and synthesis in `agents/denial_prevention.py` is deterministic. A Documentation Review Agent is deferred, not a third implemented live agent.

### Retrieval and RAG provenance

The repository supports section-aware policy chunking, document/section/effective-date metadata and an optional ChromaDB vector index. Its wrapper documents the default `all-MiniLM-L6-v2` embedding function. When the vector index is unavailable or empty, review can use the curated JSON policy corpus. **A labelled fallback is not live CMS ingestion or proof that a semantic index ran.**

The rule-reference data status and the agents' policy-retrieval source are separate. Inspect each displayed source/version. Citation membership checks reduce invented references but do not establish that the model interpreted a policy correctly. No applicable context must not be reported as a successfully clean review.

## Models and configuration

| Component | Model or implementation |
|---|---|
| Default live LLM provider | Groq, not xAI Grok |
| Default review model | `openai/gpt-oss-20b`; configurable with `GROQ_MODEL` |
| Optional legacy provider | Anthropic, with its own key and configuration |
| Ambulance classifier | scikit-learn `LogisticRegression` |
| Comparison model | `DummyClassifier(strategy="prior")` |
| Agent orchestration | Custom Python; not LangChain or LangGraph |

The Groq model is a practical starting point for hosted inference and the structured tool-output interface. It avoids loading the LLM on the CPU-only app host and is configurable. GPT-OSS is an Apache-2.0 open-weight model; Groq is a separate hosted API with its own quotas and pricing. No comparative benchmark establishes it as the best model for these claims. Neither the LLM nor the optional embedding model was trained here.

## Run locally - Python 3.11 / PowerShell

```powershell
git clone https://github.com/praveenraj9623-sketch/denialguard-medical-billing.git
Set-Location denialguard-medical-billing
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-demo.txt
.\.venv\Scripts\python.exe -m streamlit run app/main.py --server.port 8502
```

The demo requirements omit optional ChromaDB; the JSON policy fallback remains available. Saved ML artifacts are included, so training is not needed to open the model tab.

For live AI, use Streamlit Secrets (local `.streamlit/secrets.toml` or Community Cloud settings):

```toml
LLM_PROVIDER = "groq"
GROQ_API_KEY = "your-key-here"
GROQ_MODEL = "openai/gpt-oss-20b"
```

The code also supports environment variables, a UTF-8 root `.env` and session-only provider keys. See [agents/provider.py](agents/provider.py) for resolution rules. A Groq session key does not enable Anthropic. Key-configured means unverified until a requested review completes. Never commit real credentials.

## Demonstrate the two paths

- **Claim Review:** choose CLM-001 and run rule-only review. Inspect findings and sources. Run Full Review only when intentionally making live provider requests. Inspect both agents' completion status; failures retain completed findings and label the review incomplete.
- **Human audit:** enter a reviewer name, inspect a finding, accept or override, save, then inspect Audit Trail/export. Hosted demo audit storage may reset on restart or redeployment.
- **Ambulance prediction:** select a scenario, edit its features and click Predict simulated denial. Inference uses the trusted saved pipeline locally, without a Groq request or retraining.

## Measured synthetic classifier results

The generator creates **6,000 simulated rows across 3,000 families**. Related variants stay together: 3,600 training / 1,200 validation / 1,200 test rows. Preprocessing is fitted on training only. Thresholds are selected using validation denial-class F1; the final test is held out.

| Model | Threshold | Denial precision | Denial recall | Denial F1 | Average precision |
|---|---:|---:|---:|---:|---:|
| Dummy prior | 0.36 | 0.3675 | 1.0000 | 0.5375 | 0.3675 |
| Logistic regression | 0.32 | 0.5952 | 0.7937 | 0.6803 | 0.7015 |

The test set has 441 simulated denials and 759 non-denials. At its selected cutoff the dummy predicts every row as denial; it is not a majority-class baseline at 0.5. AP is non-interpolated average precision, not trapezoidal PR-AUC. F1 is not accuracy. These results measure learning of invented simulator assumptions, not real payer accuracy or real-world calibration.

The [model card](docs/ambulance-model-card.md), [evaluation](artifacts/ambulance/evaluation.json) and [metadata](artifacts/ambulance/metadata.json) document features, assumptions and reproducibility. The inherited 15-claim review benchmark is a **different upstream experiment**, predating this Groq adaptation. Its 0.92/0.85/0.88 review figures are not current Groq results or the ambulance classifier's results. Inherited repository-wide test totals are not all adaptation-authored tests.

## Reproduce or verify

```powershell
.\.venv\Scripts\python.exe -m ambulance_ml.evaluate --artifact-dir artifacts/ambulance
.\.venv\Scripts\python.exe -m pytest -q
```

To deliberately regenerate the documented synthetic experiment:

```powershell
.\.venv\Scripts\python.exe -m ambulance_ml.train --seed 20261109 --families 3000 --output-dir artifacts/ambulance
```

The separate review harness is `python -m evaluation.run_evaluation` (offline); `--live` requests external AI and can consume quota. This documentation cleanup did not rerun training, tests or paid/live LLM checks. Previous verification details are retained in [coding validation](docs/coding-argument-validation.md) and the model card.

## Limits and engineering boundaries

Generic review rules are not comprehensive ambulance validation. The model's documentation flags are self-reported; it does not validate clinical necessity, payer-specific authorisation, HCPCS/modifier combinations, covered destinations, mileage, PCS timing or signature exceptions. No real claims, PHI, production throughput or established HIPAA compliance is demonstrated. Load only trusted model artifacts. A failed or missing check is not a passed check.

## Foundation and licence

Built on [jigger-shah/denial-prevention-copilot](https://github.com/jigger-shah/denial-prevention-copilot), with upstream history and [MIT LICENSE](LICENSE) preserved. Adaptation contributions include the Groq adapter, validation/diagnostics and failure handling, and the synthetic ambulance generator, training/evaluation, saved-model inference, model card and separate UI. The existing rules, review/retrieval and audit foundation remain attributed. Historical assistant guidance files are not runtime model configuration; the current code and setup above describe this adaptation.
