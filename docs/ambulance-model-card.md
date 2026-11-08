# Synthetic ambulance classifier model card

This is a genuine fitted scikit-learn classifier trained entirely on generated
claims. All outcomes, simulator coefficients and feature distributions are invented for a
portfolio demonstration. The classifier coefficients are learned by fitting the generated data.
The synthetic assumptions are **not real payer decisions, validated medical
billing rules, or evidence of real-world denial prediction accuracy**.

## Reproduction

From the repository root, with Python 3.11:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-demo.txt
.\.venv\Scripts\python.exe -m ambulance_ml.train --seed 20261109 --families 3000 --output-dir artifacts/ambulance
.\.venv\Scripts\python.exe -m ambulance_ml.evaluate --artifact-dir artifacts/ambulance
.\.venv\Scripts\python.exe -m streamlit run app/main.py --server.port 8502
```

Training generates the dataset as its first step. The standalone generator is
`python -m ambulance_ml.synthetic --seed 20261109 --families 3000 --output artifacts/ambulance/dataset.csv`.
Evaluation reloads frozen pipelines and thresholds; it neither retrains nor
chooses a threshold. Training/inference need no API key, external data download,
LLM or paid service. Dependency installation requires package access once.

## Data and assumptions

Seed: **20261109**. Generator: `ambulance-simulator-v1`.
There are **6,000 rows from 3,000 scenario families**, two related variants per
family. Every tenth family contains an intentional exact duplicate pair; the
other families flip one documentation flag. Distances and delays are continuous
random values, so independently generated families do not share a full feature
profile. A family-level Beta(5, 2) documentation quality drives correlated flag
availability. Transport level is sampled 65% basic / 35% advanced; dispatch is
40% emergency / 60% scheduled. Loaded miles are uniform [0.1, 180], and delay is
uniform [0, 120] hours. UI/schema bounds are broader ([0.1, 250] miles and [0, 168]
hours); predictions near the outer bounds extrapolate beyond training support.
No missing feature values are generated, and missing/invalid inputs are rejected,
not silently imputed. Documentation flags represent author-supplied pre-submission
availability, not independently verified clinical adequacy.

### Label generation

`simulated_denial=1` if a shared family uniform draw is less than sigmoid(logit).
The logit is the sum of the following **invented** terms:

```json
{
  "intercept": -3.6,
  "missing_document_weights": {
    "loaded_miles_recorded": 0.8,
    "medical_necessity_documented": 1.6,
    "mobility_limitation_documented": 0.7,
    "crew_assessment_documented": 0.7,
    "patient_signature_recorded": 0.55,
    "origin_destination_recorded": 0.8
  },
  "scheduled_missing_pcs": 1.0,
  "scheduled_missing_authorization": 0.85,
  "advanced_transport": 0.35,
  "distance_per_100_miles": 0.35,
  "documentation_delay_per_48_hours": 0.4,
  "unobserved_family_noise_sd": 0.65,
  "outcome": "Bernoulli(sigmoid(logit)); shared uniform draw within each family"
}
```

An unobserved normal family effect and stochastic outcome draw introduce noise;
related variants share both, so outcomes within a family are correlated. Neither
latent values nor simulator probabilities are written as predictor inputs.
There are no denial-reason or adjudication-status input fields. Logistic
regression is a deliberately simple main-effects model; it does not exactly
represent the simulator's scheduled-transport interactions.

### Pre-submission feature schema

| Feature | Type / allowed values | Meaning |
|---|---|---|
| `transport_level` | basic, advanced | Synthetic basic or advanced service category; no HCPCS validation. |
| `dispatch_type` | emergency, scheduled | Whether dispatch was emergency or scheduled. |
| `distance_miles` | 0.1–250.0 | Distance travelled with the patient, before claim submission. |
| `documentation_delay_hours` | 0.0–168.0 | Hours from transport to completion of the current record; an invented simulator input. |
| `loaded_miles_recorded` | true / false | The record includes loaded mileage. |
| `medical_necessity_documented` | true / false | The author marked the need for ambulance transport as documented; this app does not assess the text. |
| `mobility_limitation_documented` | true / false | The author marked a mobility limitation as documented; not an eligibility determination. |
| `crew_assessment_documented` | true / false | A crew assessment is available before submission. |
| `patient_signature_recorded` | true / false | A signature is recorded; exception eligibility is not checked. |
| `origin_destination_recorded` | true / false | Transport endpoints are documented; covered destinations are not validated. |
| `pcs_documented` | true / false | A physician certification statement is present; actual requirements and timing are not checked. |
| `authorization_documented` | true / false | Authorization paperwork is on file before submission; payer-specific applicability is not checked. |

### Leakage prevention and partitions

A separate RNG using seed+1 shuffles whole families before assigning 60/20/20
partitions, independently of outcomes. IDs, split assignments and the target are
kept in the dataset only for provenance, isolation and supervised training.
`feature_frame()` selects exactly the 12 allowlisted feature names. Unexpected
dataset columns or prediction fields fail validation, including identifiers,
denial reasons, adjudication/payment outcomes, existing risk scores and AI findings.
Family and exact-profile checks reject cross-partition overlap.

| Partition | Claims | Families | Non-denial | Denial |
|---|---:|---:|---:|---:|
| train | 3600 | 1800 | 2270 | 1330 |
| validation | 1200 | 600 | 762 | 438 |
| test | 1200 | 600 | 759 | 441 |

`ColumnTransformer(StandardScaler, OneHotEncoder, boolean passthrough)` is fitted
inside each pipeline on the **training partition only**. Category vocabularies
and numeric statistics never use validation/test data. Each model is fitted once;
there is no refit on training+validation. LogisticRegression uses C=1, lbfgs,
max_iter=1000 and the fixed seed; no hyperparameter search is performed.

For each model independently, a fixed grid of thresholds from 0.05 to 0.95 in
0.01 steps is scored on **validation only**. The maximum denial-class F1 wins;
exact ties use the highest threshold. Test outcomes do not select models,
features, hyperparameters or thresholds. Future model tuning should reserve a
new untouched test sample rather than optimize against this published test set.

## Measured held-out synthetic results

| Model | Threshold | Denial precision | Denial recall | Denial F1 | Average precision |
|---|---:|---:|---:|---:|---:|
| DummyClassifier (prior) | 0.36 | 0.3675 | 1.0000 | 0.5375 | 0.3675 |
| LogisticRegression | 0.32 | 0.5952 | 0.7937 | 0.6803 | 0.7015 |

Positive class is **1 = simulated denial**. Precision = TP/(TP+FP), recall =
TP/(TP+FN), F1 = 2TP/(2TP+FP+FN); undefined precision/recall is reported as zero.
Average precision is the non-interpolated PR summary AP = sum((R_n − R_(n−1))P_n),
as implemented by [scikit-learn average_precision_score](https://scikit-learn.org/1.7/modules/generated/sklearn.metrics.average_precision_score.html).
It is not trapezoidal PR-AUC. AP is calculated from probability scores, independent
of the selected classification threshold.

The prior dummy emits the training denial prevalence for every row. At its
validation-selected threshold it predicts every test row as denial: its recall is
1.0, precision/AP equal test prevalence, and its F1 is a useful all-positive
reference. This is a validation-tuned baseline, not a majority-class predictor at
threshold 0.5.

Confusion matrices are **rows actual [non-denial, denial], columns predicted
[non-denial, denial]**, i.e. `[[TN, FP], [FN, TP]]`:

- Dummy prior: `[[0, 759], [0, 441]]`.
- Logistic regression: `[[521, 238], [91, 350]]`.

Full validation/test metrics and exact class counts are in `metadata.json` and
`evaluation.json`; scored test rows are in `heldout_predictions.csv`. This is
row-weighted evaluation, with 600 independent scenario families behind the 1,200
test variants. It is not a claim of 1,200 independent real-world observations.
No confidence intervals, real-world calibration or clinical utility are claimed.

## Saved artifacts and provenance

`artifacts/ambulance/` contains the UTF-8 dataset, family split manifest, both
fitted `.joblib` pipelines, metadata, measured evaluation and held-out predictions.
Metadata includes the full feature schema, excluded input list, seed, generator
formula, threshold selection procedure, split counts, model settings, dataset
SHA-256 and model SHA-256 checksums. Scoped `.gitattributes` rules preserve CSV/JSON LF
line endings and binary model files across Git checkouts. Inference validates the saved schema/checksum
and scikit-learn version; it never fits. The Streamlit model cache invalidates
when artifact file timestamps change after an explicit training run.

Package versions used:

```json
{
  "python": "3.11.9",
  "scikit-learn": "1.7.2",
  "numpy": "2.4.6",
  "pandas": "3.0.3",
  "scipy": "1.17.1",
  "joblib": "1.5.2",
  "threadpoolctl": "3.8.0"
}
```

Load only locally generated/trusted joblib files; pickle-based artifacts are not
safe for untrusted uploads. There is no model-upload feature. Pinned dependencies
support Python 3.11; exact numerical reproduction is expected in the recorded
environment, with small floating-point variation possible across platforms.

## Interface, limitations and audit

Open **Ambulance prediction**, choose a synthetic scenario, edit documented
inputs, and click **Predict simulated denial**. The table and confusion matrices
come from the saved metadata. Prediction does not call Groq, execute the generic
rule engine, approve a claim, create a cited finding, or write a human audit
decision. The existing Claim Review and Audit Trail tabs retain their workflows.

Generic NPI/code/NCCI/MUE checks are not comprehensive ambulance coverage. No
ambulance HCPCS/modifier correctness, actual medical necessity, covered destination,
loaded-mile audit, PCS applicability/timing, signature exception, payer-specific
authorization rule or real reimbursement amount is validated by this model.
Human review remains necessary. Self-reported documentation availability cannot
establish clinical adequacy. The same-simulator test split measures learning of
invented correlations, not transfer to actual payers or healthcare populations.

## Verification

The affected offline suite completed **389 passed**, including leakage/partition
checks, saved-model reproducibility and inference, invalid-input rejection,
independent confusion/metric calculations, schema/checksum failures, Streamlit
startup and editable ambulance predictions, missing-model UI handling, existing
Groq-mocked/citation/orchestrator behavior, and audit tests. The UI audit test
accepted and saved a rule finding, exported its audit row, then made an ambulance
prediction and verified no additional audit row was written. The old default-path
audit test now uses an isolated subprocess/temp directory instead of deleting a
developer's shared audit DB; production audit code was not changed.

External TCP connections were blocked in the verification runner, local owner
credentials excluded, and no paid API requests made. The test runner emitted one
pytest plugin rewrite warning for pre-imported anyio; no tests failed. The broader
legacy full suite was not rerun; the previously documented absent CMS/ChromaDB
reference/dependency cases are outside this phase's affected suite.
